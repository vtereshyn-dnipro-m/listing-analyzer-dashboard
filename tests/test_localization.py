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


MODE = {"fail": False, "real": False}

# Настоящий товар, прочитанный из Figma: у него есть узел, а значит
# и превью макета. Демо узла не имеет намеренно.
REAL_PRODUCT = pd.DataFrame([dict(
    id=7, asin="B0G4S9SJ3M", sku="54225000", name="Stapler CC-36",
    section_type="Main Images", page_name="UK/US", figma_file_key="ZZJ9",
    figma_node_id="1:1", layers_count=2, synced_at=pd.Timestamp.utcnow(),
    langs_done=["de"])])
# Двух строк достаточно и обязательно: при одной «перевести строку»
# и «перевести товар» дают одинаковый результат, и проверка размера
# выборки ничего не проверяет.
REAL_LAYERS = pd.DataFrame([
    dict(layer_id="1:5", slot="B0G4S9SJ3M.PT01#0.0", frame_name="title",
         lang="es", source_text="USB-C Charging",
         translated_text="Carga USB-C", char_limit=20, status="translated",
         edited_after_model=False),
    dict(layer_id="1:8", slot="B0G4S9SJ3M.PT01#0.1", frame_name="body",
         lang="es", source_text="Charges from power banks",
         translated_text="", char_limit=44, status="none",
         edited_after_model=False),
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
            return REAL_LAYERS.copy()
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
loc.preview_png.clear()

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
check("и подпись объясняет, что макет английский",
      any("Английский макет" in str(c.value) for c in at.caption))

# отказ рендера не должен уносить с собой таблицу текста
fg.node_png = lambda node_id, key=None, scale=fg.IMAGE_SCALE: (
    None, "429, ждать 306 с")
loc.preview_png.clear()
at.run()
check("отказ превью назван отказом",
      any("Не удалось получить рендер" in str(c.value) for c in at.caption))
check("а строки перевода остались на месте", len(at.text_input) > 0)
fg.node_png = fake_png
loc.preview_png.clear()

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

# --- 8. след правки виден в строке
REAL_LAYERS.loc[0, "edited_after_model"] = True
st.cache_data.clear()
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
at.switch_page("pages/content.py").run()
at.session_state["loc-product"] = 7
at.session_state["loc-lang"] = "es"
at.run()
check("правленная человеком строка помечена",
      any("правил человек" in str(m.value) for m in at.markdown))
REAL_LAYERS.loc[0, "edited_after_model"] = False

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
