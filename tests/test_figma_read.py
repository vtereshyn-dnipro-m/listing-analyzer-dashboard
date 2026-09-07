# -*- coding: utf-8 -*-
"""
tests/test_figma_read.py — чтение макетов из Figma: разбор и лимит.

Три вещи ломаются тихо, и все три проверяются здесь.

ОБХОД. Текстовые слои лежат на разной глубине: между секцией и текстом
бывает три-четыре вложенных фрейма. Обход по верхнему уровню нашёл бы
часть текстов и показал неполный список как полный.

СВЯЗЬ. Имена фреймов вида «carousel 2.2» повторяются у разных товаров,
поэтому товар определяется ТОЛЬКО именем секции. Свяжи мы по имени
фрейма — тексты одного товара уехали бы к другому.

ЛИМИТ. Предел символов считается по ширине слоя и кеглю, и точным он
быть не может. Здесь заперты его края: без геометрии предел неизвестен
(а не выдуман), многострочный слой вмещает больше, и есть самопроверка
коэффициента — английский текст УЖЕ стоит в макете, и если расчёт
говорит, что он не влезает, занижен коэффициент, а не макет неверен.

Плюс лимит запросов: при 429 ретраев нет, наверх идёт время ожидания.
Повтор внутри кода только съел бы лимит и растянул паузу. И само это
время нормализуется: Retry-After у Figma приходит то в секундах, то
в миллисекундах, а «ждать 85 часов» вместо пяти минут человек читает
как «сегодня уже никак».

Сеть здесь не трогается: HTTP подменён.

Запуск (pytest не нужен):  python tests/test_figma_read.py
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


import services.figma as fg                             # noqa: E402


def text_node(nid, name, chars, w, h, size, line_h=None):
    node = {"id": nid, "type": "TEXT", "name": name, "characters": chars,
            "absoluteBoundingBox": {"width": w, "height": h},
            "style": {"fontSize": size}}
    if line_h:
        node["style"]["lineHeightPx"] = line_h
    return node


# Структура повторяет живой файл: секция → фрейм → фрейм → фрейм → текст,
# рядом картинка (её трогать нельзя), чужие страницы и секция чужого
# формата.
DOC = {"document": {"children": [
    {"name": "UK/US", "children": [
        {"id": "1:1",
         "name": "Main Images_B0G4S9SJ3M 54225000 Battery stapler Dnipro-M CC-36",
         "children": [
             {"id": "1:2", "type": "FRAME", "name": "B0G4S9SJ3M.PT01", "children": [
                 {"id": "1:3", "type": "FRAME", "name": "Frame 35841", "children": [
                     {"id": "1:4", "type": "FRAME", "name": "Frame 1614", "children": [
                         text_node("1:5", "title", "USB-C Charging", 220, 24, 20),
                         {"id": "1:6", "type": "RECTANGLE",
                          "name": "ChatGPT Image 6 авг. 2026.png",
                          "absoluteBoundingBox": {"width": 4822, "height": 3709,
                                                  "x": -964, "y": -893}},
                     ]}]}]},
             {"id": "1:7", "type": "FRAME", "name": "B0G4S9SJ3M.MAIN", "children": [
                 text_node("1:8", "body",
                           "Charges from power banks and car adapters",
                           300, 66, 18, 22),
             ]}]},
        {"id": "1:9",
         "name": "A+ Premium Content_B0GTRY26HB 99601000 Leaf blower SBA-36",
         "children": [text_node("1:10", "carousel 2.2", "Two-year warranty",
                                220, 20, 16)]},
        {"id": "1:11", "name": "Random frame without pattern", "children": []},
    ]},
    {"name": "ES", "children": [
        {"id": "2:1",
         "name": "Main Images_B0G4S9SJ3M 54225000 Battery stapler Dnipro-M CC-36",
         "children": [text_node("2:2", "title", "Carga USB-C", 220, 24, 20)]}]},
    {"name": "Gazi", "children": [{"id": "9:1", "name": "чужое", "children": []}]},
    {"name": "UK/US (OLD)", "children": []},
]}}

R = fg.parse_document(DOC)

# --- обход и связь
check("товары собраны с двух страниц-языков", len(R["products"]) == 3)
check("текст найден на глубине четырёх фреймов",
      any(l["layer_id"] == "1:5" for p in R["products"] for l in p["layers"]))
check("картинка в слои не попала",
      not any(l["layer_id"] == "1:6" for p in R["products"] for l in p["layers"]))

_en = [p for p in R["products"] if p["lang"] == "en"]
_by_asin = {p["asin"]: p for p in _en}
check("ASIN, SKU и название разобраны из имени секции",
      _by_asin["B0G4S9SJ3M"]["sku"] == "54225000"
      and _by_asin["B0G4S9SJ3M"]["name"] == "Battery stapler Dnipro-M CC-36")
check("тип секции различается",
      _by_asin["B0GTRY26HB"]["section_type"] == "A+ Premium Content")
# «carousel 2.2» встречается у многих товаров — товар определяет секция
check("фрейм с повторяющимся именем привязан к своему товару",
      any(l["frame_name"] == "carousel 2.2"
          for l in _by_asin["B0GTRY26HB"]["layers"]))

_es = [p for p in R["products"] if p["lang"] == "es"]
check("испанская страница даёт тот же товар отдельной записью",
      len(_es) == 1 and _es[0]["asin"] == "B0G4S9SJ3M")

# --- что не разобралось: в отчёт, а не в тишину
check("секция чужого формата попала в отчёт",
      any("Random frame" in s for s in R["skipped_sections"]))
check("чужие страницы названы поимённо",
      set(R["skipped_pages"]) == {"Gazi", "UK/US (OLD)"})

# --- предел символов
check("без геометрии предел неизвестен, а не выдуман",
      fg.char_limit({"type": "TEXT"}) is None)
check("без кегля предел тоже неизвестен",
      fg.char_limit({"absoluteBoundingBox": {"width": 200, "height": 20}}) is None)
_one = fg.char_limit({"absoluteBoundingBox": {"width": 220, "height": 24},
                      "style": {"fontSize": 20}})
_three = fg.char_limit({"absoluteBoundingBox": {"width": 220, "height": 66},
                        "style": {"fontSize": 20, "lineHeightPx": 22}})
check(f"однострочный слой: {_one} знаков", _one == 21)
check(f"многострочный вмещает кратно больше ({_three} против {_one})",
      _three == _one * 3)

# --- самопроверка коэффициента
check("исходные английские строки посчитаны", R["source_checked"] == 3)
check("на нормальной ширине английский влезает в свой предел",
      R["source_over"] == 0)

_narrow = {"document": {"children": [{"name": "UK/US", "children": [
    {"id": "3:1", "name": "Main Images_B0G4S9SJ3M 54225000 Stapler",
     "children": [text_node("3:2", "t", "USB-C Charging", 40, 20, 20)]}]}]}}
_r2 = fg.parse_document(_narrow)
check("а при заниженном коэффициенте это видно по исходнику",
      _r2["source_checked"] == 1 and _r2["source_over"] == 1)

# --- лимит запросов Figma
class _Resp:
    def __init__(self, code, headers=None, body=""):
        self.status_code, self.headers, self.text = code, headers or {}, body

    def json(self):
        return {"document": {"children": []}}


_calls = {"n": 0}


def _fake_get(url, headers=None, timeout=None):
    _calls["n"] += 1
    return _Resp(429, {"Retry-After": "399"})


fg.requests.get = _fake_get
fg.cfg = lambda name, default=None: {"FIGMA_TOKEN": "figd_x",
                                     "FIGMA_FILE_KEY": "ZZJ9"}.get(name, default)
try:
    fg.fetch_document()
    check("429 поднимается как ошибка", False)
except fg.FigmaError as e:
    check("429 поднимается как ошибка", True)
    check("время ожидания названо числом", e.retry_after == 399)
check("ретраев нет: запрос ровно один", _calls["n"] == 1)

# Единицы Retry-After у Figma непостоянны: тот же заголовок приходит
# то в секундах, то в миллисекундах. 306325 — это пять минут, а не
# 85 часов, и разница здесь не арифметическая: «ждать 85 часов»
# человек читает как «сегодня уже никак» и уходит.
check("миллисекунды приводятся к секундам", fg.retry_seconds("306325") == 306)
check("секунды остаются секундами", fg.retry_seconds("399") == 399)
check("сутки — ещё секунды, а не миллисекунды",
      fg.retry_seconds(86400) == 86400)
check("нечисловое значение не превращается в число",
      fg.retry_seconds("Wed, 21 Oct 2026 07:28:00 GMT") is None
      and fg.retry_seconds(None) is None)


def _fake_ms(url, headers=None, timeout=None):
    return _Resp(429, {"Retry-After": "306325"})


fg.requests.get = _fake_ms
try:
    fg.fetch_document()
    check("наверх уходит уже пересчитанное ожидание", False)
except fg.FigmaError as e:
    check("наверх уходит уже пересчитанное ожидание", e.retry_after == 306)


def _forbidden(url, headers=None, timeout=None):
    return _Resp(403, body="Invalid token")


fg.requests.get = _forbidden
try:
    fg.fetch_document()
    check("403 отличается от лимита", False)
except fg.FigmaError as e:
    check("403 отличается от лимита",
          e.retry_after is None and "403" in str(e))

# без секретов до сети дело не доходит вовсе
fg.cfg = lambda name, default=None: default
try:
    fg.fetch_document()
    check("без секретов запрос не уходит", False)
except fg.FigmaError as e:
    check("без секретов запрос не уходит",
          "FIGMA_TOKEN" in str(e) and "FIGMA_FILE_KEY" in str(e))

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
