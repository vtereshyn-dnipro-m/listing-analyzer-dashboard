# -*- coding: utf-8 -*-
"""
pages/methodology.py — Методология Синтеза: просмотр, правка, версии.

Скилл (правила генерации тайтлов) живёт в listing_data.synthesis_skill
и правится отсюда без единого коммита кода. Каждое сохранение = новая
версия; старые остаются в истории, активна всегда одна (на маркетплейс).

Плейсхолдеры {title_limit} и {highlights_limit} подставляются Синтезом
автоматически — их в тексте не трогать.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from i18n import t
from services.db import get_conn
from components.ui import inject_fonts, eyebrow

inject_fonts()
st.header("Методология Синтеза")
st.caption(
    "Правила, по которым ИИ режет тайтлы. Правишь текст — сохраняешь новую "
    "версию — все следующие генерации идут по ней. Код не трогается."
)


@st.cache_data(ttl=60)
def load_versions() -> pd.DataFrame:
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT id, version, marketplace, skill_text, created_at, is_active
            FROM synthesis_skill
            ORDER BY marketplace, version DESC
            """,
            conn,
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


versions = load_versions()

if versions.empty:
    st.warning(
        "Таблица synthesis_skill пуста. Прогони DDL с методологией v1 в SQL Editor."
    )
    st.stop()

mp_options = sorted(versions["marketplace"].unique())
mp = st.selectbox("Маркетплейс (all = общая методология)", mp_options)

mp_versions = versions[versions["marketplace"] == mp]
active = mp_versions[mp_versions["is_active"]]

if active.empty:
    st.warning(f"Для '{mp}' нет активной версии — сохрани новую ниже.")
    current_text = ""
    current_version = int(mp_versions["version"].max() or 0)
else:
    current_text = active.iloc[0]["skill_text"]
    current_version = int(active.iloc[0]["version"])
    st.markdown(
        eyebrow(f"активная версия v{current_version} · "
                f"{pd.to_datetime(active.iloc[0]['created_at']).strftime('%d.%m %H:%M')}"),
        unsafe_allow_html=True,
    )

edited = st.text_area(
    "Текст методологии",
    value=current_text,
    height=420,
    label_visibility="collapsed",
)

col1, col2 = st.columns([1, 3])
with col1:
    save = st.button(
        f"Сохранить как v{current_version + 1}",
        type="primary",
        disabled=(edited.strip() == current_text.strip() or not edited.strip()),
    )

if save:
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE synthesis_skill SET is_active = FALSE "
                "WHERE marketplace = %s AND is_active = TRUE",
                (mp,),
            )
            cur.execute(
                """
                INSERT INTO synthesis_skill
                    (version, marketplace, skill_text, is_active)
                VALUES (%s, %s, %s, TRUE)
                """,
                (current_version + 1, mp, edited.strip()),
            )
        conn.close()
        st.cache_data.clear()
        st.success(f"Сохранено как v{current_version + 1} — теперь активна она.")
        st.rerun()
    except Exception as e:
        st.error(f"Не сохранилось: {e}")

# ---- история версий и откат
st.divider()
st.markdown("### История версий")

for _, v in mp_versions.iterrows():
    label = (
        f"v{int(v['version'])} · "
        f"{pd.to_datetime(v['created_at']).strftime('%d.%m.%Y %H:%M')}"
        + (" · **активная**" if v["is_active"] else "")
    )
    with st.expander(label):
        st.text(v["skill_text"][:2000])
        if not v["is_active"]:
            if st.button(f"Откатиться на v{int(v['version'])}",
                         key=f"rollback-{v['id']}"):
                try:
                    conn = get_conn()
                    with conn, conn.cursor() as cur:
                        cur.execute(
                            "UPDATE synthesis_skill SET is_active = FALSE "
                            "WHERE marketplace = %s AND is_active = TRUE",
                            (mp,),
                        )
                        cur.execute(
                            "UPDATE synthesis_skill SET is_active = TRUE "
                            "WHERE id = %s",
                            (int(v["id"]),),
                        )
                    conn.close()
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Откат не удался: {e}")
