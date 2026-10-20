# -*- coding: utf-8 -*-
"""
services/title_rules.py — правила тайтла и Item Highlights кодом.

Один модуль на всех, кто проверяет тайтл: Синтез («Title AMZ»), будущий
«Генератор текстов (пилот)» и правило Диагноза. Раньше проверки жили прямо
в `pages/synthesis.py`, а страницу Streamlit из другой страницы не
импортировать, поэтому вторая страница получила бы копию. Модуль чистый:
ни Streamlit, ни базы — его возьмут и задача Databricks, и ноутбук сборщика.

Две части:

1. **Общие проверки** — то, что Синтез делал и раньше: запрещённые символы,
   повторы слов, длина, обрезка по границе слова, сохранность обязательных
   фраз. Перенесены из `pages/synthesis.py` без изменения поведения; это
   запирает `tests/test_title_rules.py` сверкой с прежней реализацией.
2. **Правила пилота** (`Ruleset` + `check`) — шаблон владельца для Amazon ES:
   бренд, формат единиц «2000W, 60Nm, Ø230mm, 6600rpm», никаких 220V и
   вольтажа аккумулятора у инструмента (у аккумуляторов и зарядок — можно),
   разделитель — запятая, Highlights «Model <модель>: …».

**Длина и позиция бренда — параметры, а не константы.** Владелец (20.10.2026)
не решил их до подтверждения в Seller Central: 75 знаков объявлены Amazon
с 27.07.2026, но Amazon на .es вырезал бренд из начала тайтла (живая
отправка 29.08.2026), и методология с v7 ставит первой ключевую фразу.
По умолчанию позиция бренда НЕ проверяется (`brand_position=None`): правило,
которое ещё не утверждено, не должно валить тайтлы.

Нарушение — код (`Violation.code`), а не текст: подписи на трёх языках даст
экран через `i18n`, а Диагнозу код нужен как `rule_id`-подобный признак.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ----------------------------------------------------------- общие проверки

# Набор Синтеза: правила Amazon от 21.01.2025 (`! $ ? _ { } ^ ¬ ¦`) плюс знаки
# ® © ™, которые методология не пускает в тайтл. Менять — меняется Синтез.
FORBIDDEN_CHARS = set("!$?_{}^¬¦®©™")

# Повторы слов: Amazon разрешает слово не больше двух раз, служебные слова
# не считаются. Список и алфавит — как в Синтезе до переноса.
_WORD_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁáéíóúñüÁÉÍÓÚÑÜäöüßÄÖÜ0-9]+")
STOP_WORDS = {"de", "con", "para", "y", "el", "la", "und", "mit", "für", "et", "avec", "e", "per"}


def norm_text(s: str) -> str:
    """Нижний регистр, знаки препинания — в пробелы, пробелы схлопнуты."""
    s = str(s).lower()
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def phrase_present(phrase: str, text: str) -> bool:
    """Фраза считается сохранённой, если все её значимые слова есть в тексте."""
    t = norm_text(text)
    words = [w for w in norm_text(phrase).split() if len(w) > 2]
    if not words:
        return False
    return all(w in t for w in words)


def keeps_all(text: str, hl: str, keep: list[str]) -> bool:
    """Все must_keep-фразы по-прежнему на месте (в title или highlights)."""
    combined = f"{text} {hl}"
    return all(phrase_present(p, combined) for p in keep)


def forbidden_chars(text: str, chars=FORBIDDEN_CHARS) -> list[str]:
    """Запрещённые символы, которые есть в тексте, по порядку."""
    return sorted({c for c in text if c in chars})


def repeated_words(text: str, max_count: int = 2) -> list[str]:
    """Слова (длиннее двух букв, не служебные), встречающиеся чаще `max_count`."""
    words = _WORD_RE.findall(text.lower())
    return sorted({w for w in words if len(w) > 2 and w not in STOP_WORDS and words.count(w) > max_count})


def trim_to_word(text: str, limit: int) -> str:
    """Обрезка строго по границе слова, никогда посреди слова.

    Хвостовую пунктуацию и разделители убираем: «…1650W ·» выглядит
    как обрыв, а не как законченный тайтл."""
    if len(text) <= limit:
        return text
    cut = text[:limit + 1]
    if " " in cut:
        cut = cut[:cut.rindex(" ")]
    else:
        cut = cut[:limit]           # одно слово длиннее лимита — режем как есть
    return cut.rstrip(" ,;·—–-|/")


def over_limits(res: dict, title_limit: int, hl_limit: int) -> list[str]:
    """Какие поля не влезли в лимит — для решения о повторе."""
    bad = []
    if len(str(res.get("title") or "")) > title_limit:
        bad.append(f"title {len(str(res.get('title') or ''))}/{title_limit}")
    if len(str(res.get("highlights") or "")) > hl_limit:
        bad.append("highlights "
                   f"{len(str(res.get('highlights') or ''))}/{hl_limit}")
    return bad


def enforce_limits(res: dict, must_keep: list[str], title_limit: int,
                   hl_limit: int) -> tuple[dict, dict]:
    """Последний рубеж: режем сами, но только если не теряем must_keep.

    Возвращает (результат, отметки). Если обрезка убивает обязательную
    фразу — НЕ режем: пусть человек правит руками, это честнее, чем
    молча выбросить фразу, по которой идут покупки."""
    marks = {"trimmed": [], "over": []}
    out = dict(res)
    for fld, limit, key in (("title", title_limit, "title"),
                            ("highlights", hl_limit, "highlights")):
        val = str(out.get(fld) or "")
        if len(val) <= limit:
            continue
        cand = trim_to_word(val, limit)
        probe = dict(out)
        probe[fld] = cand
        if cand and keeps_all(str(probe.get("title") or ""),
                              str(probe.get("highlights") or ""), must_keep):
            out[fld] = cand
            marks["trimmed"].append(key)
        else:
            marks["over"].append(key)
    return out, marks


# ------------------------------------------------------------ правила пилота

# Вида товара два: у инструмента вольтаж в тайтл не пишется никогда, у
# аккумуляторов и зарядок вольтаж — главная характеристика (владелец, 20.10).
TOOL, POWER_PACK = "tool", "power_pack"

# Единицы шаблона и их единственно верное написание. Число пишется вплотную:
# «2000W», «60Nm», «Ø230mm», «6600rpm».
UNITS = {"w": "W", "kw": "kW", "nm": "Nm", "mm": "mm", "cm": "cm", "rpm": "rpm",
         "j": "J", "ah": "Ah", "v": "V", "bar": "bar", "kg": "kg"}
_UNIT_ALT = "|".join(sorted(UNITS, key=len, reverse=True))
_NUM = r"\d+(?:[.,]\d+)*"
# Начало числа: перед ним не буква и не цифра — чтобы «M14», «BP-260» и
# «DHR-202BC» не читались как величины, — и не «цифра + точка/запятая»,
# чтобы «1,7J» было одним числом. «Ø», «ø» и «×» буквой НЕ считаются (с re.I
# «Ø» совпадает и с «ø», поэтому из класса убраны обе): «Ø230 mm» —
# как раз то, что надо проверять (замечание проверяющего #143: `\w` включает Ø,
# и число после него не проверялось вовсе). Запятая без пробела тоже не мешает:
# «2000W,60Nm» — два числа.
_LB = r"(?<![A-Za-z0-9_\u00C0-\u00D6\u00D9-\u00F6\u00F9-\u00FF\u0400-\u04FF])(?<!\d[.,])"
# Число и единица через пробел: «2000 W». Единица — целым словом.
_SPACED = re.compile(rf"{_LB}({_NUM})\s+({_UNIT_ALT})\b", re.I)
# Число вплотную к единице — для проверки регистра и разделителя тысяч.
_TIGHT = re.compile(rf"{_LB}({_NUM})({_UNIT_ALT})\b", re.I)
_THOUSANDS = re.compile(r"^\d{1,3}(?:[.,]\d{3})+$")
# Тысячи через пробел: «10 000rpm», «10 000 rpm» — частая запись в ES и FR.
_SPACE_THOUSANDS = re.compile(rf"{_LB}(\d{{1,3}}(?: \d{{3}})+)\s*({_UNIT_ALT})\b", re.I)
# Сетевое напряжение — никогда, ни у кого: 220V, 230 V, 220-240V.
_MAINS = re.compile(rf"{_LB}2[234]0\s*(?:[-–/]\s*2[234]0\s*)?V\b", re.I)
# Любой вольтаж: «20V», «12 V», «18,5V».
_VOLT = re.compile(rf"{_LB}({_NUM})\s*V\b", re.I)
# Ø и число через пробел: «Ø 230mm».
_DIAM_SPACE = re.compile(r"Ø\s+\d+(?:[.,]\d+)*")
# Разделители частей шаблона, кроме выбранного. Дефис без пробелов
# («SDS-Plus», «DGA-201M») разделителем не считается. Запятая не
# проверяется никогда: это и перечисление внутри части.
ALT_SEPARATORS = (" - ", " – ", " — ", " / ", ";")

# Разделитель частей шаблона — запятая (владелец, 20.10.2026). Вертикальная
# черта и её родственники запрещены: «|» Amazon сам ставит между тайтлом и
# Highlights, «¦» запрещён правилами 2025 года, «│» читается как декор.
PILOT_FORBIDDEN = FORBIDDEN_CHARS | set("|│┃¦")


@dataclass(frozen=True)
class Ruleset:
    """Параметры правил. Всё, что владелец ещё не решил, — здесь, а не в коде.

    `brand_position`:
        None      — не проверяется (по умолчанию, пока не решено);
        "start"   — тайтл начинается с бренда, регистр как в `brand`;
        "anywhere"— бренд где-то в тайтле, регистр как в `brand`;
        "absent"  — бренда в тайтле нет ни в каком регистре (методология v7:
                    Amazon его вырезает).

    `separator` — разделитель частей шаблона; остальные из `ALT_SEPARATORS`
    в тайтле — нарушение `SEPARATOR`. Вертикальная черта запрещена всегда
    (`forbidden`).
    """
    title_limit: int = 75
    highlight_limit: int = 125
    brand: str = "DNIPRO-M"
    brand_position: str | None = None
    separator: str = ","
    forbidden: frozenset = field(default_factory=lambda: frozenset(PILOT_FORBIDDEN))
    max_word_repeats: int = 2
    highlight_prefix: str = "Model {model}: "
    # Где вольтаж у инструмента — нарушение. Решение «у инструмента никогда»
    # (20.10.2026) по умолчанию держится строго, в обоих полях. Нужна ли
    # совместимость «baterías 20V» в Highlights — вопрос владельцу.
    tool_voltage_in: tuple = ("title", "highlights")


@dataclass(frozen=True)
class Violation:
    code: str
    field: str          # "title" | "highlights"
    detail: str = ""


BRAND_POSITIONS = (None, "start", "anywhere", "absent")


def _brand_in(text: str, brand: str, *, any_case: bool = False) -> int:
    """Позиция бренда целым словом; -1 — нет. «DNIPRO-MX» — не бренд,
    «DNIPRO-M-Amoladora» — бренд (за ним дефис, а не буква)."""
    m = re.search(rf"(?<![\w-]){re.escape(brand)}(?!\w)", text, re.I if any_case else 0)
    return m.start() if m else -1


def check(title: str, highlights: str = "", *, kind: str = TOOL, model: str | None = None,
          rules: Ruleset = Ruleset()) -> list[Violation]:
    """Нарушения правил пилота. Пусто — тайтл и Highlights по правилам.

    `kind` — TOOL или POWER_PACK (аккумулятор, зарядка). `model` — код
    модели для префикса Highlights; None — префикс не проверяется."""
    if rules.brand_position not in BRAND_POSITIONS:
        raise ValueError(f"brand_position: {rules.brand_position!r}, ждём одно из {BRAND_POSITIONS}")
    if kind not in (TOOL, POWER_PACK):
        raise ValueError(f"kind: {kind!r}, ждём {TOOL!r} или {POWER_PACK!r}")
    if rules.separator not in (",",) + ALT_SEPARATORS:
        raise ValueError(f"separator: {rules.separator!r}, ждём «,» или одно из {ALT_SEPARATORS}")
    title, highlights = str(title or ""), str(highlights or "")
    out: list[Violation] = []

    def add(code, fld, detail=""):
        out.append(Violation(code, fld, detail))

    if len(title) > rules.title_limit:
        add("TITLE_TOO_LONG", "title", f"{len(title)}/{rules.title_limit}")
    if len(highlights) > rules.highlight_limit:
        add("HIGHLIGHTS_TOO_LONG", "highlights", f"{len(highlights)}/{rules.highlight_limit}")

    for fld, text in (("title", title), ("highlights", highlights)):
        if not text:
            continue
        bad = forbidden_chars(text, rules.forbidden)
        if bad:
            add("FORBIDDEN_CHAR", fld, " ".join(bad))
        for m in _MAINS.finditer(text):
            add("MAINS_VOLTAGE", fld, m.group(0))
        if kind == TOOL and fld in rules.tool_voltage_in:
            mains = {m.span() for m in _MAINS.finditer(text)}
            for m in _VOLT.finditer(text):
                if not any(s <= m.start() < e for s, e in mains):
                    add("TOOL_VOLTAGE", fld, m.group(0))
        for m in _SPACED.finditer(text):
            add("UNIT_SPACING", fld, m.group(0))
        for m in _TIGHT.finditer(text):
            num, unit = m.group(1), m.group(2)
            if unit != UNITS[unit.lower()]:
                add("UNIT_CASE", fld, f"{m.group(0)} → {num}{UNITS[unit.lower()]}")
            if _THOUSANDS.match(num):
                add("UNIT_THOUSANDS", fld, f"{m.group(0)} → {re.sub(r'[.,]', '', num)}{UNITS[unit.lower()]}")
        for m in _SPACE_THOUSANDS.finditer(text):
            add("UNIT_THOUSANDS", fld, f"{m.group(0)} → {m.group(1).replace(' ', '')}{UNITS[m.group(2).lower()]}")
        for m in _DIAM_SPACE.finditer(text):
            add("DIAMETER_SPACING", fld, m.group(0))

    alt = [s for s in ALT_SEPARATORS if s != rules.separator and s in title]
    if alt:
        add("SEPARATOR", "title", f"{', '.join(repr(s) for s in alt)} → {rules.separator!r}")

    rep = repeated_words(title, rules.max_word_repeats)
    if rep:
        add("WORD_REPEATED", "title", ", ".join(rep))

    if rules.brand_position:
        exact = _brand_in(title, rules.brand)
        anyc = _brand_in(title, rules.brand, any_case=True)
        # Бренд в другом регистре («Dnipro-M» при «DNIPRO-M») — отдельный код:
        # это не «нет бренда» и не «не первым», а «бренд написан не так».
        if rules.brand_position == "start":
            if anyc != 0:
                add("BRAND_NOT_FIRST", "title", rules.brand)
            elif exact != 0:
                add("BRAND_CASE", "title", rules.brand)
        elif rules.brand_position == "anywhere":
            if anyc < 0:
                add("BRAND_MISSING", "title", rules.brand)
            elif exact < 0:
                add("BRAND_CASE", "title", rules.brand)
        # «Бренда быть не должно» — в любом регистре: в живых тайтлах он
        # «Dnipro-M», и Amazon вырезает его независимо от регистра.
        elif rules.brand_position == "absent" and anyc >= 0:
            add("BRAND_PRESENT", "title", rules.brand)

    if model is not None and highlights:
        prefix = rules.highlight_prefix.format(model=model)
        if not highlights.startswith(prefix):
            add("HIGHLIGHTS_PREFIX", "highlights", prefix.strip())

    return out


def codes(violations: list[Violation]) -> list[str]:
    """Коды без повторов, в порядке первого появления."""
    seen: list[str] = []
    for v in violations:
        if v.code not in seen:
            seen.append(v.code)
    return seen
