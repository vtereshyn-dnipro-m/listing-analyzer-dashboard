# -*- coding: utf-8 -*-
"""
pages/guide.py — Как это работает: порядок шагов и логика Listing Suite.

Статичная инструкция для команды: с чего начать, что где делается,
что происходит автоматически. Обновляется по мере роста продукта.
"""
from __future__ import annotations

import streamlit as st

from i18n import t
from components.ui import inject_fonts, eyebrow

inject_fonts()
st.title(t("guide.title"))

# --ls-mono, .ls-mono и .ls-eyebrow объявлены в inject_fonts() — локальная
# копия этих стилей раньше жила здесь и печаталась на странице текстом
# (блок был с отступом, markdown принимал его за код).

INK = "#1A1815"
MUTED = "#57534A"
BORDER = "#E7E4DD"
CARD = "#FFFFFF"
ACCENT = "#E8590C"
MONO = "var(--ls-mono)"


def step_card(num: int, title: str, page: str, body: str, auto: bool = False) -> None:
    """Карточка шага. HTML одной строкой — см. правило в components/ui.py."""
    badge = (
        f'<span style="background:#DCEEE0;color:#2F6B3A;border-radius:999px;'
        f'padding:2px 10px;font-size:11px;font-weight:600;">'
        f"{t('guide.auto_badge')}</span>"
        if auto else ""
    )
    html = (
        f'<div style="background:{CARD};border:1px solid {BORDER};'
        f'border-radius:12px;padding:16px 20px;margin-bottom:12px;'
        f'display:flex;gap:16px;">'
        f'<div style="min-width:34px;height:34px;border-radius:50%;'
        f'background:{INK};color:#FAFAF8;display:flex;align-items:center;'
        f'justify-content:center;font-weight:700;font-size:15px;">{num}</div>'
        f'<div style="flex:1;">'
        f'<div style="font-size:15px;font-weight:700;color:{INK};'
        f'margin-bottom:2px;">{title}'
        f'<span style="font-family:{MONO};font-weight:400;font-size:12px;'
        f'color:{MUTED};"> · {page}</span> {badge}</div>'
        f'<div style="font-size:13px;color:{MUTED};line-height:1.55;">'
        f"{body}</div></div></div>"
    )
    st.markdown(html, unsafe_allow_html=True)


st.caption(t("guide.caption"))

st.markdown("")
st.markdown(eyebrow(t("guide.flow.header")), unsafe_allow_html=True)


@st.cache_data(ttl=300)
def load_flow_status() -> dict:
    """Живой статус для схемы: свежесть сбора и число активных болей."""
    out = {"fresh_collect": False, "pains": 0, "last_fetch": None}
    try:
        from services.db import get_conn
        import pandas as pd
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT
                (SELECT MAX(fetched_at) FROM listing_snapshots WHERE ok = TRUE) AS last_fetch,
                (SELECT COUNT(*) FROM (
                    SELECT DISTINCT ON (asin, marketplace, rule_id) 1
                    FROM diagnosis
                    ORDER BY asin, marketplace, rule_id, created_at DESC
                ) x) AS pains
            """,
            conn,
        )
        conn.close()
        if not df.empty:
            lf = df.iloc[0]["last_fetch"]
            if lf is not None and not pd.isna(lf):
                age_h = (pd.Timestamp.utcnow() - pd.to_datetime(lf, utc=True)
                         ).total_seconds() / 3600
                out["fresh_collect"] = age_h <= 24
                out["last_fetch"] = pd.to_datetime(lf).strftime("%d.%m %H:%M")
            out["pains"] = int(df.iloc[0]["pains"] or 0)
    except Exception:
        pass
    return out


_flow = load_flow_status()
_fetch_ds = (f"{t('guide.flow.collect_last')} {_flow['last_fetch']}" if _flow["last_fetch"]
             else t("guide.flow.collect_default"))
_pain_ds = (f"{t('guide.flow.diagnosis_pains')} {_flow['pains']}" if _flow["pains"]
            else t("guide.flow.diagnosis_default"))

def flow_node(name: str, desc: str, hot: bool = False) -> str:
    """Узел схемы потока. Подсветка hot — свежий сбор."""
    return (
        f'<div class="ls-node{" hot" if hot else ""}" style="width:16%;">'
        f'<div class="nm">{name}</div>'
        f'<div class="ds">{desc}</div></div>'
    )


LANE = ('<div class="ls-lane"><span class="ls-dot"></span>'
        '<span class="ls-dot d2"></span></div>')

# CSS схемы — одной строкой: с переносами и отступами markdown принимает
# блок за код и печатает стили текстом вместо применения.
FLOW_CSS = (
    "<style>"
    "@keyframes lsflow{0%{left:0%;opacity:0;}8%{opacity:1;}"
    "92%{opacity:1;}100%{left:calc(100% - 10px);opacity:0;}}"
    "@keyframes lspulse{0%,100%{box-shadow:0 0 0 0 rgba(232,89,12,0.35);}"
    "50%{box-shadow:0 0 0 10px rgba(232,89,12,0);}}"
    f".ls-node{{background:{CARD};border:1.5px solid {BORDER};"
    "border-radius:12px;padding:12px 10px;text-align:center;"
    "position:relative;z-index:2;}"
    f".ls-node .nm{{font-size:12.5px;font-weight:700;color:{INK};}}"
    f".ls-node .ds{{font-size:10.5px;color:{MUTED};line-height:1.3;"
    "margin-top:3px;}"
    f".ls-node.hot{{border-color:{ACCENT};animation:lspulse 2.4s infinite;}}"
    f".ls-lane{{position:relative;height:3px;background:{BORDER};flex:1;"
    "margin-top:34px;z-index:1;border-radius:2px;}"
    ".ls-dot{position:absolute;top:-3.5px;width:10px;height:10px;"
    f"border-radius:50%;background:{ACCENT};"
    "animation:lsflow 2.8s linear infinite;}"
    ".ls-dot.d2{animation-delay:1.4s;background:#EF9F27;}"
    "</style>"
)

nodes = LANE.join([
    flow_node(t("guide.flow.matrix"), t("guide.flow.matrix_ds")),
    flow_node(t("guide.flow.collect"), _fetch_ds, hot=_flow["fresh_collect"]),
    flow_node(t("guide.flow.diagnosis"), _pain_ds),
    flow_node(t("guide.flow.synthesis"), t("guide.flow.synthesis_ds")),
    flow_node("Amazon", t("guide.flow.amazon_ds")),
])

st.markdown(
    FLOW_CSS
    + '<div style="display:flex;align-items:flex-start;gap:0;'
      f'margin-top:10px;">{nodes}</div>'
    + '<div style="display:flex;justify-content:space-between;'
      f'margin-top:14px;font-size:11px;color:{MUTED};">'
      f'<span>{t("guide.flow.human_adds")}</span>'
      f'<span style="color:{ACCENT};font-weight:600;">'
      f'{t("guide.flow.data_flows")}</span>'
      f'<span>{t("guide.flow.human_approves")}</span></div>',
    unsafe_allow_html=True,
)


st.markdown(eyebrow(t("guide.steps_header")), unsafe_allow_html=True)
st.markdown("")

step_card(1, t("guide.step1_title"), t("nav.matrix"), t("guide.step1_body"))
step_card(2, t("guide.step2_title"), t("nav.matrix"), t("guide.step2_body"), auto=True)
step_card(3, t("guide.step3_title"), t("nav.dashboard"), t("guide.step3_body"), auto=True)
step_card(4, t("guide.step4_title"), t("nav.catalog"), t("guide.step4_body"))
step_card(5, t("guide.step5_title"), t("nav.synthesis"), t("guide.step5_body"))
step_card(6, t("guide.step6_title"), t("nav.methodology"), t("guide.step6_body"))

st.markdown("")
st.markdown(eyebrow(t("guide.roadmap_header")), unsafe_allow_html=True)
st.markdown(
    f'<div style="background:{CARD};border:1px dashed {BORDER};'
    f'border-radius:12px;padding:16px 20px;color:{MUTED};font-size:13px;'
    f'line-height:1.6;">{t("guide.roadmap_body")}</div>',
    unsafe_allow_html=True,
)

st.markdown("")
st.caption(
    f"Вопросы и идеи — Vitalii T. · дедлайн тайтлов: лимит 75 симв. с 27.07.2026"
) 
