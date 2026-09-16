# -*- coding: utf-8 -*-
"""
tests/test_plugin_api.py — маршрут для плагина Figma: закрыт без токена,
отвечает той же формой, что кнопка, и не молчит при сбое.

Плагин забирает переводы сам, по HTTP. Три вещи, которые тут ломаются
тихо и дорого:

1. Маршрут без токена. Не «отвечает 401», а НЕ СУЩЕСТВУЕТ: без
   секрета FIGMA_PLUGIN_TOKEN приложение не открывает наружу ничего.
   Проверяется список маршрутов, а не код ответа.
2. Две сборки одной формы. Кнопка «Выгрузить для Figma» и маршрут
   обязаны отдавать байт в байт одно и то же — иначе плагин, который
   проверили на файле, разойдётся с сетью на первом же поле.
   Проверяется РАВЕНСТВО двух сборок на одних строках.
3. Сбой базы как HTML. Плагин читает `error` из JSON; страница ошибки
   Starlette ему нечитаема. Проверяется тип ответа при исключении.

Обработчик зовётся напрямую, с собранным вручную ASGI-скоупом: это
то же, что делает сервер, но без сети и без httpx. Отдельно
проверяется, что `streamlit run app.py` распознаёт обёртку как ASGI-
приложение — иначе маршрут молча не поднимется, а страницы будут
работать как ни в чём не бывало.

Запуск (pytest не нужен):  python tests/test_plugin_api.py
"""
from __future__ import annotations

import asyncio
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd                                        # noqa: E402

import services.plugin_api as api                          # noqa: E402
import services.localization as loc                        # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


SECRETS = {}
api.cfg = lambda name, default=None: SECRETS.get(name, default)


def call(method="GET", query="", auth=None):
    from starlette.requests import Request
    headers = [(b"host", b"test")]
    if auth is not None:
        headers.append((b"authorization", auth.encode()))
    scope = {"type": "http", "method": method, "path": api.PATH,
             "query_string": query.encode(), "headers": headers}
    resp = asyncio.run(api.translations(Request(scope)))
    body = resp.body.decode("utf-8") if resp.body else ""
    return resp.status_code, dict(resp.headers), (json.loads(body) if body else None)


ROWS = [
    dict(asin="B0G4S9SJ3M", lang="de", layer_id="9:5", slot="B0G4S9SJ3M.PT01#0.0",
         translated_text="USB-C-Laden", file_key="ZZJ9"),
    dict(asin="B0G4S9SJ3M", lang="de", layer_id="9:6", slot="B0G4S9SJ3M.PT01#0.1",
         translated_text="Lädt an Powerbanks", file_key="ZZJ9"),
    dict(asin="B0G4S9SJ3M", lang="es", layer_id="1:5", slot="B0G4S9SJ3M.PT01#0.0",
         translated_text="Carga USB-C", file_key="ZZJ9"),
]
ASKED: list = []


def fake_fetch(asins, langs):
    ASKED.append((asins, langs))
    return [r for r in ROWS
            if (asins is None or r["asin"] in asins)
            and (langs is None or r["lang"] in langs)]


api.fetch_rows = fake_fetch

# --- 1. без токена маршрута нет вовсе
SECRETS.clear()
check("без FIGMA_PLUGIN_TOKEN маршрутов нет", api.routes() == [])
SECRETS["FIGMA_PLUGIN_TOKEN"] = "s3cret-token"
_routes = api.routes()
check(f"с токеном маршрут один и по своему пути ({[r.path for r in _routes]})",
      [r.path for r in _routes] == [api.PATH])
check("путь не задевает зарезервированные Streamlit'ом",
      not api.PATH.startswith(("/_stcore", "/media", "/component", "/static")))

# --- 2. доступ
st, _, body = call(auth=None)
check(f"без заголовка — 401 и причина словами ({st})", st == 401 and "Authorization" in body["error"])
st, _, body = call(auth="Bearer wrong")
check("с чужим токеном — 401", st == 401)
st, _, body = call(auth="Basic s3cret-token")
check("чужая схема с верным токеном — тоже 401", st == 401)
check("сравнение за постоянное время", "compare_digest" in
      (ROOT / "services/plugin_api.py").read_text(encoding="utf-8"))

# --- 3. форма ответа — та же, что у кнопки
ASKED.clear()
st, hdr, body = call(query="asins=B0G4S9SJ3M&langs=de,es", auth="Bearer s3cret-token")
check(f"с верным токеном — 200 ({st})", st == 200)
check("тип ответа JSON в utf-8", hdr.get("content-type", "").startswith("application/json"))
check("CORS открыт — доступ решает токен, а не происхождение",
      hdr.get("access-control-allow-origin") == "*")
check(f"фильтры дошли до запроса ({ASKED})",
      ASKED == [(["B0G4S9SJ3M"], ["de", "es"])])
via_button = loc.export_payload("ZZJ9", pd.DataFrame(ROWS))
check("ответ маршрута байт в байт равен выгрузке кнопки",
      json.dumps(body, ensure_ascii=False, sort_keys=True)
      == json.dumps(via_button, ensure_ascii=False, sort_keys=True))
check("позиции по (товар, язык), ключ макета на месте",
      body["file_key"] == "ZZJ9"
      and [(i["asin"], i["lang"], len(i["layers"])) for i in body["items"]]
      == [("B0G4S9SJ3M", "de", 2), ("B0G4S9SJ3M", "es", 1)])

ASKED.clear()
st, _, body = call(auth="Bearer s3cret-token")
check(f"без параметров — без фильтра, всё переведённое ({ASKED})",
      ASKED == [(None, None)] and len(body["items"]) == 2)

st, hdr, body = call(method="OPTIONS")
check(f"OPTIONS для CORS — 204 и заголовки, без токена ({st})",
      st == 204 and "authorization" in hdr.get("access-control-allow-headers", "").lower())

# --- 4. сбой базы — JSON с причиной, не HTML
def broken(asins, langs):
    raise RuntimeError("relation figma_layers does not exist")


api.fetch_rows = broken
st, hdr, body = call(auth="Bearer s3cret-token")
check(f"сбой чтения — 500 ({st})", st == 500)
check("и это JSON с причиной, а не страница ошибки",
      hdr.get("content-type", "").startswith("application/json")
      and "RuntimeError" in body["error"] and "figma_layers" in body["error"])
api.fetch_rows = fake_fetch

# --- 5. обёртка распознаётся как ASGI-приложение
from streamlit.web.server.app_discovery import discover_asgi_app   # noqa: E402

_app = discover_asgi_app(ROOT / "app.py")
check(f"streamlit run app.py поднимет ASGI-обёртку ({_app.import_string})",
      _app.is_asgi_app and _app.import_string == "app:app")
check("main.py — обычный скрипт, не обёртка",
      not discover_asgi_app(ROOT / "main.py").is_asgi_app)
check("обёртка монтирует маршруты плагина",
      "routes=routes()" in (ROOT / "app.py").read_text(encoding="utf-8"))
check("зависимость закреплена: st.App есть с 1.64",
      "streamlit>=1.64" in (ROOT / "requirements.txt").read_text(encoding="utf-8"))

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
