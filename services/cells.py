# -*- coding: utf-8 -*-
"""
services/cells.py — значение ячейки DataFrame строкой, с NaN как пустотой.

Правило 4 проекта. `x or ""` выглядит защитой от пустоты, но NaN
в Python ИСТИННЫЙ: наружу выходит float, `.strip()` и срез на нём
падают с AttributeError / TypeError, а `str(x or "")` молча печатает
«nan» там, где должно быть пусто. Пустая колонка из LEFT JOIN
и целиком пустая колонка (pandas делает её float64) приходят именно
NaN, а не None.

Так «Контент» упал 10.09; ещё восемь таких чтений — `sku_group`,
`cause`, `action`, `scopes` и другие — «nan» не роняли, а показывали.
Один хелпер вместо восьми повторов условия, и он же — эталон для
следующих.
"""
from __future__ import annotations

import pandas as pd


def cell_text(row, col: str, default: str = "") -> str:
    """Строка из ячейки; NaN, None и NaT — `default`.

    `row` — Series или dict: у обоих есть `.get`. Число приходит
    числом и превращается в строку как есть — «17557000», а не
    «17557000.0» — только если колонка не стала float из-за NaN
    в соседях; такое место лучше читать через `int()` отдельно.
    """
    val = row.get(col) if hasattr(row, "get") else None
    try:
        if val is None or pd.isna(val):
            return default
    except (TypeError, ValueError):
        # pd.isna на списке/массиве отдаёт массив — это не пустота
        pass
    return str(val)
