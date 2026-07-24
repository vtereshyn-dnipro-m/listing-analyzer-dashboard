# -*- coding: utf-8 -*-
"""
pages/synthesis.py — Синтез: Split 75/125. v2.

Что нового в v2:
- Методология берётся из listing_data.synthesis_skill (активная версия,
  правится на странице «Методология» без коммитов кода).
- Защищённые фразы (protected_keywords): чипы + добавление/удаление
  прямо здесь; передаются в промпт, после генерации проверяются кодом.
- Пост-проверки по официальным правилам Amazon: длина, запрещённые
  символы, повторы слов, наличие must-keep фраз, отсутствие forbid-фраз.
- Черновик сохраняется в synthesis_drafts со skill_version.
"""

from __future__ import annotations

import json
import re

import pandas as pd
import streamlit as st

from config import TITLE_LIMIT, HIGHLIGHTS_LIMIT
from i18n import t
from services.db import get_conn, cfg
from components.ui import inject_fonts, eyebrow, limit_ruler_html

inject_fonts()
st.header(t("nav.synthesis"))

GEMINI_MODEL = "gemini-3.5-flash"
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

FORBIDDEN_CHARS = set("!$?_{}^¬¦®©™")

BASE_PROMPT = """Ты эксперт по Amazon-листингам бренда Dnipro-M.

МЕТОДОЛОГИЯ (следуй ей строго):
{skill_text}

{keywords_block}

Исходный тайтл (маркетплейс {marketplace}):
{title}

Задача — сплит: title максимум {title_limit} символов, highlights максимум {highlights_limit} символов, dropped — что выброшено на ревью человеку.

Ответь ТОЛЬКО валидным JSON без markdown:
{{"title": "...", "highlights": "...", "dropped": ["...", "..."]}}"""


# ---------------------------------------------------------------- загрузка

@st.cache_data(ttl=300)
def load_candidates() -> pd.DataFrame:
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT DISTINCT ON (d.asin, d.marketplace)
                   d.asin, d.marketplace, s.title
            FROM diagnosis d
            JOIN LATERAL (
                SELECT title FROM listing_snapshots s
                WHERE s.asin = d.asin AND s.marketplace = d.marketplace
                  AND s.ok = TRUE AND s.title <> ''
                ORDER BY s.fetched_at DESC LIMIT 1
            ) s ON TRUE
            WHERE d.rule_id = 'title_over_limit'
            ORDER BY d.asin, d.marketplace, d.created_at DESC
            """,
            conn,
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=120)
def load_skill() -> tuple[str, int]:
    """Общая методология (common) + title_split, склеенные.
    Версия в подписи — от title_split."""
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT DISTINCT ON (scope) scope, skill_text, version
            FROM synthesis_skill
            WHERE is_active = TRUE AND scope IN ('common', 'title_split')
            ORDER BY scope, version DESC
            """,
            conn,
        )
        conn.close()
        if not df.empty:
            parts: list[str] = []
            version = 0
            common = df[df["scope"] == "common"]
            spec = df[df["scope"] == "title_split"]
            if not common.empty:
                parts.append(str(common.iloc[0]["skill_text"]))
            if not spec.empty:
                parts.append(str(spec.iloc[0]["skill_text"]))
                version = int(spec.iloc[0]["version"])
            if parts:
                return "\n\n".join(parts), version
    except Exception:
        pass
    return ("Бренд Dnipro-M первым. Язык маркетплейса. "
            "Уложись в лимиты символов.", 0)


def load_keywords(asin: str, mp: str) -> pd.DataFrame:
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT id, phrase, phrase_type, source FROM protected_keywords
            WHERE asin = %(asin)s AND marketplace = %(mp)s
            ORDER BY phrase_type, phrase
            """,
            conn, params={"asin": asin, "mp": mp},
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


# ---------------------------------------------------------------- генерация

def generate_split(title: str, marketplace: str,
                   skill_text: str, keep: list[str], forbid: list[str]) -> dict | None:
    api_key = cfg("GEMINI_API_KEY")
    if not api_key:
        st.error("GEMINI_API_KEY не найден в секретах — добавь его до [databricks].")
        return None
    api_key = str(api_key).strip()

    kw_lines = []
    if keep:
        kw_lines.append("ОБЯЗАТЕЛЬНО сохрани дословно (в title или highlights): "
                        + "; ".join(keep))
    if forbid:
        kw_lines.append("ЗАПРЕЩЕНО использовать: " + "; ".join(forbid))
    keywords_block = "\n".join(kw_lines) if kw_lines else ""

    prompt = BASE_PROMPT.format(
        skill_text=skill_text.replace("{title_limit}", str(TITLE_LIMIT))
                             .replace("{highlights_limit}", str(HIGHLIGHTS_LIMIT)),
        keywords_block=keywords_block,
        marketplace=marketplace,
        title=title,
        title_limit=TITLE_LIMIT,
        highlights_limit=HIGHLIGHTS_LIMIT,
    )

    try:
        import requests as _rq
        resp = _rq.post(
            GEMINI_URL,
            headers={"x-goog-api-key": api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"},
            },
            timeout=60,
        )
        if resp.status_code != 200:
            st.error(f"Gemini HTTP {resp.status_code}: {resp.text[:300]}")
            return None
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except Exception as e:
        st.error(f"Ошибка генерации: {e}")
        return None


def run_checks(new_title: str, new_hl: str,
               keep: list[str], forbid: list[str]) -> list[tuple[bool, str]]:
    """Пост-проверки кодом. Возвращает [(ok, сообщение), ...]."""
    checks: list[tuple[bool, str]] = []
    combined = f"{new_title} {new_hl}".lower()

    checks.append((len(new_title) <= TITLE_LIMIT,
                   f"title {len(new_title)}/{TITLE_LIMIT} символов"))
    checks.append((len(new_hl) <= HIGHLIGHTS_LIMIT,
                   f"highlights {len(new_hl)}/{HIGHLIGHTS_LIMIT} символов"))

    bad_chars = sorted({c for c in new_title if c in FORBIDDEN_CHARS})
    checks.append((not bad_chars,
                   "запрещённые символы в title: " + (" ".join(bad_chars) if bad_chars else "нет")))

    words = re.findall(r"[a-zA-Zа-яА-ЯёЁáéíóúñüÁÉÍÓÚÑÜäöüßÄÖÜ0-9]+", new_title.lower())
    stop = {"de", "con", "para", "y", "el", "la", "und", "mit", "für", "et", "avec", "e", "con", "per"}
    over_words = sorted({w for w in words
                         if len(w) > 2 and w not in stop and words.count(w) > 2})
    checks.append((not over_words,
                   "слова чаще 2 раз: " + (", ".join(over_words) if over_words else "нет")))

    for ph in keep:
        checks.append((ph.lower() in combined, f"фраза сохранена: «{ph}»"))
    for ph in forbid:
        checks.append((ph.lower() not in combined, f"запрещённая отсутствует: «{ph}»"))

    return checks


def save_draft(asin: str, mp: str, original: str, result: dict, skill_version: int) -> bool:
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO synthesis_drafts
                    (asin, marketplace, original_title, new_title,
                     new_highlights, dropped_words, model, skill_version, raw)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (asin, mp, original,
                 result.get("title", ""),
                 result.get("highlights", ""),
                 ", ".join(result.get("dropped", [])),
                 GEMINI_MODEL, skill_version,
                 json.dumps(result, ensure_ascii=False)),
            )
        conn.close()
        return True
    except Exception as e:
        st.warning(f"Сплит сгенерирован, но не сохранён: {e}")
        return False


# ---------------------------------------------------------------- UI

candidates = load_candidates()

if candidates.empty:
    st.info(t("synth.no_candidates"))
    st.stop()

skill_text, skill_version = load_skill()

options = {
    f"{r['asin']} · {r['marketplace']} · {len(r['title'])} симв.": i
    for i, r in candidates.iterrows()
}
choice = st.selectbox(t("synth.select_title"), list(options.keys()))
row = candidates.loc[options[choice]]
asin, mp, title = row["asin"], row["marketplace"], row["title"]

st.markdown(
    eyebrow(f"{t('synth.original')} · {asin} · {mp} · "
            f"<a href='/methodology' target='_self' "
            f"style='color:#8A8578;text-decoration:underline;'>{t('synth.methodology')} v{skill_version}</a>"),
    unsafe_allow_html=True,
)
st.markdown(f"«{title}»")
st.markdown(
    limit_ruler_html(len(title), TITLE_LIMIT,
                     left_label=f"{TITLE_LIMIT} допуск",
                     right_label=f"+{max(0, len(title) - TITLE_LIMIT)} резать"),
    unsafe_allow_html=True,
)

# ---- защищённые фразы
st.markdown(f"**{t('synth.protected')}** — {t('synth.protected_hint')}")
kw = load_keywords(asin, mp)

if not kw.empty:
    for _, k in kw.iterrows():
        c1, c2 = st.columns([6, 1])
        icon = "🔒" if k["phrase_type"] == "keep" else "🚫"
        c1.markdown(f"{icon} `{k['phrase']}` · {k['source']}")
        if c2.button("✕", key=f"del-kw-{k['id']}"):
            try:
                conn = get_conn()
                with conn, conn.cursor() as cur:
                    cur.execute("DELETE FROM protected_keywords WHERE id = %s",
                                (int(k["id"]),))
                conn.close()
                st.rerun()
            except Exception as e:
                st.error(f"Не удалилось: {e}")

nc1, nc2, nc3 = st.columns([4, 2, 1])
new_phrase = nc1.text_input("Новая фраза", key="new-kw",
                            label_visibility="collapsed",
                            placeholder="например: taladro atornillador")
new_type = nc2.selectbox("тип", ["keep", "forbid"], label_visibility="collapsed")
if nc3.button(t("synth.add")) and new_phrase.strip():
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO protected_keywords (asin, marketplace, phrase, phrase_type, source)
                VALUES (%s, %s, %s, %s, 'manual')
                ON CONFLICT (asin, marketplace, phrase) DO UPDATE
                    SET phrase_type = EXCLUDED.phrase_type
                """,
                (asin, mp, new_phrase.strip().lower(), new_type),
            )
        conn.close()
        st.rerun()
    except Exception as e:
        st.error(f"Не добавилось: {e}")

keep_list = kw[kw["phrase_type"] == "keep"]["phrase"].tolist() if not kw.empty else []
forbid_list = kw[kw["phrase_type"] == "forbid"]["phrase"].tolist() if not kw.empty else []

st.divider()

if st.button(t("synth.generate"), type="primary"):
    with st.spinner(f"Gemini режет тайтл по методологии v{skill_version}..."):
        result = generate_split(title, mp, skill_text, keep_list, forbid_list)
    if result:
        st.session_state["synth_result"] = result
        st.session_state["synth_asin"] = (asin, mp, title)
        st.session_state["synth_saved"] = save_draft(asin, mp, title, result, skill_version)

result = st.session_state.get("synth_result")
saved_for = st.session_state.get("synth_asin")
if result and saved_for and saved_for[0] == asin and saved_for[1] == mp:
    new_title = result.get("title", "")
    new_hl = result.get("highlights", "")
    dropped = result.get("dropped", [])

    st.divider()
    st.markdown(eyebrow(t("synth.result")), unsafe_allow_html=True)

    st.markdown(f"**title** · {len(new_title)}/{TITLE_LIMIT}")
    st.code(new_title, language=None)
    st.markdown(
        limit_ruler_html(len(new_title), TITLE_LIMIT,
                         left_label=f"{TITLE_LIMIT} допуск",
                         right_label=f"свободно {max(0, TITLE_LIMIT - len(new_title))}"),
        unsafe_allow_html=True,
    )

    st.markdown(f"**item highlights** · {len(new_hl)}/{HIGHLIGHTS_LIMIT}")
    st.code(new_hl, language=None)

    if dropped:
        st.markdown(f"**{t('synth.dropped')}:**")
        st.markdown(" · ".join(f"`{w}`" for w in dropped))

    # ---- пост-проверки кодом
    st.markdown(f"**{t('synth.checks')}:**")
    checks = run_checks(new_title, new_hl, keep_list, forbid_list)
    failed = [msg for ok, msg in checks if not ok]
    for ok, msg in checks:
        st.markdown(("✅ " if ok else "❌ ") + msg)

    if failed:
        st.warning(t("synth.checks_failed"))
    else:
        st.success(t("synth.checks_ok"))
