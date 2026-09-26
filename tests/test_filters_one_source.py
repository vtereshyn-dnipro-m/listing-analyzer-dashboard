# -*- coding: utf-8 -*-
"""
tests/test_filters_one_source.py — фильтр один, и его слушает весь экран.

26.09 на Каталоге отметили ES — и увидели Италию: галочки рынков резали
сбор и выгрузку, а список слушал отдельную выпадашку. Класс ошибки
общий — «два выбора одного и того же, и разные части экрана слушают
разные», — поэтому страницы пройдены целиком, и на каждой проверяется
одно и то же:

1. один переключатель на одно измерение (рынок, статус, группа);
2. список, счётчики над ним, выгрузка и массовые кнопки берут ОДНУ
   выборку — отметил ES, и нигде нет Италии;
3. счётчик совпадает со списком;
4. строк в файле столько же, сколько в списке;
5. кнопка действия берёт то, что видно, а не скрытое фильтром;
6. ключи session_state одной страницы не задевают другую.

Что было найдено и починено (по страницам):

  Диагноз — шапка «N товаров требуют внимания», «под риском €…»
    и выгрузка «Исправить все → CSV» считались по всей базе и стояли
    над фильтрами, не слушая их; счётчики сегментов («Красные 40»)
    не учитывали рынок и поиск.
  Каталог — счётчики групп («Amazon 490 · Контент 1026») считались
    по всему каталогу при отмеченном рынке.
  Матрица — «Наши · 1019 / Конкуренты · 33» по всей матрице при
    фильтре рынка и поиске; ключи кнопок сбора делили префикс
    `collect-` с Каталогом.
  Синтез — выгрузка и «Отправить в Amazon» слушали рынок, но не поиск
    (проверяется в test_card_actions.py: там фикстура принятых правок).

Фото, Контент, Методология, «Как это работает», Настройки — нарушений
нет: на Фото один набор фильтров и счётчик от него, без выгрузки и
массовых кнопок; на Контенте фильтров списка нет, массовые кнопки
идут по отмеченным.

Запуск (pytest не нужен):  python tests/test_filters_one_source.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import services.db                                     # noqa: E402
services.db.get_conn = lambda: type("C", (), {"close": lambda self: None})()

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


# ================================================================ 6. ключи
# Ключ session_state живёт дольше страницы: фильтр, записанный одной,
# другая прочитает, если имя совпало. Проверяется БЕЗ запуска: литеральные
# ключи и префиксы f-строк каждой страницы не должны совпадать и не должны
# быть префиксом чужого ключа. Общий допуск — только тумблер мобильного
# вида, он общий намеренно.
SHARED_OK = {"mobile_preview"}
KEY_RE = re.compile(
    r'(?:key=|state_key=|session_state\[|session_state\.get\(|'
    r'session_state\.pop\(|session_state\.setdefault\()\s*(f?)"([^"]+)"')


def page_keys(path: pathlib.Path) -> set:
    out = set()
    for is_f, k in KEY_RE.findall(path.read_text(encoding="utf-8")):
        k = k.split("{", 1)[0] if is_f else k
        if k and k not in SHARED_OK:
            out.add(k)
    return out


PAGES = sorted((ROOT / "pages").glob("*.py"))
KEYS = {p.name: page_keys(p) for p in PAGES}
_clash = []
for a in PAGES:
    for b in PAGES:
        if a.name >= b.name:
            continue
        for ka in KEYS[a.name]:
            for kb in KEYS[b.name]:
                if ka == kb or ka.startswith(kb) or kb.startswith(ka):
                    _clash.append(f"{a.name}:{ka} ↔ {b.name}:{kb}")
check(f"ключи состояния страниц не пересекаются ({_clash[:4]})", not _clash)
check("Матрица держит ключи сбора под своим префиксом",
      "matrix-collect-" in KEYS["matrix_setup.py"]
      and not any(k.startswith("collect-") for k in KEYS["matrix_setup.py"]))

# ================================================================ 1. один переключатель рынка
_mp_widgets = {p.name: len(re.findall(r'multiselect\(\s*"MP"', p.read_text(encoding="utf-8")))
               for p in PAGES}
check(f"на странице не больше одного выбора рынка ({_mp_widgets})",
      all(n <= 1 for n in _mp_widgets.values()))
check("на Каталоге рынок выбирается только галочками",
      _mp_widgets["catalog.py"] == 0)

# ================================================================ фикстура
NOW = pd.Timestamp.now("UTC")
RAW = json.dumps({"images": ["a"], "number_of_videos": 1, "aplus": True,
                  "average_rating": "4,5", "price": "10", "sold_by": "Dnipro-M"})

# Боли: ES — две красные и одна жёлтая на двух товарах, IT — три красные
# на трёх. Под ES «Красные» обязаны показать 2, а не 5.
PAINS = pd.DataFrame([
    dict(asin="B0ES00001", marketplace="es", sku_group="1001", rule_id="title_over_limit",
         severity="red", pain="Тайтл 120", cause="c", action="a", money_impact=0.0,
         created_at=NOW, resolved_at=None),
    dict(asin="B0ES00001", marketplace="es", sku_group="1001", rule_id="low_reviews",
         severity="yellow", pain="Мало отзывов", cause="c", action="a", money_impact=0.0,
         created_at=NOW, resolved_at=None),
    dict(asin="B0ES00002", marketplace="es", sku_group="1002", rule_id="no_aplus",
         severity="red", pain="Нет A+", cause="c", action="a", money_impact=0.0,
         created_at=NOW, resolved_at=None),
] + [
    dict(asin=f"B0IT0000{i}", marketplace="it", sku_group=f"200{i}", rule_id="no_video",
         severity="red", pain="Нет видео", cause="c", action="a", money_impact=0.0,
         created_at=NOW, resolved_at=None)
    for i in range(1, 4)
])


def cat_row(asin, mp, comp=False):
    return dict(sku_group=f"sku{asin}", asin=asin, marketplace=mp, is_competitor=comp,
                status="active", collection_tier="daily", weekly_day=3,
                fetched_at=NOW - pd.Timedelta(hours=3), ok=True, title=f"T {asin}",
                in_stock=True, review_count=100, is_amazon_choice=False, raw=RAW,
                main_image=None, last_fetch=NOW - pd.Timedelta(hours=3), last_ok=True,
                added_at=NOW, red=0, amber=0, yellow=0)


# Каталог и Матрица: ES — 3 наших и 1 конкурент, IT — 4 наших и 2 конкурента.
CAT = pd.DataFrame(
    [cat_row(f"B0ES0000{i}", "es") for i in range(1, 4)]
    + [cat_row("B0ESCOMP1", "es", comp=True)]
    + [cat_row(f"B0IT0000{i}", "it") for i in range(1, 5)]
    + [cat_row(f"B0ITCOMP{i}", "it", comp=True) for i in range(1, 3)])


def fake_sql(sql, conn=None, **kw):
    s = " ".join(str(sql).split())
    # список Матрицы: в его SQL есть и COUNT(*), и product_matrix — он
    # обязан сработать раньше счётчиков ниже
    if "AS last_fetch" in s:
        return CAT.copy()
    if "FROM diagnosis" in s:
        df = PAINS.copy()
        if "resolved_at IS NULL" in s:
            df = df[df["resolved_at"].isna()]
        return df
    if "count(*) AS pairs" in s:
        return pd.DataFrame(columns=["marketplace", "pairs"])
    if "count(DISTINCT" in s and "listing_snapshots" in s:
        return pd.DataFrame([{"n": len(CAT)}])
    if "count(*)" in s and "product_matrix" in s:
        return pd.DataFrame([{"n": len(CAT)}])
    if ("FROM product_matrix" in s or "FROM listing_snapshots" in s
            or "listing_latest" in s):
        return CAT.copy()
    return pd.DataFrame()


pd.read_sql = fake_sql
import streamlit as st                                 # noqa: E402
from streamlit.testing.v1 import AppTest               # noqa: E402


def page(path: str):
    st.cache_data.clear()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=240).run()
    at.switch_page(path).run()
    return at


def md(at) -> str:
    return " ".join(str(m.value) for m in at.markdown)


def seg(at, key: str) -> list:
    """Подписи сегмент-контрола по ключу (в AppTest это button_group)."""
    return [str(o.content) for w in at.get("button_group")
            if getattr(w, "key", None) == key for o in w.proto.options]


# ================================================================ Диагноз
at = page("pages/dashboard.py")
check("Диагноз отрисован", not at.exception)
_dl = next((b for b in at.get("download_button") if b.key == "diag-export"), None)
check(f"без фильтра выгрузка — все 6 болей ({_dl.label if _dl else None})",
      _dl is not None and str(_dl.label).endswith("· 6"))
check("без фильтра в шапке все 5 товаров", "5 товаров требуют внимания" in md(at))

next(w for w in at.multiselect if w.key == "diag_mp").set_value(["es"]).run()
_dl = next((b for b in at.get("download_button") if b.key == "diag-export"), None)
_head = md(at)
check("под ES шапка считает только ES: 2 товара, и фильтр назван",
      "2 товаров требуют внимания" in _head and "фильтр: ES" in _head)
check(f"под ES выгрузка — те же 3 боли, что в списке ({_dl.label if _dl else None})",
      _dl is not None and str(_dl.label).endswith("· 3"))
check("в списке нет Италии", "B0IT0000" not in _head)
_seg = seg(at, "sev_seg")
check(f"счётчик красных под ES — 2, а не 5 ({_seg})",
      any(o.startswith("критично") and o.endswith(" 2") for o in _seg))
check(f"и группы считаются под ES ({seg(at, 'grp_seg')})",
      not any(o.startswith("медиа") and o.endswith(" 3") for o in seg(at, "grp_seg")))
check("под фильтром нет итогов по всей базе («здоровых»)",
      "здоровых" not in _head)

# ================================================================ Каталог
at = page("pages/catalog.py")
check("Каталог отрисован", not at.exception)


def grp_labels(a) -> list:
    return seg(a, "cat_group")


_before = grp_labels(at)
next(c for c in at.checkbox if c.key == "collect-mp-es").set_value(True).run()
_after = grp_labels(at)
check(f"без фильтра «Контент» — 5 пар с болями ({_before})",
      any(o.startswith("Контент") and o.endswith(" 5") for o in _before))
check(f"под ES «Контент» — 2 пары, как в списке ({_after})",
      any(o.startswith("Контент") and o.endswith(" 2") for o in _after))
check("и в списке под ES нет Италии", "B0IT" not in md(at))

# ================================================================ Матрица
at = page("pages/matrix_setup.py")
check("Матрица отрисована", not at.exception)


def seg_labels(a) -> list:
    return seg(a, "matrix-seg")


check(f"без фильтра «Наши · 7», «Конкуренты · 3» ({seg_labels(at)})",
      any(o.endswith("· 7") for o in seg_labels(at))
      and any(o.endswith("· 3") for o in seg_labels(at)))
next(w for w in at.multiselect if w.key == "matrix-mp").set_value(["es"]).run()
check(f"под ES «Наши · 3», «Конкуренты · 1» ({seg_labels(at)})",
      any(o.endswith("· 3") for o in seg_labels(at))
      and any(o.endswith("· 1") for o in seg_labels(at)))
_found = next((str(c.value) for c in at.caption if "Найдено" in str(c.value)
               or "найдено" in str(c.value).lower()), "")
check(f"счётчик под списком — те же 3 ({_found[:40]})", _found and " 3 " in f" {_found} ")
check("кнопки сбора в карточках — под префиксом Матрицы",
      any(str(b.key or "").startswith("matrix-collect-") for b in at.button)
      and not any(str(b.key or "").startswith("collect-") for b in at.button))

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
