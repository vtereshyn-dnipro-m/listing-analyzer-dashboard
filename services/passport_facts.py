"""Факты паспорта SKU (docx) для генерации текстов (решение владельца 21.10.2026).

Паспорт — каноническая форма: заголовки разделов (стиль Heading1) и таблицы под
ними. В модель идут только разделы-источники фактов. Раздел «Конфлікти» сам в
модель не идёт: значения ОТКРЫТОГО конфликта не использовать (решение владельца
по 99601000-B), они выводятся на экран списком «нужно решение». Конфликт,
закрытый статусом в самом паспорте, значений не вырезает; конфликт, решённый
верификатором (`passport_conflict_decisions`, решение владельца 28.10.2026), —
тоже, а решённое значение идёт в модель отдельным разделом. Служебные разделы
(прогалины, источники, контроль версии) не идут: это не факты о товаре.

Разбор чистый — без Streamlit и базы; копию паспорта читает вызывающий.
"""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# Разделы-источники фактов, по началу заголовка (регистр не важен).
FACT_SECTIONS = ("ідентичність", "технічні характеристики", "комплектація",
                 "сумісні аксесуари", "сценарії використання", "кандидати jbtd")
CONFLICT_SECTION = "конфлікти"
# Колонки-ссылки на источники в модель не идут: это шум, а не факт о товаре.
SOURCE_COLS = ("джерело", "evidence")
SOURCE_MARK = "джерел"          # «Статус / джерела» и подобные — тоже ссылки

# Значения сторон конфликта, по которым узнаётся строка факта: коды моделей
# («BP-240», «FC-230») и величины («36 В», «4 Ah», «45×20×45 cm», «39 minutes»).
# Строка факта с таким значением в модель НЕ идёт — запрет конфликта держит код,
# а не послушание модели (проверка #167). Фильтр с запасом: уходит и соседний
# факт с тем же кодом — лишнее молчание дешевле выдуманного комплекта.
_CODE = re.compile(r"\b[A-ZА-ЯІЇЄ]{1,4}-\d{2,4}[A-Z]{0,3}\b")
_QTY = re.compile(r"\b\d+(?:[.,]\d+)?\s?(?:[×x]\s?\d+(?:[.,]\d+)?\s?)*"
                  r"(?:В|V|Ah|А·год|Аг|mAh|W|Вт|cm|см|mm|мм|kg|кг|L|л|min|хв|minutes|months|місяц\w*|years?|рок\w*|рік)\b",
                  re.I)


# Статус конфликта в паспорте (решение владельца 28.10.2026): закрытым считается
# только статус, начинающийся с RESOLVED, CLOSED, DECIDED или SCOPED_APART. Всё
# прочее — OPEN_*, пустое, незнакомое, опечатка — открытый и вырезается: ошибиться
# в сторону «не дать модели» дешевле, чем пропустить спорное значение. В каноне
# словаря закрытых статусов нет — список ушёл вопросом Ярославу.
CLOSED_STATUSES = ("RESOLVED", "CLOSED", "DECIDED", "SCOPED_APART")
DECISIONS = ("SIDE_A", "SIDE_B", "VALUE")


def is_closed_status(status) -> bool:
    s = status.strip().upper() if isinstance(status, str) else ""
    return bool(s) and s.startswith(CLOSED_STATUSES)


def is_open(c: dict) -> bool:
    """Открыт: нет решения верификатора и статус в паспорте не закрытый."""
    return not c.get("decision") and not is_closed_status(c.get("status"))


def decided_value(c: dict) -> str:
    """Значение, выбранное решением: записанное значение, а без него — текст
    выбранной стороны (A или B). Своё значение (VALUE) пишется всегда."""
    d = c.get("decision") or {}
    kind = d.get("decision")
    if isinstance(d.get("value"), str) and d["value"].strip():
        return d["value"].strip()
    return c.get("a", "") if kind == "SIDE_A" else c.get("b", "") if kind == "SIDE_B" else ""


@dataclass
class Section:
    title: str
    rows: list[list[str]] = field(default_factory=list)   # первая строка — шапка таблицы


def side_tokens(text: str) -> set[str]:
    """Коды и величины текста, нормализованные (без пробелов, нижний регистр)."""
    text = text or ""
    return {_norm(m.group(0)) for m in _CODE.finditer(text)} | {_norm(m.group(0)) for m in _QTY.finditer(text)}


def conflict_tokens(conflicts: list[dict]) -> set[str]:
    """Значения, которые в модель не идут. Открытый конфликт — обе стороны.
    Решённый верификатором — стороны за вычетом выбранного значения: отвергнутая
    сторона по-прежнему не идёт. Закрытый статусом в паспорте — ничего."""
    out = set()
    for c in conflicts:
        sides = side_tokens(c.get("a")) | side_tokens(c.get("b"))
        if c.get("decision"):
            out |= sides - side_tokens(decided_value(c))
        elif not is_closed_status(c.get("status")):
            out |= sides
    return out


def identity_value(facts: "Facts", label: str) -> str | None:
    """Значение строки «Поле»/«Характеристика» = label (например «модель»)."""
    for s in facts.sections:
        if not s.rows:
            continue
        head = [h.strip().lower() for h in s.rows[0]]
        for r in s.rows[1:]:
            row = dict(zip(head, r))
            name = row.get("поле") or row.get("характеристика") or ""
            if name.strip().lower() == label and row.get("значення"):
                return row["значення"].strip()
    return None


def apply_decisions(facts: "Facts", decisions: dict) -> "Facts":
    """Решения верификатора по id конфликта этой копии. Решение по id, которого в
    копии нет, не применяется: оно о другом паспорте."""
    for c in facts.conflicts:
        d = decisions.get(c.get("id"))
        if d and d.get("decision") in DECISIONS:
            c["decision"] = d
    return facts


def _norm(x: str) -> str:
    return re.sub(r"\s+", "", x).lower()


def has_tokens(text: str, tokens: set[str]) -> list[str]:
    """ВСЕ значения конфликта, найденные в тексте, в постоянном порядке (по
    алфавиту). Раньше бралось первое из множества: при равной длине («20в»,
    «36в», «40в») порядок множества зависел от запуска процесса, и подпись
    FACT-006 менялась от перезапуска к перезапуску при том же паспорте."""
    flat = _norm(text)
    return sorted(tk for tk in tokens if tk and tk in flat)


@dataclass
class Facts:
    sections: list[Section]
    conflicts: list[dict]        # {id, field, a, b, status, source, decision}
    dropped: list[str] = field(default_factory=list)   # строки фактов, снятые из-за конфликта

    def prompt_text(self) -> str:
        """Разделы-источники как текст: заголовок, затем строки «колонка: значение»;
        в конце — поля открытых конфликтов, которые использовать нельзя."""
        out = []
        tokens = conflict_tokens(self.conflicts)
        self.dropped = []
        for s in self.sections:
            out.append(f"## {s.title}")
            if not s.rows:
                continue
            head, body = s.rows[0], s.rows[1:]
            for r in body:
                cells = [f"{h}: {v}" for h, v in zip(head, r)
                         if v and not h.strip().lower().startswith(SOURCE_COLS) and SOURCE_MARK not in h.lower()]
                if not cells:
                    continue
                hits = has_tokens(" ".join(r), tokens)
                if hits:
                    self.dropped.append(f"{r[0]} ({', '.join(hits)})")
                    continue
                out.append("- " + " | ".join(cells))
        decided = [c for c in self.conflicts if c.get("decision") and c["field"]]
        if decided:
            out.append("## РЕШЕНИЯ ПО КОНФЛИКТАМ — использовать эти значения")
            out += [f"- {c['field']}: {decided_value(c)}" for c in decided]
        still = [c for c in self.conflicts if is_open(c) and c["field"]]
        if still:
            out.append("## НЕ ИСПОЛЬЗОВАТЬ — открытые конфликты паспорта (нужно решение)")
            out += [f"- {c['field']}" for c in still]
        return "\n".join(out)


def _text(el) -> str:
    return "".join(x.text or "" for x in el.iter(W + "t")).strip()


def _style(p) -> str:
    st = p.find(f"{W}pPr/{W}pStyle")
    return (st.get(f"{W}val") or "") if st is not None else ""


def _conflict_columns(head: list[str]) -> dict:
    """Колонки таблицы «Конфлікти» по шапке; без узнанной шапки — по местам, как
    в v2: ID, Поле, Сторона A, Сторона B, Статус. «Джерело рішення» — если есть."""
    col = {"id": 0, "field": 1, "a": 2, "b": 3, "status": 4}
    for i, h in enumerate(x.strip().lower() for x in head):
        if "рішен" in h or "decision" in h:
            col["source"] = i
        elif h.startswith("статус") or h.startswith("status"):
            col["status"] = i
        elif h.endswith(" a") or h == "a":
            col["a"] = i
        elif h.endswith(" b") or h == "b":
            col["b"] = i
        elif h in ("поле", "field"):
            col["field"] = i
        elif h == "id":
            col["id"] = i
    return col


def read(data: bytes) -> Facts:
    """Разделы паспорта по порядку тела документа. Шапка (первая таблица до
    первого раздела) сюда не входит — её читает `passport_copies.read_header`."""
    root = ET.fromstring(zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml"))
    body = root.find(W + "body")
    cur: Section | None = None
    all_sections: list[Section] = []
    for el in list(body) if body is not None else []:
        if el.tag == W + "p" and _style(el).lower().startswith("heading1"):
            cur = Section(_text(el))
            all_sections.append(cur)
        elif el.tag == W + "tbl" and cur is not None:
            for tr in el.iter(W + "tr"):
                cur.rows.append([_text(tc) for tc in tr.findall(W + "tc")])
    facts, conflicts = [], []
    for s in all_sections:
        low = s.title.strip().lower()
        if low.startswith(CONFLICT_SECTION):
            col = _conflict_columns(s.rows[0] if s.rows else [])
            for r in s.rows[1:]:
                r = r + [""] * (max(col.values()) + 1 - len(r))
                conflicts.append({k: r[i] for k, i in col.items() if k != "source"}
                                 | {"source": r[col["source"]] if "source" in col else ""})
        elif low.startswith(FACT_SECTIONS):
            facts.append(s)
    return Facts(facts, conflicts)
