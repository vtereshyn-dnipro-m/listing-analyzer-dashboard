# -*- coding: utf-8 -*-
"""
tests/test_localization.py — контроль длины перевода и честность демо.

Ради колонки длины эта страница и делается. Испанский и немецкий длиннее
английского примерно на пятую часть, слой в макете фиксированной ширины,
и текст, который в него не влез, обнаруживается при ЭКСПОРТЕ — когда
работа уже сделана и переделывать её дорого. Поэтому длина считается
до вставки, и проверяется здесь не наличие колонки, а её ответы:
влезает, впритык, не влезает, предел неизвестен.

Отдельно заперта честность демонстрационных данных. Пока Figma не
прочитана, экран показывает выдуманный набор — иначе по пустой странице
не понять, как устроена работа. Демо, неотличимое от настоящих данных,
хуже пустого экрана: по нему начнут считать объём работы. Поэтому оно
обязано объявляться плашкой, а сбой чтения — оставаться сбоем, а не
превращаться в «данных нет».

Запуск (pytest не нужен):  python tests/test_localization.py
"""
from __future__ import annotations

import pathlib
import re
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import services.db                                     # noqa: E402
services.db.get_conn = lambda: type(
    "C", (), {"close": lambda self: None})()

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


MODE = {"fail": False, "real": False, "layers": None}

# Настоящий товар, прочитанный из Figma: у него есть узел, а значит
# и превью макета. Демо узла не имеет намеренно.
REAL_PRODUCT = pd.DataFrame([dict(
    id=7, asin="B0G4S9SJ3M", sku="54225000", name="Stapler CC-36",
    section_type="Main Images", page_name="UK/US", figma_file_key="ZZJ9",
    figma_node_id="1:1", layers_count=2, synced_at=pd.Timestamp.utcnow(),
    # у этого товара дизайнер уже сделал немецкий макет в самой Figma
    lang_nodes={"de": "9:9"},
    langs_done=["de"])])
# Двух строк достаточно и обязательно: при одной «перевести строку»
# и «перевести товар» дают одинаковый результат, и проверка размера
# выборки ничего не проверяет.
REAL_LAYERS = pd.DataFrame([
    dict(layer_id="1:5", slot="B0G4S9SJ3M.PT01#0.0", frame_name="title",
         lang="es", source_text="USB-C Charging",
         translated_text="Carga USB-C", char_limit=20, status="translated",
         edited_after_model=False),
    # NaN, а не "": непереведённая строка приходит из LEFT JOIN именно
    # так. Пустая строка в фикстуре скрывала правило 4 — NaN истинный,
    # и `x or ""` отдаёт float, на котором .strip() падает. Ровно на
    # этом страница и упала после ребута.
    dict(layer_id="1:8", slot="B0G4S9SJ3M.PT01#0.1", frame_name="body",
         lang="es", source_text="Charges from power banks",
         translated_text=float("nan"), char_limit=44, status="none",
         edited_after_model=float("nan")),
    # служебная: число с единицей. В модель не уходит и в таблице
    # лежит свёрнутой — иначе треть экрана это шум.
    dict(layer_id="1:9", slot="B0G4S9SJ3M.PT01#0.2", frame_name="spec",
         lang="es", source_text="2 Ah",
         translated_text=float("nan"), char_limit=12, status="none",
         edited_after_model=float("nan")),
])
GLOSSARY = pd.DataFrame([{"en": "Fabric fastening", "tr": "Stoffbefestigung",
                          "char_limit": 30}])


def fake_sql(sql, con=None, **kw):
    if MODE["fail"]:
        raise RuntimeError("relation figma_products does not exist")
    q = str(sql)
    if "synthesis_skill" in q:
        # своего промпта ещё нет: страница обязана показать текст
        # по умолчанию и сказать, что он не сохранён
        return pd.DataFrame()
    if MODE["real"]:
        if "JOIN figma_layers src" in q:
            return GLOSSARY.copy()
        if "FROM figma_layers" in q:
            # подмена целым кадром, а не срезом: pandas 3 не кладёт NaN
            # в строковую колонку через `df[:] = other`
            return (MODE["layers"] if MODE.get("layers") is not None
                    else REAL_LAYERS).copy()
        return REAL_PRODUCT.copy()
    return pd.DataFrame()


pd.read_sql = fake_sql

import services.localization as loc                     # noqa: E402
from streamlit.testing.v1 import AppTest                # noqa: E402
import streamlit as st                                  # noqa: E402


# --- 1. сам расчёт длины
check("влезает с запасом", loc.fits("Carga USB-C", 18)[2] == "ok")
check("не влезает — over",
      loc.fits("Se carga desde power banks y adaptadores", 34)[2] == "over")
check("впритык — отдельное состояние, а не «влезает»",
      loc.fits("x" * 19, 20)[2] == "tight")
check("длина и предел возвращаются числами",
      loc.fits("abc", 10)[:2] == (3, 10))

# Предел приходит из макета и может отсутствовать. «Не знаем предел»
# и «предел нулевой» — разные вещи, и вторая не должна выглядеть первой:
# ноль в Python ложный, и проверка через истинность их бы склеила.
check("предел неизвестен — так и сказано", loc.fits("abc", None)[2] == "unknown")
check("нулевой предел — это не «неизвестно»", loc.fits("abc", 0)[2] == "over")
check("пустой перевод при известном пределе влезает",
      loc.fits("", 10)[2] == "ok")
check("NaN вместо предела не роняет расчёт",
      loc.fits("abc", float("nan"))[2] == "unknown")

_df = pd.DataFrame([
    {"translated_text": "коротко", "char_limit": 20},
    {"translated_text": "x" * 40, "char_limit": 34},
    {"translated_text": "y" * 50, "char_limit": 34},
])
check("считаются именно непомещающиеся строки", loc.over_rows(_df) == 2)

# --- 2. сводка по товарам
_p = pd.DataFrame([
    {"langs_done": {"de", "es", "it", "fr"}},
    {"langs_done": {"es"}},
    {"langs_done": set()},
])
_s = loc.summarize(_p)
check(f"сводка считает три состояния ({_s})",
      _s == {"total": 3, "all": 1, "partial": 1, "none": 1})
check("английский не делает товар переведённым",
      loc.product_state({"en"}) == "none")

# --- 3. экран: демо объявлено, сбой назван сбоем
def page():
    st.cache_data.clear()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
    at.switch_page("pages/content.py").run()
    return at


MODE["fail"] = True
at = page()
check("страница открывается при недоступных таблицах", not at.exception)
check("сбой чтения назван сбоем",
      any("не удалось прочитать" in str(e.value).lower() for e in at.error))
check("демо объявлено плашкой",
      any("емонстрационные данные" in str(i.value) for i in at.info))
check("плашка предупреждает, что числа выдуманы",
      any("выдуман" in str(i.value) for i in at.info))

MODE["fail"] = False
at = page()
check("на пустых таблицах тоже показывается демо, а не пустой экран",
      any("емонстрационные данные" in str(i.value) for i in at.info))

# --- 4. список: очередь работы сверху
_labels = [str(b.label) for b in at.button if str(b.key or "").startswith("loc-open-")]
check(f"кнопка ведёт на непереведённый язык ({_labels[:1]})",
      bool(_labels) and _labels[0].endswith("DE"))

# --- 5. экран перевода: счётчик, подсветка, предупреждение
at.session_state["loc-product"] = -1
at.session_state["loc-lang"] = "es"
at.run()
_md = " ".join(str(m.value) for m in at.markdown)
_counters = re.findall(r">(\d+ / (?:\d+|—)(?: ⚠)?)<", _md)
check(f"у каждой строки счётчик «длина / предел» ({len(_counters)})",
      len(_counters) == len(at.text_input) and len(_counters) > 0)
check("непомещающийся перевод помечен", any("⚠" in c for c in _counters))
check("строка с превышением подсвечена целиком",
      _md.count("background:#FDF3D8") == 1)
check("под таблицей сказано, сколько строк править",
      any("Длиннее макета строк: 1" in str(w.value) for w in at.warning))
check("экспорт остаётся в Figma — это сказано на экране",
      any("Экспорт PNG" in str(c.value) for c in at.caption))

# «Применить в Figma» не заглушка: REST в Figma не пишет, поэтому
# кнопка отдаёт файл для плагина. Кнопка, которая ничего не делает
# и объясняет почему, хуже кнопки, которая делает половину дела.
_apply = next((b for b in at.get("download_button") if b.key == "loc-apply"),
              None)
check("«Применить в Figma» отдаёт файл, а не пустоту",
      _apply is not None and not _apply.disabled)
check("и сказано, что это для плагина",
      any("для плагина" in str(c.value) for c in at.caption))
_retry = next((b for b in at.button if b.key == "loc-retry"), None)
check("«Перевести заново» работает", _retry is not None and not _retry.disabled)
# Кнопка стоит НАД таблицей: под тремя десятками строк её не видно,
# и её уже считали пропавшей. Проверяется порядок, а не наличие.
_ids = [e.key or "" for e in at.get("button") + at.get("text_input")]
check(f"кнопка товара выше строк перевода ({_ids[:3]})",
      "loc-retry" in _ids
      and _ids.index("loc-retry") < min(
          (i for i, k in enumerate(_ids) if str(k).startswith("loc-txt-")),
          default=10 ** 6))
check("и в подписи названо число строк",
      _retry is not None and str(len(at.text_input)) in str(_retry.label))

# --- 5б. пробный заход виден на экране
# Четыре товара не должны выглядеть как весь файл: по такому списку
# начнут считать объём работы — та же ошибка, что с демо-данными.
st.cache_data.clear()
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
at.switch_page("pages/content.py").run()
_box = next((c for c in at.checkbox if c.key == "loc-first-pass"), None)
check("галочка пробного захода есть и включена",
      _box is not None and _box.value is True)
check("в подписи названо число товаров",
      _box is not None and "4" in str(_box.label))

at.session_state["loc-sync-report"] = {"limited": True, "skipped_sections": [],
                                       "skipped_pages": [], "aplus_frames": 564}
at.run()
check("после чтения сказано, что прочитан не весь файл",
      any("не весь файл" in str(i.value) for i in at.info))
check("и сказано, сколько модулей A+ отложено",
      any("A+ пропущено: 564" in str(c.value) for c in at.caption))
at.session_state["loc-sync-report"] = {}

# и главное — что галочка ДЕЙСТВУЕТ, а не украшает экран
PARSED_WITH: list = []
fg_mod = __import__("services.figma", fromlist=["figma"])
_real_parse = fg_mod.parse_document
fg_mod.fetch_document = lambda key=None: {"document": {"children": []}}
fg_mod.parse_document = lambda doc, only_asins=None: (
    PARSED_WITH.append(only_asins) or _real_parse(doc, only_asins))

st.cache_data.clear()
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
at.switch_page("pages/content.py").run()
next(b for b in at.button if b.key == "loc-sync").click().run()
check(f"с галочкой читаются только пробные товары ({PARSED_WITH})",
      PARSED_WITH and PARSED_WITH[-1] == set(fg_mod.FIRST_PASS_ASINS))

at.checkbox[0].set_value(False).run()
next(b for b in at.button if b.key == "loc-sync").click().run()
check("без галочки читается весь файл", PARSED_WITH[-1] is None)
fg_mod.parse_document = _real_parse

# --- 6. картинки: миниатюра в списке и превью в редакторе
# По названию товары не различаются — «Blower DCB-201BC» и «Blower
# DVB-200» читаются одинаково. Поэтому в списке миниатюра, но ОДНА
# на товар (узел .MAIN), а не по картинке на слой: каждая стоит
# запроса ссылки у API, и это квота.
#
# Кэшируются БАЙТЫ, а не ссылка: ссылку Figma держит около часа,
# и суточный кэш ссылки означал бы битые картинки через час.
import base64                                            # noqa: E402
import services.figma as fg                               # noqa: E402

CALLS: list = []
# настоящий PNG 1×1: Streamlit отдаёт байты в PIL, и подделка из восьми
# байт роняет страницу — ровно так и нашлось, что битый ответ Figma
# уносил весь список
PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
    "IQAAAABJRU5ErkJggg==")


def fake_png(node_id, key=None, scale=fg.IMAGE_SCALE):
    CALLS.append((node_id, scale))
    return PNG_1x1, None


fg.node_png = fake_png
loc._png_cached.clear()

check("кэш картинок живёт сутки, а не час",
      fg.IMAGE_TTL >= 24 * 60 * 60)
check("миниатюра мельче превью", fg.THUMB_SCALE < fg.IMAGE_SCALE)

# демо узла не имеет — рендер выдуманного был бы запросом в никуда
st.cache_data.clear()
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
at.switch_page("pages/content.py").run()
check("для демо-списка рендер не запрашивается", not CALLS)

at.session_state["loc-product"] = -1
at.session_state["loc-lang"] = "es"
at.run()
check("для демо-товара рендер тоже не запрашивается", not CALLS)
check("и сказано, почему превью нет",
      any("не прочитан из Figma" in str(c.value) for c in at.caption))

# настоящие данные: в списке ОДНА миниатюра на товар, мелкая
MODE["real"] = True
st.cache_data.clear()
CALLS.clear()
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
at.switch_page("pages/content.py").run()
check(f"в списке ровно одна картинка на товар ({CALLS})",
      CALLS == [("1:1", fg.THUMB_SCALE)])
check("и она на экране", len(at.get("image")) == 1)

at.run()          # ещё одна отрисовка — кэш обязан удержать байты
check(f"повторная отрисовка списка запроса не делает ({len(CALLS)})",
      len(CALLS) == 1)

# в редакторе — то же изображение, но крупнее
at.session_state["loc-product"] = 7
at.session_state["loc-lang"] = "es"
at.run()
check(f"превью в редакторе просит полный масштаб ({CALLS})",
      CALLS == [("1:1", fg.THUMB_SCALE), ("1:1", fg.IMAGE_SCALE)])
check("картинка действительно на экране", len(at.get("image")) == 1)
check("и подпись называет, ЧЕЙ это макет",
      any(("уже переведён в Figma" in str(c.value))
          or ("показан английский" in str(c.value)) for c in at.caption))

# отказ рендера не должен уносить с собой таблицу текста
fg.node_png = lambda node_id, key=None, scale=fg.IMAGE_SCALE: (
    None, "429, ждать 306 с")
loc._png_cached.clear()
at.run()
check("отказ превью назван отказом",
      any("Не удалось получить рендер" in str(c.value) for c in at.caption))
check("а строки перевода остались на месте", len(at.text_input) > 0)
fg.node_png = fake_png
loc._png_cached.clear()

# отказ рендера НЕ должен кэшироваться: кэш суточный, и запомненный
# отказ переживает починку причины — вчерашний 403 по истёкшему токену
# так и пережил замену токена, права были уже в порядке.
CALLS.clear()
loc._png_cached.clear()
fg.node_png = lambda node_id, key=None, scale=fg.IMAGE_SCALE: (None, "403")
_p1, _e1 = loc.preview_png("1:1", fg.THUMB_SCALE)
_p2, _e2 = loc.preview_png("1:1", fg.THUMB_SCALE)
check(f"отказ рендера не залипает в кэше ({_e1})",
      _p1 is None and _p2 is None and "403" in str(_e1))
fg.node_png = fake_png
_p3, _e3 = loc.preview_png("1:1", fg.THUMB_SCALE)
check("после починки причины картинка приходит сразу",
      _p3 is not None and _e3 is None)
_p4, _e4 = loc.preview_png("1:1", fg.THUMB_SCALE)
check("а удачный рендер кэшируется и запроса не делает",
      _p4 is not None and len([c for c in CALLS if c[0] == "1:1"]) == 1)
loc._png_cached.clear()
CALLS.clear()

def page_editor():
    st.cache_data.clear()
    a = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
    a.switch_page("pages/content.py").run()
    a.session_state["loc-product"] = 7
    a.session_state["loc-lang"] = "es"
    a.run()
    return a


# --- 6б. языковой макет вместо английского, когда он есть
# Часть товаров переведена прямо в Figma, и для них существует
# НАСТОЯЩАЯ карточка на языке — с текстом на картинке. Показывать
# вместо неё английскую значит прятать готовую работу.
check("для языка со своим макетом берётся ЕГО узел",
      loc.preview_node({"lang_nodes": {"de": "9:9"},
                                "figma_node_id": "1:1"}, "de") == ("9:9", "de"))
check("для языка без макета — английский, и это ВИДНО в ответе",
      loc.preview_node({"lang_nodes": {"de": "9:9"},
                                "figma_node_id": "1:1"}, "es") == ("1:1", "en"))
check("jsonb приходит строкой — разбирается",
      loc.preview_node({"lang_nodes": '{"it": "7:7"}',
                                "figma_node_id": "1:1"}, "it") == ("7:7", "it"))
check("мусор вместо jsonb не роняет экран",
      loc.preview_node({"lang_nodes": "не json",
                                "figma_node_id": "1:1"}, "it") == ("1:1", "en"))

# на экране: свой макет назван своим, чужой — чужим
CALLS.clear()
loc._png_cached.clear()
MODE["real"] = True
at = page_editor()
at.session_state["loc-lang"] = "de"
for lg in ("de", "es", "it", "fr"):
    at.session_state[f"loc-lang-0-{lg}"] = (lg == "de")
at.run()
check(f"немецкий макет запрошен по своему узлу ({CALLS})",
      any(c[0] == "9:9" for c in CALLS))
check("и подпись говорит, что макет уже переведён",
      any("уже переведён в Figma" in str(c.value) for c in at.caption))

at.session_state["loc-lang"] = "es"
for lg in ("de", "es", "it", "fr"):
    at.session_state[f"loc-lang-0-{lg}"] = (lg == "es")
at.run()
check("для испанского показан английский макет",
      any(c[0] == "1:1" for c in CALLS))
check("и сказано, что своего макета ещё нет",
      any("ещё нет" in str(c.value) for c in at.caption))
MODE["layers"] = None

# --- 7. правка, перевод строки и след модели
# Правка уезжает в базу СРАЗУ: кнопка «Сохранить» означала бы, что
# часть работы живёт только в браузере, а строк здесь десятки.
SAVED: list = []
MODEL_CALLS: list = []


def fake_save(pid, slot, lang, text):
    SAVED.append((pid, slot, lang, text))
    return None


def fake_run(prompt_text, lang, rows, pairs):
    MODEL_CALLS.append({"lang": lang, "rows": rows, "prompt": prompt_text,
                        "pairs": pairs})
    return {r["slot"]: "Akku-Tacker" for r in rows}, "claude-sonnet-5"


WROTE: list = []


def fake_save_model(pid, lang, model, texts):
    WROTE.append((pid, lang, model, texts))
    return len(texts), None


import services.translate as tr                            # noqa: E402
loc.save_translation = fake_save
loc.save_model_translation = fake_save_model
tr.run = fake_run

MODE["real"] = True
st.cache_data.clear()
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
at.switch_page("pages/content.py").run()
at.session_state["loc-product"] = 7
at.session_state["loc-lang"] = "es"
at.run()

# Первым делом — что страница вообще жива на РЕАЛЬНОЙ форме данных.
# Непереведённая строка приходит как NaN, а NaN истинный: `x or ""`
# отдаёт float, и `.strip()` на нём роняет весь экран. Проверка стоит
# до всех остальных, иначе они падают каскадом и причина теряется.
check(f"редактор не падает на непереведённых строках "
      f"({[str(e.value)[:60] for e in at.exception]})", not at.exception)
check(f"строк перевода на экране ({len(at.text_input)})", len(at.text_input) == 2)
at.text_input[0].set_value("Carga rápida USB-C").run()
check(f"правка ушла в базу сразу ({SAVED})",
      SAVED and SAVED[0][3] == "Carga rápida USB-C")
check("и записана по МЕСТУ слоя, а не по id узла",
      SAVED and SAVED[0][1] == "B0G4S9SJ3M.PT01#0.0")

# перевод ОДНОЙ строки: переделать чаще надо именно её
_row_btn = next((b for b in at.button
                 if str(b.key or "").startswith("loc-tr-")), None)
check("у строки есть своя кнопка перевода", _row_btn is not None)
_row_btn.click().run()
check(f"модель позвана на ОДНУ строку ({len(MODEL_CALLS[-1]['rows'])})",
      len(MODEL_CALLS) == 1 and len(MODEL_CALLS[-1]["rows"]) == 1)
check("в промпт уехал предел этой строки",
      MODEL_CALLS[-1]["rows"][0]["char_limit"] == 20)
check("результат модели записан со следом модели",
      WROTE and WROTE[-1][2] == "claude-sonnet-5")

# перевод всего товара — та же дорога, но со всеми строками
next(b for b in at.button if b.key == "loc-retry").click().run()
check(f"кнопка товара переводит ВСЕ строки ({len(MODEL_CALLS[-1]['rows'])})",
      len(MODEL_CALLS) == 2 and len(MODEL_CALLS[-1]["rows"]) == 2)

# --- 7б. язык, которого в макете НЕТ, всё равно даёт работу
# Перевод чаще всего делается туда, где страницы в макете ещё нет:
# у B0G4S9SJ3M на ES не нарисовано ни одного слоя. Прежний запрос читал
# `WHERE lang = 'es'`, получал пусто и говорил «текстовых слоёв нет»
# у товара, где их 33, — то есть страница умела показывать только уже
# переведённое, ровно наоборот своему назначению.
NO_TRANSLATION = REAL_LAYERS.assign(
    translated_text=[float("nan")] * len(REAL_LAYERS), status="none")
MODE["layers"] = NO_TRANSLATION

st.cache_data.clear()
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
at.switch_page("pages/content.py").run()
at.session_state["loc-product"] = 7
at.session_state["loc-lang"] = "es"
at.run()
check("непереведённый язык показывает строки, а не «слоёв нет»",
      len(at.text_input) == 2)
check("и исходник на месте — переводить есть что",
      any("USB-C Charging" in str(m.value) for m in at.markdown))
check("плашки «слоёв нет» при этом нет",
      not any("слоёв" in str(i.value) and "нет" in str(i.value)
              for i in at.info))

# правка по такому языку обязана СОЗДАТЬ строку, а не потеряться:
# UPDATE несуществующей строки молча не делает ничего
SAVED.clear()
at.text_input[0].set_value("Carga USB-C").run()
check(f"правка по новому языку ушла в базу ({SAVED})",
      SAVED and SAVED[0][2] == "es" and SAVED[0][3] == "Carga USB-C")
MODE["layers"] = None

# Тесты подделывают pd.read_sql, поэтому UI-проверка выше прошла бы
# и со старым запросом. Сам контракт запроса проверяется текстом:
# основа — строки ИСТОЧНИКА, перевод подтягивается по языку.
_src = (ROOT / "services/localization.py").read_text(encoding="utf-8")
_ll = _src[_src.index("def load_layers"):_src.index("DEMO_PRODUCT")]
check("основа выборки — английские строки, а не строки языка",
      "s.lang = %(src)s" in _ll and "AND s.lang = %(lang)s" not in _ll)
check("перевод подтягивается по слоту и языку",
      "d.slot = s.slot" in _ll and "d.lang = %(lang)s" in _ll)
# правка по языку без строк обязана ВСТАВЛЯТЬ, а не обновлять пустоту
_st = _src[_src.index("def save_translation"):_src.index("def save_model_translation")]
check("правка вставляет строку, если её ещё нет",
      "INSERT INTO figma_layers" in _st and "ON CONFLICT" in _st)
_sm = _src[_src.index("def save_model_translation"):_src.index("def load_prompt")]
check("перевод модели тоже вставляет, а не только обновляет",
      "INSERT INTO figma_layers" in _sm)

# --- 7б². служебные строки не мешают работе
check(f"в таблице только переводимые строки ({len(at.text_input)})",
      len(at.text_input) == 2)
check("служебные свёрнуты и посчитаны",
      any("Перевод не нужен: 1" in str(e.label) for e in at.get("expander")))
check("и сказано, почему их не переводят",
      any("одинаковы на всех языках" in str(c.value) for c in at.caption))

# --- 7б³. несколько языков одним нажатием
# Перевод на четыре рынка — одна работа, а не четыре захода.
LANG_CALLS: list = []
tr.run = lambda prompt, lang, rows, pairs: (
    LANG_CALLS.append((lang, len(rows)))
    or ({r["slot"]: f"[{lang}] текст" for r in rows}, "claude-opus-5"))

at = page_editor()
def lang_boxes(a):
    """Чекбоксы языков текущего поколения: ключ включает поколение,
    иначе кнопка «все без перевода» не смогла бы их переставить."""
    return {str(c.key).rsplit("-", 1)[-1]: c for c in a.checkbox
            if str(c.key or "").startswith("loc-lang-")}


# Ряд языков собирается ФЛЕКСОМ, а не долями колонок (правило 0):
# доли делят ширину поровну и сжимают содержимое — пять контролов
# в узкой колонке обрезали подписи до одной буквы, «D» вместо «DE».
# Обрезку тестом не увидеть, поэтому проверяется способ вёрстки.
_css = " ".join(str(m.value) for m in at.markdown)
check("ряд языков свёрстан флексом, а не долями",
      ".st-key-loc-head" in _css and "flex:0 0 auto" in _css)
check("и подписи не переносятся", "white-space:nowrap" in _css)

_boxes = lang_boxes(at)
check(f"языки выбираются чекбоксами ({sorted(_boxes)})",
      set(_boxes) == {"de", "es", "it", "fr"})
check("открытый язык отмечен", _boxes["es"].value is True)

_boxes["de"].set_value(True).run()
LANG_CALLS.clear()
next(b for b in at.button if b.key == "loc-retry").click().run()
check(f"перевод ушёл на ОБА выбранных языка ({[c[0] for c in LANG_CALLS]})",
      sorted(c[0] for c in LANG_CALLS) == ["de", "es"])
check("и в каждый язык ушли только переводимые строки",
      all(c[1] == 2 for c in LANG_CALLS))
check("в подписи кнопки видно строки и языки",
      any("2 × 2" in str(b.label) for b in at.button if b.key == "loc-retry"))

# «все без перевода» — это очередь работы по товару
next(b for b in at.button if b.key == "loc-langs-missing").click().run()
_after = {k: b.value for k, b in lang_boxes(at).items()}
check(f"кнопка отметила языки без перевода ({_after})",
      _after["es"] and _after["it"] and _after["fr"] and not _after["de"])
check("и сделала это без падения виджета", not at.exception)

# перевод — основное действие экрана, выгрузка вторична
def weight(b):
    """Вес кнопки из protobuf, а не из подписи — как в test_card_states."""
    return str(getattr(getattr(b, "proto", None), "type", "") or "secondary")


_retry = next(b for b in at.button if b.key == "loc-retry")
check(f"кнопка перевода основная ({weight(_retry)})",
      weight(_retry) == "primary")
_apply = next(b for b in at.get("download_button") if b.key == "loc-apply")
check(f"а «Применить в Figma» вторичная ({weight(_apply)})",
      weight(_apply) != "primary")
tr.run = fake_run

# --- 7в. отказ модели обязан доходить до экрана
# Кнопка вызывается КОЛБЭКОМ, а из колбэка st.error на экран не
# попадает: Streamlit рисует элементы позже. Поэтому раньше выходило
# худшее — кнопка нажата, счётчики нули, объяснения нет. Три разных
# отказа выглядели одинаково: провайдер молчит, ответ не разобрался,
# места не совпали.
import services.ai as ai_mod                              # noqa: E402


# 1. провайдер не ответил — причина известна слою вызова
tr.run = lambda *a, **k: ({}, "claude-sonnet-5")
ai_mod.last_call_error = lambda: "Anthropic: HTTP 401 — invalid x-api-key"
at = page_editor()
next(b for b in at.button if str(b.key or "").startswith("loc-tr-")).click().run()
check("отказ провайдера назван на экране",
      any("401" in str(e.value) for e in at.error))

# 2. ответ пустой, причины нет — всё равно не молчим
ai_mod.last_call_error = lambda: None
at = page_editor()
next(b for b in at.button if str(b.key or "").startswith("loc-tr-")).click().run()
check("пустой ответ назван отказом, а не пустым переводом",
      any("не вернула ничего" in str(e.value) for e in at.error))

# 3. модель ответила про ЧУЖИЕ места — записывать нечего
tr.run = lambda *a, **k: ({"выдуманный.slot#9": "Texto"}, "claude-sonnet-5")
at = page_editor()
next(b for b in at.button if str(b.key or "").startswith("loc-tr-")).click().run()
check("несовпадение мест названо прямо",
      any("места не совпадают" in str(e.value) for e in at.error))

# перевод обязан ПОЯВИТЬСЯ в поле, а не остаться за старым значением
# session_state: text_input с key игнорирует value, и строка, впервые
# отрисованная пустой, прятала бы уже записанный в базу перевод
# третье значение — служебной строке «2 Ah»: она в таблицу не попадает,
# но длина списка обязана совпадать с числом строк фикстуры
TRANSLATED = REAL_LAYERS.assign(
    translated_text=["Carga USB-C", "Carga desde power banks",
                     float("nan")])
tr.run = lambda prompt, lang, rows, pairs: (
    {r["slot"]: "Carga desde power banks" for r in rows}, "claude-opus-5")
at = page_editor()


def field_value(a, slot):
    """Значение поля строки — по КЛЮЧУ ТЕКУЩЕГО поколения.

    Ключ включает поколение данных: снять его из session_state мало,
    состояние виджета живёт в браузере и возвращается оттуда поверх
    `value=`. Пересоздание виджета — единственный способ показать
    то, что записано в базу.
    """
    gen = int(a.session_state["loc-gen-7-es"]
              if "loc-gen-7-es" in a.session_state else 0)
    key = f"loc-txt-7-es-{gen}-{slot}"
    return (str(a.session_state[key]) if key in a.session_state else None)


check("до перевода поле пустое",
      (field_value(at, "B0G4S9SJ3M.PT01#0.1") or "") == "")
MODE["layers"] = TRANSLATED          # база уже отдаёт перевод
next(b for b in at.button if str(b.key or "").endswith("#0.1")).click().run()
_after = field_value(at, "B0G4S9SJ3M.PT01#0.1")
check(f"после перевода поле показывает результат ({_after!r})",
      _after == "Carga desde power banks")
MODE["layers"] = None

# 4. удача тоже называется: сколько строк и какой моделью
tr.run = fake_run
at = page_editor()
next(b for b in at.button if str(b.key or "").startswith("loc-tr-")).click().run()
check("успех виден числом строк и именем модели",
      any("Переведено моделью" in str(x.value) for x in at.success))

# --- 8. след правки виден в строке
MODE["layers"] = REAL_LAYERS.assign(
    edited_after_model=[True] * len(REAL_LAYERS))
st.cache_data.clear()
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
at.switch_page("pages/content.py").run()
at.session_state["loc-product"] = 7
at.session_state["loc-lang"] = "es"
at.run()
check("правленная человеком строка помечена",
      any("правил человек" in str(m.value) for m in at.markdown))
MODE["layers"] = None

# --- 9. промпт виден и правится
_areas = [a for a in at.text_area if a.key == "loc-prompt-draft"]
check("промпт на экране, а не спрятан в коде", len(_areas) == 1)
check("и это ровно текст по умолчанию, пока своего нет",
      _areas and "CC-36" in str(_areas[0].value))
check("сказано, что текст не сохранён",
      any("не сохранён" in str(c.value) for c in at.caption))

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
