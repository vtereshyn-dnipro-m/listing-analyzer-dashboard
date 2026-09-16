# -*- coding: utf-8 -*-
"""
app.py — точка входа Listing Suite. Запуск: streamlit run app.py

Здесь не страницы, а обёртка: Streamlit поднимается как ASGI-приложение
(`st.App`, Streamlit ≥ 1.64), и рядом с ним монтируется HTTP-маршрут
для плагина Figma — `GET /figma/translations`. Сами страницы, сайдбар
и навигация живут в main.py и от обёртки не зависят.

Почему так, а не иначе. Streamlit — не API-сервер: своих маршрутов
у него нет, а внедрять обработчик во внутренности сервера нельзя —
между версиями он сменил Tornado на Starlette, и такая заплатка
сломалась бы молча при следующем деплое. `st.App(routes=…)` —
единственный ПОДДЕРЖИВАЕМЫЙ способ добавить маршрут, и `streamlit
run` сам распознаёт его в этом файле по AST. Главный файл на Cloud
остаётся app.py, менять там ничего не надо.

Маршрут защищён токеном FIGMA_PLUGIN_TOKEN из секретов; без токена
маршрут не поднимается вовсе — см. services/plugin_api.py.
"""
import streamlit as st

from services.plugin_api import routes

app = st.App("main.py", routes=routes())
