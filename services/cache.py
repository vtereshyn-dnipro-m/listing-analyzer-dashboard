# -*- coding: utf-8 -*-
"""
services/cache.py — точечная инвалидация кэшей вместо глобальной.

`st.cache_data.clear()` сносит ВСЕ кэши приложения, а не свой. После
приёмки одного тайтла заново читались каталог, диагнозы, экономика, SQP
и трёхмегабайтные шаблоны flat file — на трёх страницах это десять
запросов к базе там, где по делу нужно два.

Здесь собраны группы «что поменялось → что перечитать». Каждая функция
чистит только то, на что действие реально влияет.

Ограничение, которое важно знать: отсюда достижимы только кэши
`services/*`. Загрузчики, живущие внутри страниц (`pages/*.py`), из
другого модуля не очистить — импорт страницы выполнил бы её целиком.
Поэтому страница чистит свои сама, вызывая эти функции следом. Кэши
ЧУЖОЙ страницы не чистит никто: они истекут по TTL (обычно 300 c).
Это осознанный размен — перечитать чужую страницу через пять минут
дешевле, чем перечитывать все страницы после каждого действия.

Исключение одно: сбор снапшотов. Он меняет данные, которые читают все
страницы разом, и там глобальный сброс честнее точечного.
"""
from __future__ import annotations

import streamlit as st


def drop(fn, *args) -> None:
    """Сбросить кэш функции. С аргументами — только одну запись.

    Ошибку глушим: инвалидация кэша не имеет права ронять действие,
    которое уже записалось в базу.
    """
    try:
        clear = getattr(fn, "clear", None)
        if clear is None:
            return
        clear(*args) if args else clear()
    except Exception:
        pass


def after_synthesis_change(asin: str | None = None,
                           mp: str | None = None) -> None:
    """Принята правка, сохранён результат или посчитан Coverage.

    Меняются synthesis_changes / synthesis_drafts / synthesis_coverage.
    Каталог, экономика, SQP и шаблоны flat file к этому отношения
    не имеют и перечитываться не должны.
    """
    from services import flatfile, history, worklog
    drop(flatfile.load_accepted_titles)
    drop(history.load_history)
    drop(worklog.load_worklog)


def after_push() -> None:
    """Отправка в Amazon: изменился listing_push_log."""
    from services import history, spapi
    drop(history.load_history)
    drop(spapi.load_pushes)


def after_matrix_change() -> None:
    """Добавили или удалили товары в матрице."""
    from services import flatfile, worklog
    drop(flatfile.load_sku_map)
    drop(worklog.load_worklog)


def after_keywords_change(asin: str | None = None,
                          mp: str | None = None) -> None:
    """Ручная разметка фраз в protected_keywords."""
    from services import seo
    drop(seo.load_sqp)


def after_settings_change() -> None:
    """Настройка сохранена: пороги и выбор модели читают все страницы,
    но через один кэш."""
    from services import settings
    drop(settings.load_settings)


def after_template_change() -> None:
    """Загружен эталон flat file — три мегабайта на строку, поэтому
    перечитывать его без причины особенно дорого."""
    from services import flatfile_template
    drop(flatfile_template.load_templates)


def after_photo_audit() -> None:
    """Сохранён аудит фото или A+."""
    from services import worklog
    drop(worklog.load_worklog)
