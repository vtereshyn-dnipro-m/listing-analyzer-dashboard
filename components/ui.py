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
MUTED = "#57534A"   # приглушённый, но хорошо читаемый
BORDER = "#E7E4DD"
CARD = "#FFFFFF"
TRACK = "#F0EFEA"

# безопасная подстановка шрифта в любые инлайн-стили
MONO = "var(--ls-mono)"

SEV_EDGE = {"red": "#A32D2D", "amber": ACCENT, "yellow": AMBER}
SEV_LABEL = {"red": "sev.red", "amber": "sev.amber", "yellow": "sev.yellow"}


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
        "--ls-ink:#1A1815;--ls-muted:#57534A;--ls-accent:#E8590C;"
        "--ls-border:#E7E4DD;}"
        ".ls-mono{font-family:var(--ls-mono);}"
        ".ls-eyebrow{font-family:var(--ls-mono);font-size:13px;"
        "letter-spacing:.06em;color:var(--ls-muted);text-transform:uppercase;}"
        ".ls-eyebrow a{color:var(--ls-muted);text-decoration:none;"
        "border-bottom:1px dotted var(--ls-muted);}"
        '[data-testid="stStatusWidget"]{visibility:hidden;}'
        # stToolbar целиком прятать НЕЛЬЗЯ: внутри него живёт кнопка
        # раскрытия схлопнутого сайдбара (stExpandSidebarButton).
        # Хром прячем поимённо: Share/звезда/GitHub — stToolbarActions,
        # меню — stMainMenu, Deploy и Manage app — свои testid.
        '[data-testid="stToolbarActions"]{display:none !important;}'
        '[data-testid="stAppDeployButton"]{display:none !important;}'
        '[data-testid="stMainMenu"]{display:none !important;}'
        '[data-testid="manage-app-button"]{display:none !important;}'
        ".viewerBadge_container__1QSob{display:none !important;}"
        "header{background:transparent !important;}"
        "footer{visibility:hidden !important;}"
        # Отступ сверху: дефолтные 6rem оставляют пустую полосу в десятую
        # часть экрана. Контент поднимаем, но хедер НЕ схлопываем в 0:
        # у него min-height:60px, а внутри — кнопка раскрытия сайдбара.
        # Вместо этого хедер сквозной для кликов (иначе он, поднявшись над
        # контентом, перехватывает клики по заголовку), кликабельность
        # возвращаем только кнопке.
        '[data-testid="stMainBlockContainer"]{padding-top:2rem !important;}'
        ".block-container{padding-top:2rem !important;}"
        'header[data-testid="stHeader"]{pointer-events:none !important;}'
        # у stToolbar собственный pointer-events:auto — перебивает
        # наследование от хедера, глушим и его
        '[data-testid="stToolbar"]{pointer-events:none !important;}'
        '[data-testid="stExpandSidebarButton"]{pointer-events:auto !important;}'
        "h1{margin-top:0 !important;padding-top:0 !important;}"
        # st.divider даёт hr с полями 2rem с каждой стороны — ужимаем
        '[data-testid="stMainBlockContainer"] hr{margin:1rem 0 !important;}'
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
    mobile = bool(st.session_state.get("mobile_preview"))

    # адаптив: правила для реальных узких экранов
    responsive = (
        "@media (max-width: 640px){"
        ".ls-card{flex-direction:column !important;gap:10px !important;"
        "padding:14px 16px !important;}"
        ".ls-card img{width:100% !important;height:auto !important;"
        "max-height:180px !important;}"
        ".ls-card .ls-head{flex-direction:column !important;"
        "align-items:flex-start !important;gap:2px !important;}"
        ".stMarkdown p,[data-testid=\"stMarkdownContainer\"] p{font-size:16px;}"
        "}"
    )

    # тот же вид принудительно — тумблер «мобильный вид»
    preview = (
        ".main .block-container{max-width:430px !important;padding-left:12px "
        "!important;padding-right:12px !important;}"
        ".ls-card{flex-direction:column !important;gap:10px !important;"
        "padding:14px 16px !important;}"
        ".ls-card img{width:100% !important;height:auto !important;"
        "max-height:180px !important;}"
        ".ls-card .ls-head{flex-direction:column !important;"
        "align-items:flex-start !important;gap:2px !important;}"
    ) if mobile else ""

    st.markdown(css + "<style>" + responsive + preview + "</style>",
                unsafe_allow_html=True)


def mobile_switch() -> None:
    """Тумблер предпросмотра мобильной вёрстки. Ставится в сайдбар."""
    st.toggle(t("sidebar.mobile"), key="mobile_preview",
              help=t("sidebar.mobile_help"))


def eyebrow(text: str) -> str:
    """Мелкая моно-подпись над блоком (стили — в классе, кавычек нет)."""
    return f'<span class="ls-eyebrow">{text}</span>'


def verdict(title: str, subtitle_html: str, meta_right: str = "") -> None:
    """Вердикт-блок: eyebrow + крупный заголовок + подстрока.
    HTML одной строкой — см. пояснение в pain_card."""
    right = (
        f'<span class="ls-mono" style="font-size:13px;color:{MUTED};">'
        f"{meta_right}</span>"
        if meta_right else ""
    )
    html = (
        f'<div style="margin-bottom:16px;">'
        f'<div style="display:flex;justify-content:space-between;'
        f'align-items:center;margin-bottom:6px;">'
        f"{eyebrow(t('dash.eyebrow'))}{right}</div>"
        f'<div style="font-size:28px;font-weight:700;color:{INK};'
        f'line-height:1.25;margin-bottom:6px;">{title}</div>'
        f'<div style="font-size:15px;color:{INK};">{subtitle_html}</div>'
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


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
        f"{chip('#A32D2D', t('sev.red'), red, red > 0)}"
        f"{chip(ACCENT, t('sev.amber'), amber, amber > 0 and red == 0)}"
        f"{chip('#BA7517', t('sev.yellow'), yellow, False)}"
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
              image_url: str | None = None,
              fetched_label: str | None = None) -> None:
    """Карточка боли: боль → причина → действие → деньги.

    HTML собирается в ОДНУ строку без переносов и отступов — иначе пустые
    участки (например отсутствующая линейка) превращаются в блок кода markdown.
    """
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

    fetched_part = f" · {fetched_label}" if fetched_label else ""
    head = eyebrow(
        f'{kind_label} · <a href="https://www.amazon.{marketplace}/dp/{asin}" '
        f'target="_blank">{asin}</a> · {marketplace}{fetched_part}'
    )

    html = (
        f'<div class="ls-card" style="background:{CARD};border:1px solid {BORDER};'
        f'border-left:3px solid {edge};border-radius:0 12px 12px 0;'
        f'padding:18px 22px;margin-bottom:14px;display:flex;gap:16px;">'
        f"{thumb}"
        f'<div style="flex:1;min-width:0;">'
        f'<div class="ls-head" style="display:flex;justify-content:space-between;'
        f'align-items:baseline;margin-bottom:4px;">'
        f"{head}"
        f'<span class="ls-mono" style="font-size:14px;font-weight:600;'
        f'color:{edge};">{money}</span>'
        f"</div>"
        f'<div style="font-size:17px;font-weight:700;color:{INK};'
        f'margin-bottom:3px;">{headline}</div>'
        f"{title_line}"
        f"{ruler_html or ''}"
        f'<div style="font-size:14px;color:{MUTED};margin-bottom:12px;">'
        f'{t("card.cause")}: {cause}</div>'
        f'<div style="display:inline-block;background:{INK};color:{BG};'
        f'border-radius:8px;padding:8px 14px;font-size:14px;'
        f'font-weight:600;">{action}</div>'
        f"</div></div>"
    )
    st.markdown(html, unsafe_allow_html=True)
