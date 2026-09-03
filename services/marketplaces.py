# -*- coding: utf-8 -*-
"""
services/marketplaces.py — рынок Amazon: домен, ссылка на товар, заглушка
для фото.

Ссылка на карточку раньше собиралась в девяти местах одинаковой строкой
`https://www.amazon.{marketplace}/dp/{asin}`. Работало это по совпадению:
код рынка в этом проекте и есть доменный суффикс. Совпадение неполное —
у Бельгии код `be`, а домена amazon.be не существует, витрина живёт на
amazon.com.be. Ссылка вела в никуда, и заметить это можно было только
кликнув.

Поэтому домен теперь спрашивают здесь, а не пишут руками. Пятая карта
маркетплейсов в проекте (после подписей в i18n, MP_COUNTRY, MP_LANGUAGE
и MARKETPLACE_REGION), и её согласованность с остальными проверяет
tests/test_marketplace_maps.py.
"""
from __future__ import annotations

# Код рынка → доменный суффикс Amazon. Перечислены только те, где они
# РАСХОДЯТСЯ или где легко ошибиться; для остальных код и есть суффикс.
DOMAIN_ALIAS = {
    "be": "com.be",     # amazon.be не существует
    "uk": "co.uk",      # встречается в чужих выгрузках
    "gb": "co.uk",      # ISO-код страны вместо кода рынка
    "us": "com",
}

# Прозрачный серый квадрат с рамкой: место под фото занято всегда.
# Пустая ячейка не отличала «фото нет» от «столбец не про это», и в
# таблице из тридцати строк ряд разъезжался по высоте.
PLACEHOLDER_IMG = (
    "data:image/svg+xml;charset=utf-8,"
    "%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20width='64'%20height='64'"
    "%3E%3Crect%20width='64'%20height='64'%20rx='8'%20fill='%23F1EFE9'"
    "%20stroke='%23E7E4DD'/%3E%3Cpath%20d='M16%2044l10-12%208%209%206-7%208%2010z'"
    "%20fill='%23C9C4B8'/%3E%3Ccircle%20cx='24'%20cy='23'%20r='4'"
    "%20fill='%23C9C4B8'/%3E%3C/svg%3E"
)


# Подпись для st.column_config.LinkColumn: в ячейке лежит ссылка,
# а показывать надо ASIN. Streamlit берёт первую группу захвата.
ASIN_IN_URL = r"^https?://www\.amazon\.[a-z.]+/dp/([A-Za-z0-9]+)"


def domain(marketplace: str | None) -> str:
    """Доменный суффикс рынка: «be» → «com.be», «es» → «es»."""
    code = str(marketplace or "").strip().lower().lstrip(".")
    if not code:
        return "com"
    return DOMAIN_ALIAS.get(code, code)


def product_url(asin: str | None, marketplace: str | None) -> str:
    """Ссылка на карточку товара. Пустой ASIN — пустая строка, чтобы
    таблица не рисовала ссылку в никуда."""
    a = str(asin or "").strip()
    if not a:
        return ""
    return f"https://www.amazon.{domain(marketplace)}/dp/{a}"


def asin_link(asin: str | None, marketplace: str | None,
              color: str = "#57534A") -> str:
    """ASIN ссылкой для HTML-разметки карточек. Одной строкой — правило 1."""
    a = str(asin or "").strip()
    url = product_url(a, marketplace)
    if not url:
        return a
    return (f'<a href="{url}" target="_blank" style="color:{color};'
            f'text-decoration:none;border-bottom:1px dotted #C9C4B8;">{a}</a>')


def img_or_stub(url: str | None) -> str:
    """URL фото или заглушка. Заглушка, а не None: в st.column_config
    .ImageColumn пустое значение даёт пустую ячейку, и строка без фото
    выглядит сломанной, а не «фото нет»."""
    try:
        import pandas as pd
        empty = url is None or pd.isna(url)
    except Exception:
        empty = url is None
    s = "" if empty else str(url).strip()
    return s if s.startswith(("http://", "https://", "data:")) else PLACEHOLDER_IMG
