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

DEFAULT_LANG = "ru"

LANGS: dict[str, dict[str, str]] = {
    "en": {
        "app.tagline": "listing diagnostics",
        "nav.section.work": "Work",
        "nav.section.control": "Control",
        "nav.section.settings": "Settings",
        "nav.dashboard": "Diagnosis",
        "nav.diagnosis": "Diagnosis",
        "nav.catalog": "Catalog",
        "nav.analyzer": "Listing Score",
        "nav.media": "Photo · Video",
        "nav.synthesis": "Synthesis",
        "nav.changes": "Before / After",
        "nav.history": "History",
        "nav.matrix": "Product Matrix",
        "nav.keys": "Keys & Connections",
        "sidebar.deadline": "title deadline: **:red[{days} d.]**  \n75-char limit from 27.07.2026",
        "sidebar.deadline_passed": "**75-char** limit is live",
        "sidebar.next_run": "next run: daily 13:00 Kyiv",
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
        # --- Синтез
        "synth.select_title": "Title over limit",
        "synth.original": "Original",
        "synth.methodology": "methodology",
        "synth.protected": "Protected phrases",
        "synth.protected_hint": "must-keep verbatim · forbidden won't appear",
        "synth.add": "Add",
        "synth.generate": "Generate Split 75/125",
        "synth.result": "Split result",
        "synth.dropped": "Dropped — for review",
        "synth.checks": "Checks (by code, not AI)",
        "synth.checks_failed": "Some checks failed — regenerate or fix manually.",
        "synth.checks_ok": "All checks passed. Draft saved.",
        "synth.no_candidates": "No over-limit titles — nothing to split.",
        # --- Методология
        "meth.title": "Methodologies",
        "meth.caption": "Rules the AI follows for a specific task. Each scope has its own methodology and its own version history. Edit the text — save a new version — every following generation uses it. The code is untouched.",
        "meth.scope": "Scope",
        "meth.active_version": "active version",
        "meth.editor_placeholder": "Describe the rules for this scope...",
        "meth.save_as": "Save as",
        "meth.saved": "Saved — the new version is now active.",
        "meth.history": "Version history",
        "meth.active_label": "active",
        "meth.rollback": "Roll back to",
        "meth.empty_scope": "No methodology for this scope yet — write the text below and save the first version.",
        "meth.no_active": "No active version — save a new one or roll back an old one below.",
    },
    "ru": {
        "app.tagline": "диагностика листингов",
        "nav.section.work": "Работа",
        "nav.section.control": "Контроль",
        "nav.section.settings": "Настройка",
        "nav.dashboard": "Диагноз",
        "nav.diagnosis": "Диагноз",
        "nav.catalog": "Каталог",
        "nav.analyzer": "Оценка листинга",
        "nav.media": "Фото · Видео",
        "nav.synthesis": "Синтез",
        "nav.changes": "До / после",
        "nav.history": "История",
        "nav.matrix": "Матрица товаров",
        "nav.keys": "Ключи и подключения",
        "sidebar.deadline": "дедлайн тайтлов: **:red[{days} дн.]**  \nлимит 75 симв. с 27.07.2026",
        "sidebar.deadline_passed": "лимит **75 симв.** действует",
        "sidebar.next_run": "след. прогон: ежедневно 13:00 Kyiv",
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
        # --- Синтез
        "synth.select_title": "Тайтл с превышением",
        "synth.original": "Оригинал",
        "synth.methodology": "методология",
        "synth.protected": "Защищённые фразы",
        "synth.protected_hint": "must-keep дословно · запрещённые не появятся",
        "synth.add": "Добавить",
        "synth.generate": "Сгенерировать Split 75/125",
        "synth.result": "Результат сплита",
        "synth.dropped": "Выброшено — на ревью",
        "synth.checks": "Проверки (кодом, не ИИ)",
        "synth.checks_failed": "Есть проваленные проверки — перегенерируй или поправь руками.",
        "synth.checks_ok": "Все проверки пройдены. Черновик сохранён.",
        "synth.no_candidates": "Нет тайтлов с превышением — Синтезу нечего резать.",
        # --- Методология
        "meth.title": "Методологии",
        "meth.caption": "Правила, по которым ИИ выполняет конкретную задачу. Каждая область — своя методология и своя история версий. Правишь текст — сохраняешь новую версию — все следующие генерации идут по ней. Код не трогается.",
        "meth.scope": "Область применения",
        "meth.active_version": "активная версия",
        "meth.editor_placeholder": "Опиши правила для этой области...",
        "meth.save_as": "Сохранить как",
        "meth.saved": "Сохранено — теперь активна новая версия.",
        "meth.history": "История версий",
        "meth.active_label": "активная",
        "meth.rollback": "Откатиться на",
        "meth.empty_scope": "Для этой области методологии ещё нет — напиши текст ниже и сохрани первую версию.",
        "meth.no_active": "Нет активной версии — сохрани новую или откати старую ниже.",
    },
    "uk": {
        "app.tagline": "діагностика лістингів",
        "nav.section.work": "Робота",
        "nav.section.control": "Контроль",
        "nav.section.settings": "Налаштування",
        "nav.dashboard": "Діагноз",
        "nav.diagnosis": "Діагноз",
        "nav.catalog": "Каталог",
        "nav.analyzer": "Оцінка лістингу",
        "nav.media": "Фото · Відео",
        "nav.synthesis": "Синтез",
        "nav.changes": "До / після",
        "nav.history": "Історія",
        "nav.matrix": "Матриця товарів",
        "nav.keys": "Ключі та підключення",
        "sidebar.deadline": "дедлайн тайтлів: **:red[{days} дн.]**  \nліміт 75 симв. з 27.07.2026",
        "sidebar.deadline_passed": "ліміт **75 симв.** діє",
        "sidebar.next_run": "наст. прогін: щодня 13:00 Kyiv",
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
        # --- Синтез
        "synth.select_title": "Тайтл з перевищенням",
        "synth.original": "Оригінал",
        "synth.methodology": "методологія",
        "synth.protected": "Захищені фрази",
        "synth.protected_hint": "must-keep дослівно · заборонені не з'являться",
        "synth.add": "Додати",
        "synth.generate": "Згенерувати Split 75/125",
        "synth.result": "Результат спліта",
        "synth.dropped": "Викинуто — на рев'ю",
        "synth.checks": "Перевірки (кодом, не ШІ)",
        "synth.checks_failed": "Є провалені перевірки — перегенеруй або виправ вручну.",
        "synth.checks_ok": "Всі перевірки пройдено. Чернетку збережено.",
        "synth.no_candidates": "Немає тайтлів з перевищенням — Синтезу нічого різати.",
        # --- Методология
        "meth.title": "Методології",
        "meth.caption": "Правила, за якими ШІ виконує конкретну задачу. Кожна область — своя методологія і своя історія версій. Правиш текст — зберігаєш нову версію — усі наступні генерації йдуть за нею. Код не чіпається.",
        "meth.scope": "Область застосування",
        "meth.active_version": "активна версія",
        "meth.editor_placeholder": "Опиши правила для цієї області...",
        "meth.save_as": "Зберегти як",
        "meth.saved": "Збережено — тепер активна нова версія.",
        "meth.history": "Історія версій",
        "meth.active_label": "активна",
        "meth.rollback": "Відкотитися на",
        "meth.empty_scope": "Для цієї області методології ще немає — напиши текст нижче і збережи першу версію.",
        "meth.no_active": "Немає активної версії — збережи нову або відкоти стару нижче.",
    },
}

LANG_LABELS = {"ru": "РУ", "uk": "УКР", "en": "EN"}
LANG_TITLE = {"ru": "Смена языка", "uk": "Зміна мови", "en": "Language"}


def current_lang() -> str:
    return st.session_state.get("lang", DEFAULT_LANG)


def t(key: str, **kwargs) -> str:
    """Перевод по ключу с подстановками: t('dash.header', n=187, days=16)."""
    lang = current_lang()
    s = LANGS.get(lang, {}).get(key) or LANGS[DEFAULT_LANG].get(key) or key
    return s.format(**kwargs) if kwargs else s


def lang_selector() -> None:
    """Пилюли смены языка — как в Кабинете (активная красная)."""
    cur = current_lang()
    st.caption(LANG_TITLE.get(cur, "Language"))
    codes = ["ru", "uk", "en"]
    try:
        choice = st.segmented_control(
            "lang", codes, default=cur if cur in codes else DEFAULT_LANG,
            format_func=lambda c: LANG_LABELS.get(c, c.upper()),
            label_visibility="collapsed", key="lang_seg",
        )
    except AttributeError:  # фолбэк для старого Streamlit без segmented_control
        idx = codes.index(cur) if cur in codes else 0
        choice = st.radio(
            "lang", codes, index=idx, horizontal=True,
            format_func=lambda c: LANG_LABELS.get(c, c.upper()),
            label_visibility="collapsed", key="lang_seg",
        )
    if choice and choice != cur:
        st.session_state["lang"] = choice
        st.rerun()


