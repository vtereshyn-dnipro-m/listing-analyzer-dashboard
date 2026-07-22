# -*- coding: utf-8 -*-
from __future__ import annotations

import streamlit as st

INK = "#1A1815"
BG = "#FAFAF8"
ACCENT = "#E8590C"
ACCENT_BG = "#FCE8DC"
OK_BG = "#DCEEE0"
OK_TEXT = "#2F6B3A"
AMBER = "#EF9F27"
AMBER_TEXT = "#854F0B"
MUTED = "#8A8578"
BORDER = "#E7E4DD"
CARD = "#FFFFFF"
TRACK = "#F0EFEA"
MONO = "'JetBrains Mono','SFMono-Regular',Consolas,monospace"

SEV_EDGE = {"red": "#A32D2D", "amber": ACCENT, "yellow": AMBER}
SEV_LABEL = {"red": "критично", "amber": "важно", "yellow": "план"}


def inject_fonts() -> None:
    st.markdown(
        "<link href='https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap' rel='stylesheet'>",
        unsafe_allow_html=True,
    )


def eyebrow(text: str) -> str:
    return (
        f"<span style='font-family:{MONO};font-size:12px;letter-spacing:.06em;"
        f"color:{MUTED};text-transform:uppercase;'>{text}</span>"
    )


def verdict(title: str, subtitle_html: str, meta_right: str = "") -> None:
    right = (
        f"<span style='font-family:{MONO};font-size:12px;color:{MUTED};'>{meta_right}</span>"
        if meta_right else ""
    )
    st.markdown(
        f"""
        <div style="margin-bottom:16px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
            {eyebrow('Диагноз · весь каталог')}{right}
          </div>
          <div style="font-size:27px;font-weight:700;color:{INK};line-height:1.25;margin-bottom:6px;">{title}</div>
          <div style="font-size:14px;color:{INK};">{subtitle_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def chips_row(red: int, amber: int, yellow: int, extra: str = "") -> None:
    def chip(dot: str, label: str, n: int, active: bool) -> str:
        bg = ACCENT_BG if active else CARD
        bd = ACCENT if active else BORDER
        w = "600" if active else "400"
        return (
            f"<span style='background:{bg};border:1px solid {bd};border-radius:999px;"
            f"padding:5px 14px;color:{INK};font-weight:{w};font-size:13px;'>"
            f"<span style='color:{dot};'>&#9679;</span> {label} {n}</span>"
        )

    extra_html = (
        f"<span style='background:{CARD};border:1px solid {BORDER};border-radius:999px;"
        f"padding:5px 14px;color:{MUTED};font-size:13px;'>{extra}</span>"
        if extra else ""
    )
    st.markdown(
        f"<div style='display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px;'>"
        f"{chip('#A32D2D', 'критично', red, red > 0)}"
        f"{chip(ACCENT, 'важно', amber, amber > 0 and red == 0)}"
        f"{chip('#BA7517', 'план', yellow, False)}"
        f"{extra_html}</div>",
        unsafe_allow_html=True,
    )


def limit_ruler_html(current: int, limit: int,
                     left_label: str, right_label: str,
                     over_style: bool = True) -> str:
    current = max(0, int(current or 0))
    limit = max(1, int(limit or 1))
    over = max(0, current - limit)

    if over > 0 and over_style:
        scale_max = max(limit * 1.35, current * 1.05)
        ok_w = (limit / scale_max) * 100
        over_w = (over / scale_max) * 100
        fill = (
            f"<div style='position:absolute;left:0;top:0;height:100%;width:{ok_w:.1f}%;background:{OK_BG};'></div>"
            f"<div style='position:absolute;left:{ok_w:.1f}%;top:0;height:100%;width:{over_w:.1f}%;"
            f"background:repeating-linear-gradient(45deg,{ACCENT_BG},{ACCENT_BG} 6px,{ACCENT} 6px,{ACCENT} 7px);opacity:.55;'></div>"
            f"<div style='position:absolute;left:{ok_w:.1f}%;top:0;height:100%;width:2px;background:{INK};opacity:.6;'></div>"
        )
        left_color, right_color = OK_TEXT, "#993C1D"
    else:
        pct = min(100.0, (current / limit) * 100)
        bar_bg = "#FAEEDA" if not over_style else OK_BG
        marker = AMBER if not over_style else INK
        fill = (
            f"<div style='position:absolute;left:0;top:0;height:100%;width:{pct:.1f}%;background:{bar_bg};'></div>"
            f"<div style='position:absolute;left:{pct:.1f}%;top:0;height:100%;width:2px;background:{marker};opacity:.7;'></div>"
        )
        left_color = AMBER_TEXT if not over_style else OK_TEXT
        right_color = MUTED

    return (
        f"<div style='position:relative;height:26px;width:100%;background:{TRACK};"
        f"border-radius:6px;overflow:hidden;margin:10px 0 12px;'>"
        f"{fill}"
        f"<span style='position:absolute;left:8px;top:5px;font-family:{MONO};font-size:11px;color:{left_color};'>{left_label}</span>"
        f"<span style='position:absolute;right:8px;top:5px;font-family:{MONO};font-size:11px;color:{right_color};'>{right_label}</span>"
        f"</div>"
    )


def pain_card(severity: str, kind_label: str, asin: str, marketplace: str,
              headline: str, product_title: str | None,
              ruler_html: str, cause: str, action: str, money: str) -> None:
    edge = SEV_EDGE.get(severity, BORDER)
    if product_title:
        short = product_title[:130] + ("…" if len(product_title) > 130 else "")
        title_line = (
            f"<div style='font-size:13px;color:{MUTED};margin-bottom:10px;'>&#171;{short}&#187;</div>"
        )
    else:
        title_line = ""
    st.markdown(
        f"""
        <div style="background:{CARD};border:1px solid {BORDER};border-left:3px solid {edge};
                    border-radius:0 12px 12px 0;padding:18px 22px;margin-bottom:14px;">
          <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px;">
            {eyebrow(f'{kind_label} · {asin} · {marketplace}')}
            <span style="font-family:{MONO};font-size:13px;font-weight:600;color:{edge};">{money}</span>
          </div>
          <div style="font-size:16px;font-weight:700;color:{INK};margin-bottom:3px;">{headline}</div>
          {title_line}
          {ruler_html}
          <div style="font-size:13px;color:{MUTED};margin-bottom:12px;">Причина: {cause}</div>
          <div style="display:inline-block;background:{INK};color:{BG};border-radius:8px;
                      padding:8px 14px;font-size:13px;font-weight:600;">{action}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
