# -*- coding: utf-8 -*-
"""
app.py — точка входа Listing Suite. Три языка: EN / RU / UA (i18n.py).
Навигация st.navigation, Дашборд по умолчанию, иконки Material (без эмодзи).
Лого Dnipro-M — как в Кабинете (logo_light.png в корне репо).
Запуск: streamlit run app.py
"""

import streamlit as st

from config import APP_NAME, days_to_deadline
from i18n import t, lang_selector

st.set_page_config(
    page_title=APP_NAME,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------- лого
try:
    st.logo("logo_light.png", size="large")
except Exception:
    pass  # лого нет в репо — работаем без него, не падаем

# ---------------------------------------------------------------- страницы
# Только существующие файлы; будущие добавляются по мере готовности шагов.
dashboard = st.Page(
    "pages/dashboard.py", title=t("nav.dashboard"),
    icon=":material/stethoscope:", default=True,
)
catalog = st.Page(
    "pages/catalog.py", title=t("nav.catalog"),
    icon=":material/table_rows:",
)
synthesis = st.Page(
    "pages/synthesis.py", title=t("nav.synthesis"),
    icon=":material/content_cut:",
)
matrix_setup = st.Page(
    "pages/matrix_setup.py", title=t("nav.matrix"),
    icon=":material/account_tree:",
)

nav = st.navigation(
    {
        t("nav.section.work"): [dashboard, catalog, synthesis],
        t("nav.section.settings"): [matrix_setup],
    }
)

# ---------------------------------------------------------------- сайдбар
with st.sidebar:
    st.markdown(f"**{APP_NAME}**  \n{t('app.tagline')}")
    lang_selector()
    st.divider()
    d = days_to_deadline()
    if d > 0:
        st.markdown(t("sidebar.deadline", days=d))
    else:
        st.markdown(t("sidebar.deadline_passed"))

# ---------------------------------------------------------------- запуск
nav.run()
