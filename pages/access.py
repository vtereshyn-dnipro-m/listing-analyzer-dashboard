# -*- coding: utf-8 -*-
"""pages/access.py — экран «Доступ»: тонкая обёртка над общим модулем.

Сам экран живёт в `access_screen.py`, и это ВЫКЛАДКА файла из репозитория Кабинета —
байт в байт (`tests/test_access_screen_copy.py` падает, если копию правили здесь).
Править его надо там, у источника, и выкладывать скриптом; две версии одной админки
разошлись бы молча, а таблицы у них общие.

Здесь остаётся только то, что принадлежит хозяину: свой модуль прав, своё соединение с
базой Кабинета, свой `t()` и код продукта.
"""
import streamlit as st  # noqa: F401  (нужен Streamlit-контексту страницы)

import access_screen
import auth
from i18n import t, current_lang
from services.kdb import get_conn

access_screen.render(product=auth.PRODUCT, auth=auth, get_connection=get_conn,
                     t=t, lang=current_lang())
