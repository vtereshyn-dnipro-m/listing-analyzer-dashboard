# -*- coding: utf-8 -*-
"""
pages/guide.py — Как это работает: порядок шагов и логика Listing Suite.

Статичная инструкция для команды: с чего начать, что где делается,
что происходит автоматически. Обновляется по мере роста продукта.
"""
from __future__ import annotations

import streamlit as st

from i18n import t
from components.ui import inject_fonts, eyebrow

inject_fonts()

INK = "#1A1815"
MUTED = "#8A8578"
BORDER = "#E7E4DD"
CARD = "#FFFFFF"
ACCENT = "#E8590C"
MONO = '"JetBrains Mono","SFMono-Regular",Consolas,monospace'


def step_card(num: int, title: str, page: str, body: str, auto: bool = False) -> None:
    badge = (
        f"<span style='background:#DCEEE0;color:#2F6B3A;border-radius:999px;"
        f"padding:2px 10px;font-size:11px;font-weight:600;'>автоматически</span>"
        if auto else ""
    )
    st.markdown(
        f"""
        <div style="background:{CARD};border:1px solid {BORDER};border-radius:12px;
                    padding:16px 20px;margin-bottom:12px;display:flex;gap:16px;">
          <div style="min-width:34px;height:34px;border-radius:50%;background:{INK};
                      color:#FAFAF8;display:flex;align-items:center;justify-content:center;
                      font-weight:700;font-size:15px;">{num}</div>
          <div style="flex:1;">
            <div style="font-size:15px;font-weight:700;color:{INK};margin-bottom:2px;">
              {title}
              <span style="font-family:{MONO};font-weight:400;font-size:12px;color:{MUTED};">
                · {page}</span> {badge}
            </div>
            <div style="font-size:13px;color:{MUTED};line-height:1.55;">{body}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.header("Как это работает")
st.caption(
    "Listing Suite находит проблемы в листингах Amazon и даёт готовые решения. "
    "Формула каждой найденной боли: что болит → почему → что делать → цена бездействия."
)

st.markdown(eyebrow("Порядок работы"), unsafe_allow_html=True)
st.markdown("")

step_card(
    1, "Добавь товары в матрицу", "Матрица товаров",
    "Закинь ASIN пачкой — строками, ссылками amazon или в формате "
    "<code>SKU, ASIN, маркетплейс</code>. Конкурентов помечай словом «конкурент» "
    "в конце строки — они мониторятся, но боли по ним не создаются. "
    "Матрица — это список «что мы отслеживаем».",
)
step_card(
    2, "Сбор данных", "Матрица товаров",
    "Каждый день по расписанию (настраивается внизу Матрицы) система сама "
    "снимает свежий снимок каждого листинга: тайтл, наличие, отзывы, буллеты. "
    "Нужно срочно — кнопка «↻ Собрать» в строке товара обновит его прямо сейчас.",
    auto=True,
)
step_card(
    3, "Диагноз", "Диагноз",
    "По собранным данным правила находят боли: тайтл длиннее 75 символов "
    "(с 27.07 Amazon перепишет сам), товар недоступен, мало отзывов. "
    "Каждая боль — карточка: причина, действие, цена бездействия. "
    "Красные — чинить сразу, оранжевые — важно, жёлтые — план.",
    auto=True,
)
step_card(
    4, "Каталог", "Каталог",
    "Все тайтлы каталога против лимитов 75/125 одним взглядом: "
    "линейка-допуск показывает, кто вылезает и на сколько резать.",
)
step_card(
    5, "Синтез — решение боли тайтла", "Синтез",
    "Выбираешь тайтл с превышением → ИИ режет его по методологии: "
    "title до 75 символов + Item Highlights до 125 + список выброшенного на ревью. "
    "Перед генерацией можно задать защищённые фразы (must-keep — сохранятся дословно, "
    "запрещённые — не появятся). После генерации код проверяет результат: длину, "
    "запрещённые символы, повторы, наличие фраз.",
)
step_card(
    6, "Методологии — правила для ИИ", "Методологии",
    "Тексты правил, по которым ИИ работает (как резать тайтл, что запрещено). "
    "Правишь как документ → сохраняешь новую версию → следующие генерации идут по ней. "
    "Есть общая методология (для всех задач) и своя на каждую область. "
    "Любую версию можно откатить.",
)

st.markdown("")
st.markdown(eyebrow("Что дальше по продукту"), unsafe_allow_html=True)
st.markdown(
    f"""
    <div style="background:{CARD};border:1px dashed {BORDER};border-radius:12px;
                padding:16px 20px;color:{MUTED};font-size:13px;line-height:1.6;">
      Применение сплита на Amazon в один клик (через API) · история изменений
      «до/после» с эффектом на продажи · автоподбор защищённых фраз из
      поисковых запросов (SQP) · боли по фото, A+ контенту и ценам ·
      методологии для буллетов и описаний.
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("")
st.caption(
    f"Вопросы и идеи — Vitalii T. · дедлайн тайтлов: лимит 75 симв. с 27.07.2026"
)
