# -*- coding: utf-8 -*-
"""
pages/settings.py — Настройки: подключения, модели ИИ, шаблоны, пороги.

Ключи API здесь НЕ хранятся и не вводятся — они живут в Streamlit Secrets.
На странице: статус подключения (маска ключа + проверка связи), выбор
провайдера и модели под задачи (список тянется живьём из API провайдеров),
загрузка эталонов flat file и ссылка на пороги правил, которые читают все
страницы из app_settings.

Эталон flat file лежит здесь, а не на «Синтезе», потому что это разовое
администраторское действие: шаблон Amazon перевыпускает раз в несколько
месяцев, а выгрузка идёт каждый день.
"""
from __future__ import annotations

import pandas as pd
import requests
import streamlit as st

from i18n import t
from services.ai import reset_last_error
from services.db import get_conn, cfg, cfg_source
from services.flatfile_template import (
    parse_template, save_template, templates_for)
from services.settings import get_setting, get_int, save_setting
from components.ui import inject_fonts, eyebrow

inject_fonts()
st.title(t("set.title"))

OK_TEXT = "#2F6B3A"
ERR_TEXT = "#A32D2D"
MUTED = "#57534A"

st.caption(t("set.caption"))


def mask(key: str | None) -> str:
    """Хвост ключа для опознания — целиком не показываем никогда."""
    if not key:
        return "—"
    k = str(key).strip()
    return f"****{k[-4:]}" if len(k) > 6 else "****"


# ================================================================ подключения
st.markdown(eyebrow(t("set.connections")), unsafe_allow_html=True)


def key_info(name: str) -> str:
    """«secrets.toml · ****6wAA · 108 симв.» — откуда взят ключ, его хвост
    и длина. Снимает вопрос «а тот ли ключ подставился» без чтения логов.
    Целиком ключ не выводится нигде."""
    val, src = cfg_source(name)
    if not val:
        return ""
    k = str(val).strip()
    return f"{src} · {mask(k)} · {t('set.key_chars', n=len(k))}"


gem_key = cfg("GEMINI_API_KEY")
ant_key = cfg("ANTHROPIC_API_KEY")
dog_key = cfg("SCRAPINGDOG_API_KEY")

try:
    conn = get_conn()
    conn.close()
    db_ok = True
except Exception:
    db_ok = False

rows = [
    ("Gemini API", t("set.purpose_gemini"),
     key_info("GEMINI_API_KEY"), bool(gem_key)),
    ("Anthropic API", t("set.purpose_anthropic"),
     key_info("ANTHROPIC_API_KEY"), bool(ant_key)),
    ("ScrapingDog", t("set.purpose_scrapingdog"),
     key_info("SCRAPINGDOG_API_KEY"), bool(dog_key)),
    ("Lakebase", t("set.purpose_db"), "", db_ok),
]

for name, purpose, info, ok in rows:
    c1, c2, c3 = st.columns([2, 3, 2.2])
    c1.markdown(f"**{name}**")
    c2.markdown(
        f"<span style='color:{MUTED};font-size:13px;'>{purpose}</span>",
        unsafe_allow_html=True)
    detail = f" · {info}" if info else ""
    c3.markdown(
        f"<span style='color:{OK_TEXT if ok else ERR_TEXT};font-size:13px;'>"
        f"{t('set.connected') if ok else t('set.no_key')}</span>"
        f"<span style='color:{MUTED};font-size:12px;'>{detail}</span>",
        unsafe_allow_html=True)


def _probe(label: str, url: str, headers: dict, params: dict | None = None,
           timeout: int = 20, provider: str | None = None) -> None:
    """Один пробный запрос к провайдеру. Показываем код, а не молчим.
    Успех сбрасывает ai.last_error провайдера — иначе баннер «баланс
    исчерпан» на Синтезе и Фото висит после починки ключа до первой
    генерации."""
    try:
        r = requests.get(url, headers=headers, params=params, timeout=timeout)
        ok = r.status_code == 200
        if ok and provider:
            reset_last_error(provider)
        st.write(f"{label}: " + ("✅ ok" if ok else f"❌ {r.status_code}"))
    except Exception as e:
        st.write(f"{label}: ❌ {e}")


if st.button(t("set.check")):
    with st.spinner(t("set.checking")):
        if gem_key:
            _probe("Gemini",
                   "https://generativelanguage.googleapis.com/v1beta/models",
                   {"x-goog-api-key": str(gem_key).strip()},
                   provider="gemini")
        if ant_key:
            _probe("Anthropic", "https://api.anthropic.com/v1/models",
                   {"x-api-key": str(ant_key).strip(),
                    "anthropic-version": "2023-06-01"},
                   provider="anthropic")
        if dog_key:
            _probe("ScrapingDog", "https://api.scrapingdog.com/amazon/product",
                   {}, {"api_key": str(dog_key).strip(), "domain": "com",
                        "asin": "B00AP877FS", "country": "us"}, timeout=40)

st.divider()

# ================================================================ модели
st.markdown(eyebrow(t("set.models")), unsafe_allow_html=True)
st.caption(t("set.models_hint"))


@st.cache_data(ttl=600)
def gemini_models() -> list[str]:
    key = cfg("GEMINI_API_KEY")
    if not key:
        return []
    try:
        r = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            headers={"x-goog-api-key": str(key).strip()}, timeout=30)
        if r.status_code != 200:
            return []
        return sorted(
            str(m["name"]).replace("models/", "")
            for m in r.json().get("models", [])
            if "generateContent" in (m.get("supportedGenerationMethods") or [])
        )
    except Exception:
        return []


@st.cache_data(ttl=600)
def anthropic_models() -> list[str]:
    key = cfg("ANTHROPIC_API_KEY")
    if not key:
        return []
    try:
        r = requests.get(
            "https://api.anthropic.com/v1/models",
            headers={"x-api-key": str(key).strip(),
                     "anthropic-version": "2023-06-01"},
            params={"limit": 50}, timeout=30)
        if r.status_code != 200:
            return []
        return [m["id"] for m in r.json().get("data", [])]
    except Exception:
        return []


if st.button(t("set.refresh_models")):
    st.cache_data.clear()
    st.rerun()

gem_list = gemini_models()
ant_list = anthropic_models()

PROVIDERS = {"gemini": "Google Gemini", "anthropic": "Anthropic Claude"}
MODELS_BY_PROVIDER = {"gemini": gem_list, "anthropic": ant_list}

# (ключ задачи, подпись, провайдер по умолчанию) — те же задачи, что в services/ai.py
TASKS = [
    ("title_split", t("set.task_split"), "gemini"),
    ("photo_audit", t("set.task_photo"), "gemini"),
    ("agents", t("set.task_agents"), "anthropic"),
]

for task, label, prov_default in TASKS:
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

    # список от провайдера может быть пуст (нет ключа / API недоступен) —
    # текущая модель всё равно должна остаться в опциях, иначе выбор слетит
    opts = list(MODELS_BY_PROVIDER.get(prov_choice) or [])
    if cur_model and cur_model not in opts:
        opts = [cur_model] + opts
    if not opts:
        opts = ["—"]

    model_choice = c3.selectbox(
        "модель", opts,
        index=opts.index(cur_model) if cur_model in opts else 0,
        label_visibility="collapsed", key=f"model-{task}")

    # потолок ответа и режим мышления — рядом с моделью: 2000 не хватало,
    # у моделей Claude 5 мышление включено по умолчанию и съедало бюджет
    lim_key, think_key = f"ai.max_tokens.{task}", f"ai.thinking.{task}"
    cur_lim = get_int(lim_key, 8000)
    cur_think = get_setting(think_key, "adaptive") or "adaptive"
    l1, l2 = st.columns([1.6, 2.4])
    lim_choice = l1.number_input(
        t("set.max_tokens"), 1000, 64000, cur_lim, 1000,
        key=f"lim-{task}", help=t("set.max_tokens_help"))
    think_opts = ["adaptive", "disabled"]
    think_choice = l2.selectbox(
        t("set.thinking"), think_opts,
        index=think_opts.index(cur_think) if cur_think in think_opts else 0,
        format_func=lambda v: (t("set.thinking_adaptive") if v == "adaptive"
                               else t("set.thinking_off")),
        key=f"think-{task}", help=t("set.thinking_help"))
    if int(lim_choice) != cur_lim or think_choice != cur_think:
        save_setting(lim_key, int(lim_choice))
        save_setting(think_key, think_choice)
        st.rerun()

    if prov_choice != cur_prov or (model_choice != cur_model
                                   and model_choice != "—"):
        save_setting(prov_key, prov_choice)
        if model_choice != "—":
            save_setting(model_key, model_choice)
        st.success(t("set.saved", task=label,
                     provider=PROVIDERS[prov_choice], model=model_choice))
        st.rerun()

fb_on = str(get_setting("ai.fallback", "off")).lower() == "on"
fb = st.toggle(t("set.fallback"), value=fb_on, help=t("set.fallback_hint"))
if fb != fb_on:
    save_setting("ai.fallback", "on" if fb else "off")
    st.rerun()

st.caption(t("set.models_note"))

if not gem_list:
    st.caption(t("set.models_unavailable", provider="Gemini"))
if not ant_list:
    st.caption(t("set.models_unavailable", provider="Anthropic"))

st.divider()

# ================================================== шаблоны flat file
# Amazon принимает не произвольную таблицу, а свой файл со служебными
# строками 1–6. Взять их неоткуда, кроме как из настоящего шаблона, —
# поэтому человек загружает его сюда один раз, а мы храним эталон
# с вырезанными строками данных.
st.markdown(eyebrow(t("set.templates")), unsafe_allow_html=True)
st.caption(t("set.templates_hint"))


@st.cache_data(ttl=300)
def known_marketplaces() -> list[str]:
    try:
        conn = get_conn()
        df = pd.read_sql(
            "SELECT DISTINCT marketplace FROM product_matrix "
            "WHERE marketplace IS NOT NULL AND marketplace <> ''", conn)
        conn.close()
        mps = sorted({str(x).lower() for x in df["marketplace"]})
        return mps or ["es"]
    except Exception:
        return ["es"]


tc1, tc2 = st.columns([1, 3])
tpl_mp = tc1.selectbox(t("set.tpl_marketplace"), known_marketplaces(),
                       key="tpl-mp")
ups = tc2.file_uploader(t("set.tpl_upload"), type=["xlsm", "xlsx"],
                        accept_multiple_files=True, key="tpl-up")

if ups and st.button(t("set.tpl_save"), type="primary", key="tpl-save"):
    for up in ups:
        try:
            parsed = parse_template(up.name, up.getvalue())
        except Exception as e:
            st.error(f"{up.name}: {e}")
            continue
        err = save_template(tpl_mp, parsed)
        note = t("set.tpl_saved", name=parsed["file_name"],
                 types=len(parsed["product_types"]),
                 rows=parsed["rows_seen"])
        if err:
            # эталон лёг в сессию: выгрузка заработает сейчас, но до
            # применения миграции он не переживёт перезапуск
            st.warning(f"{note} · {t('set.tpl_session')}")
            st.code(err)
        else:
            st.success(note)

_saved = templates_for(tpl_mp)
if not _saved:
    st.caption(t("set.tpl_none"))
else:
    st.dataframe(
        pd.DataFrame([{
            "file": x["file_name"],
            "types": len(x.get("product_types") or []),
            "rows": x.get("rows_seen") or 0,
            "action": x.get("partial_label") or "",
            "store": x.get("stored") or "db",
        } for x in _saved]),
        hide_index=True, use_container_width=True,
        column_config={
            "file": st.column_config.TextColumn(t("set.tpl_c_file")),
            "types": st.column_config.NumberColumn(t("set.tpl_c_types")),
            "rows": st.column_config.NumberColumn(t("set.tpl_c_rows")),
            "action": st.column_config.TextColumn(t("set.tpl_c_action")),
            "store": st.column_config.TextColumn(t("set.tpl_c_store")),
        })
    _cov = sorted({p for x in _saved for p in (x.get("product_types") or [])})
    st.caption(t("set.tpl_coverage", n=len(_cov)))

st.divider()

# ================================================================ пороги
st.markdown(eyebrow(t("meth.thresholds")), unsafe_allow_html=True)
st.caption(t("set.thresholds_moved"))
st.page_link("pages/methodology.py", label=t("set.goto_methodology"),
             icon=":material/menu_book:")
