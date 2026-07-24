# -*- coding: utf-8 -*-
"""
pages/methodology.py — Методологии: библиотека скиллов с версиями.

Каждая область (scope) — своя методология: title_split (Синтез),
дальше bullets, photo_brief, ai_grade и т.д. Правки без коммитов кода:
новая версия при каждом сохранении, откат в один клик.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from i18n import t
from services.db import get_conn
from components.ui import inject_fonts, eyebrow

inject_fonts()
st.header(t("meth.title"))
st.caption(t("meth.caption"))

SCOPES = {
    "common": "Общая · базовые правила для всех областей",
    "title_split": "Split тайтла 75/125 · страница Синтез",
    "bullets": "Буллеты · переписывание 5 пунктов",
    "highlights": "Item Highlights · отдельная доработка 125 симв.",
    "description": "Описание товара · product description",
    "aplus": "A+ контент · структура и тексты модулей",
    "photo_brief": "Фото · ТЗ дизайнеру на главное фото и галерею",
    "video_brief": "Видео · сценарий и ТЗ на product video",
    "ai_grade": "Оценка листинга · критерии грейда A-D",
    "keyword_research": "Ключевые фразы · чистка, группировка, must-keep",
    "review_analysis": "Отзывы · анализ негатива и инсайты для листинга",
    "competitor_teardown": "Конкуренты · разбор чужого листинга",
    "ppc_negatives": "PPC · минус-слова и структура кампаний",
}

scope = st.selectbox(
    t("meth.scope"),
    list(SCOPES.keys()),
    format_func=lambda s: SCOPES.get(s, s),
)


@st.cache_data(ttl=60)
def load_versions(scope_: str) -> pd.DataFrame:
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT id, version, marketplace, skill_text, created_at, is_active
            FROM synthesis_skill
            WHERE scope = %(scope)s
            ORDER BY version DESC
            """,
            conn, params={"scope": scope_},
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


versions = load_versions(scope)

if versions.empty:
    st.info(t("meth.empty_scope"))
    current_text = ""
    current_version = 0
else:
    active = versions[versions["is_active"]]
    if active.empty:
        current_text = ""
        current_version = int(versions["version"].max())
        st.warning(t("meth.no_active"))
    else:
        current_text = active.iloc[0]["skill_text"]
        current_version = int(active.iloc[0]["version"])
        st.markdown(
            eyebrow(
                f"{t('meth.active_version')} v{current_version} · "
                f"{pd.to_datetime(active.iloc[0]['created_at']).strftime('%d.%m %H:%M')}"
            ),
            unsafe_allow_html=True,
        )

edited = st.text_area(
    t("meth.title"),
    value=current_text,
    height=420,
    label_visibility="collapsed",
    placeholder=t("meth.editor_placeholder"),
)

save = st.button(
    f"{t('meth.save_as')} v{current_version + 1}",
    type="primary",
    disabled=(edited.strip() == current_text.strip() or not edited.strip()),
)

if save:
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE synthesis_skill SET is_active = FALSE "
                "WHERE scope = %s AND is_active = TRUE",
                (scope,),
            )
            cur.execute(
                """
                INSERT INTO synthesis_skill
                    (version, marketplace, scope, skill_text, is_active)
                VALUES (%s, 'all', %s, %s, TRUE)
                """,
                (current_version + 1, scope, edited.strip()),
            )
        conn.close()
        st.cache_data.clear()
        st.success(t("meth.saved"))
        st.rerun()
    except Exception as e:
        st.error(f"Не сохранилось: {e}")

# ---- история версий и откат
if not versions.empty:
    st.divider()
    st.markdown(f"### {t('meth.history')}")

    for _, v in versions.iterrows():
        label = (
            f"v{int(v['version'])} · "
            f"{pd.to_datetime(v['created_at']).strftime('%d.%m.%Y %H:%M')}"
            + (f" · **{t('meth.active_label')}**" if v["is_active"] else "")
        )
        with st.expander(label):
            st.text(v["skill_text"][:2000])
            if not v["is_active"]:
                if st.button(f"{t('meth.rollback')} v{int(v['version'])}",
                             key=f"rollback-{v['id']}"):
                    try:
                        conn = get_conn()
                        with conn, conn.cursor() as cur:
                            cur.execute(
                                "UPDATE synthesis_skill SET is_active = FALSE "
                                "WHERE scope = %s AND is_active = TRUE",
                                (scope,),
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
