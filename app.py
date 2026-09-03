# -*- coding: utf-8 -*-
"""
app.py — точка входа Listing Suite. Три языка: EN / RU / UA (i18n.py).
Навигация st.navigation, Диагноз по умолчанию, иконки Material.
Запуск: streamlit run app.py
"""

import pathlib
import re

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
@st.cache_data(ttl=300, show_spinner=False)
def _keys_on_disk(path: str, mtime: float) -> set:
    """Ключи словаря, лежащего на ДИСКЕ. mtime в аргументах — чтобы кэш
    сам протух после деплоя."""
    src = pathlib.Path(path).read_text(encoding="utf-8")
    return set(re.findall(r'^        "([\w.]+)":', src, re.M))


def stale_modules() -> str | None:
    """Рассинхрон страницы и модулей: свежий код, старый импортированный
    модуль. Возвращает, что именно отстало, или None.

    app.py перечитывается на каждом запуске, а `i18n` — нет: Streamlit
    Cloud держит его в sys.modules с прошлого деплоя. Отсюда сырые ключи
    на экране при живых переводах в репозитории.

    Сравниваем ключи ФАЙЛА и ключи модуля В ПАМЯТИ. Это единственный
    признак, который означает ровно рассинхрон и ничего больше.
    По промахам t() судить нельзя: есть места, где отсутствие перевода
    штатно (подписи болей по rule_id, коды проблем Amazon), и первая же
    версия этой проверки объявила ребут там, где всё работало.
    """
    if getattr(i18n_mod, "tr_opt", None) is None:
        return "i18n"                     # модуль старее самой проверки
    try:
        path = pathlib.Path(i18n_mod.__file__)
        disk = _keys_on_disk(str(path), path.stat().st_mtime)
    except Exception:
        return None                       # файл не прочитался — молчим
    loaded: set = set()
    for d in i18n_mod.LANGS.values():
        loaded |= set(d)
    ahead = sorted(disk - loaded)
    if not ahead:
        return None
    return ", ".join(ahead[:6]) + ("…" if len(ahead) > 6 else "")


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
