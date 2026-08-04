# -*- coding: utf-8 -*-
"""services/settings.py — настройки приложения из базы (app_settings).

Использование на странице:
    from services.settings import get_setting, get_int, get_float
    TITLE_LIMIT = get_int("limit.title", 75)
    MODEL = get_setting("model.title_split", "gemini-3.5-flash")
"""
from __future__ import annotations

import streamlit as st

from services.db import get_conn

DEFAULTS = {
    "model.title_split": "gemini-3.5-flash",
    "model.photo_audit": "gemini-3.5-flash",
    "model.agents": "claude-sonnet-5",
    "provider.title_split": "gemini",
    "provider.photo_audit": "gemini",
    "provider.agents": "anthropic",
    "ai.fallback": "off",
    "limit.title": "75",
    "limit.highlights": "125",
    "threshold.min_reviews": "50",
    "threshold.min_images": "7",
    "threshold.rating_red": "4.3",
    "threshold.rating_green": "4.4",
}


@st.cache_data(ttl=120)
def load_settings() -> dict:
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM app_settings")
        rows = dict(cur.fetchall())
        cur.close()
        conn.close()
        return {**DEFAULTS, **rows}
    except Exception:
        return dict(DEFAULTS)


def get_setting(key: str, default: str | None = None) -> str:
    return load_settings().get(key, default if default is not None
                               else DEFAULTS.get(key, ""))


def get_int(key: str, default: int) -> int:
    try:
        return int(float(get_setting(key, str(default))))
    except (TypeError, ValueError):
        return default


def get_float(key: str, default: float) -> float:
    try:
        return float(str(get_setting(key, str(default))).replace(",", "."))
    except (TypeError, ValueError):
        return default


def save_setting(key: str, value: str) -> None:
    conn = get_conn()
    with conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO app_settings (key, value, updated_at) "
            "VALUES (%s, %s, now()) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, "
            "updated_at = now()",
            (key, str(value)))
    conn.close()
    st.cache_data.clear()
