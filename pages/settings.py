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

from config import TITLE_LIMIT as _TL_DEFAULT, HIGHLIGHTS_LIMIT as _HL_DEFAULT
from i18n import t
from services.db import get_conn, cfg
from services.settings import get_setting, get_int
from services.ai import generate_json, task_config
from services.economics import econ_map, money_at_risk, fmt_money
from services.seo import (
    build_keyword_table, coverage, compress_phrase,
    TIER_LABEL, TIER_COLOR, TIERS,
)
from components.ui import inject_fonts, eyebrow, limit_ruler_html

inject_fonts()
st.title(t("nav.synthesis"))

GEMINI_MODEL = task_config("title_split")[1]
TITLE_LIMIT = get_int("limit.title", _TL_DEFAULT)
HIGHLIGHTS_LIMIT = get_int("limit.highlights", _HL_DEFAULT)
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

FORBIDDEN_CHARS = set("!$?_{}^¬¦®©™")
ACCENT = "#E8590C"

BASE_PROMPT = """Ты эксперт по Amazon-листингам бренда Dnipro-M.

МЕТОДОЛОГИЯ (следуй ей строго):
{skill_text}

{keywords_block}

Исходный тайтл (маркетплейс {marketplace}):
{title}

ЗАДАЧА — сплит с сохранением поискового веса, а не просто обрезка:
- title максимум {title_limit} символов
- highlights максимум {highlights_limit} символов
- dropped — что выброшено на ревью человеку

ПОРЯДОК ПРИОРИТЕТОВ:
1. Фразы MUST KEEP обязаны попасть в title дословно — по ним идут реальные покупки.
2. Фразы PREFERRED — в title, если помещаются; иначе в highlights.
3. Фразы COMPRESS можно сокращать без потери смысла: 1500 mAh → 1,5 Ah,
   milímetros → mm, Newton-metros → Nm, voltios → V. Сокращай, а не выбрасывай.
4. Фразы FORBID не должны появиться ни в title, ни в highlights.
5. Всё, что не влезло, перечисли в dropped — человек решит.

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
                   d.asin, d.marketplace, s.title, s.fetched_at,
                   s.main_image, m.sku_group
            FROM diagnosis d
            JOIN LATERAL (
                SELECT title, fetched_at, raw->>'main_image' AS main_image
                FROM listing_snapshots s
                WHERE s.asin = d.asin AND s.marketplace = d.marketplace
                  AND s.ok = TRUE AND s.title <> ''
                ORDER BY s.fetched_at DESC LIMIT 1
            ) s ON TRUE
            LEFT JOIN product_matrix m
                   ON m.asin = d.asin AND m.marketplace = d.marketplace
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
    """Генерация сплита. Провайдер и модель — из Настроек (задача title_split)."""
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
    return generate_json("title_split", prompt, timeout=120)


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


@st.cache_data(ttl=60)
def load_draft_stats() -> dict:
    """Сколько черновиков и последний Coverage по каждому товару."""
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT d.asin, d.marketplace, count(*) AS drafts,
                   max(c.coverage_score) AS coverage
            FROM synthesis_drafts d
            LEFT JOIN synthesis_coverage c
                   ON c.asin = d.asin AND c.marketplace = d.marketplace
            GROUP BY d.asin, d.marketplace
            """, conn)
        conn.close()
        return {(r["asin"], r["marketplace"]): r.to_dict()
                for _, r in df.iterrows()}
    except Exception:
        return {}


@st.cache_data(ttl=60)
def load_accepted() -> dict:
    """Принятые правки: (asin, mp) -> дата и статус."""
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT DISTINCT ON (asin, marketplace)
                   asin, marketplace, accepted_at, status, after_len,
                   coverage_score
            FROM listing_changes
            ORDER BY asin, marketplace, accepted_at DESC
            """, conn)
        conn.close()
        return {(r["asin"], r["marketplace"]): r.to_dict()
                for _, r in df.iterrows()}
    except Exception:
        return {}


def accept_change(asin: str, mp: str, before: str, result: dict,
                  coverage_score, skill_version: int, model: str) -> bool:
    """Фиксирует принятый сплит — цикл замыкается здесь.

    Дальше эта запись используется экраном «До / после»: сравнение
    sessions и продаж до правки и после.
    """
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO listing_changes
                    (asin, marketplace, change_type, before_title, before_len,
                     after_title, after_len, after_highlights,
                     after_highlights_len, dropped, coverage_score,
                     skill_version, model, status)
                VALUES (%s,%s,'title_split',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                        'accepted')
                """,
                (asin, mp, before, len(before or ""),
                 result.get("title", ""), len(result.get("title", "")),
                 result.get("highlights", ""), len(result.get("highlights", "")),
                 "; ".join(result.get("dropped", []) or []),
                 coverage_score, skill_version, model))
        conn.close()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Не удалось записать: {e}")
        return False


@st.cache_data(ttl=30)
def load_drafts_for_review() -> pd.DataFrame:
    """Черновики без принятой правки — очередь на разбор."""
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT DISTINCT ON (d.asin, d.marketplace)
                   d.id, d.asin, d.marketplace, d.created_at,
                   d.title_before, d.title_after, d.highlights_after,
                   d.dropped, d.skill_version, c.coverage_score
            FROM synthesis_drafts d
            LEFT JOIN LATERAL (
                SELECT coverage_score FROM synthesis_coverage c
                WHERE c.asin = d.asin AND c.marketplace = d.marketplace
                ORDER BY c.created_at DESC LIMIT 1
            ) c ON TRUE
            WHERE NOT EXISTS (
                SELECT 1 FROM listing_changes lc
                WHERE lc.asin = d.asin AND lc.marketplace = d.marketplace
            )
            ORDER BY d.asin, d.marketplace, d.created_at DESC
            """, conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def draft_quality(cov, checks_failed: int) -> tuple[str, str]:
    """Зелёный — принимать бегло, красный — смотреть глазами."""
    try:
        v = float(cov) if cov is not None and not pd.isna(cov) else None
    except (TypeError, ValueError):
        v = None
    if checks_failed:
        return "red", "проверки не пройдены"
    if v is None:
        return "amber", "Coverage не считался — нет данных SQP"
    if v < 70:
        return "red", f"Coverage {v:.0f}% — потеряно много веса"
    if v >= 85:
        return "green", f"Coverage {v:.0f}%"
    return "amber", f"Coverage {v:.0f}%"


def save_coverage(asin: str, mp: str, cov: dict) -> None:
    if cov.get("score") is None:
        return
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO synthesis_coverage
                    (asin, marketplace, coverage_score, weight_total,
                     weight_kept, kept_phrases, lost_phrases)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (asin, mp, cov["score"], cov["weight_total"], cov["weight_kept"],
                 "; ".join(p for p, _, _ in cov["kept"][:30]),
                 "; ".join(p for p, _, _ in cov["lost"][:30])))
        conn.close()
    except Exception:
        pass


def batch_generate(items: list, skill_text: str, skill_version: int) -> dict:
    """Пакетная генерация: только черновики, ничего не применяется."""
    done, failed = 0, 0
    bar = st.progress(0.0, text="Готовлю партию...")
    for i, x in enumerate(items, 1):
        r = x["r"]
        asin, mp, title = r["asin"], r["marketplace"], r["title"] or ""
        bar.progress(i / len(items), text=f"[{i}/{len(items)}] {asin} ({mp})")
        kw = build_keyword_table(asin, mp, title)
        keep, forbid = [], []
        if not kw.empty:
            keep = kw.loc[kw["tier"].isin(["must_keep", "preferred"]),
                          "search_query"].tolist()
            forbid = kw.loc[kw["tier"] == "forbid", "search_query"].tolist()
        try:
            res = generate_split(title, mp, skill_text, keep, forbid)
        except Exception:
            res = None
        if res:
            save_draft(asin, mp, title, res, skill_version)
            if not kw.empty:
                save_coverage(asin, mp, coverage(
                    kw, res.get("title", ""), res.get("highlights", "")))
            done += 1
        else:
            failed += 1
    bar.empty()
    st.cache_data.clear()
    return {"done": done, "failed": failed}


@st.cache_data(ttl=300)
def load_all_products() -> pd.DataFrame:
    """Все товары матрицы со свежим снапшотом — для работы с любым тайтлом,
    а не только с теми, у кого сработало правило title_over_limit."""
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT m.asin, m.marketplace, m.sku_group,
                   s.title, s.fetched_at, s.main_image
            FROM product_matrix m
            LEFT JOIN LATERAL (
                SELECT title, fetched_at, raw->>'main_image' AS main_image
                FROM listing_snapshots s
                WHERE s.asin = m.asin AND s.marketplace = m.marketplace
                  AND s.ok = TRUE AND s.title <> ''
                ORDER BY s.fetched_at DESC LIMIT 1
            ) s ON TRUE
            WHERE m.is_competitor = FALSE
            ORDER BY m.sku_group, m.asin, m.marketplace
            """, conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_sqp_coverage() -> set:
    """Товары, по которым Brand Analytics реально загружен.

    Раньше состояние определялось по наличию трафика — из-за этого строка
    могла утверждать «SQP собран», а таблица фраз оказывалась пустой.
    """
    try:
        conn = get_conn()
        df = pd.read_sql(
            "SELECT DISTINCT asin, marketplace FROM sqp_reports", conn)
        conn.close()
        return set(zip(df["asin"], df["marketplace"]))
    except Exception:
        return set()


# ================================================================ UI
SQP_MARKETPLACES = {"es", "de", "it"}
SQP_LABEL = {
    "ready": t("synth.sqp_ready"),
    "queued": t("synth.sqp_queued"),
    "off": t("synth.sqp_off"),
}
Q_COLOR = {"green": "#2F6B3A", "amber": "#854F0B", "red": "#A32D2D"}

st.caption(t("synth.caption"))

candidates = load_candidates()
if candidates.empty:
    st.info(t("synth.no_candidates"))
    st.stop()

skill_text, skill_version = load_skill()
ECON = econ_map()
DRAFTS = load_draft_stats()
ACCEPTED = load_accepted()
SQP_HAVE = load_sqp_coverage()

rows = []
for _, r in candidates.iterrows():
    key = (r["asin"], r["marketplace"])
    e = ECON.get(key) or {}
    rows.append({
        "r": r,
        "risk": money_at_risk("title_over_limit", e.get("revenue_30d")),
        "over": max(0, len(r["title"] or "") - TITLE_LIMIT),
        "econ": e,
        "draft": DRAFTS.get(key) or {},
        "accepted": ACCEPTED.get(key),
        "sqp_state": ("ready" if (r["asin"], r["marketplace"]) in SQP_HAVE
                      else "queued" if r["marketplace"] in SQP_MARKETPLACES
                      else "off"),
    })

total_risk = sum(x["risk"] for x in rows)
n_ready = sum(1 for x in rows if x["sqp_state"] == "ready")
st.markdown(
    f"{t('synth.at_risk_line')} <b style='color:{ACCENT}'>"
    f"{fmt_money(total_risk, '')}</b>/мес · "
    f"{len(rows)} {t('synth.summary')} {n_ready}",
    unsafe_allow_html=True)

pending = load_drafts_for_review()
all_products = load_all_products()
tab_queue, tab_review, tab_any = st.tabs([
    f"{t('synth.tab_queue')} · {len(rows)}",
    f"{t('synth.tab_review')} · {len(pending)}",
    f"{t('synth.tab_any')} · {len(all_products)}",
])


def render_card_head(x: dict) -> None:
    """Строка товара: фото, ASIN, превышение, деньги, состояние работы."""
    r = x["r"]
    asin, mp = r["asin"], r["marketplace"]
    title = r["title"] or ""
    sku = r["sku_group"] if r["sku_group"] and r["sku_group"] != asin else ""
    img = None if pd.isna(r.get("main_image")) else r.get("main_image")
    thumb = (f'<div style="flex:0 0 42px;"><img src="{img}" '
             f'style="width:42px;height:42px;object-fit:contain;background:#fff;'
             f'border:1px solid #E7E4DD;border-radius:7px;"></div>') if img else ""
    sub = [SQP_LABEL[x["sqp_state"]]]
    if x["draft"].get("drafts"):
        cov = x["draft"].get("coverage")
        sub.append(f"черновиков {int(x['draft']['drafts'])}"
                   + (f" · Coverage {int(cov)}%" if pd.notna(cov) else ""))
    if x["accepted"]:
        sub.append("✓ правка принята "
                   + pd.to_datetime(x["accepted"]["accepted_at"]).strftime("%d.%m"))
    edge = ACCENT if x["risk"] else "#E7E4DD"
    st.markdown(
        f'<div class="ls-card" style="background:#fff;border:1px solid #E7E4DD;'
        f'border-left:3px solid {edge};border-radius:0 10px 10px 0;'
        f'padding:11px 14px;margin-bottom:4px;display:flex;gap:12px;'
        f'align-items:center;">{thumb}'
        f'<div style="flex:1;min-width:0;">'
        f'<div style="font-size:13.5px;font-weight:700;">'
        f'{sku + " · " if sku else ""}'
        f'<a href="https://www.amazon.{mp}/dp/{asin}" target="_blank" '
        f'style="color:#1A1815;text-decoration:none;'
        f'border-bottom:1px dotted #57534A;">{asin}</a> '
        f'<span style="font-weight:400;color:#57534A;">· {mp} · '
        f'{len(title)}/{TITLE_LIMIT} · +{x["over"]} · {title[:58]}…</span></div>'
        f'<div style="font-size:11.5px;color:#57534A;">{" · ".join(sub)}</div>'
        f'</div><span class="ls-mono" style="font-size:13px;font-weight:700;'
        f'color:{ACCENT if x["risk"] else "#57534A"};">'
        f'{fmt_money(x["risk"]) if x["risk"] else "нет данных"}</span></div>',
        unsafe_allow_html=True)


# ================================================================ очередь
with tab_queue:
    b1, b2, b3 = st.columns([1.6, 2, 3])
    batch_n = b1.selectbox("партия", [10, 20, 50], index=1,
                           format_func=lambda n: f"top-{n}",
                           label_visibility="collapsed", key="batch-n")
    if b2.button(f"{t('synth.batch_run')} ({batch_n})", type="primary"):
        top = [x for x in sorted(rows, key=lambda z: -z["risk"])
               if not x["draft"].get("drafts")][:batch_n]
        if not top:
            st.info(t("synth.batch_none"))
        else:
            res = batch_generate(top, skill_text, skill_version)
            st.success(t("synth.batch_done", done=res["done"],
                         failed=res["failed"]))
            st.rerun()
    b3.caption(t("synth.batch_hint"))

    f1, f2, f3, f4 = st.columns([2.6, 1.7, 2.2, 1.5])
    query = f1.text_input("Поиск", label_visibility="collapsed",
                          placeholder="Поиск: ASIN, SKU или тайтл...")
    mps = sorted({x["r"]["marketplace"] for x in rows})
    mp_sel = f2.multiselect("MP", mps, default=[], label_visibility="collapsed",
                            placeholder=t("list.all_mp"))
    try:
        scope = f3.segmented_control(
            "фильтр", ["all", "sqp", "todo", "done"], default="all",
            format_func=lambda k: {"all": t("work.all"),
                                   "sqp": t("work.with_sqp"),
                                   "todo": t("work.no_draft"),
                                   "done": t("work.accepted")}[k],
            selection_mode="single", label_visibility="collapsed",
            key="syn-scope",
            help="все — вся очередь · с SQP — только там, где есть данные "
                 "Brand Analytics · без черновика — ещё не генерировали · "
                 "принято — правка уже записана")
    except AttributeError:
        scope = f3.radio("фильтр", ["all", "sqp", "todo", "done"],
                         horizontal=True,
                         label_visibility="collapsed", key="syn-scope")
    scope = scope or "all"
    try:
        q_mode = f4.segmented_control(
            "вид", ["cards", "table"], default="cards",
            format_func=lambda k: t("list.cards") if k == "cards"
            else t("list.table"),
            selection_mode="single", label_visibility="collapsed",
            key="syn-mode")
    except AttributeError:
        q_mode = f4.radio("вид", ["cards", "table"], horizontal=True,
                          label_visibility="collapsed", key="syn-mode")
    q_mode = q_mode or "cards"

    st.caption(t("synth.batch_hint"))

    view = rows
    if mp_sel:
        view = [x for x in view if x["r"]["marketplace"] in mp_sel]
    if scope == "sqp":
        view = [x for x in view if x["sqp_state"] == "ready"]
    elif scope == "todo":
        view = [x for x in view if not x["draft"].get("drafts")]
    elif scope == "done":
        view = [x for x in view if x["accepted"]]
    if query.strip():
        q = query.strip().lower()
        view = [x for x in view
                if q in str(x["r"]["asin"]).lower()
                or q in str(x["r"].get("sku_group") or "").lower()
                or q in str(x["r"]["title"] or "").lower()]

    if not view:
        st.caption(t("catalog.nothing"))
    else:
        view.sort(key=lambda z: (-z["risk"], -z["over"]))

        if q_mode == "table":
            tv = pd.DataFrame([{
                "фото": (None if pd.isna(z["r"].get("main_image"))
                         else z["r"].get("main_image")),
                "SKU": z["r"]["sku_group"], "ASIN": z["r"]["asin"],
                "MP": z["r"]["marketplace"],
                "симв.": len(z["r"]["title"] or ""),
                "превышение": z["over"],
                "под риском, €": round(z["risk"]) if z["risk"] else None,
                "SQP": {"ready": "есть", "queued": "в очереди",
                        "off": "не собирается"}[z["sqp_state"]],
                "черновиков": (int(z["draft"]["drafts"])
                               if z["draft"].get("drafts") else 0),
                "Coverage": (int(z["draft"]["coverage"])
                             if z["draft"].get("coverage") is not None
                             and not pd.isna(z["draft"].get("coverage"))
                             else None),
                "принято": ("да" if z["accepted"] else ""),
                "тайтл": (z["r"]["title"] or "")[:70],
                "ссылка": f"https://www.amazon.{z['r']['marketplace']}"
                          f"/dp/{z['r']['asin']}",
            } for z in view])
            st.dataframe(
                tv,
                column_config={
                    "фото": st.column_config.ImageColumn("Фото", width="small"),
                    "под риском, €": st.column_config.NumberColumn(
                        "Под риском, €", format="%.0f", width="small"),
                    "Coverage": st.column_config.NumberColumn(
                        "Coverage, %", format="%.0f", width="small"),
                    "ссылка": st.column_config.LinkColumn(
                        "Листинг", display_text="открыть"),
                    "тайтл": st.column_config.TextColumn("Тайтл", width="large"),
                },
                hide_index=True, use_container_width=True, height=520)
            st.caption(t("list.sort_hint"))
            st.stop()

        for x in view[:30]:
            r = x["r"]
            asin, mp = r["asin"], r["marketplace"]
            title = r["title"] or ""
            render_card_head(x)

            with st.expander(f"{t('synth.work_with')} · {asin} · {mp}"):
                fetched = (pd.to_datetime(r["fetched_at"]).strftime("%d.%m %H:%M")
                           if pd.notna(r["fetched_at"]) else "—")
                st.markdown(
                    eyebrow(f"{t('synth.original')} · {len(title)} симв. · "
                            f"{t('matrix.collected_at')} {fetched} · "
                            f"{t('synth.methodology')} v{skill_version}"),
                    unsafe_allow_html=True)
                st.code(title, language=None)
                st.markdown(
                    limit_ruler_html(len(title), TITLE_LIMIT,
                                     left_label=f"{TITLE_LIMIT} {t('ruler.limit')}",
                                     right_label=f"+{x['over']} {t('ruler.cut')}"),
                    unsafe_allow_html=True)

                st.markdown(eyebrow(t("synth.keywords")),
                            unsafe_allow_html=True)
                kw = build_keyword_table(asin, mp, title)
                kw_edit = pd.DataFrame()
                if kw.empty:
                    st.caption(SQP_LABEL[x["sqp_state"]] + " · "
                               + t("synth.no_sqp"))
                else:
                    v = kw.rename(columns={
                        "search_query": "фраза", "volume": "спрос",
                        "impressions": "показы", "clicks": "клики",
                        "purchases": "покупки", "weight": "вес",
                        "in_title": "в тайтле", "tier": "тип"})
                    v["вес"] = v["вес"].round(1)
                    kw_edit = st.data_editor(
                        v[["фраза", "спрос", "показы", "клики", "покупки",
                           "вес", "в тайтле", "тип"]],
                        column_config={
                            "тип": st.column_config.SelectboxColumn(
                                "Тип", options=TIERS, required=True),
                            "в тайтле": st.column_config.CheckboxColumn(
                                "В тайтле", disabled=True),
                            "фраза": st.column_config.TextColumn(
                                "Фраза", width="large", disabled=True),
                        },
                        hide_index=True, use_container_width=True, height=280,
                        key=f"kw-{asin}-{mp}")
                    cnt = kw_edit["тип"].value_counts().to_dict()
                    st.markdown(" · ".join(f"{TIER_LABEL[k]} {cnt.get(k, 0)}"
                                           for k in TIERS))

                keep_list, forbid_list = [], []
                if not kw_edit.empty:
                    o = kw_edit.sort_values("вес", ascending=False)
                    keep_list = o.loc[o["тип"].isin(["must_keep", "preferred"]),
                                      "фраза"].tolist()
                    forbid_list = o.loc[o["тип"] == "forbid", "фраза"].tolist()

                if st.button(t("synth.generate"), type="primary",
                             key=f"gen-{asin}-{mp}"):
                    with st.spinner(f"Режу по методологии v{skill_version}..."):
                        res = generate_split(title, mp, skill_text,
                                             keep_list, forbid_list)
                    if res:
                        save_draft(asin, mp, title, res, skill_version)
                        if not kw.empty:
                            save_coverage(asin, mp, coverage(
                                kw, res.get("title", ""),
                                res.get("highlights", "")))
                        st.session_state[f"res-{asin}-{mp}"] = res
                        st.cache_data.clear()
                        st.rerun()

    if len(view) > 30:
        st.caption(f"показано 30 из {len(view)} — уточни фильтры")


# ================================================================ разбор
with tab_review:
    if pending.empty:
        st.info(t("synth.no_drafts"))
    else:
        st.caption(t("synth.review_hint"))
        econ_sorted = []
        for _, d in pending.iterrows():
            e = ECON.get((d["asin"], d["marketplace"])) or {}
            econ_sorted.append((money_at_risk("title_over_limit",
                                              e.get("revenue_30d")), d))
        econ_sorted.sort(key=lambda z: -z[0])

        for risk, d in econ_sorted:
            asin, mp = d["asin"], d["marketplace"]
            before = d["title_before"] or ""
            after = d["title_after"] or ""
            hl = d["highlights_after"] or ""
            checks = run_checks(after, hl, [], [])
            n_failed = sum(1 for ok, _ in checks if not ok)
            qual, qtext = draft_quality(d.get("coverage_score"), n_failed)
            color = Q_COLOR[qual]

            st.markdown(
                f'<div class="ls-card" style="background:#fff;'
                f'border:1px solid #E7E4DD;border-left:3px solid {color};'
                f'border-radius:0 10px 10px 0;padding:10px 14px;'
                f'margin-bottom:4px;">'
                f'<div style="display:flex;justify-content:space-between;">'
                f'<span style="font-size:13px;font-weight:700;">{asin} · {mp}'
                f'<span style="font-weight:400;color:#57534A;"> · '
                f'{len(before)} → {len(after)} симв.</span></span>'
                f'<span class="ls-mono" style="font-size:12.5px;color:{color};">'
                f'{qtext}{" · " + fmt_money(risk) if risk else ""}</span></div>'
                f'<div style="font-size:12.5px;color:#1A1815;margin-top:4px;'
                f'font-family:var(--ls-mono);">{after}</div></div>',
                unsafe_allow_html=True)

            with st.expander(f"{t('synth.details')} · {asin} · {mp}"):
                st.markdown(f"**{t('synth.was')}**")
                st.code(before, language=None)
                st.markdown(f"**title** · {len(after)}/{TITLE_LIMIT}")
                st.code(after, language=None)
                st.markdown(f"**item highlights** · {len(hl)}/{HIGHLIGHTS_LIMIT}")
                st.code(hl, language=None)
                if d.get("dropped"):
                    st.markdown(f"**{t('synth.dropped')}:** {d['dropped']}")
                st.markdown(" · ".join(("✅ " if ok else "❌ ") + m
                                       for ok, m in checks))

            c1, c2, c3 = st.columns([1.3, 1.2, 4])
            if c1.button(t("synth.accept_short"), type="primary",
                         disabled=bool(n_failed),
                         key=f"acc-{asin}-{mp}-{d['id']}"):
                if accept_change(asin, mp, before,
                                 {"title": after, "highlights": hl,
                                  "dropped": (d.get("dropped") or "").split("; ")},
                                 d.get("coverage_score"),
                                 int(d.get("skill_version") or 0),
                                 GEMINI_MODEL):
                    st.success(t("synth.accepted_ok"))
                    st.rerun()
            if c2.button(t("synth.regenerate"), key=f"re-{asin}-{mp}-{d['id']}"):
                kw = build_keyword_table(asin, mp, before)
                keep = forbid = []
                if not kw.empty:
                    keep = kw.loc[kw["tier"].isin(["must_keep", "preferred"]),
                                  "search_query"].tolist()
                    forbid = kw.loc[kw["tier"] == "forbid",
                                    "search_query"].tolist()
                with st.spinner("Генерирую заново..."):
                    res = generate_split(before, mp, skill_text, keep, forbid)
                if res:
                    save_draft(asin, mp, before, res, skill_version)
                    if not kw.empty:
                        save_coverage(asin, mp, coverage(
                            kw, res.get("title", ""), res.get("highlights", "")))
                    st.cache_data.clear()
                    st.rerun()


# ================================================================ любой товар
with tab_any:
    st.caption(t("synth.any_hint"))
    if all_products.empty:
        st.info(t("common.no_data"))
    else:
        aq1, aq2 = st.columns([3, 2])
        any_query = aq1.text_input(
            "Поиск", label_visibility="collapsed", key="any-q",
            placeholder="Поиск: ASIN, SKU или название...")
        any_mps = sorted(all_products["marketplace"].dropna().unique())
        any_mp = aq2.multiselect("MP", any_mps, default=[],
                                 label_visibility="collapsed",
                                 placeholder=t("list.all_mp"), key="any-mp")

        av = all_products
        if any_mp:
            av = av[av["marketplace"].isin(any_mp)]
        if any_query.strip():
            q = any_query.strip().lower()
            av = av[
                av["asin"].astype(str).str.lower().str.contains(q, na=False)
                | av["sku_group"].astype(str).str.lower().str.contains(q, na=False)
                | av["title"].astype(str).str.lower().str.contains(q, na=False)
            ]

        st.caption(f"{t('matrix.found')} {len(av)}")
        if av.empty:
            st.caption(t("catalog.nothing"))
        else:
            with st.expander(f"{t('list.table')} ({len(av)})"):
                atv = av.copy()
                atv["симв."] = atv["title"].astype(str).str.len().where(
                    atv["title"].notna(), None)
                atv["превышение"] = (atv["симв."] - TITLE_LIMIT).clip(lower=0)
                atv["собрано"] = pd.to_datetime(
                    atv["fetched_at"], errors="coerce").dt.strftime("%d.%m %H:%M")
                atv["ссылка"] = atv.apply(
                    lambda z: f"https://www.amazon.{z['marketplace']}"
                              f"/dp/{z['asin']}", axis=1)
                st.dataframe(
                    atv[["main_image", "sku_group", "asin", "marketplace",
                         "симв.", "превышение", "собрано", "title", "ссылка"]]
                    .rename(columns={"main_image": "фото", "sku_group": "SKU",
                                     "asin": "ASIN", "marketplace": "MP",
                                     "title": "тайтл"}),
                    column_config={
                        "фото": st.column_config.ImageColumn("Фото",
                                                             width="small"),
                        "ссылка": st.column_config.LinkColumn(
                            "Листинг", display_text="открыть"),
                        "тайтл": st.column_config.TextColumn("Тайтл",
                                                             width="large"),
                    },
                    hide_index=True, use_container_width=True, height=420)
                st.caption(t("list.sort_hint"))

            opts = {}
            for _, r in av.head(300).iterrows():
                # NaN истинный в Python: без pd.isna() len(NaN) уронит страницу
                raw_title = r.get("title")
                title_s = "" if raw_title is None or pd.isna(raw_title) else str(raw_title)
                raw_sku = r.get("sku_group")
                sku_s = "" if raw_sku is None or pd.isna(raw_sku) else str(raw_sku)
                sku = f"{sku_s} · " if sku_s and sku_s != r["asin"] else ""
                ln = f" · {len(title_s)}" if title_s else ""
                ttl = title_s[:60] if title_s else t("matrix.not_collected")
                opts[f"{sku}{r['asin']} · {r['marketplace']}{ln} · {ttl}"] = (
                    r["asin"], r["marketplace"])

            pick = st.selectbox("Товар", list(opts.keys()), key="any-pick")
            a_asin, a_mp = opts[pick]
            arow = av[(av["asin"] == a_asin)
                      & (av["marketplace"] == a_mp)].iloc[0]
            a_title = arow["title"] or ""

            if not a_title:
                st.warning(t("synth.no_snapshot"))
            else:
                over = max(0, len(a_title) - TITLE_LIMIT)
                fetched = (pd.to_datetime(arow["fetched_at"]).strftime("%d.%m %H:%M")
                           if pd.notna(arow["fetched_at"]) else "—")
                st.markdown(
                    eyebrow(f"{t('synth.original')} · {len(a_title)} симв. · "
                            f"{t('matrix.collected_at')} {fetched} · "
                            f"{t('synth.methodology')} v{skill_version}"),
                    unsafe_allow_html=True)
                st.code(a_title, language=None)
                st.markdown(
                    limit_ruler_html(
                        len(a_title), TITLE_LIMIT,
                        left_label=f"{TITLE_LIMIT} {t('ruler.limit')}",
                        right_label=(f"+{over} {t('ruler.cut')}" if over
                                     else f"{t('ruler.free')} "
                                          f"{TITLE_LIMIT - len(a_title)}")),
                    unsafe_allow_html=True)
                if not over:
                    st.caption(t("synth.in_limit"))

                st.markdown(eyebrow(t("synth.keywords")),
                            unsafe_allow_html=True)
                a_kw = build_keyword_table(a_asin, a_mp, a_title)
                a_edit = pd.DataFrame()
                if a_kw.empty:
                    st.caption(t("synth.no_sqp"))
                else:
                    v = a_kw.rename(columns={
                        "search_query": "фраза", "volume": "спрос",
                        "impressions": "показы", "clicks": "клики",
                        "purchases": "покупки", "weight": "вес",
                        "in_title": "в тайтле", "tier": "тип"})
                    v["вес"] = v["вес"].round(1)
                    a_edit = st.data_editor(
                        v[["фраза", "спрос", "показы", "клики", "покупки",
                           "вес", "в тайтле", "тип"]],
                        column_config={
                            "тип": st.column_config.SelectboxColumn(
                                "Тип", options=TIERS, required=True),
                            "в тайтле": st.column_config.CheckboxColumn(
                                "В тайтле", disabled=True),
                            "фраза": st.column_config.TextColumn(
                                "Фраза", width="large", disabled=True),
                        },
                        hide_index=True, use_container_width=True, height=280,
                        key=f"any-kw-{a_asin}-{a_mp}")
                    cnt = a_edit["тип"].value_counts().to_dict()
                    st.markdown(" · ".join(f"{TIER_LABEL[k]} {cnt.get(k, 0)}"
                                           for k in TIERS))

                a_keep, a_forbid = [], []
                if not a_edit.empty:
                    o = a_edit.sort_values("вес", ascending=False)
                    a_keep = o.loc[o["тип"].isin(["must_keep", "preferred"]),
                                   "фраза"].tolist()
                    a_forbid = o.loc[o["тип"] == "forbid", "фраза"].tolist()

                if st.button(t("synth.generate"), type="primary",
                             key=f"any-gen-{a_asin}-{a_mp}"):
                    with st.spinner(f"Режу по методологии v{skill_version}..."):
                        ares = generate_split(a_title, a_mp, skill_text,
                                              a_keep, a_forbid)
                    if ares:
                        save_draft(a_asin, a_mp, a_title, ares, skill_version)
                        if not a_kw.empty:
                            save_coverage(a_asin, a_mp, coverage(
                                a_kw, ares.get("title", ""),
                                ares.get("highlights", "")))
                        st.session_state[f"any-res-{a_asin}-{a_mp}"] = ares
                        st.cache_data.clear()
                        st.rerun()

                ares = st.session_state.get(f"any-res-{a_asin}-{a_mp}")
                if ares:
                    a_new = ares.get("title", "")
                    a_hl = ares.get("highlights", "")
                    st.divider()
                    a_cov = None
                    if not a_edit.empty:
                        cdf = a_kw.copy()
                        tmap = dict(zip(a_edit["фраза"], a_edit["тип"]))
                        cdf["tier"] = cdf["search_query"].map(tmap).fillna("compress")
                        cv = coverage(cdf, a_new, a_hl)
                        a_cov = cv["score"]
                        if a_cov is not None:
                            col = ("#2F6B3A" if a_cov >= 85
                                   else "#854F0B" if a_cov >= 65 else "#A32D2D")
                            st.markdown(
                                f'<div style="font-size:19px;font-weight:700;">'
                                f'SEO Coverage <span style="color:{col};'
                                f'font-family:var(--ls-mono);">{a_cov}%</span>'
                                f'</div>', unsafe_allow_html=True)
                            if cv["lost"]:
                                st.markdown(f"**{t('synth.lost')}:** "
                                            + " · ".join(
                                    f"`{p}`" for p, _, _ in cv["lost"][:6]))

                    st.markdown(f"**title** · {len(a_new)}/{TITLE_LIMIT}")
                    st.code(a_new, language=None)
                    st.markdown(f"**item highlights** · {len(a_hl)}/{HIGHLIGHTS_LIMIT}")
                    st.code(a_hl, language=None)
                    if ares.get("dropped"):
                        st.markdown(f"**{t('synth.dropped')}:** "
                                    + " · ".join(f"`{w}`"
                                                 for w in ares["dropped"]))

                    a_checks = run_checks(a_new, a_hl, a_keep, a_forbid)
                    a_failed = [m for ok, m in a_checks if not ok]
                    st.markdown(" · ".join(("✅ " if ok else "❌ ") + m
                                           for ok, m in a_checks))

                    ac1, ac2 = st.columns([1.4, 1])
                    if ac1.button(t("synth.accept"), type="primary",
                                  disabled=bool(a_failed),
                                  key=f"any-acc-{a_asin}-{a_mp}"):
                        if accept_change(a_asin, a_mp, a_title, ares, a_cov,
                                         skill_version, GEMINI_MODEL):
                            st.success(t("synth.accepted_ok"))
                            st.rerun()
                    if ac2.button(t("synth.regenerate"),
                                  key=f"any-re-{a_asin}-{a_mp}"):
                        st.session_state.pop(f"any-res-{a_asin}-{a_mp}", None)
                        st.rerun()
