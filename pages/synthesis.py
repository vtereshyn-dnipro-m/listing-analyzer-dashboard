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
st.header(t("nav.synthesis"))

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


# ================================================================ UI
SQP_MARKETPLACES = {"es", "de", "it"}   # где загрузчик SQP собирает данные

st.header(t("nav.synthesis"))
st.caption("Сжатие тайтла под лимит без потери поискового веса. "
           "Приоритет — по деньгам под риском.")

candidates = load_candidates()
if candidates.empty:
    st.info(t("synth.no_candidates"))
    st.stop()

skill_text, skill_version = load_skill()
ECON = econ_map()
DRAFTS = load_draft_stats()
ACCEPTED = load_accepted()

# ---- сводка и фильтры
rows = []
for _, r in candidates.iterrows():
    key = (r["asin"], r["marketplace"])
    e = ECON.get(key) or {}
    risk = money_at_risk("title_over_limit", e.get("revenue_30d"))
    rows.append({
        "r": r, "risk": risk,
        "over": max(0, len(r["title"] or "") - TITLE_LIMIT),
        "econ": e,
        "draft": DRAFTS.get(key) or {},
        "accepted": ACCEPTED.get(key),
        "sqp_state": ("ready" if r["marketplace"] in SQP_MARKETPLACES
                      and e.get("sessions_30d") else
                      "queued" if r["marketplace"] in SQP_MARKETPLACES
                      else "off"),
    })

total_risk = sum(x["risk"] for x in rows)
n_ready = sum(1 for x in rows if x["sqp_state"] == "ready")
st.markdown(
    f"Под риском <b style='color:{ACCENT}'>{fmt_money(total_risk, '')}</b>/мес · "
    f"{len(rows)} тайтлов сверх лимита · SQP есть у {n_ready}",
    unsafe_allow_html=True)

f1, f2, f3 = st.columns([3, 2, 2])
query = f1.text_input("Поиск", label_visibility="collapsed",
                      placeholder="Поиск: ASIN, SKU или тайтл...")
mps = sorted({x["r"]["marketplace"] for x in rows})
mp_sel = f2.multiselect("MP", mps, default=[], label_visibility="collapsed",
                        placeholder=t("list.all_mp"))
try:
    scope = f3.segmented_control(
        "фильтр", ["all", "sqp", "todo"], default="all",
        format_func=lambda k: {"all": "все", "sqp": "с SQP",
                               "todo": "без черновика"}[k],
        selection_mode="single", label_visibility="collapsed", key="syn-scope")
except AttributeError:
    scope = f3.radio("фильтр", ["all", "sqp", "todo"], horizontal=True,
                     label_visibility="collapsed", key="syn-scope")
scope = scope or "all"

view = rows
if mp_sel:
    view = [x for x in view if x["r"]["marketplace"] in mp_sel]
if scope == "sqp":
    view = [x for x in view if x["sqp_state"] == "ready"]
elif scope == "todo":
    view = [x for x in view if not x["draft"].get("drafts")]
if query.strip():
    q = query.strip().lower()
    view = [x for x in view
            if q in str(x["r"]["asin"]).lower()
            or q in str(x["r"].get("sku_group") or "").lower()
            or q in str(x["r"]["title"] or "").lower()]

if not view:
    st.caption(t("catalog.nothing"))
    st.stop()

view.sort(key=lambda x: (-x["risk"], -x["over"]))

SQP_LABEL = {
    "ready": "",
    "queued": "○ SQP в очереди — загрузчик идёт по каталогу",
    "off": "○ SQP не собирается для этого маркетплейса",
}

# ---- карточки
for x in view[:30]:
    r = x["r"]
    asin, mp = r["asin"], r["marketplace"]
    title = r["title"] or ""
    sku = r["sku_group"] if r["sku_group"] and r["sku_group"] != asin else ""
    fetched = (pd.to_datetime(r["fetched_at"]).strftime("%d.%m %H:%M")
               if pd.notna(r["fetched_at"]) else "—")
    img = None if pd.isna(r.get("main_image")) else r.get("main_image")
    edge = ACCENT if x["risk"] else "#E7E4DD"

    thumb = (f'<div style="flex:0 0 42px;"><img src="{img}" '
             f'style="width:42px;height:42px;object-fit:contain;background:#fff;'
             f'border:1px solid #E7E4DD;border-radius:7px;"></div>') if img else ""

    sub_parts = []
    if x["sqp_state"] == "ready":
        sub_parts.append(f"SQP по товару собран")
    else:
        sub_parts.append(SQP_LABEL[x["sqp_state"]])
    if x["draft"].get("drafts"):
        cov = x["draft"].get("coverage")
        sub_parts.append(f"черновиков {int(x['draft']['drafts'])}"
                         + (f" · Coverage {int(cov)}%" if pd.notna(cov) else ""))
    if x["accepted"]:
        sub_parts.append("✓ правка принята "
                         + pd.to_datetime(x["accepted"]["accepted_at"]).strftime("%d.%m"))

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
        f'{len(title)}/{TITLE_LIMIT} · +{x["over"]} · {title[:60]}…</span></div>'
        f'<div style="font-size:11.5px;color:#57534A;">{" · ".join(p for p in sub_parts if p)}</div>'
        f'</div>'
        f'<span class="ls-mono" style="font-size:13px;font-weight:700;'
        f'color:{ACCENT if x["risk"] else "#57534A"};">'
        f'{fmt_money(x["risk"]) if x["risk"] else "нет данных"}</span></div>',
        unsafe_allow_html=True)

    with st.expander(f"Работа с тайтлом · {asin}"):
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

        # ---- ключевые фразы
        st.markdown(eyebrow("Ключевые фразы · Brand Analytics"),
                    unsafe_allow_html=True)
        kw_sqp = build_keyword_table(asin, mp, title)
        kw_edit = pd.DataFrame()

        if kw_sqp.empty:
            st.caption(
                SQP_LABEL.get(x["sqp_state"]) or
                "Данных Brand Analytics по этому товару пока нет. "
                "Генерация пойдёт по методологии, без весов фраз.")
        else:
            v = kw_sqp.rename(columns={
                "search_query": "фраза", "volume": "спрос",
                "impressions": "показы", "clicks": "клики",
                "purchases": "покупки", "weight": "вес",
                "in_title": "в тайтле", "tier": "тип"})
            v["вес"] = v["вес"].round(1)
            kw_edit = st.data_editor(
                v[["фраза", "спрос", "показы", "клики", "покупки", "вес",
                   "в тайтле", "тип"]],
                column_config={
                    "тип": st.column_config.SelectboxColumn(
                        "Тип", options=TIERS, required=True),
                    "в тайтле": st.column_config.CheckboxColumn(
                        "В тайтле", disabled=True),
                    "фраза": st.column_config.TextColumn(
                        "Фраза", width="large", disabled=True),
                    "спрос": st.column_config.NumberColumn("Спрос", disabled=True),
                    "показы": st.column_config.NumberColumn("Показы", disabled=True),
                    "клики": st.column_config.NumberColumn("Клики", disabled=True),
                    "покупки": st.column_config.NumberColumn("Покупки", disabled=True),
                    "вес": st.column_config.NumberColumn("Вес", disabled=True),
                },
                hide_index=True, use_container_width=True, height=300,
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

        # ---- генерация
        if st.button(t("synth.generate"), type="primary", key=f"gen-{asin}-{mp}"):
            with st.spinner(f"Режу тайтл по методологии v{skill_version}..."):
                res = generate_split(title, mp, skill_text, keep_list, forbid_list)
            if res:
                st.session_state[f"res-{asin}-{mp}"] = res
                save_draft(asin, mp, title, res, skill_version)
                st.cache_data.clear()

        res = st.session_state.get(f"res-{asin}-{mp}")
        if res:
            new_title = res.get("title", "")
            new_hl = res.get("highlights", "")
            dropped = res.get("dropped", []) or []

            st.divider()
            cov_score = None
            if not kw_edit.empty:
                cov_df = kw_sqp.copy()
                tmap = dict(zip(kw_edit["фраза"], kw_edit["тип"]))
                cov_df["tier"] = cov_df["search_query"].map(tmap).fillna("compress")
                cov = coverage(cov_df, new_title, new_hl)
                cov_score = cov["score"]
                if cov_score is not None:
                    col = ("#2F6B3A" if cov_score >= 85
                           else "#854F0B" if cov_score >= 65 else "#A32D2D")
                    vtxt = ("поисковый вес сохранён" if cov_score >= 85
                            else "часть веса потеряна" if cov_score >= 65
                            else "потеряно слишком много")
                    st.markdown(
                        f'<div style="font-size:19px;font-weight:700;">'
                        f'SEO Coverage <span style="color:{col};'
                        f'font-family:var(--ls-mono);">{cov_score}%</span> '
                        f'<span style="font-size:13px;font-weight:400;'
                        f'color:#57534A;">· {vtxt}</span></div>',
                        unsafe_allow_html=True)
                    st.caption(
                        "Покупка весит как 20 кликов, клик — как 200 показов. "
                        "Фразы FORBID не считаются.")
                    if cov["lost"]:
                        lost_txt = " · ".join(
                            f"`{p}` ({TIER_LABEL.get(tr, tr)})"
                            for p, _, tr in cov["lost"][:6])
                        st.markdown(f"**Потеряно:** {lost_txt}")

            st.markdown(f"**title** · {len(new_title)}/{TITLE_LIMIT}")
            st.code(new_title, language=None)
            st.markdown(f"**item highlights** · {len(new_hl)}/{HIGHLIGHTS_LIMIT}")
            st.code(new_hl, language=None)
            if dropped:
                st.markdown(f"**{t('synth.dropped')}:** "
                            + " · ".join(f"`{w}`" for w in dropped))

            checks = run_checks(new_title, new_hl, keep_list, forbid_list)
            failed = [m for ok, m in checks if not ok]
            st.markdown(" · ".join(("✅ " if ok else "❌ ") + m
                                   for ok, m in checks))
            if failed:
                st.warning(t("synth.checks_failed"))

            a1, a2 = st.columns([1.4, 1])
            if a1.button("✓ Принять и записать", type="primary",
                         disabled=bool(failed), key=f"acc-{asin}-{mp}"):
                if accept_change(asin, mp, title, res, cov_score,
                                 skill_version, GEMINI_MODEL):
                    st.success(
                        "Правка записана. Вставь title и highlights в Seller "
                        "Central — эффект замерим по sessions и продажам.")
                    st.rerun()
            if a2.button("Перегенерировать", key=f"regen-{asin}-{mp}"):
                st.session_state.pop(f"res-{asin}-{mp}", None)
                st.rerun()

if len(view) > 30:
    st.caption(f"показано 30 из {len(view)} — уточни фильтры")
