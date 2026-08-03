# -*- coding: utf-8 -*-
"""
pages/settings.py — Настройки: подключения, модели ИИ, пороги правил.

Ключи API здесь НЕ хранятся и не вводятся — они живут в Streamlit Secrets.
На странице только: статус подключения (маска ключа + проверка связи),
выбор моделей под задачи (список тянется живьём из API провайдеров)
и пороги правил, которые читают все страницы из app_settings.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from services.db import get_conn, cfg
from services.settings import get_setting, get_int, get_float, save_setting
from components.ui import inject_fonts, eyebrow

inject_fonts()
st.title(t("set.title"))

OK_TEXT = "#2F6B3A"
ERR_TEXT = "#A32D2D"
MUTED = "#57534A"

st.caption("Подключения, модели ИИ и пороги правил. "
           "Ключи API хранятся в защищённых секретах и здесь не отображаются.")


def mask(key: str | None) -> str:
    if not key:
        return "—"
    k = str(key).strip()
    return f"****{k[-4:]}" if len(k) > 6 else "****"


# ================================================================ подключения
st.markdown(eyebrow("Подключения"), unsafe_allow_html=True)

gem_key = cfg("GEMINI_API_KEY")
ant_key = cfg("ANTHROPIC_API_KEY")
dog_key = cfg("SCRAPINGDOG_API_KEY")

rows = [
    ("Gemini API", "тайтлы, аудит фото и A+", mask(gem_key), bool(gem_key)),
    ("Anthropic API", "агенты и сводки", mask(ant_key), bool(ant_key)),
    ("ScrapingDog", "данные листингов Amazon", mask(dog_key), bool(dog_key)),
]
try:
    conn = get_conn()
    conn.close()
    db_ok = True
except Exception:
    db_ok = False
rows.append(("Lakebase", "база проекта listing-suite", "—", db_ok))

for name, purpose, m, ok in rows:
    c1, c2, c3 = st.columns([2, 3, 1.4])
    c1.markdown(f"**{name}**")
    c2.markdown(f"<span style='color:{MUTED};font-size:13px;'>{purpose}</span>",
                unsafe_allow_html=True)
    color = OK_TEXT if ok else ERR_TEXT
    c3.markdown(
        f"<span style='color:{color};font-size:13px;'>"
        f"{'● подключён' if ok else '○ нет ключа'} {m}</span>",
        unsafe_allow_html=True)

if st.button("Проверить связь"):
    with st.spinner("Проверяю..."):
        import requests as _rq
        # Gemini
        if gem_key:
            try:
                r = _rq.get("https://generativelanguage.googleapis.com/v1beta/models",
                            headers={"x-goog-api-key": str(gem_key).strip()},
                            timeout=20)
                st.write(f"Gemini: {'✅ ok' if r.status_code == 200 else '❌ ' + str(r.status_code)}")
            except Exception as e:
                st.write(f"Gemini: ❌ {e}")
        # Anthropic
        if ant_key:
            try:
                r = _rq.get("https://api.anthropic.com/v1/models",
                            headers={"x-api-key": str(ant_key).strip(),
                                     "anthropic-version": "2023-06-01"},
                            timeout=20)
                st.write(f"Anthropic: {'✅ ok' if r.status_code == 200 else '❌ ' + str(r.status_code)}")
            except Exception as e:
                st.write(f"Anthropic: ❌ {e}")
        # ScrapingDog
        if dog_key:
            try:
                r = _rq.get("https://api.scrapingdog.com/amazon/product",
                            params={"api_key": str(dog_key).strip(), "domain": "com",
                                    "asin": "B00AP877FS", "country": "us"},
                            timeout=40)
                st.write(f"ScrapingDog: {'✅ ok' if r.status_code == 200 else '❌ ' + str(r.status_code)}")
            except Exception as e:
                st.write(f"ScrapingDog: ❌ {e}")

st.divider()

# ================================================================ модели
st.markdown(eyebrow("Модели ИИ по задачам"), unsafe_allow_html=True)
st.caption("Список тянется из API провайдеров. Меняешь здесь — "
           "все следующие генерации идут на новой модели.")


@st.cache_data(ttl=600)
def gemini_models() -> list[str]:
    key = cfg("GEMINI_API_KEY")
    if not key:
        return []
    try:
        import requests as _rq
        r = _rq.get("https://generativelanguage.googleapis.com/v1beta/models",
                    headers={"x-goog-api-key": str(key).strip()}, timeout=30)
        if r.status_code != 200:
            return []
        out = []
        for m in r.json().get("models", []):
            if "generateContent" in (m.get("supportedGenerationMethods") or []):
                out.append(str(m["name"]).replace("models/", ""))
        return sorted(out)
    except Exception:
        return []


@st.cache_data(ttl=600)
def anthropic_models() -> list[str]:
    key = cfg("ANTHROPIC_API_KEY")
    if not key:
        return []
    try:
        import requests as _rq
        r = _rq.get("https://api.anthropic.com/v1/models",
                    headers={"x-api-key": str(key).strip(),
                             "anthropic-version": "2023-06-01"},
                    params={"limit": 50}, timeout=30)
        if r.status_code != 200:
            return []
        return [m["id"] for m in r.json().get("data", [])]
    except Exception:
        return []


if st.button("Обновить списки моделей"):
    st.cache_data.clear()
    st.rerun()

gem_list = gemini_models()
ant_list = anthropic_models()

PROVIDERS = {"gemini": "Google Gemini", "anthropic": "Anthropic Claude"}
MODELS_BY_PROVIDER = {"gemini": gem_list, "anthropic": ant_list}

tasks = [
    ("title_split", "Сплит тайтлов (Синтез)", "gemini"),
    ("photo_audit", "Аудит фото и A+ (Vision)", "gemini"),
    ("agents", "Агенты и сводки", "anthropic"),
]

for task, label, prov_default in tasks:
    prov_key, model_key = f"provider.{task}", f"model.{task}"
    cur_prov = get_setting(prov_key, prov_default) or prov_default
    cur_model = get_setting(model_key)

    c1, c2, c3 = st.columns([2, 1.6, 2.4])
    c1.markdown(f"**{label}**")

    prov_opts = list(PROVIDERS.keys())
    prov_choice = c2.selectbox(
        "провайдер", prov_opts,
        index=prov_opts.index(cur_prov) if cur_prov in prov_opts else 0,
        format_func=lambda p: PROVIDERS[p],
        label_visibility="collapsed", key=f"prov-{task}")

    opts = MODELS_BY_PROVIDER.get(prov_choice) or []
    if not opts:
        opts = [cur_model] if cur_model else ["—"]
    if cur_model not in opts:
        opts = [cur_model] + opts if cur_model else opts

    model_choice = c3.selectbox(
        "модель", opts, index=opts.index(cur_model) if cur_model in opts else 0,
        label_visibility="collapsed", key=f"model-{task}")

    if prov_choice != cur_prov or model_choice != cur_model:
        save_setting(prov_key, prov_choice)
        save_setting(model_key, model_choice)
        st.success(f"{label}: {PROVIDERS[prov_choice]} · {model_choice}")
        st.rerun()

fb_on = str(get_setting("ai.fallback", "off")).lower() == "on"
fb = st.toggle(
    "Автопереключение при перегрузке", value=fb_on,
    help="Если основной провайдер недоступен (429/503), запрос уйдёт ко "
         "второму автоматически. Выключено — предложим кнопку «Повторить», "
         "чтобы смена модели не была незаметной.")
if fb != fb_on:
    save_setting("ai.fallback", "on" if fb else "off")
    st.rerun()

st.caption(
    "Провайдер и модель применяются сразу к следующей генерации. "
    "Vision (фото, A+) поддерживают обе линейки — можно сравнить качество "
    "на своих товарах и оставить лучшую."
)

if not gem_list:
    st.caption("Список моделей Gemini недоступен — проверь ключ.")
if not ant_list:
    st.caption("Список моделей Anthropic недоступен — проверь ключ.")

st.divider()

# ================================================================ пороги
st.markdown(eyebrow("Пороги правил"), unsafe_allow_html=True)
st.caption(
    "Пороги, по которым правила находят боли (лимит тайтла, минимум отзывов "
    "и фото, границы рейтинга), живут на странице Методологии — рядом с "
    "правилами, которые они дополняют."
)
st.page_link("pages/methodology.py", label="Перейти в Методологии",
             icon=":material/menu_book:")
