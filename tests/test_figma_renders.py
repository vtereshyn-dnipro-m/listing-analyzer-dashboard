# -*- coding: utf-8 -*-
"""
tests/test_figma_renders.py — картинку макета рендерим ОДИН раз.

У места View владельца токена Figma шесть запросов в МЕСЯЦ на чтение
файла и рендер вместе (тип лимита «low», проверено 27.09). Суточный
кэш в памяти терялся при каждом ребуте Cloud, а список и редактор
просили ссылку на каждую миниатюру и каждый слайд — 21 и 27 запросов.
Теперь рендер хранится в `figma_renders` навсегда, перерисовывается
только изменившийся узел, а недостающие рендерятся пачкой.

Проверяется ЦЕНА в запросах к Figma, а не наличие кэша:

1. пять недостающих узлов — ОДИН запрос рендера, и все пять легли
   в хранилище;
2. повторный показ — ноль запросов; «ребут» (сброс кэшей процесса) —
   тоже ноль: картинки из базы;
3. изменился один узел — один запрос, и только за ним;
4. отпечаток неизвестен (товар читали до миграции) — годится
   сохранённое, запроса нет;
5. 429 — сохранённое показывается, недостающее названо причиной,
   и дальше в Figma не ходим;
6. миграции нет — прежний путь, без записи в несуществующую таблицу.

И отпечаток узла: сдвиг фрейма по холсту и переименование его не
меняют (картинка та же), правка текста, заливки или сдвиг слоя
внутри — меняют.

psycopg2 и HTTP подменены: сеть и база не трогаются.

Запуск (pytest не нужен):  python tests/test_figma_renders.py
"""
from __future__ import annotations

import copy
import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


PNG = b"\x89PNG\r\n\x1a\n" + b"fake-image-"

# ------------------------------------------------------------ поддельная база
STORE: dict = {}                    # (file, node, scale) -> (hash, png)
STATE = {"migrated": True}


class _Cur:
    def execute(self, q, params=None):
        if "INSERT INTO figma_renders" in q:
            fk, node, scale, h, png, _n = params
            STORE[(fk, node, round(float(scale), 3))] = (h, bytes(png))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


class _Conn:
    def cursor(self):
        return _Cur()

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def fake_sql(sql, con=None, params=None, **kw):
    q = " ".join(str(sql).split())
    params = params or {}
    if "to_regclass" in q:
        return pd.DataFrame([{"t": "listing_data.figma_renders" if STATE["migrated"] else None}])
    if "information_schema.columns" in q:
        return pd.DataFrame({"column_name": ["node_hashes"] if STATE["migrated"] else []})
    if q.startswith("SELECT node_id, scale, node_hash FROM figma_renders"):
        return pd.DataFrame([{"node_id": n, "scale": s, "node_hash": h}
                             for (fk, n, s), (h, _p) in STORE.items() if fk == params["k"]],
                            columns=["node_id", "scale", "node_hash"])
    if q.startswith("SELECT png FROM figma_renders"):
        key = (params["k"], params["n"], round(float(params["s"]), 3))
        return pd.DataFrame([{"png": STORE[key][1]}]) if key in STORE else pd.DataFrame()
    return pd.DataFrame()


pd.read_sql = fake_sql
import services.db as db                                   # noqa: E402
db.get_conn = lambda: _Conn()

import services.figma as fg                                # noqa: E402
import services.localization as loc                        # noqa: E402
import streamlit as st                                     # noqa: E402

# ------------------------------------------------------------ поддельная Figma
RENDER_CALLS: list = []             # по списку узлов на каждый запрос /images
MODE = {"429": False}


class _Resp:
    def __init__(self, code=200, payload=None, content=b"", headers=None):
        self.status_code, self._p, self.content = code, payload or {}, content
        self.headers, self.text = headers or {}, ""

    def json(self):
        return self._p


def fake_get(url, params=None, headers=None, timeout=None):
    if "/images/" in url:
        ids = params["ids"].split(",")
        RENDER_CALLS.append(ids)
        if MODE["429"]:
            return _Resp(429, headers={"Retry-After": "266304",
                                       "X-Figma-Rate-Limit-Type": "low"})
        return _Resp(200, {"err": None, "images": {i: f"https://s3/{i}.png" for i in ids}})
    node = url.rsplit("/", 1)[-1].replace(".png", "")
    return _Resp(200, content=PNG + node.encode())


fg.requests.get = fake_get
fg.token = lambda: "tok"
fg.file_key = lambda: "FILE"
FK = "FILE"


def reset_caches():
    st.cache_data.clear()
    fg._IMG_PAUSE.update(until=0.0, reason="")


reset_caches()
NODES = [(f"1:{i}", f"h{i}") for i in range(1, 6)]

# --- 1. пять недостающих — ОДИН запрос рендера
out = loc.ensure_renders(FK, NODES, fg.IMAGE_SCALE)
check(f"пять недостающих узлов — один запрос рендера ({len(RENDER_CALLS)})",
      len(RENDER_CALLS) == 1 and sorted(RENDER_CALLS[0]) == sorted(n for n, _ in NODES))
check("все пять вернулись картинкой",
      all(out[n][0] and out[n][0].startswith(PNG) and out[n][1] is None for n, _ in NODES))
check("и все пять легли в хранилище с отпечатком",
      all(STORE.get((FK, n, 0.5), (None,))[0] == h for n, h in NODES))

# --- 2. повторно — ноль; «ребут» — тоже ноль
RENDER_CALLS.clear()
out2 = loc.ensure_renders(FK, NODES, fg.IMAGE_SCALE)
check("повторный показ — ни одного запроса к Figma", not RENDER_CALLS)
check("картинки те же", all(out2[n][0] == out[n][0] for n, _ in NODES))
reset_caches()                                        # как после ребута Cloud
out3 = loc.ensure_renders(FK, NODES, fg.IMAGE_SCALE)
check("после сброса кэшей процесса — тоже ноль: картинки из базы",
      not RENDER_CALLS and all(out3[n][0] == out[n][0] for n, _ in NODES))

# --- 3. изменился один узел — один запрос, только за ним
changed = [(n, (h + "-new") if n == "1:3" else h) for n, h in NODES]
loc.ensure_renders(FK, changed, fg.IMAGE_SCALE)
check(f"изменился один узел — один запрос, только за ним ({RENDER_CALLS})",
      RENDER_CALLS == [["1:3"]])
check("и в хранилище у него новый отпечаток", STORE[(FK, "1:3", 0.5)][0] == "h3-new")

# --- 4. отпечаток неизвестен — годится сохранённое
RENDER_CALLS.clear()
out4 = loc.ensure_renders(FK, [("1:1", ""), ("1:2", "")], fg.IMAGE_SCALE)
check("отпечаток неизвестен — сохранённое, без запроса",
      not RENDER_CALLS and out4["1:1"][0] is not None)

# --- 5. другой масштаб — отдельная картинка; миниатюры пачкой
out5 = loc.ensure_renders(FK, NODES, fg.THUMB_SCALE)
check(f"миниатюры (0.25) — своя пачка, один запрос ({len(RENDER_CALLS)})",
      len(RENDER_CALLS) == 1 and len(RENDER_CALLS[0]) == 5)

# --- 6. 429: сохранённое показывается, недостающее названо, дальше не ходим
RENDER_CALLS.clear()
MODE["429"] = True
mixed = changed + [("1:9", "h9")]                      # текущие отпечатки + новый узел
out6 = loc.ensure_renders(FK, mixed, fg.IMAGE_SCALE)
check("при 429 сохранённые (и свежие) картинки всё равно на экране",
      all(out6[n][0] is not None for n, _ in changed))
check(f"а недостающая названа причиной — место View ({out6['1:9'][1]})",
      out6["1:9"][0] is None and "место View" in (out6["1:9"][1] or ""))
loc.ensure_renders(FK, [("1:10", "h10"), ("1:11", "h11")], fg.IMAGE_SCALE)
check(f"после 429 в Figma больше не ходим ({len(RENDER_CALLS)} запрос)",
      len(RENDER_CALLS) == 1)
MODE["429"] = False
fg._IMG_PAUSE.update(until=0.0, reason="")

# --- 7. миграции нет — прежний путь, без записи в несуществующую таблицу
STATE["migrated"] = False
reset_caches()
before = dict(STORE)
_single: list = []
_real_png = fg.node_png
fg.node_png = lambda node_id, key=None, scale=fg.IMAGE_SCALE: (_single.append(node_id), (PNG, None))[1]
out7 = loc.ensure_renders(FK, [("2:1", "x")], fg.IMAGE_SCALE)
check("без миграции — прежний путь по одному узлу, хранилище не трогается",
      _single == ["2:1"] and out7["2:1"][0] == PNG and STORE == before)
fg.node_png = _real_png
STATE["migrated"] = True
reset_caches()

# --- 8. отпечаток узла: меняется от картинки, а не от места на холсте
FRAME = {"id": "5:1", "name": "B0X.PT01", "type": "FRAME",
         "absoluteBoundingBox": {"x": 100, "y": 200, "width": 500, "height": 500},
         "fills": [{"type": "SOLID", "color": {"r": 1, "g": 1, "b": 1}}],
         "children": [
             {"id": "5:2", "name": "title", "type": "TEXT", "characters": "Battery",
              "absoluteBoundingBox": {"x": 120, "y": 230, "width": 100, "height": 20}},
             {"id": "5:3", "name": "photo", "type": "RECTANGLE",
              "fills": [{"type": "IMAGE", "imageRef": "abc"}],
              "absoluteBoundingBox": {"x": 150, "y": 300, "width": 200, "height": 200}}]}
base = fg.node_hash(FRAME)


def moved(node, dx, dy):
    n = copy.deepcopy(node)
    stack = [n]
    while stack:
        cur = stack.pop()
        b = cur.get("absoluteBoundingBox")
        if b:
            b["x"] += dx
            b["y"] += dy
        stack.extend(cur.get("children") or [])
    return n


renamed = copy.deepcopy(FRAME)
renamed["name"] = "B0X.PT01 (old)"
retext = copy.deepcopy(FRAME)
retext["children"][0]["characters"] = "Batería"
refill = copy.deepcopy(FRAME)
refill["children"][1]["fills"][0]["imageRef"] = "def"
inner = copy.deepcopy(FRAME)
inner["children"][0]["absoluteBoundingBox"]["x"] += 10
check("сдвиг фрейма по холсту отпечаток не меняет", fg.node_hash(moved(FRAME, 3000, -700)) == base)
check("переименование — тоже", fg.node_hash(renamed) == base)
check("правка текста — меняет", fg.node_hash(retext) != base)
check("замена картинки в заливке — меняет", fg.node_hash(refill) != base)
check("сдвиг слоя ВНУТРИ фрейма — меняет", fg.node_hash(inner) != base)

# --- 9. разбор файла кладёт отпечатки всех узлов слайдов
DOC = {"document": {"children": [{"name": "UK/US", "children": [
    dict(FRAME, name="B0G4S9SJ3M.PT01", id="7:1"),
    dict(FRAME, name="B0G4S9SJ3M.MAIN", id="7:2", children=[])]}]}}
parsed = fg.parse_document(DOC)
prod = parsed["products"][0]
check(f"у каждого узла из lang_nodes есть отпечаток ({sorted(prod.get('node_hashes', {}))})",
      set(prod.get("node_hashes", {})) == {v for parts in prod["lang_nodes"].values()
                                          for v in parts.values()})

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
