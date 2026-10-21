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


@dataclass
class Section:
    title: str
    rows: list[list[str]] = field(default_factory=list)   # первая строка — шапка таблицы


@dataclass
class Facts:
    sections: list[Section]
    conflicts: list[dict]        # {id, field, a, b, status}

    def prompt_text(self) -> str:
        """Разделы-источники как текст: заголовок, затем строки «колонка: значение»;
        в конце — поля открытых конфликтов, которые использовать нельзя."""
        out = []
        for s in self.sections:
            out.append(f"## {s.title}")
            if not s.rows:
                continue
            head, body = s.rows[0], s.rows[1:]
            for r in body:
                cells = [f"{h}: {v}" for h, v in zip(head, r)
                         if v and not h.strip().lower().startswith(SOURCE_COLS)]
                if cells:
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
