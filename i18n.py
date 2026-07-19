# -*- coding: utf-8 -*-
"""
i18n.py — переводы интерфейса. ru / uk / en.

Использование на любой странице:
    from i18n import t, lang_selector
    st.title(t("nav.dashboard"))

Добавить язык = добавить словарь в LANGS. Ключа нет в языке -> фолбэк en ->
сам ключ (видно в UI, что перевод забыт — честно, без тихих дыр).
"""

import streamlit as st

DEFAULT_LANG = "en"

LANGS: dict[str, dict[str, str]] = {
    "en": {
        "app.tagline": "listing diagnostics",
        "nav.section.work": "Work",
        "nav.section.control": "Control",
        "nav.section.settings": "Settings",
        "nav.dashboard": "Diagnosis",
        "nav.catalog": "Catalog 75/125",
        "nav.analyzer": "Listing Score",
        "nav.media": "Photo · Video",
        "nav.synthesis": "Synthesis",
        "nav.changes": "Before / After",
        "nav.history": "History",
        "nav.matrix": "Product Matrix",
        "nav.keys": "Keys & Connections",
        "sidebar.deadline": "title deadline: **:red[{days} d.]**  \n75-char limit from 27.07.2026",
        "sidebar.deadline_passed": "**75-char** limit is live",
        "common.no_data": "No data yet — run batch_fetch first",
        "common.our": "ours",
        "common.competitor": "competitor",
        "dash.header": "{n} titles will be rewritten by Amazon in {days} days",
        "dash.reason": "Reason: 75-char limit from 27.07 · At risk: {money}/mo revenue",
        "dash.fix_all_csv": "Fix all → CSV",
        "dash.top10": "Top-10 by revenue first",
        "dash.no_diagnosis": "Diagnosis not run yet — waiting for services/diagnose.py cron",
        "pain.fix_now": "fix now",
        "pain.test": "test via before/after",
    },
    "ru": {
        "app.tagline": "диагностика листингов",
        "nav.section.work": "Работа",
        "nav.section.control": "Контроль",
        "nav.section.settings": "Настройка",
        "nav.dashboard": "Диагноз",
        "nav.catalog": "Каталог 75/125",
        "nav.analyzer": "Оценка листинга",
        "nav.media": "Фото · Видео",
        "nav.synthesis": "Синтез",
        "nav.changes": "До / после",
        "nav.history": "История",
        "nav.matrix": "Матрица товаров",
        "nav.keys": "Ключи и подключения",
        "sidebar.deadline": "дедлайн тайтлов: **:red[{days} дн.]**  \nлимит 75 симв. с 27.07.2026",
        "sidebar.deadline_passed": "лимит **75 симв.** действует",
        "common.no_data": "Данных ещё нет — сначала прогони batch_fetch",
        "common.our": "наш",
        "common.competitor": "конкурент",
        "dash.header": "{n} тайтлов перепишет Amazon через {days} дней",
        "dash.reason": "Причина: лимит 75 симв. с 27.07 · Под риском: {money}/мес revenue",
        "dash.fix_all_csv": "Исправить все → CSV",
        "dash.top10": "Сначала топ-10 по revenue",
        "dash.no_diagnosis": "Диагноз ещё не запускался — ждёт cron services/diagnose.py",
        "pain.fix_now": "чинить сразу",
        "pain.test": "тест через до/после",
    },
    "uk": {
        "app.tagline": "діагностика лістингів",
        "nav.section.work": "Робота",
        "nav.section.control": "Контроль",
        "nav.section.settings": "Налаштування",
        "nav.dashboard": "Діагноз",
        "nav.catalog": "Каталог 75/125",
        "nav.analyzer": "Оцінка лістингу",
        "nav.media": "Фото · Відео",
        "nav.synthesis": "Синтез",
        "nav.changes": "До / після",
        "nav.history": "Історія",
        "nav.matrix": "Матриця товарів",
        "nav.keys": "Ключі та підключення",
        "sidebar.deadline": "дедлайн тайтлів: **:red[{days} дн.]**  \nліміт 75 симв. з 27.07.2026",
        "sidebar.deadline_passed": "ліміт **75 симв.** діє",
        "common.no_data": "Даних ще немає — спочатку прожени batch_fetch",
        "common.our": "наш",
        "common.competitor": "конкурент",
        "dash.header": "{n} тайтлів перепише Amazon через {days} днів",
        "dash.reason": "Причина: ліміт 75 симв. з 27.07 · Під ризиком: {money}/міс revenue",
        "dash.fix_all_csv": "Виправити все → CSV",
        "dash.top10": "Спочатку топ-10 за revenue",
        "dash.no_diagnosis": "Діагноз ще не запускався — чекає cron services/diagnose.py",
        "pain.fix_now": "чинити одразу",
        "pain.test": "тест через до/після",
    },
}

LANG_LABELS = {"en": "EN", "ru": "RU", "uk": "UA"}


def current_lang() -> str:
    return st.session_state.get("lang", DEFAULT_LANG)


def t(key: str, **kwargs) -> str:
    """Перевод по ключу с подстановками: t('dash.header', n=187, days=16)."""
    lang = current_lang()
    s = LANGS.get(lang, {}).get(key) or LANGS[DEFAULT_LANG].get(key) or key
    return s.format(**kwargs) if kwargs else s


def lang_selector() -> None:
    """Переключатель языка для сайдбара."""
    codes = list(LANGS.keys())
    cur = current_lang()
    idx = codes.index(cur) if cur in codes else 0
    choice = st.radio(
        "language", codes, index=idx, horizontal=True,
        format_func=lambda c: LANG_LABELS.get(c, c.upper()),
        label_visibility="collapsed", key="lang_radio",
    )
    if choice != cur:
        st.session_state["lang"] = choice
        st.rerun()
