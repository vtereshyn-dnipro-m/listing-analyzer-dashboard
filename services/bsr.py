# -*- coding: utf-8 -*-
"""
services/bsr.py — Best Sellers Rank из product_information ScrapingDog.

Ранг приходит не полем, а СТРОКОЙ на языке страницы, под ключом на том
же языке. Девять рынков — девять форматов, живые образцы 18.09:

    co.uk  Best Sellers Rank
           1,104,828 in DIY & Tools (See Top 100 in DIY & Tools) 177 in Power Tool Combo Kits
    ie     #178,252 in DIY & Tools (See Top 100 …) #51 in Rotary Hammers
    de     Amazon Bestseller-Rang
           Nr. 1.010.110 in Baumarkt (Siehe Top 100 in Baumarkt) Nr. 4.326 in Schleifer
    es     Clasificación en los más vendidos de Amazon
           nº1.830 en Jardín (Ver el Top 100 en Jardín)    nº24 en Pulverizadores de jardinería
    fr     Classement des meilleures ventes d'Amazon
           1 264 457 en Cuisine et Maison (Voir les 100 premiers …) 1 429 en Aspirateurs à main
    it     Posizione nella classifica Bestseller di Amazon
           n. 1.858 in Fai da te (Visualizza i Top 100 …) n. 974 in Trapani avvitatori elettrici
    nl/be  Plaats in bestsellerlijst
           #237.463 in Klussen & gereedschap (Top 100 … bekijken) #566 in Schroefboormachines
    pl     Ranking najlepiej sprzedających się produktów
           Pozycja 105 136 w kategorii Narzędzia i renowacja domu (Zobacz Top 100 …) Pozycja 216 w kategorii Wiertarki udarowe

ДВЕ ЛОВУШКИ, из-за которых покрытие по рынкам было разным.

Ключ выбирался регуляркой «best|rank|posizione|…» по ПЕРВОМУ
совпадению. У ES перед BSR в product_information стоит «Rango de
medición», у IT — «Composizione della batteria» (содержит
«posizione»), у DE — «Wasserbeständigkeit» (содержит «best»). Ранг
у таких товаров терялся молча. Здесь ключ узнаётся по своему началу
и с якорем `^`, а не по вхождению.

Число разбиралось по предлогам «in/en/dans/nella/di» — польское
«w kategorii» в список не входило, и весь PL шёл мимо. Здесь предлоги
перечислены по факту, и тест ест все девять языков: новый рынок без
образца в тесте — это не «пока работает», а «не проверено».

ScrapingDog отдаёт ключи без диакритики («Clasificacin», «dAmazon») —
поэтому сравнение идёт по нормализованному ключу: строчные, только
латинские буквы, и с допуском на выпавшие гласные.

Берётся САМЫЙ УЗКИЙ ранг — последняя пара в строке (правило 2 в
CLAUDE.md, «Данные Amazon»): широкий у десятка товаров почти одинаков
и ничего не различает. Функция чистая — та же копия работает
в ноутбуке сборщика; правишь здесь — обнови ячейку там.
"""
from __future__ import annotations

import re

# Начало нормализованного ключа (строчные, только a-z) — по языку.
# Якорь ^ обязателен: «composizione…» не должен ловиться на «posizione».
KEY_PATTERNS = (
    r"^bestsellersrank",                 # en (co.uk, ie)
    r"^amazonbestsellerrang",            # de
    r"^clasificaci.{0,2}nenlosm",        # es — «Clasificación en los más…», гласные могут выпасть
    r"^classementdesmeilleuresventes",   # fr
    r"^posizionenellaclassifica",        # it
    r"^plaatsinbestsellerlijst",         # nl, be
    r"^rankingnajlepiej",                # pl
)
_KEY_RE = re.compile("|".join(KEY_PATTERNS))

# Число с тысячными разделителями любого рынка: «1,104,828», «1.010.110»,
# «1 264 457» (пробел или NBSP), «105 136».
_NUM = r"\d{1,3}(?:[.,  ]\d{3})+|\d+"
# Префикс перед числом: «#», «Nr.», «nº», «n.», «Pozycja».
_PREFIX = r"(?:#\s*|nr\.?\s*|n[ºo°]\s*|n\.\s*|pozycja\s+)?"
# Предлог между числом и категорией — по языкам, по факту.
_SEP = r"\s+(?:in|en|w kategorii)\s+"
_ENTRY = re.compile(
    rf"{_PREFIX}({_NUM}){_SEP}(.+?)"
    rf"(?=\s*(?:{_PREFIX}(?:{_NUM}){_SEP})|\s*$)",
    re.I,
)


def normalize_key(key: str) -> str:
    return re.sub(r"[^a-z]", "", str(key or "").lower())


def find_bsr_text(info: dict | None) -> str | None:
    """Строка ранга из product_information — или None, если ключа нет."""
    if not isinstance(info, dict):
        return None
    for k, v in info.items():
        if _KEY_RE.search(normalize_key(k)):
            return str(v) if v is not None else None
    return None


def parse_bsr_text(text: str | None) -> tuple[int | None, str | None]:
    """«Nr. 94.213 in Baumarkt (…) Nr. 325 in Akku- & Bohrschrauber» → (325, 'Akku- & Bohrschrauber')."""
    if not text:
        return None, None
    clean = re.sub(r"\([^)]*\)", " ", str(text))       # «(See Top 100 …)» — мусор
    clean = re.sub(r"\s+", " ", clean).strip()
    pairs = _ENTRY.findall(clean)
    if not pairs:
        return None, None
    num, cat = pairs[-1]                                # самый узкий — последний
    rank = int(re.sub(r"[^\d]", "", num))
    return (rank if rank > 0 else None), cat.strip(" .;,") or None


def parse_bsr(info: dict | None) -> tuple[int | None, str | None]:
    """product_information → (ранг в подкатегории, подкатегория)."""
    return parse_bsr_text(find_bsr_text(info))
