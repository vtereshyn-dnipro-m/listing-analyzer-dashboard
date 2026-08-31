# -*- coding: utf-8 -*-
"""
app.py — точка входа Listing Suite. Три языка: EN / RU / UA (i18n.py).
Навигация st.navigation, Диагноз по умолчанию, иконки Material.
Запуск: streamlit run app.py
"""

import streamlit as st

from config import APP_NAME, days_to_deadline
import i18n as i18n_mod
from i18n import t, lang_selector

st.set_page_config(
    page_title=APP_NAME,
    page_icon="logo_light.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------- лого
try:
    st.logo("logo_light.png", size="large")
except Exception:
    pass  # лого нет в репо — работаем без него, не падаем

# ---------------------------------------------------------------- страницы
guide = st.Page(
    "pages/guide.py", title=t("nav.guide"),
    icon=":material/help:",
)
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
photo = st.Page(
    "pages/photo.py", title=t("nav.photo"),
    icon=":material/photo_camera:",
)
matrix_setup = st.Page(
    "pages/matrix_setup.py", title=t("nav.matrix"),
    icon=":material/account_tree:",
)
methodology = st.Page(
    "pages/methodology.py", title=t("nav.methodology"),
    icon=":material/menu_book:",
)
settings = st.Page(
    "pages/settings.py", title=t("nav.settings"),
    icon=":material/settings:",
)

nav = st.navigation(
    {
        t("nav.section.work"): [guide, dashboard, catalog, synthesis, photo],
        t("nav.section.settings"): [matrix_setup, methodology, settings],
    }
)

# ---------------------------------------------------------------- сайдбар
def stale_modules() -> str | None:
    """Рассинхрон страницы и модулей: свежий код, старый импортированный
    модуль. Возвращает, что именно отстало, или None.

    app.py перечитывается на каждом запуске, а `i18n` — нет: Streamlit
    Cloud держит его в sys.modules с прошлого деплоя. Отсюда сырые ключи
    на экране при живых переводах в репозитории. Проверяем две вещи:
    нет ли в словаре самой функции-детектора (значит модуль старее этой
    правки) и не промахнулись ли уже вызовы t().

    Заглушек здесь нет намеренно: смысл в том, чтобы рассинхрон КРИЧАЛ,
    а не прятался.
    """
    probe = getattr(i18n_mod, "missing_keys", None)
    if probe is None:
        return "i18n"
    miss = probe()
    return ", ".join(miss[:6]) + ("…" if len(miss) > 6 else "") if miss else None


with st.sidebar:
    st.markdown(f"**{APP_NAME}**  \n{t('app.tagline')}")
    _stale = stale_modules()
    if _stale:
        st.warning(f"⚠ Интерфейс новее модулей: {_stale}. "
                   f"Нужен ребут приложения (Manage app → Reboot app).")
    lang_selector()
    # тумблер мобильного вида: флаг читает inject_fonts() в components/ui.py
    st.toggle(t("sidebar.mobile"), key="mobile_preview",
              help=t("sidebar.mobile_help"))
    st.divider()
    d = days_to_deadline()
    if d > 0:
        st.markdown(t("sidebar.deadline", days=d))
    else:
        st.markdown(t("sidebar.deadline_passed"))

# ---------------------------------------------------------------- запуск
nav.run()  
