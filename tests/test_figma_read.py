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


# Структура повторяет живой файл, снятый 08.09: на странице лежат
# ПОДПИСИ (текст) и ФРЕЙМЫ макетов с ASIN в имени, а текст — внутри
# фреймов на глубине трёх-четырёх вложений. Рядом картинка (её трогать
# нельзя), модули A+ «carousel» и чужие страницы.
DOC = {"document": {"children": [
    {"name": "UK/US", "children": [
        # подписи: восемь вариантов написания, здесь три из них
        {"id": "1:0", "type": "TEXT",
         "name": "label",
         "characters": "Main Images_B0G4S9SJ3M  54225000 Battery stapler CC-36"},
        {"id": "1:0b", "type": "TEXT", "name": "label",
         "characters": "Main Images_41500000_B0DG2Y9MSS_Blower DVB-200"},
        {"id": "1:0c", "type": "TEXT", "name": "label",
         "characters": "Просто заметка дизайнера"},
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
                      300, 66, 18, 22)]},
        {"id": "1:12", "type": "FRAME", "name": "B0DG2Y9MSS.PT01", "children": [
            text_node("1:13", "t", "Tapered Nozzle", 220, 24, 20)]},
        # A+ отложен: ASIN в имени нет, «carousel 2.2» есть у многих
        {"id": "1:9", "type": "FRAME", "name": "carousel 2.2", "children": [
            text_node("1:10", "t", "Two-year warranty", 220, 20, 16)]},
        {"id": "1:11", "type": "FRAME", "name": "Random frame", "children": []},
    ]},
    {"name": "ES", "children": [
        {"id": "2:1", "type": "FRAME", "name": "B0G4S9SJ3M.PT01", "children": [
            {"id": "2:3", "type": "FRAME", "name": "Frame 35841", "children": [
                {"id": "2:4", "type": "FRAME", "name": "Frame 1614", "children": [
                    text_node("2:2", "title", "Carga USB-C", 220, 24, 20)]}]}]}]},
    {"name": "Gazi", "children": [{"id": "9:1", "name": "чужое", "children": []}]},
    {"name": "UK/US (OLD)", "children": []},
]}}

R = fg.parse_document(DOC)

# --- подписи разбираются по признакам, а не по одному шаблону
_lbl = fg.parse_label("Main Images_41473000_B0DG616BXX_Cordless angle grinder")
check("SKU впереди ASIN разбирается",
      _lbl["asin"] == "B0DG616BXX" and _lbl["sku"] == "41473000"
      and _lbl["name"] == "Cordless angle grinder")
_lbl2 = fg.parse_label("A+ Premium Content_B0H26Y485K  Cordless blower DCB-202BC")
check("подпись без SKU не теряется целиком",
      _lbl2["asin"] == "B0H26Y485K" and _lbl2["sku"] is None)
_lbl3 = fg.parse_label("B0DG2Y9MSS 41500000 Blower DVB-200")
check("подпись без типа тоже читается",
      _lbl3["asin"] == "B0DG2Y9MSS" and _lbl3["type"] is None)
check("SKU с хвостом остаётся целым",
      fg.parse_label("Main Images_B0FXY75N5G_84516000-49_Saw")["sku"]
      == "84516000-49")
check("текст без ASIN подписью не считается",
      fg.parse_label("Просто заметка дизайнера") is None)

# --- обход и связь
# Товар определяется ИМЕНЕМ ФРЕЙМА: «B0G4S9SJ3M.PT01». Подпись даёт
# только SKU и название, и одного шаблона на неё не хватает.
check(f"товары собраны по фреймам ({len(R['products'])})",
      len(R["products"]) == 2)
check("текст найден на глубине четырёх фреймов",
      any(l["layer_id"] == "1:5" for p in R["products"] for l in p["layers"]))
check("картинка в слои не попала",
      not any(l["layer_id"] == "1:6" for p in R["products"] for l in p["layers"]))

_by_asin = {p["asin"]: p for p in R["products"]}
check("SKU и название подставлены из подписи",
      _by_asin["B0G4S9SJ3M"]["sku"] == "54225000"
      and _by_asin["B0G4S9SJ3M"]["name"] == "Battery stapler CC-36")
check("товар с подписью другого формата тоже нашёлся",
      _by_asin["B0DG2Y9MSS"]["sku"] == "41500000")

# A+ отложен целиком и попадает в отчёт ЧИСЛОМ, а не молча
check("модули A+ в слои не попали",
      not any(l["layer_id"] == "1:10" for p in R["products"] for l in p["layers"]))
check(f"и они посчитаны ({R['aplus_frames']})", R["aplus_frames"] == 1)

# --- slot: то, чем строки разных языков связываются между собой
_stapler = _by_asin["B0G4S9SJ3M"]
check(f"языки собраны на одном товаре ({_stapler['langs']})",
      set(_stapler["langs"]) == {"en", "es"})
_en = {l["slot"] for l in _stapler["layers"] if l["lang"] == "en"}
_es = {l["slot"] for l in _stapler["layers"] if l["lang"] == "es"}
check(f"место испанской строки совпало с английской ({_es})",
      _es and _es <= _en)
check("slot называет фрейм и путь внутри него",
      any(s.startswith("B0G4S9SJ3M.PT01#") for s in _es))
# id узла на каждой странице свой — связывать по нему нельзя
check("id узлов у пары разные, а место одно",
      {l["layer_id"] for l in _stapler["layers"]} >= {"1:5", "2:2"})
check("узел товара взят с английской страницы",
      _stapler["figma_node_id"] == "1:7"
      and _stapler["page_name"] == "UK/US")

# --- пробный заход: четыре товара вместо всего файла
# Список из четырёх не должен выглядеть как весь файл — по нему
# начнут считать объём работы, ровно как по демо-данным. Поэтому
# ограничение видно на экране, а не только в коде.
_lim = fg.parse_document(DOC, only_asins={"B0G4S9SJ3M"})
check(f"ограничение режет выборку ({len(_lim['products'])})",
      len(_lim["products"]) == 1
      and _lim["products"][0]["asin"] == "B0G4S9SJ3M")
check("без ограничения читается всё", len(R["products"]) == 2)
check("пробный набор непустой и состоит из ASIN",
      len(fg.FIRST_PASS_ASINS) >= 3
      and all(a.startswith("B0") for a in fg.FIRST_PASS_ASINS))

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
    {"id": "3:1", "type": "FRAME", "name": "B0G4S9SJ3M.PT01",
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

# --- превью макета: один запрос на ОТКРЫТЫЙ товар, не на список
fg.cfg = lambda name, default=None: {"FIGMA_TOKEN": "figd_x",
                                     "FIGMA_FILE_KEY": "ZZJ9"}.get(name, default)
_img_calls: list = []


class _ImgResp:
    def __init__(self, payload, code=200, headers=None):
        self.status_code, self._p = code, payload
        self.headers, self.text = headers or {}, ""

    def json(self):
        return self._p


def _img_ok(url, headers=None, timeout=None, params=None):
    _img_calls.append(params)
    return _ImgResp({"err": None, "images": {"1:1": "https://figma.example/x.png"}})


fg.requests.get = _img_ok
_url, _err = fg.node_image("1:1")
check("ссылка на рендер получена", _url and _err is None)
check("запрошен именно png половинного масштаба",
      _img_calls[-1]["format"] == "png" and _img_calls[-1]["scale"] == 0.5)
check("запрошен ровно один узел", _img_calls[-1]["ids"] == "1:1")

# Figma кладёт причину отказа в тело, а не в код ответа: 200 с err —
# это отказ, и молча вернуть None значит показать пустое место
fg.requests.get = lambda *a, **k: _ImgResp({"err": "Nothing to render"})
_url, _err = fg.node_image("1:1")
check("200 с err — это отказ, а не пустая картинка",
      _url is None and "Nothing to render" in (_err or ""))

fg.requests.get = lambda *a, **k: _ImgResp({}, 429, {"Retry-After": "306325"})
_url, _err = fg.node_image("1:1")
check("лимит на превью назван лимитом и в секундах",
      _url is None and "306" in (_err or ""))

# без секретов до сети дело не доходит вовсе
fg.cfg = lambda name, default=None: default
_url, _err = fg.node_image("1:1")
check("без секретов превью не запрашивается", _url is None and _err)
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
