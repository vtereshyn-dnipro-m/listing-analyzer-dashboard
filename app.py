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
from services import memprobe   # ВРЕМЕННО: замер памяти, снять после ответа
import auth

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

# ---------------------------------------------------------------- ворота
# Ворота стоят ЗДЕСЬ — раньше, чем читается хоть одна таблица, и раньше навигации.
# Страницы собраны через st.navigation, поэтому любой URL проходит через app.py, и
# прямая ссылка на /synthesis закрывается этой же проверкой. Если навигацию когда-нибудь
# заменят на автоматическую (папка pages/ без роутера), страницы станут
# самостоятельными точками входа, и guard() придётся звать в начале каждой.
auth.guard()

# ---------------------------------------------------------------- страницы
# Список страниц объявлен в auth.PAGES: видимость страницы — такое же право, как любое
# другое, и держать два списка (страниц и прав) значило бы однажды их разойтись.
#
# Страница, которую роли видеть нельзя, НЕ исчезает из навигации — она становится
# скрытой заглушкой с тем же адресом. Разница существенная: просто убрать её из списка
# значило бы, что по прямой ссылке Streamlit покажет своё «Page not found» и молча
# перебросит на главную, а человек должен получить ОТКАЗ и понять, что страница есть,
# но ему закрыта.
def _адрес(файл: str) -> str:
    """Адрес страницы в ссылке — тот же, что Streamlit выводит из имени файла:
    отбрасывает путь, числовой префикс и расширение. `pages/matrix_setup.py` →
    `matrix_setup`. Нужен затем, чтобы заглушка отвечала по ТОМУ ЖЕ адресу."""
    имя = файл.rsplit("/", 1)[-1]
    if имя.endswith(".py"):
        имя = имя[:-3]
    return re.sub(r"^\d+_", "", имя)


def _отказ():
    st.title(t("auth.page_closed_title"))
    st.error(t("auth.page_closed"))
    st.caption(t("auth.page_closed_hint"))


_видимые = [p for p in auth.PAGES if auth.can("ls.page." + p[0])]
_закрытые = [p for p in auth.PAGES if not auth.can("ls.page." + p[0])]

if not _видимые:
    # Ни одной открытой страницы — показываем отказ целиком, а не пустое меню
    st.navigation([st.Page(_отказ, title=t("auth.page_closed_title"))],
                  position="hidden").run()
    st.stop()

# «Диагноз» по умолчанию, если он открыт; иначе первая из открытых — пустого экрана
# при живых страницах быть не должно
_по_умолчанию = next((k for k, *_ in _видимые if k == "dashboard"), _видимые[0][0])
_разделы: dict[str, list] = {}
for _ключ, _файл, _подпись, _значок, _раздел in _видимые:
    _разделы.setdefault(_раздел, []).append(
        st.Page(_файл, title=t(_подпись), icon=_значок,
                default=(_ключ == _по_умолчанию)))
_скрытые = [st.Page(_отказ, title=t(_подпись), icon=_значок,
                    url_path=_адрес(_файл), visibility="hidden")
            for _ключ, _файл, _подпись, _значок, _раздел in _закрытые]

nav = st.navigation(
    {t("nav.section.work"): _разделы.get("work", []),
     t("nav.section.settings"): _разделы.get("settings", []) + _скрытые}
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
    auth.header()
    st.divider()
    d = days_to_deadline()
    if d > 0:
        st.markdown(t("sidebar.deadline", days=d))
    else:
        st.markdown(t("sidebar.deadline_passed"))

# ---------------------------------------------------------------- запуск
# ВРЕМЕННО: панель замера памяти. Ставится ДО nav.run(), чтобы показать
# то, что накоплено предыдущими заходами, — сайдбар рисуется раньше
# страницы, и панель после run() отставала бы на один прогон.
memprobe.panel()
nav.run()
# ВРЕМЕННО: замер после отрисовки — здесь страница уже построила свои
# таблицы и кэши, то есть RSS отражает её настоящую цену.
memprobe.note(nav)          # имя страницы достаётся внутри, безотказно  
