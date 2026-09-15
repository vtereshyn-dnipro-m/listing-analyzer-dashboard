# -*- coding: utf-8 -*-
"""
tests/test_figma_plugin.py — обход плагина совпадает с обходом Listing Suite.

Плагин кладёт перевод в слой, найденный по `slot`. Слот считает
Listing Suite (services/figma.py::_walk_text) при чтении файла, а
плагин пересчитывает его сам на языковой странице — двумя разными
языками, Python и JavaScript. Разойдутся — переводы встанут не в те
строки, и это ХУДШИЙ исход: карточка выглядит правдоподобно, а текст
под картинкой чужой.

Поэтому проверяется не «плагин что-то находит», а РАВЕНСТВО: одно
и то же дерево скармливается обоим обходам, и списки «slot → текст»
обязаны совпасть буквально, включая порядок. Дерево собрано из
ловушек, на которых обходы расходятся чаще всего: картинка перед
текстом (индекс считается, слота нет), пустой и пробельный текст
(индекс считается, слота нет), скрытый слой, вложенный INSTANCE,
группа, опечатка `BB0…` в имени фрейма, два фрейма с одним именем.

JavaScript исполняется по-настоящему: Node, если есть, иначе
JavaScriptCore через `osascript -l JavaScript` (есть в любом macOS).
Без движка тест ПАДАЕТ, а не пропускает проверку: тест, который
молча проходит, когда не может проверить, — это тот же обман, что
и `or True`.

Запуск (pytest не нужен):  python tests/test_figma_plugin.py
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services import figma                                # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


CODE_JS = (ROOT / "figma-plugin/code.js").read_text(encoding="utf-8")


# ---------------------------------------------------------------- дерево
def T(text, **kw):
    return dict({"type": "TEXT", "name": "t", "characters": text}, **kw)


PAGE = {
    "type": "CANVAS", "name": "DE",
    "children": [
        # подпись товара на холсте: текст верхнего уровня, не фрейм — мимо
        T("54225000 B0G4S9SJ3M Battery stapler"),
        {"type": "FRAME", "name": "B0G4S9SJ3M.PT01", "children": [
            {"type": "RECTANGLE", "name": "photo"},               # 0: индекс есть, слота нет
            {"type": "FRAME", "name": "specs", "children": [       # 1
                T("1,500 mAh"),                                    # 1.0
                T(""),                                             # 1.1 пустой — индекс есть
                T("Batteriekapazität"),                            # 1.2
            ]},
            {"type": "GROUP", "name": "g", "children": [           # 2
                T("   "),                                          # 2.0 пробелы — индекс есть
                {"type": "INSTANCE", "name": "chip", "children": [ # 2.1
                    T("Spannung"),                                 # 2.1.0
                ]},
            ]},
            T("Akku-Tacker CC-36"),                                # 3
            T("Versteckt", visible=False),                         # 4 скрытый — считается
            T("Gemischt", mixed=True),                             # 5 смешанное оформление
        ]},
        # опечатка в имени: лишняя B перед ASIN
        {"type": "FRAME", "name": "BB0GJMT58WT.MAIN", "children": [T("Hauptbild")]},
        # два фрейма с одним именем — слот двусмысленный
        {"type": "FRAME", "name": "B0DUPLICAT.PT02", "children": [T("eins")]},
        {"type": "FRAME", "name": "B0DUPLICAT.PT02", "children": [T("zwei")]},
        # секция верхнего уровня — не фрейм, оба обхода её не смотрят
        {"type": "SECTION", "name": "s", "children": [
            {"type": "FRAME", "name": "B0INSECTIO.PT01", "children": [T("drin")]}]},
        # A+ модуль: в Python отложен, но обход по нему тот же
        {"type": "FRAME", "name": "carousel 2.2", "children": [T("A+")]},
    ],
}

LAYERS = [
    {"slot": "B0G4S9SJ3M.PT01#1.2", "text": "Batteriekapazität"},   # уже так
    {"slot": "B0G4S9SJ3M.PT01#2.1.0", "text": "Spannung NEU"},      # заменим
    {"slot": "B0G4S9SJ3M.PT01#9.9", "text": "nirgends"},            # слоя нет
    {"slot": "B0GJMT58WT.MAIN#0", "text": "Neu"},                   # через опечатку
    {"slot": "B0G4S9SJ3M.PT01#3", "text": "   "},                   # пустой перевод
    {"slot": "B0DUPLICAT.PT02#0", "text": "drei"},                  # двусмысленный
    {"slot": "B0G4S9SJ3M.PT01#5", "text": "Anders"},                # смешанный
]


# ---------------------------------------------------------------- Python
def python_slots(page: dict) -> list[tuple[str, str]]:
    out: list = []
    for node in page["children"]:
        if node.get("type") != "FRAME":
            continue
        found: list = []
        figma._walk_text(node, found, frame=str(node.get("name") or ""))
        out.extend((f["slot"], f["source_text"]) for f in found)
    return out


# ---------------------------------------------------------------- JavaScript
HARNESS = """
var PAGE = %(page)s;
var LAYERS = %(layers)s;
var bySlot = indexPage(PAGE);
var slots = [];
(PAGE.children || []).forEach(function (fr) {
  if (fr.type !== "FRAME") return;
  var found = [];
  walkText(fr, found, String(fr.name || ""), []);
  found.forEach(function (f) { slots.push([f.slot, f.text]); });
});
var rows = buildPlan(bySlot, LAYERS, function (n) { return !!n.mixed; });
// файл на несколько позиций: DE есть, ES нет — вторая позиция откладывается
var multi = planItems(payloadItems({ items: [
    { asin: "B0G4S9SJ3M", lang: "de", layers: LAYERS.slice(0, 2) },
    { asin: "B0G4S9SJ3M", lang: "es", layers: LAYERS.slice(0, 2) },
    { asin: "B0GJMT58WT", lang: "de", layers: [LAYERS[3]] }
  ]}), function (l) { return l === "de" ? bySlot : null; }, function (n) { return !!n.mixed; });
var single = payloadItems({ asin: "X", lang: "de", layers: [] });
var RESULT = JSON.stringify({
  multi: { rows: multi.rows.map(function (r) { return [r.asin, r.lang, r.slot, r.state]; }),
           skipped: multi.skipped },
  single_items: single.length,
  slots: slots,
  page_lang: PAGE_LANG,
  frame_re: %(names)s.map(function (n) { var m = FRAME_RE.exec(n);
    return m ? [m[1], m[2], m[3]] : null; }),
  plan: rows.map(function (r) { return [r.slot, r.state, r.now, r.want, r.typo]; }),
  summary: summarize(rows)
});
"""
NAMES = ["B0G4S9SJ3M.PT01", "BB0GJMT58WT.MAIN", "XB0FXY75N5G.MAIN",
         "carousel 2.2", "B0G4S9SJ3M", "ABCB0G4S9SJ3M.PT01", "b0g4s9sj3m.pt01"]


def run_js() -> dict:
    src = CODE_JS + "\n" + HARNESS % {
        "page": json.dumps(PAGE, ensure_ascii=False),
        "layers": json.dumps(LAYERS, ensure_ascii=False),
        "names": json.dumps(NAMES),
    }
    if shutil.which("node"):
        r = subprocess.run(["node", "-e", src + "\nconsole.log(RESULT);"],
                           capture_output=True, text=True, timeout=60)
        engine = "node"
    elif shutil.which("osascript"):
        r = subprocess.run(["osascript", "-l", "JavaScript", "-e", src + "\nRESULT;"],
                           capture_output=True, text=True, timeout=60)
        engine = "JavaScriptCore"
    else:
        sys.exit("FAIL: нет JavaScript-движка (node или osascript) — обход "
                 "плагина проверить нечем. Установите node.")
    if r.returncode != 0:
        sys.exit(f"FAIL: {engine} упал:\n{r.stderr[:800]}")
    print(f"  ..   JavaScript исполнен: {engine}")
    return json.loads(r.stdout.strip())


js = run_js()

# --- 1. обходы совпадают буквально, включая порядок
py = python_slots(PAGE)
check(f"Python и плагин нашли одни и те же слоты ({len(py)} шт.)",
      [list(x) for x in py] == js["slots"])
check("индексы считают ВСЕХ детей: картинка под #0 сдвигает текст на #1.0",
      ("B0G4S9SJ3M.PT01#1.0", "1,500 mAh") in py)
check("пустой и пробельный текст занимают индекс, но слота не дают",
      ("B0G4S9SJ3M.PT01#1.2", "Batteriekapazität") in py
      and not any(s.endswith("#1.1") or s.endswith("#2.0") for s, _ in py))
check("текст внутри INSTANCE и GROUP найден по полному пути",
      ("B0G4S9SJ3M.PT01#2.1.0", "Spannung") in py)
check("верхний фрейм пути не даёт: прямой ребёнок — это #3",
      ("B0G4S9SJ3M.PT01#3", "Akku-Tacker CC-36") in py)
check("секция верхнего уровня не обходится ни одним из двух",
      not any("B0INSECTIO" in s for s, _ in py)
      and not any("B0INSECTIO" in s for s, _ in js["slots"]))

# --- 2. общие константы не разошлись
check(f"PAGE_LANG одинаковый ({js['page_lang']})", js["page_lang"] == figma.PAGE_LANG)
py_re = [(list(m.groups()) if (m := figma.FRAME_RE.match(n)) else None) for n in NAMES]
py_re = [([g or "" for g in m] if m else None) for m in py_re]
check(f"FRAME_RE даёт те же разборы на {len(NAMES)} именах", py_re == js["frame_re"])
check("опечатка BB0… разбирается обоими, три лишние буквы — ни одним",
      py_re[1] is not None and py_re[5] is None)

# --- 3. план: каждое состояние названо, ничего не выбрано «первым попавшимся»
plan = {slot: (state, now, want, typo) for slot, state, now, want, typo in js["plan"]}
check("текст уже такой — «уже так», не замена",
      plan["B0G4S9SJ3M.PT01#1.2"][0] == "same")
check("другой текст — «заменим», и видно, что было",
      plan["B0G4S9SJ3M.PT01#2.1.0"][:3] == ("replace", "Spannung", "Spannung NEU"))
check("слота нет — «слоя нет», а не тихий пропуск",
      plan["B0G4S9SJ3M.PT01#9.9"][0] == "missing")
check("опечатка в имени фрейма находится и НАЗЫВАЕТСЯ",
      plan["B0GJMT58WT.MAIN#0"][0] == "replace" and plan["B0GJMT58WT.MAIN#0"][3] is True)
check("пустой перевод не затирает текст",
      plan["B0G4S9SJ3M.PT01#3"][0] == "empty")
check("два фрейма с одним именем — двусмысленно, не «первый попавшийся»",
      plan["B0DUPLICAT.PT02#0"][0] == "ambiguous")
check("смешанное оформление пропускается с именем причины",
      plan["B0G4S9SJ3M.PT01#5"][0] == "mixed")
check(f"итог считает каждое состояние ({js['summary']})",
      js["summary"] == {"replace": 2, "same": 1, "missing": 1,
                        "ambiguous": 1, "mixed": 1, "empty": 1})

# --- 3б. один файл на несколько товаров и языков
# «Выгрузить для Figma» из списка отдаёт {items: [...]}, где каждая
# позиция — та же единица, что одиночная выгрузка. Позиция без языковой
# страницы откладывается и НАЗЫВАЕТСЯ, остальные от этого не страдают.
m = js["multi"]
check("одиночная выгрузка читается как одна позиция", js["single_items"] == 1)
check(f"позиции с существующей страницей разобраны ({len(m['rows'])} строк)",
      [r[:2] for r in m["rows"]] == [["B0G4S9SJ3M", "de"]] * 2 + [["B0GJMT58WT", "de"]])
check("позиция без языковой страницы отложена и названа",
      m["skipped"] == [{"asin": "B0G4S9SJ3M", "lang": "es"}])
check("и не мешает остальным: их состояния те же, что поодиночке",
      [r[3] for r in m["rows"]] == ["same", "replace", "replace"])

# --- 4. плагин не применяет молча и не трогает лишнего
check("замена только по кнопке: план и применение — разные сообщения",
      'msg.type === "plan"' in CODE_JS and 'msg.type === "apply"' in CODE_JS)
check("шрифт грузится перед правкой текста",
      CODE_JS.index("loadFontAsync") < CODE_JS.index("node.characters = "))
check("меняется только characters — ни шрифт, ни кегль, ни картинки",
      not re.search(r"\.(fontName|fontSize|fills|resize|x|y)\s*=(?!=)", CODE_JS))
check("слои не создаются", "createText" not in CODE_JS and "clone(" not in CODE_JS)
check("сеть плагину не нужна",
      '"allowedDomains": ["none"]' in (ROOT / "figma-plugin/manifest.json").read_text())

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
