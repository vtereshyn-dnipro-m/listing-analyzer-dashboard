# -*- coding: utf-8 -*-
"""
services/buybox.py — кто держит Buy Box по снапшоту ScrapingDog.

`sold_by` и `merchant_id` со страницы: продавец, чьё предложение
в Buy Box. Нет ни того, ни другого — на странице нет предложения
вовсе (264 пары на 18.09, из них 242 в наличии по SP-API — это и есть
«Buy Box никому»). Наш merchant id один на все рынки ЕС, имя магазина
по рынкам разное — различаем по id.

ТА ЖЕ функция и те же id лежат в ноутбуке сборщика (ячейка рядом
с конфигом рынков): он пишет `buy_box_owner` в снапшот, а здесь она
нужна для СТАРЫХ снапшотов, где колонки ещё нет. Правишь — правь оба.

Правило Диагноза `buy_box_lost` НЕ заведено намеренно: на IE `sold_by`
есть у 1 пары из 131, на co.uk у 5 из 32 — пока не проверено глазами,
рынок это или ScrapingDog там не парсит блок продавца, правило дало
бы 130 ложных болей.
"""
from __future__ import annotations

import re

OWN_MERCHANT_IDS = {"A4JU8NB3VJG0K"}
AMAZON_MERCHANT_IDS = {"A30DC7701CXIBH"}

OWN, AMAZON, OTHER, NONE = "own", "amazon", "other", "none"


def buy_box_of(data: dict | None) -> tuple[str, str | None]:
    """(owner, seller): own / amazon / other / none. none — предложения нет."""
    d = data if isinstance(data, dict) else {}
    seller = d.get("sold_by")
    mid = d.get("merchant_id")
    if not seller and not mid:
        return NONE, None
    if mid in OWN_MERCHANT_IDS:
        return OWN, seller
    if mid in AMAZON_MERCHANT_IDS or re.match(r"^amazon\b", str(seller or ""), re.I):
        return AMAZON, seller
    return OTHER, seller
