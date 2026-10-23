"""Факты паспорта SKU (docx) для генерации текстов (решение владельца 21.10.2026).

Паспорт — каноническая форма: заголовки разделов (стиль Heading1) и таблицы под
ними. В модель идут только разделы-источники фактов. «Конфлікти» не идут вовсе —
их факты не использовать (решение владельца по 99601000-B), они выводятся на
экран списком «нужно решение». Служебные разделы (прогалины, источники, контроль
версии) тоже не идут: это не факты о товаре.

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


@dataclass
class Section:
    title: str
    rows: list[list[str]] = field(default_factory=list)   # первая строка — шапка таблицы


def conflict_tokens(conflicts: list[dict]) -> set[str]:
    """Коды и величины из сторон конфликтов, нормализованные (без пробелов, нижний регистр)."""
    out = set()
    for c in conflicts:
        for side in (c.get("a") or "", c.get("b") or ""):
            out |= {_norm(m.group(0)) for m in _CODE.finditer(side)}
            out |= {_norm(m.group(0)) for m in _QTY.finditer(side)}
    return out


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
    conflicts: list[dict]        # {id, field, a, b, status}
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
        if self.conflicts:
            out.append("## НЕ ИСПОЛЬЗОВАТЬ — открытые конфликты паспорта (нужно решение)")
            out += [f"- {c['field']}" for c in self.conflicts if c["field"]]
        return "\n".join(out)


def _text(el) -> str:
    return "".join(x.text or "" for x in el.iter(W + "t")).strip()


def _style(p) -> str:
    st = p.find(f"{W}pPr/{W}pStyle")
    return (st.get(f"{W}val") or "") if st is not None else ""


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
            for r in s.rows[1:]:
                r = (r + [""] * 5)[:5]
                conflicts.append({"id": r[0], "field": r[1], "a": r[2], "b": r[3], "status": r[4]})
        elif low.startswith(FACT_SECTIONS):
            facts.append(s)
    return Facts(facts, conflicts)
