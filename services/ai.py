# -*- coding: utf-8 -*-
"""
services/ai.py — единый слой вызова ИИ.

Страницы не знают, к какому провайдеру идут: выбор задаётся в Настройках
(provider.<task> + model.<task>) и хранится в app_settings.

    from services.ai import generate_json
    res = generate_json("title_split", prompt)              # только текст
    res = generate_json("photo_audit", prompt, images=urls)  # текст + картинки
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

import requests
import streamlit as st

from i18n import t
from services.db import cfg
from services.settings import get_setting, save_setting

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

DEFAULTS = {
    "title_split": ("gemini", "gemini-3.5-flash"),
    "photo_audit": ("gemini", "gemini-3.5-flash"),
    "agents": ("anthropic", "claude-sonnet-5"),
}


PROVIDER_NAME = {"gemini": "Gemini", "anthropic": "Anthropic"}

# маркеры «кончились деньги/квота» в теле ошибки провайдера
_NO_CREDIT_MARKERS = ("credit balance", "insufficient_quota", "quota exceeded",
                      "resource_exhausted", "billing")


def _is_no_credit(status: int, body: str) -> bool:
    if status == 402:
        return True
    b = (body or "").lower()
    return status in (400, 403, 429) and any(m in b for m in _NO_CREDIT_MARKERS)


def _set_last_error(provider: str, code: str | None) -> None:
    """Состояние последней ошибки провайдера в app_settings
    (ai.last_error.<provider>, с меткой времени). code=None — сброс при
    успешном вызове. Пишем только при ИЗМЕНЕНИИ: save_setting чистит
    весь st.cache_data, на каждый вызов это делать нельзя."""
    key = f"ai.last_error.{provider}"
    cur = get_setting(key, "") or ""
    try:
        if code is None:
            if cur:
                save_setting(key, "")
        elif not cur.startswith(code):
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
            save_setting(key, f"{code} {stamp}")
    except Exception:
        pass   # диагностика не должна ронять сам вызов ИИ


def reset_last_error(provider: str) -> None:
    """Сброс ai.last_error.<provider> — та же логика, что при успешной
    генерации. Зовётся и из «Проверить связь» в Настройках: иначе баннер
    «баланс исчерпан» висит после починки ключа до первой генерации."""
    _set_last_error(provider, None)


def no_credit_banner(task: str) -> None:
    """Предупреждение ДО кнопок генерации: у выбранного провайдера
    последний вызов упал с no_credit. Кнопки не блокируются — человек
    может пополнить счёт в соседней вкладке и нажать снова."""
    provider, _ = task_config(task)
    if str(get_setting(f"ai.last_error.{provider}", "") or "").startswith("no_credit"):
        st.warning(t("ai.no_credit_banner",
                     provider=PROVIDER_NAME.get(provider, provider)))
        st.page_link("pages/settings.py", label=t("nav.settings"),
                     icon=":material/settings:")


def task_config(task: str) -> tuple[str, str]:
    """(provider, model) для задачи."""
    prov_default, model_default = DEFAULTS.get(task, ("gemini", "gemini-3.5-flash"))
    provider = get_setting(f"provider.{task}", prov_default) or prov_default
    model = get_setting(f"model.{task}", model_default) or model_default
    return provider, model


def _fetch_images(urls: list[str]) -> list[tuple[str, bytes]]:
    out = []
    for u in urls:
        try:
            r = requests.get(u, timeout=30)
            if r.status_code == 200:
                out.append((r.headers.get("Content-Type", "image/jpeg"), r.content))
        except Exception:
            continue
    return out


def _clean_json(text: str) -> dict | None:
    t = text.strip()
    t = t.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(t)
    except Exception:
        return None


def _call_gemini(model: str, prompt: str,
                 imgs: list[tuple[str, bytes]], timeout: int) -> dict | None:
    key = cfg("GEMINI_API_KEY")
    if not key:
        st.error("GEMINI_API_KEY не найден в секретах.")
        return None
    parts: list[dict] = []
    for mime, data in imgs:
        parts.append({"inline_data": {"mime_type": mime,
                                      "data": base64.b64encode(data).decode()}})
    parts.append({"text": prompt})
    r = requests.post(
        GEMINI_URL.format(model=model),
        headers={"x-goog-api-key": str(key).strip()},
        json={"contents": [{"parts": parts}],
              "generationConfig": {"responseMimeType": "application/json"}},
        timeout=timeout,
    )
    if r.status_code != 200:
        if _is_no_credit(r.status_code, r.text):
            _set_last_error("gemini", "no_credit")
        st.error(f"Gemini HTTP {r.status_code}: {r.text[:300]}")
        return None
    _set_last_error("gemini", None)
    return _clean_json(r.json()["candidates"][0]["content"]["parts"][0]["text"])


def _call_anthropic(model: str, prompt: str,
                    imgs: list[tuple[str, bytes]], timeout: int) -> dict | None:
    key = cfg("ANTHROPIC_API_KEY")
    if not key:
        st.error("ANTHROPIC_API_KEY не найден в секретах.")
        return None
    content: list[dict] = []
    for mime, data in imgs:
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": mime.split(";")[0],
            "data": base64.b64encode(data).decode()}})
    content.append({"type": "text", "text": prompt})
    r = requests.post(
        ANTHROPIC_URL,
        headers={"x-api-key": str(key).strip(),
                 "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": model, "max_tokens": 2000,
              "messages": [{"role": "user", "content": content}]},
        timeout=timeout,
    )
    if r.status_code != 200:
        if _is_no_credit(r.status_code, r.text):
            _set_last_error("anthropic", "no_credit")
        st.error(f"Anthropic HTTP {r.status_code}: {r.text[:300]}")
        return None
    _set_last_error("anthropic", None)
    text = "".join(b.get("text", "") for b in r.json().get("content", []))
    return _clean_json(text)


def generate_json(task: str, prompt: str,
                  images: list[str] | None = None,
                  timeout: int = 240) -> dict | None:
    """Вызов ИИ по задаче. Провайдер и модель берутся из Настроек.
    Возвращает распарсенный JSON или None (ошибка уже показана в UI)."""
    provider, model = task_config(task)
    imgs = _fetch_images(images or [])
    if images and not imgs:
        st.error("Не удалось загрузить ни одного изображения.")
        return None
    try:
        if provider == "anthropic":
            return _call_anthropic(model, prompt, imgs, timeout)
        return _call_gemini(model, prompt, imgs, timeout)
    except Exception as e:
        st.error(f"Ошибка вызова ИИ ({provider}/{model}): {e}")
        return None 
