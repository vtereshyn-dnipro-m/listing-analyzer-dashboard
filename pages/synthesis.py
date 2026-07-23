# -*- coding: utf-8 -*-
"""
pages/synthesis.py — Синтез: Split 75/125.

Берёт ASIN с болью title_over_limit, реальный тайтл из listing_snapshots,
генерит через Claude: title <=75 + highlights <=125 + выброшенное на ревью.
Результат сохраняется в synthesis_drafts (append-only) — история версий.

DDL для таблицы (прогнать один раз в SQL Editor):
    CREATE TABLE IF NOT EXISTS listing_data.synthesis_drafts (
        id BIGSERIAL PRIMARY KEY,
        asin TEXT NOT NULL,
        marketplace TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        original_title TEXT,
        new_title TEXT,
        new_highlights TEXT,
        dropped_words TEXT,
        model TEXT,
        raw JSONB
    );
    GRANT ALL PRIVILEGES ON listing_data.synthesis_drafts
        TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA listing_data
        TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from config import TITLE_LIMIT, HIGHLIGHTS_LIMIT
from i18n import t
from services.db import get_conn, cfg
from components.ui import inject_fonts, eyebrow, limit_ruler_html

inject_fonts()
st.header(t("nav.synthesis"))

SYNTH_PROMPT = """Ты эксперт по Amazon-листингам. С 27.07.2026 тайтл ограничен {title_limit} символами, появилось поисковое поле Item Highlights ({highlights_limit} символов).

Исходный тайтл ({marketplace}):
{title}

Задача — сплит:
1. title: максимум {title_limit} символов. Бренд первым (Dnipro-M). Сохрани модель, ключевые характеристики и поисковые термины. Язык маркетплейса.
2. highlights: максимум {highlights_limit} символов. Сюда уходят характеристики, не влезшие в title.
3. dropped: слова/фразы из оригинала, которые не попали никуда — на ревью человеку.

Ответь ТОЛЬКО валидным JSON без markdown:
{{"title": "...", "highlights": "...", "dropped": ["...", "..."]}}"""


@st.cache_data(ttl=300)
def load_candidates() -> pd.DataFrame:
    """ASIN с болью title_over_limit + их живой тайтл."""
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


def generate_split(title: str, marketplace: str) -> dict | None:
    api_key = cfg("ANTHROPIC_API_KEY")
    if not api_key:
        st.error("ANTHROPIC_API_KEY не найден в секретах — добавь его до [databricks].")
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{
                "role": "user",
                "content": SYNTH_PROMPT.format(
                    title_limit=TITLE_LIMIT,
                    highlights_limit=HIGHLIGHTS_LIMIT,
                    marketplace=marketplace,
                    title=title,
                ),
            }],
        )
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(text)
    except Exception as e:
        st.error(f"Ошибка генерации: {e}")
        return None


def save_draft(asin: str, mp: str, original: str, result: dict) -> None:
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO synthesis_drafts
                    (asin, marketplace, original_title, new_title,
                     new_highlights, dropped_words, model, raw)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (asin, mp, original,
                 result.get("title", ""),
                 result.get("highlights", ""),
                 ", ".join(result.get("dropped", [])),
                 "claude-sonnet-4-6",
                 json.dumps(result, ensure_ascii=False)),
            )
        conn.close()
    except Exception as e:
        st.warning(f"Сплит сгенерирован, но не сохранён в базу: {e}")


candidates = load_candidates()

if candidates.empty:
    st.info("Нет тайтлов с превышением — Синтезу нечего резать. "
            "Прогони диагноз на странице «Матрица товаров».")
    st.stop()

options = {
    f"{r['asin']} · {r['marketplace']} · {len(r['title'])} симв.": i
    for i, r in candidates.iterrows()
}
choice = st.selectbox("Тайтл с превышением", list(options.keys()))
row = candidates.loc[options[choice]]
asin, mp, title = row["asin"], row["marketplace"], row["title"]

st.markdown(eyebrow(f"Оригинал · {asin} · {mp}"), unsafe_allow_html=True)
st.markdown(f"«{title}»")
st.markdown(
    limit_ruler_html(len(title), TITLE_LIMIT,
                     left_label=f"{TITLE_LIMIT} допуск",
                     right_label=f"+{max(0, len(title) - TITLE_LIMIT)} резать"),
    unsafe_allow_html=True,
)

if st.button("Сгенерировать Split 75/125", type="primary"):
    with st.spinner("Claude режет тайтл..."):
        result = generate_split(title, mp)
    if result:
        st.session_state["synth_result"] = result
        st.session_state["synth_asin"] = (asin, mp, title)
        save_draft(asin, mp, title, result)

result = st.session_state.get("synth_result")
saved_for = st.session_state.get("synth_asin")
if result and saved_for and saved_for[0] == asin and saved_for[1] == mp:
    new_title = result.get("title", "")
    new_hl = result.get("highlights", "")
    dropped = result.get("dropped", [])

    st.divider()
    st.markdown(eyebrow("Результат сплита"), unsafe_allow_html=True)

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
        st.markdown("**Выброшено — на ревью:**")
        st.markdown(" · ".join(f"`{w}`" for w in dropped))

    if len(new_title) > TITLE_LIMIT:
        st.warning(f"Внимание: сгенерированный title {len(new_title)} симв. — "
                   f"всё ещё больше {TITLE_LIMIT}. Перегенерируй или подрежь вручную.")

    st.caption("Черновик сохранён в synthesis_drafts — история версий копится.")
