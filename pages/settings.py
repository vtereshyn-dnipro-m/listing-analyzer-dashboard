# -*- coding: utf-8 -*-
"""
pages/settings.py — Настройки: подключения, модели ИИ, пороги правил.

Ключи API здесь НЕ хранятся и не вводятся — они живут в Streamlit Secrets.
На странице только: статус подключения (маска ключа + проверка связи),
выбор провайдера и модели под задачи (список тянется живьём из API
провайдеров) и ссылка на пороги правил, которые читают все страницы
из app_settings.
"""
from __future__ import annotations

import requests
import streamlit as st

from i18n import t
from services.db import get_conn, cfg, cfg_source
from services.settings import get_setting, save_setting
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
           timeout: int = 20) -> None:
    """Один пробный запрос к провайдеру. Показываем код, а не молчим."""
    try:
        r = requests.get(url, headers=headers, params=params, timeout=timeout)
        st.write(f"{label}: "
                 + ("✅ ok" if r.status_code == 200 else f"❌ {r.status_code}"))
    except Exception as e:
        st.write(f"{label}: ❌ {e}")


if st.button(t("set.check")):
    with st.spinner(t("set.checking")):
        if gem_key:
            _probe("Gemini",
                   "https://generativelanguage.googleapis.com/v1beta/models",
                   {"x-goog-api-key": str(gem_key).strip()})
        if ant_key:
            _probe("Anthropic", "https://api.anthropic.com/v1/models",
                   {"x-api-key": str(ant_key).strip(),
                    "anthropic-version": "2023-06-01"})
        if dog_key:
            _probe("ScrapingDog", "https://api.scrapingdog.com/amazon/product",
                   {}, {"api_key": str(dog_key).strip(), "domain": "com",
                        "asin": "B00AP877FS", "country": "us"}, timeout=40)

# ================================================================ отладка
# ВРЕМЕННАЯ раскрывашка для разработки (строки намеренно мимо t() —
# блок будет удалён): ключ по дороге от secrets до запроса где-то
# меняется, ищем где. Ключ целиком не выводится нигде.
with st.expander("🔧 Отладка ключа Anthropic (временно, для разработки)"):
    import os as _os

    _NAME = "ANTHROPIC_API_KEY"

    def _probe_val(v) -> str:
        if v is None:
            return "— нет"
        s = str(v)
        return f"{mask(s.strip())} · {len(s)} симв."

    # 1. сравнение источников — где что лежит
    _env_v = _os.environ.get(_NAME)
    try:
        _sec_v = st.secrets[_NAME] if _NAME in st.secrets else None
    except Exception as _e:
        _sec_v = None
        st.caption(f"st.secrets недоступен: {_e}")
    from services.db import _load_secrets as _lsf
    _file_exists = _os.path.exists(_os.path.join(".streamlit", "secrets.toml"))
    _file_v = _lsf().get(_NAME) if _file_exists else None
    _cfg_v = cfg(_NAME)

    st.markdown("**1. Источники**")
    st.write(f"os.environ: {_probe_val(_env_v)}")
    st.write(f"st.secrets: {_probe_val(_sec_v)}")
    st.write(".streamlit/secrets.toml: "
             + (_probe_val(_file_v) if _file_exists else "— файла нет"))
    st.write(f"cfg() вернул: {_probe_val(_cfg_v)}")

    _vals = {str(v).strip() for v in (_env_v, _sec_v, _file_v)
             if v is not None and str(v).strip()}
    if len(_vals) > 1:
        st.error("⚠ ЗНАЧЕНИЯ В ИСТОЧНИКАХ РАЗЛИЧАЮТСЯ — cfg() берёт первое "
                 "по порядку env → secrets.toml → st.secrets. Это и есть ответ.")
    elif _vals:
        st.success("Источники согласованы: везде одно значение.")

    # 2. побайтовая проверка того, что уходит в заголовок
    st.markdown("**2. Байты**")
    if _cfg_v is None:
        st.write("cfg() вернул None — проверять нечего.")
    else:
        _raw = str(_cfg_v)
        _k = _raw.strip()
        st.write(f"длина до strip: {len(_raw)} · после strip: {len(_k)}")
        if len(_raw) != len(_k):
            st.error("⚠ по краям есть пробельные символы — "
                     "в secrets ключ с переносом строки или пробелом")
        if "\n" in _k or "\r" in _k:
            st.error("⚠ ВНУТРИ ключа есть перенос строки — "
                     "похоже на многострочный литерал TOML")
        st.code(f"первые 8: {_raw[:8]!r}\nпоследние 8: {_raw[-8:]!r}",
                language=None)
        st.write("префикс sk-ant-api03-: "
                 + ("✅ совпадает" if _k.startswith("sk-ant-api03-")
                    else f"❌ НЕ совпадает (начинается с {_k[:7]!r})"))

    # 3. живой запрос: к какой организации привязан ключ и что отвечает API
    st.markdown("**3. Живой запрос** · POST /v1/messages, max_tokens=1, haiku")
    if st.button("Выполнить тестовый запрос", key="dbg-anthropic-ping"):
        if not _cfg_v:
            st.error("Ключа нет — запрос не отправлен.")
        else:
            try:
                _r = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": str(_cfg_v).strip(),
                             "anthropic-version": "2023-06-01",
                             "content-type": "application/json"},
                    json={"model": "claude-haiku-4-5-20251001",
                          "max_tokens": 1,
                          "messages": [{"role": "user", "content": "ping"}]},
                    timeout=30,
                )
                st.write(f"HTTP {_r.status_code}")
                _rid = _r.headers.get("request-id", "—")
                _org = _r.headers.get("anthropic-organization-id", "—")
                st.write(f"request-id: `{_rid}`")
                st.write(f"anthropic-organization-id: `{_org}` — по нему "
                         "видно, к какой организации привязан ключ")
                st.code(_r.text[:1500], language="json")
            except Exception as _e:
                st.error(f"Запрос не прошёл: {_e}")

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

# ================================================================ пороги
st.markdown(eyebrow(t("meth.thresholds")), unsafe_allow_html=True)
st.caption(t("set.thresholds_moved"))
st.page_link("pages/methodology.py", label=t("set.goto_methodology"),
             icon=":material/menu_book:")
