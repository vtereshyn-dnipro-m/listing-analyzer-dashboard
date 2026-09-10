# -*- coding: utf-8 -*-
"""
services/memprobe.py — ВРЕМЕННЫЙ замер памяти процесса.

Ставится ради одного вопроса: упирается ли приложение в лимит
бесплатного тарифа Streamlit Cloud (около гигабайта на приложение).
Ответили — модуль вынимается вместе с вызовами в app.py. Он намеренно
маленький и без зависимостей: тащить psutil ради разовой цифры значит
оставить его в requirements навсегда.

ЧТО ИМЕННО МЕРЯЕТСЯ, иначе цифры прочтут неверно.

RSS — сколько памяти процесс держит у операционной системы СЕЙЧАС.
Именно по нему Cloud убивает приложение, поэтому меряем его, а не
размеры объектов Python.

Пик (`ru_maxrss`) — наибольшее значение RSS за всю жизнь процесса.
Он важнее текущего: убивают по пику, а не по среднему.

ГЛАВНАЯ ОГОВОРКА. Разница «до страницы / после страницы» — это НЕ
цена страницы. Python отдаёт освобождённую память операционной системе
неохотно: аллокатор держит её под будущие объекты. Поэтому RSS растёт
и почти не падает, и вторая по счёту тяжёлая страница покажет прирост
меньше своей настоящей цены — часть она возьмёт из того, что осталось
от первой. Читать эти числа надо как «сколько процесс занял к этому
моменту», а порядок обхода страниц влияет на раскладку.

Отсюда же способ померить страницу честно: открыть её ПЕРВОЙ после
перезапуска приложения. Тогда прирост от базового уровня и есть её
цена, а панель показывает базовый уровень отдельной строкой.

Откуда берётся RSS. На Linux (а Cloud — Linux) из `/proc/self/status`,
это стандартная библиотека и никаких прав не нужно. На macOS такого
файла нет, поэтому локально текущий RSS недоступен и панель честно
говорит «—», а пик берётся из `resource` — он есть везде. Единицы
у `ru_maxrss` разные: на Linux килобайты, на macOS байты.
"""
from __future__ import annotations

import pathlib
import resource
import sys

import streamlit as st

KEY = "memprobe"                 # {страница: {...}} в session_state
BASE = "memprobe-base"           # RSS до первой отрисованной страницы

# Лимит бесплатного тарифа Streamlit Cloud. Число ориентировочное:
# Streamlit его не публикует как гарантию, и оно менялось. Нужно оно
# только чтобы показать ЗАПАС, поэтому берём консервативно 1 ГБ.
CLOUD_LIMIT_MB = 1024.0


def rss_mb() -> float | None:
    """Текущий RSS процесса в мегабайтах. None — измерить нечем."""
    try:
        for line in pathlib.Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024.0
    except Exception:
        pass
    return None


def peak_mb() -> float | None:
    """Наибольший RSS за жизнь процесса, в мегабайтах."""
    try:
        raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except Exception:
        return None
    # Linux отдаёт килобайты, macOS — байты. Различаем по платформе,
    # а не по величине: порог «больше миллиона — значит байты» на
    # Linux сработал бы наоборот у процесса под гигабайт.
    return raw / 1024.0 if sys.platform.startswith("linux") else raw / 1048576.0


ERR = "memprobe-error"           # отказ самого замера — показываем, не глотаем


def _title_of(page) -> str:
    """Имя страницы из объекта навигации или из строки.

    Отдельной функцией, потому что `.title` у страницы Streamlit —
    свойство, а не поле: у него своя жизнь между версиями, и разовый
    замер не имеет права ронять приложение из-за переименованного
    атрибута.
    """
    if isinstance(page, str):
        return page
    return str(getattr(page, "title", None) or page)


def note(page) -> None:
    """Записать замер после отрисовки страницы.

    Базовый уровень фиксируется один раз — тем, что было до первой
    страницы. Дальше по каждой странице держим последний замер и
    наибольший: между заходами память не возвращается, и «последний»
    сам по себе сказал бы, что вторая страница дешевле первой.

    Отказ замера НЕ роняет страницу и НЕ молчит: причина кладётся
    в `session_state` и выводится панелью. Временный инструмент,
    способный уронить приложение, стоит дороже цифры, которую он даёт;
    но и тихо не считающий — это пустая панель без объяснения.
    """
    try:
        cur = rss_mb()
        if cur is None:
            return
        st.session_state.setdefault(BASE, cur)
        book = st.session_state.setdefault(KEY, {})
        name = _title_of(page)
        was = book.get(name, {})
        book[name] = {
            "last": cur,
            "max": max(cur, was.get("max", 0.0)),
            "peak": peak_mb(),
            "hits": was.get("hits", 0) + 1,
        }
        st.session_state.pop(ERR, None)
    except Exception as e:                       # noqa: BLE001 — см. выше
        st.session_state[ERR] = f"{type(e).__name__}: {e}"


def panel() -> None:
    """Панель в сайдбаре. Вынимается вместе с модулем."""
    cur, peak = rss_mb(), peak_mb()
    with st.sidebar.expander("⏱ Память (временно)", expanded=False):
        failed = st.session_state.get(ERR)
        if failed:
            st.warning(f"Замер не сработал: {failed}")
        if cur is None:
            st.caption("Текущий RSS доступен только на Linux — "
                       "на Cloud цифры будут, локально нет.")
        else:
            free = CLOUD_LIMIT_MB - cur
            st.metric("RSS сейчас", f"{cur:,.0f} МБ",
                      f"запас {free:,.0f} МБ до {CLOUD_LIMIT_MB:,.0f}",
                      delta_color="normal" if free > 200 else "inverse")
        if peak is not None:
            st.caption(f"Пик за жизнь процесса: {peak:,.0f} МБ")
        base = st.session_state.get(BASE)
        if base is not None:
            st.caption(f"База до первой страницы: {base:,.0f} МБ")

        book = st.session_state.get(KEY) or {}
        if not book:
            st.caption("Обойдите страницы — замеры появятся здесь.")
            return
        # Таблица строится вручную: pandas тут же и утяжелил бы замер,
        # а вопрос ровно про вес.
        rows = "".join(
            f"<tr><td>{p}</td><td align=right>{v['max']:,.0f}</td>"
            f"<td align=right>{v['max'] - base:+,.0f}</td>"
            f"<td align=right>{v['hits']}</td></tr>"
            for p, v in sorted(book.items(), key=lambda kv: -kv[1]["max"])
            if base is not None)
        st.markdown(
            "<table style='width:100%;font-size:12px'><tr>"
            "<th align=left>страница</th><th align=right>RSS макс, МБ</th>"
            "<th align=right>к базе</th><th align=right>заходов</th></tr>"
            + rows + "</table>", unsafe_allow_html=True)
        st.caption("Прирост «к базе» — не цена страницы: память "
                   "не возвращается, и порядок обхода влияет на раскладку. "
                   "Честная цена страницы — открыть её первой после ребута.")
