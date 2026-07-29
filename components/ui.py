# -*- coding: utf-8 -*-
"""
components/ui.py — визуальные компоненты Listing Suite (макет B + линейка C).

Палитра: тёплый белый #FAFAF8, чернильный #1A1815, акцент #E8590C
(только боль и превышения).

ВАЖНО про шрифт: имя "JetBrains Mono" содержит пробел и в CSS требует кавычек.
Раньше это ломало разметку (кавычки внутри атрибута style рвали тег).
Теперь шрифт объявлен ОДИН раз в CSS-переменной --ls-mono (см. inject_fonts),
а в разметку подставляется MONO = "var(--ls-mono)" — строка без кавычек.
Поэтому вложенных кавычек в атрибутах больше не возникает в принципе.
"""

from __future__ import annotations

import streamlit as st

from i18n import t

INK = "#1A1815"
BG = "#FAFAF8"
ACCENT = "#E8590C"
ACCENT_BG = "#FCE8DC"
OK_BG = "#DCEEE0"
OK_TEXT = "#2F6B3A"
AMBER = "#EF9F27"
AMBER_TEXT = "#854F0B"
MUTED = "#6B665C"   # приглушённый, но читаемый
BORDER = "#E7E4DD"
CARD = "#FFFFFF"
TRACK = "#F0EFEA"

# безопасная подстановка шрифта в любые инлайн-стили
MONO = "var(--ls-mono)"

SEV_EDGE = {"red": "#A32D2D", "amber": ACCENT, "yellow": AMBER}
SEV_LABEL = {"red": "критично", "amber": "важно", "yellow": "план"}


def inject_fonts() -> None:
    """Подключает JetBrains Mono, объявляет CSS-переменные и утилитарные
    классы. Вызывается один раз в начале каждой страницы.

    ВАЖНО: строка со стилями формируется без отступов и без пустых строк —
    иначе markdown Streamlit принимает её за блок кода и печатает как текст.
    """
    css = (
        '<link href="https://fonts.googleapis.com/css2?'
        'family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">'
        "<style>"
        ":root{"
        "--ls-mono:\"JetBrains Mono\",\"SFMono-Regular\",Consolas,monospace;"
        "--ls-ink:#1A1815;--ls-muted:#6B665C;--ls-accent:#E8590C;"
        "--ls-border:#E7E4DD;}"
        ".ls-mono{font-family:var(--ls-mono);}"
        ".ls-eyebrow{font-family:var(--ls-mono);font-size:13px;"
        "letter-spacing:.06em;color:var(--ls-muted);text-transform:uppercase;}"
        ".ls-eyebrow a{color:var(--ls-muted);text-decoration:none;"
        "border-bottom:1px dotted var(--ls-muted);}"
        '[data-testid="stStatusWidget"]{visibility:hidden;}'
        ".stMarkdown p,.stMarkdown li,"
        '[data-testid="stMarkdownContainer"] p{font-size:15px;}'
        '[data-testid="stCaptionContainer"],'
        '[data-testid="stCaptionContainer"] p{font-size:13.5px;'
        "color:var(--ls-muted);}"
        ".stButton button,.stDownloadButton button{font-size:14px;}"
        '[data-testid="stExpander"] summary p{font-size:15px;}'
        'section[data-testid="stSidebar"] .stMarkdown p,'
        'section[data-testid="stSidebar"] .stMarkdown li{font-size:15px;}'
        'section[data-testid="stSidebar"] a span{font-size:15px;}'
        "</style>"
    )
    st.markdown(css, unsafe_allow_html=True)


def eyebrow(text: str) -> str:
    """Мелкая моно-подпись над блоком (стили — в классе, кавычек нет)."""
    return f'<span class="ls-eyebrow">{text}</span>'


def verdict(title: str, subtitle_html: str, meta_right: str = "") -> None:
    """Вердикт-блок: eyebrow + крупный заголовок + подстрока."""
    right = (
        f'<span class="ls-mono" style="font-size:13px;color:{MUTED};">{meta_right}</span>'
        if meta_right else ""
    )
    st.markdown(
        f"""
        <div style="margin-bottom:16px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
            {eyebrow(t('dash.eyebrow'))}{right}
          </div>
          <div style="font-size:28px;font-weight:700;color:{INK};line-height:1.25;margin-bottom:6px;">{title}</div>
          <div style="font-size:15px;color:{INK};">{subtitle_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def chips_row(red: int, amber: int, yellow: int, extra: str = "") -> None:
    """Строка чипов-счётчиков."""
    def chip(dot: str, label: str, n: int, active: bool) -> str:
        bg = ACCENT_BG if active else CARD
        bd = ACCENT if active else BORDER
        w = "600" if active else "400"
        return (
            f'<span style="background:{bg};border:1px solid {bd};'
            f'border-radius:999px;padding:5px 14px;color:{INK};'
            f'font-weight:{w};font-size:14px;">'
            f'<span style="color:{dot};">&#9679;</span> {label} {n}</span>'
        )

    extra_html = (
        f'<span style="background:{CARD};border:1px solid {BORDER};'
        f'border-radius:999px;padding:5px 14px;color:{MUTED};'
        f'font-size:14px;">{extra}</span>'
        if extra else ""
    )
    st.markdown(
        f'<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px;">'
        f"{chip('#A32D2D', 'критично', red, red > 0)}"
        f"{chip(ACCENT, 'важно', amber, amber > 0 and red == 0)}"
        f"{chip('#BA7517', 'план', yellow, False)}"
        f"{extra_html}</div>",
        unsafe_allow_html=True,
    )


def limit_ruler_html(current: int, limit: int,
                     left_label: str, right_label: str,
                     over_style: bool = True) -> str:
    """Линейка-допуск. over_style=True — штриховка превышения,
    False — прогресс к цели (отзывы, фото)."""
    current = max(0, int(current or 0))
    limit = max(1, int(limit or 1))
    over = max(0, current - limit)

    if over > 0 and over_style:
        scale_max = max(limit * 1.35, current * 1.05)
        ok_w = (limit / scale_max) * 100
        over_w = (over / scale_max) * 100
        fill = (
            f'<div style="position:absolute;left:0;top:0;height:100%;'
            f'width:{ok_w:.1f}%;background:{OK_BG};"></div>'
            f'<div style="position:absolute;left:{ok_w:.1f}%;top:0;height:100%;'
            f'width:{over_w:.1f}%;background:repeating-linear-gradient(45deg,'
            f'{ACCENT_BG},{ACCENT_BG} 6px,{ACCENT} 6px,{ACCENT} 7px);'
            f'opacity:.55;"></div>'
            f'<div style="position:absolute;left:{ok_w:.1f}%;top:0;height:100%;'
            f'width:2px;background:{INK};opacity:.6;"></div>'
        )
        left_color, right_color = OK_TEXT, "#993C1D"
    else:
        pct = min(100.0, (current / limit) * 100)
        bar_bg = "#FAEEDA" if not over_style else OK_BG
        marker = AMBER if not over_style else INK
        fill = (
            f'<div style="position:absolute;left:0;top:0;height:100%;'
            f'width:{pct:.1f}%;background:{bar_bg};"></div>'
            f'<div style="position:absolute;left:{pct:.1f}%;top:0;height:100%;'
            f'width:2px;background:{marker};opacity:.7;"></div>'
        )
        left_color = AMBER_TEXT if not over_style else OK_TEXT
        right_color = MUTED

    return (
        f'<div style="position:relative;height:26px;width:100%;'
        f'background:{TRACK};border-radius:6px;overflow:hidden;'
        f'margin:10px 0 12px;">'
        f"{fill}"
        f'<span class="ls-mono" style="position:absolute;left:8px;top:5px;'
        f'font-size:12px;color:{left_color};">{left_label}</span>'
        f'<span class="ls-mono" style="position:absolute;right:8px;top:5px;'
        f'font-size:12px;color:{right_color};">{right_label}</span>'
        f"</div>"
    )


def pain_card(severity: str, kind_label: str, asin: str, marketplace: str,
              headline: str, product_title: str | None,
              ruler_html: str, cause: str, action: str, money: str,
              image_url: str | None = None) -> None:
    """Карточка боли: боль → причина → действие → деньги."""
    edge = SEV_EDGE.get(severity, BORDER)

    thumb = (
        f'<div style="flex:0 0 72px;"><img src="{image_url}" '
        f'style="width:72px;height:72px;object-fit:contain;background:#fff;'
        f'border:1px solid {BORDER};border-radius:10px;"></div>'
    ) if image_url else ""

    if product_title:
        short = product_title[:130] + ("…" if len(product_title) > 130 else "")
        title_line = (
            f'<div style="font-size:14px;color:{MUTED};margin-bottom:10px;">'
            f"&#171;{short}&#187;</div>"
        )
    else:
        title_line = ""

    head = eyebrow(
        f'{kind_label} · <a href="https://www.amazon.{marketplace}/dp/{asin}" '
        f'target="_blank">{asin}</a> · {marketplace}'
    )

    st.markdown(
        f"""
        <div style="background:{CARD};border:1px solid {BORDER};
                    border-left:3px solid {edge};border-radius:0 12px 12px 0;
                    padding:18px 22px;margin-bottom:14px;display:flex;gap:16px;">
          {thumb}
          <div style="flex:1;min-width:0;">
            <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px;">
              {head}
              <span class="ls-mono" style="font-size:14px;font-weight:600;color:{edge};">{money}</span>
            </div>
            <div style="font-size:17px;font-weight:700;color:{INK};margin-bottom:3px;">{headline}</div>
            {title_line}
            {ruler_html}
            <div style="font-size:14px;color:{MUTED};margin-bottom:12px;">{t("card.cause")}: {cause}</div>
            <div style="display:inline-block;background:{INK};color:{BG};
                        border-radius:8px;padding:8px 14px;font-size:14px;
                        font-weight:600;">{action}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    ) 
