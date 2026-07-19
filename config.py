# -*- coding: utf-8 -*-
"""
config.py — единственный источник констант проекта.
Меняется здесь -> меняется везде (страницы, сервисы, промпты).
"""

from datetime import date

# Лимиты Amazon с 27.07.2026
TITLE_LIMIT = 75          # максимум символов тайтла
HIGHLIGHTS_LIMIT = 125    # поле Item Highlights (searchable)

# Дедлайн ввода нового формата
TITLE_DEADLINE = date(2026, 7, 27)

# Пороги диагностики (источник — здесь)
STALE_DAYS = 7            # снапшот старше — «нет данных»
LOW_REVIEWS_RATIO = 0.25  # < 25% медианы конкурентов = боль LOW_REVIEWS
MIN_IMAGES = 5            # меньше — боль NO_IMAGES

APP_NAME = "Listing Suite"
APP_TAGLINE = "диагностика листингов"


def days_to_deadline() -> int:
    """Дней до 27.07.2026 (для виджета в сайдбаре и правила TITLE_OVER_75)."""
    return max((TITLE_DEADLINE - date.today()).days, 0)
