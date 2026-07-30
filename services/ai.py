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

import requests
import streamlit as st

from services.db import cfg
from services.settings import get_setting

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

DEFAULTS = {
    "title_split": ("gemini", "gemini-3.5-flash"),
    "photo_audit": ("gemini", "gemini-3.5-flash"),
    "agents": ("anthropic", "claude-sonnet-5"),
}


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
        st.error(f"Gemini HTTP {r.status_code}: {r.text[:300]}")
        return None
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
        st.error(f"Anthropic HTTP {r.status_code}: {r.text[:300]}")
        return None
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
