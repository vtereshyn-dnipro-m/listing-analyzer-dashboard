# -*- coding: utf-8 -*-
"""
tests/test_textgen_rules.py — пять правил 21.10.2026 в проверках черновика
генератора (`services/textgen.run_checks`; правки Ярослава по 99601000-B и
правка Алексея по DTW-205BC, по слову владельца общие для генерации).

Каждое правило — нарушение ловится, верный текст проходит:

  1. Капс = ценность. Заголовок буллета — капсом через двоеточие
     («ЗАГОЛОВОК: текст»), BULLET_HEAD. Единицы при числе («4Ah», «20V») в
     заголовке — не нарушение. Что заголовок — ценность, а не название функции,
     по тексту не проверить: это держит методология (её текст сверяется здесь
     по md5 с записанной в базу 26.10.2026) и человек при приёмке.
  2. Переключение первым. У 99601000-B (es) первый буллет — переключение
     aspirar ↔ soplar без разборки, FIRST_BULLET. Ожидание задано по SKU и
     площадке: у другого товара и рынка правило не срабатывает. Живой TG-1
     (23.10, до правила) — нарушение: переключение там вторым.
  3. 245 = скорость воздуха. Цифра в тайтле подписана тем, что она значит:
     «Aire 245km/h», «Bolsa 45L», «Tritura 15:1», UNLABELED_VALUE.
  4. Бренд первым. «DNIPRO-M» в начале тайтла (title_rules, BRAND_NOT_FIRST;
     другой регистр — BRAND_CASE).
  5. 2800 не превращать в 0 - 2800. Одиночное значение паспорта не становится
     диапазоном «0 - N» ни в одном поле, RANGE_FROM_SINGLE: «2800» (DTW-205BC) и
     живые одиночные цифры 99601000-B — 245 km/h и 45 л. Диапазон, который есть
     в паспорте («0-2800», «126-205»), — можно.

Запуск (pytest не нужен):  python tests/test_textgen_rules.py
"""
from __future__ import annotations

import hashlib
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services import passport_facts as pf  # noqa: E402
from services import textgen as tg  # noqa: E402

FAILS: list[str] = []


def check(name: str, cond) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


def codes(texts, **kw) -> list[tuple[str, str]]:
    return [(v["code"], v["field"]) for v in tg.run_checks(texts, "DVB-200BC Dual", **kw)]


def new_codes(texts, **kw) -> set[str]:
    return {c for c, _ in codes(texts, **kw)} & {"BULLET_HEAD", "FIRST_BULLET", "UNLABELED_VALUE", "RANGE_FROM_SINGLE"}


def facts(rows) -> pf.Facts:
    return pf.Facts([pf.Section("Технічні характеристики", [["ID", "Характеристика", "Значення", "Статус", "Джерело"]]
                                + [list(r) + ["PROPOSED/UNVERIFIED", "SRC-99601000-B-0003"] for r in rows])], [])


# Живые факты паспорта 99601000-B v2 (копия DOCX-PASS-99601000-B-001-v2, чтение 27.10.2026).
F_996 = facts([("FACT-99601000-B-010", "Швидкість повітря / TURBO", "126-205 / 245 км/год"),
               ("FACT-99601000-B-013", "Об’єм мішка", "45 л"),
               ("FACT-99601000-B-015", "Коефіцієнт подрібнення", "15:1")])
# DTW-205BC: обороты одиночным значением (dnipro-m.ua, правка Алексея 21.10.2026).
F_DTW = facts([("FACT-DTW-001", "Оберти холостого ходу", "2800 об/хв")])
F_DTW_DOT = facts([("FACT-DTW-001", "Оберти холостого ходу", "2.800 об/хв")])
F_DTW_RANGE = facts([("FACT-DTW-001", "Оберти холостого ходу", "0-2800 об/хв")])

# Живой TG-1 от 23.10.2026 (content_versions, чтение 27.10.2026): тайтл и первые два буллета.
TG1_TITLE = "DNIPRO-M Aspirador Soplador de Hojas, Tritura 15:1, Aire 245km/h, Bolsa 45L"
TG1_B1 = ("LIMPIA HOJAS Y RESTOS DEL JARDÍN CON UN SOLO APARATO SIN CABLE: aspirador soplador inalámbrico para "
          "quitar las hojas secas y los pequeños restos vegetales del jardín, los caminos, las terrazas y el césped.")
TG1_B2 = ("CAMBIA DE ASPIRAR A SOPLAR SIN DESMONTAR: un mismo aparato aspira, sopla y tritura las hojas. Incluye "
          "un tubo de aspiración y un tubo de soplado, cada uno de dos partes.")
OK = {"title": TG1_TITLE,
      "highlight": "Model DVB-200BC Dual: inalámbrico, motor brushless, TURBO, ruedas y correa de hombro",
      "bullet_1": TG1_B2, "bullet_2": TG1_B1,
      "bullet_3": "VACÍA LA BOLSA CON MENOS FRECUENCIA: las hojas se trituran 15:1 y van a una bolsa de 45L.",
      "bullet_4": "MÁS POTENCIA CUANDO LA NECESITAS: el aire va a 126 - 205km/h y llega a 245km/h en TURBO.",
      "bullet_5": "BATERÍA 4Ah NO INCLUIDA: compatible con baterías 20V de la plataforma.",
      "description": "Aspirador soplador de jardín. Aire 126 - 205km/h, 245km/h en TURBO; bolsa de 45L."}
SKU = {"sku": "99601000-B", "marketplace": "es", "facts": F_996}

check("эталон (TG-1, переключение первым) — ни одного нарушения", codes(OK, **SKU) == [])

# ------------------------------------------------------------- 1. капс = ценность
print("1. капс = ценность")
for bad, why in (("Motor brushless: potencia", "заголовок не капсом"),
                 ("MOTOR BRUSHLESS con potencia", "нет двоеточия"),
                 ("Cambia de aspirar a soplar: texto", "строчные"),
                 (": texto sin cabecera", "пустой заголовок"),
                 ("AB: texto", "заголовок из двух букв"),
                 ("CAMBIA DE ASPIRAR A SOPLAR:", "после двоеточия пусто")):
    got = codes({**OK, "bullet_3": bad}, **SKU)
    check(f"{why} — BULLET_HEAD у буллета 3", ("BULLET_HEAD", "bullet_3") in got)
check("единицы при числе в заголовке капсом («4Ah», «20V») — не нарушение",
      ("BULLET_HEAD", "bullet_5") not in codes(OK, **SKU))
check("все пять буллетов TG-1 — заголовки капсом", all(
    ("BULLET_HEAD", f"bullet_{i}") not in codes({**OK, "bullet_1": TG1_B1, "bullet_2": TG1_B2}, **SKU)
    for i in range(1, 6)))

DOC = (ROOT / "docs" / "textgen.md").read_text(encoding="utf-8")
m = re.search(r"### Методология `textgen` v1[^\n]*\n\n```\n(.*?)\n```", DOC, re.S)
METHOD = m.group(1).strip() if m else ""
check("методология textgen v1 в docs — та, что в базе (md5 7d5c6ccd…, проверено 26.10.2026)",
      hashlib.md5(METHOD.encode("utf-8")).hexdigest() == "7d5c6ccdf8331aeab60114c1fc3c6b7a")
for frag, what in (("Заголовок буллета капсом — ценность для покупателя: что он получает, а не название функции",
                    "капс = ценность, а не функция"),
                   ("«CAMBIA DE ASPIRAR A SOPLAR SIN DESMONTAR», а не «MOTOR BRUSHLESS»", "пример ценности"),
                   ("Главная ценность товара — первым буллетом", "главная ценность первой"),
                   ("Бренд «DNIPRO-M» первым", "бренд первым"),
                   ("«Aire 245km/h»", "цифра подписана")):
    check(f"в методологии: {what}", frag in METHOD)

# ------------------------------------------------------------- 2. переключение первым
print("2. переключение первым")
tg1 = {**OK, "bullet_1": TG1_B1, "bullet_2": TG1_B2}
check("TG-1 как есть (переключение вторым) — FIRST_BULLET у первого буллета",
      ("FIRST_BULLET", "bullet_1") in codes(tg1, **SKU))
check("переключение первым — нарушения нет", ("FIRST_BULLET", "bullet_1") not in codes(OK, **SKU))
for b1, why in (("CAMBIA DE ASPIRAR A SOPLAR: texto", "без «sin desmontar»"),
                ("ASPIRA SIN DESMONTAR: texto", "без «soplar»"),
                ("SOPLA SIN DESMONTAR: texto", "без «aspirar»")):
    check(f"{why} — FIRST_BULLET", ("FIRST_BULLET", "bullet_1") in codes({**OK, "bullet_1": b1}, **SKU))
check("«sin herramientas» — тоже без разборки",
      ("FIRST_BULLET", "bullet_1") not in codes({**OK, "bullet_1": "PASA DE ASPIRAR A SOPLAR SIN HERRAMIENTAS: x"}, **SKU))
check("другой SKU — ожидания нет, правило не срабатывает",
      "FIRST_BULLET" not in new_codes(tg1, sku="99601000", marketplace="es", facts=F_996))
check("тот же SKU на другом рынке — ожидания нет",
      "FIRST_BULLET" not in new_codes(tg1, sku="99601000-B", marketplace="de", facts=F_996))
check("без SKU (старый вызов) — правило не срабатывает", "FIRST_BULLET" not in new_codes(tg1))

# ------------------------------------------------------------- 3. 245 = скорость воздуха
print("3. цифра подписана")
for title, bad in (("DNIPRO-M Aspirador Soplador de Hojas, 245km/h, Bolsa 45L", "245km/h"),
                   ("DNIPRO-M Aspirador Soplador de Hojas 245km/h, Aire potente", "245km/h"),
                   ("DNIPRO-M Aspirador Soplador, Aire 245km/h, 45L", "45L"),
                   ("DNIPRO-M Aspirador Soplador, Aire 245km/h, 15:1", "15:1"),
                   ("DNIPRO-M Soplador, Caudal 3,5 m³/min, 10,5m3/min", "10,5m3/min")):
    got = [v for v in tg.run_checks({**OK, "title": title}, "M", **SKU) if v["code"] == "UNLABELED_VALUE"]
    check(f"«{bad}» без подписи в своей части — UNLABELED_VALUE", [v["detail"] for v in got] == [bad])
for title in ("DNIPRO-M Aspirador Soplador de Hojas, Aire 245km/h, Bolsa 45L, Tritura 15:1",
              "DNIPRO-M Soplador, Velocidad 245km/h, Triturador 15:1",
              "DNIPRO-M Soplador, Caudal 3,5 m³/min"):
    check(f"подписано — нарушения нет: «{title}»", "UNLABELED_VALUE" not in new_codes({**OK, "title": title}, **SKU))
check("самоговорящие единицы (W, Nm, Ø…mm, rpm, Ah) подписи не требуют",
      "UNLABELED_VALUE" not in new_codes({**OK, "title": "DNIPRO-M Amoladora, 2000W, Ø230mm, 6600rpm, 4Ah"}, **SKU))
check("в буллетах подпись не требуется (правило — для тайтла)",
      "UNLABELED_VALUE" not in new_codes({**OK, "bullet_4": "MÁS POTENCIA: 245km/h y 45L."}, **SKU))

# ------------------------------------------------------------- 4. бренд первым
print("4. бренд первым")
check("TG-1 — бренд первым, нарушения нет", not {"BRAND_NOT_FIRST", "BRAND_CASE"} & {c for c, _ in codes(OK, **SKU)})
check("бренд не первым — BRAND_NOT_FIRST",
      ("BRAND_NOT_FIRST", "title") in codes({**OK, "title": "Aspirador Soplador DNIPRO-M, Aire 245km/h"}, **SKU))
check("бренд первым, но не тем регистром — BRAND_CASE",
      ("BRAND_CASE", "title") in codes({**OK, "title": "Dnipro-M Aspirador Soplador, Aire 245km/h"}, **SKU))
check("бренда нет — BRAND_NOT_FIRST",
      ("BRAND_NOT_FIRST", "title") in codes({**OK, "title": "Aspirador Soplador de Hojas, Aire 245km/h"}, **SKU))

# ------------------------------------------------------------- 5. не превращать N в 0 - N
print("5. одиночное значение — не диапазон «0 - N»")
DTW = {**OK, "title": "DNIPRO-M Llave de Impacto, 0 - 2800rpm, 300Nm"}
got = [v for v in tg.run_checks(DTW, "M", facts=F_DTW) if v["code"] == "RANGE_FROM_SINGLE"]
check("DTW-205BC: «2800» в паспорте, «0 - 2800rpm» в тайтле — RANGE_FROM_SINGLE",
      [(v["field"], v["detail"]) for v in got] == [("title", "0 - 2800 → 2800")])
check("«2800rpm» как есть — нарушения нет",
      "RANGE_FROM_SINGLE" not in new_codes({**OK, "title": "DNIPRO-M Llave de Impacto, 2800rpm, 300Nm"}, facts=F_DTW))
for form in ("0-2800rpm", "0–2800rpm", "0 – 2800rpm", "0 — 2800 rpm"):
    check(f"форма «{form}» — тоже нарушение",
          "RANGE_FROM_SINGLE" in new_codes({**OK, "title": f"DNIPRO-M Llave, {form}"}, facts=F_DTW))
check("в паспорте «2.800» (тысячи через точку) — «0 - 2800rpm» всё равно нарушение",
      "RANGE_FROM_SINGLE" in new_codes(DTW, facts=F_DTW_DOT))
check("в паспорте сам диапазон «0-2800» — «0 - 2800rpm» можно",
      "RANGE_FROM_SINGLE" not in new_codes(DTW, facts=F_DTW_RANGE))
check("в описании тоже: «0 - 2800» — нарушение",
      ("RANGE_FROM_SINGLE", "description") in codes({**OK, "description": "Gira a 0 - 2800 rpm."}, facts=F_DTW))
for fld, txt, what in (("title", "DNIPRO-M Aspirador Soplador, Aire 0 - 245km/h, Bolsa 45L", "245 km/h"),
                       ("title", "DNIPRO-M Aspirador Soplador, Aire 245km/h, Bolsa 0 - 45L", "45 л"),
                       ("bullet_4", "MÁS POTENCIA: el aire va de 0 - 245km/h.", "245 km/h в буллете")):
    check(f"99601000-B: {what} одиночным в паспорте — «0 - N» нарушение",
          ("RANGE_FROM_SINGLE", fld) in codes({**OK, fld: txt}, **SKU))
check("99601000-B: диапазон паспорта «126 - 205km/h» — можно (он есть в паспорте не от нуля)",
      "RANGE_FROM_SINGLE" not in new_codes(OK, **SKU))
check("номера и источники паспорта («FACT-99601000-B-010», «SRC-…-0003») значениями не считаются",
      tg.passport_values(F_996)[0] == {"126", "205", "245", "45", "15", "1"})
check("без фактов (старый вызов) — правило не срабатывает",
      "RANGE_FROM_SINGLE" not in new_codes({**OK, "title": "DNIPRO-M, Aire 0 - 245km/h"}))

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
