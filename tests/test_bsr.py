# -*- coding: utf-8 -*-
"""
tests/test_bsr.py — Best Sellers Rank разбирается на всех девяти языках.

Ранг приходит строкой на языке страницы под ключом на том же языке.
Покрытие по рынкам было разным по двум причинам, и обе — молчаливые:
ключ выбирался по первому вхождению «best|rank|posizione» (у ES перед
BSR стоит «Rango de medición», у IT — «Composizione della batteria»),
а польское «w kategorii» в список предлогов не входило — весь PL шёл
мимо, и никто этого не видел.

Образцы — ЖИВЫЕ строки из raw снапшотов (18.09), не выдуманные: ключи
ScrapingDog отдаёт без диакритики («Clasificacin», «dAmazon»), и тест
это повторяет. Правило: новый рынок без образца здесь — не проверен.

Запуск (pytest не нужен):  python tests/test_bsr.py
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.bsr import parse_bsr, parse_bsr_text, find_bsr_text   # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


# (рынок, ключ как отдаёт ScrapingDog, строка, ожидаемый узкий ранг, категория)
LIVE = [
    ("co.uk", "Best Sellers Rank",
     "1,104,828 in DIY & Tools (See Top 100 in DIY & Tools) 177 in Power Tool Combo Kits",
     177, "Power Tool Combo Kits"),
    ("ie", "Best Sellers Rank",
     "#178,252 in DIY & Tools (See Top 100 in DIY & Tools) #51 in Rotary Hammers",
     51, "Rotary Hammers"),
    ("de", "Amazon BestsellerRang",
     "Nr. 1.010.110 in Baumarkt (Siehe Top 100 in Baumarkt) Nr. 4.326 in Schleifer",
     4326, "Schleifer"),
    ("es", "Clasificacin en los ms vendidos de Amazon",
     "nº1.830 en Jardín (Ver el Top 100 en Jardín)    nº24 en Pulverizadores de jardinería",
     24, "Pulverizadores de jardinería"),
    ("fr", "Classement des meilleures ventes dAmazon",
     "1 264 457 en Cuisine et Maison (Voir les 100 premiers en Cuisine et Maison) 1 429 en Aspirateurs à main",
     1429, "Aspirateurs à main"),
    ("it", "Posizione nella classifica Bestseller di Amazon",
     "n. 1.858 in Fai da te (Visualizza i Top 100 nella categoria Fai da te) n. 974 in Trapani avvitatori elettrici",
     974, "Trapani avvitatori elettrici"),
    ("nl", "Plaats in bestsellerlijst",
     "#237.463 in Klussen & gereedschap (Top 100 in Klussen & gereedschap bekijken) #566 in Schroefboormachines",
     566, "Schroefboormachines"),
    ("be", "Plaats in bestsellerlijst",
     "#14.177 in Klussen en gereedschap (Top 100 in Klussen en gereedschap bekijken) #96 in Schroevendraaiersets",
     96, "Schroevendraaiersets"),
    ("pl", "Ranking najlepiej sprzedajcych si produktw",
     "Pozycja 105 136 w kategorii Narzędzia i renowacja domu (Zobacz Top 100 w kategorii Narzędzia i renowacja domu) Pozycja 216 w kategorii Wiertarki udarowe",
     216, "Wiertarki udarowe"),
]

# --- 1. девять языков, живые строки
for mp, key, text, rank, cat in LIVE:
    got = parse_bsr({key: text})
    check(f"{mp}: {got}", got == (rank, cat))

check("девять рынков в образцах — ни один не забыт",
      {m for m, *_ in LIVE} == {"co.uk", "ie", "de", "es", "fr", "it", "nl", "be", "pl"})

# --- 2. ловушки ключа: соседи с похожими словами не перехватывают BSR
es_info = {"Rango de medicin": "40 Metros",
           "Rango superior de temperaturas": "450 Grados Celsius",
           "Clasificacin en los ms vendidos de Amazon": LIVE[3][2]}
check("ES: «Rango de medición» перед BSR не перехватывает ключ",
      parse_bsr(es_info) == (24, "Pulverizadores de jardinería"))
it_info = {"Composizione della batteria": "Ioni di litio",
           "Posizione nella classifica Bestseller di Amazon": LIVE[5][2]}
check("IT: «Composizione…» (содержит «posizione») не перехватывает",
      parse_bsr(it_info) == (974, "Trapani avvitatori elettrici"))
de_info = {"Wasserbestndigkeit": "IPX4", "Amazon BestsellerRang": LIVE[2][2]}
check("DE: «Wasserbeständigkeit» (содержит «best») не перехватывает",
      parse_bsr(de_info) == (4326, "Schleifer"))
check("без ключа — (None, None), а не падение",
      parse_bsr({"Marke": "Dnipro-M"}) == (None, None) and find_bsr_text(None) is None)

# --- 3. форма строки
check("один ранг без подкатегории — он и берётся",
      parse_bsr_text("Nr. 94.213 in Baumarkt") == (94213, "Baumarkt"))
check("три уровня — берётся самый узкий, последний",
      parse_bsr_text("1,000 in A (See Top 100 in A) 200 in B 30 in C") == (30, "C"))
check("тысячные с NBSP (fr) читаются как число",
      parse_bsr_text("1 264 457 en Cuisine et Maison 1 429 en Aspirateurs à main")
      == (1429, "Aspirateurs à main"))
check("мусор в значении — (None, None), не число из воздуха",
      parse_bsr_text("Nicht verfügbar") == (None, None))
check("пусто — (None, None)", parse_bsr_text("") == (None, None) and parse_bsr_text(None) == (None, None))

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
