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


def task_limits(task: str) -> tuple[int, str]:
    """(max_tokens, режим мышления) для задачи — из Настроек.

    Расширенное мышление у моделей Claude 5 включено по умолчанию: если
    max_tokens мал, весь бюджет уходит в thinking и до текста ответа дело
    не доходит — приходит stop_reason=max_tokens с пустым текстом. Ровно
    это и ломало сплит тайтлов при лимите 2000."""
    try:
        mt = int(float(get_setting(f"ai.max_tokens.{task}", "8000") or 8000))
    except (TypeError, ValueError):
        mt = 8000
    mode = str(get_setting(f"ai.thinking.{task}", "adaptive") or "adaptive")
    return max(1000, mt), ("disabled" if mode == "disabled" else "adaptive")


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


# последняя ошибка вызова — в session_state, потому что st.error не
# переживает st.rerun(): страница перерисовывается и сообщение пропадает.
# Именно так провалы и оставались молчаливыми.
LAST_CALL_KEY = "ai.last_call_error"


def _report(detail: str) -> None:
    """Показать ошибку сейчас и запомнить, чтобы пережила перерисовку."""
    try:
        st.session_state[LAST_CALL_KEY] = detail
    except Exception:
        pass
    st.error(detail)


def _clear_report() -> None:
    try:
        st.session_state.pop(LAST_CALL_KEY, None)
    except Exception:
        pass


def last_call_error() -> str | None:
    """Текст последней ошибки вызова ИИ (переживает rerun)."""
    try:
        return st.session_state.get(LAST_CALL_KEY)
    except Exception:
        return None


# расход токенов — единственный способ УБЕДИТЬСЯ, что кэш работает.
# Метка cache_control не гарантирует попадания: короткий префикс не кэшируется
# молча, а любое изменение байтов префикса начинает запись заново. Поэтому
# копим usage по вызовам и показываем на странице.
USAGE_KEY = "ai.usage"
USAGE_FIELDS = ("input_tokens", "output_tokens",
                "cache_creation_input_tokens", "cache_read_input_tokens")


def _record_usage(usage: dict) -> None:
    try:
        acc = st.session_state.get(USAGE_KEY) or {"calls": 0}
        acc["calls"] = int(acc.get("calls", 0)) + 1
        for f in USAGE_FIELDS:
            acc[f] = int(acc.get(f, 0)) + int(usage.get(f) or 0)
        st.session_state[USAGE_KEY] = acc
    except Exception:
        pass


def reset_usage() -> None:
    """Обнулить счётчик перед партией — иначе цифры складываются с прошлой."""
    try:
        st.session_state.pop(USAGE_KEY, None)
    except Exception:
        pass


def usage_totals() -> dict:
    """Итог по вызовам с момента reset_usage(): сколько токенов ушло,
    сколько записано в кэш и сколько прочитано из него."""
    try:
        return dict(st.session_state.get(USAGE_KEY) or {})
    except Exception:
        return {}


def _clean_json(text: str) -> dict | None:
    t = (text or "").strip()
    t = t.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    # модель часто добавляет фразу до/после JSON — вытаскиваем тело по скобкам
    i, j = t.find("{"), t.rfind("}")
    if 0 <= i < j:
        try:
            return json.loads(t[i:j + 1])
        except Exception:
            return None
    return None


def _call_gemini(model: str, prompt: str, imgs: list[tuple[str, bytes]],
                 timeout: int, max_tokens: int = 8000,
                 system: str | None = None) -> dict | None:
    key = cfg("GEMINI_API_KEY")
    if not key:
        st.error("GEMINI_API_KEY не найден в секретах.")
        return None
    parts: list[dict] = []
    for mime, data in imgs:
        parts.append({"inline_data": {"mime_type": mime,
                                      "data": base64.b64encode(data).decode()}})
    parts.append({"text": prompt})
    payload = {"contents": [{"parts": parts}],
               "generationConfig": {"responseMimeType": "application/json",
                                    "maxOutputTokens": max_tokens}}
    if system:
        # у Gemini постоянная часть — systemInstruction; явного cache_control
        # тут нет, но отделять её всё равно правильно: один и тот же текст
        # на своём месте, а не смешан с данными товара
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    r = requests.post(
        GEMINI_URL.format(model=model),
        headers={"x-goog-api-key": str(key).strip()},
        json=payload,
        timeout=timeout,
    )
    if r.status_code != 200:
        if _is_no_credit(r.status_code, r.text):
            _set_last_error("gemini", "no_credit")
        _report(f"Gemini HTTP {r.status_code} · {model}: {r.text[:400]}")
        return None
    _set_last_error("gemini", None)
    # у Gemini расход лежит в другом месте и под другими именами — приводим
    # к одним полям, чтобы строка расхода на странице не зависела от провайдера
    _meta = (r.json().get("usageMetadata") or {})
    _record_usage({
        "input_tokens": _meta.get("promptTokenCount") or 0,
        "output_tokens": _meta.get("candidatesTokenCount") or 0,
        "cache_read_input_tokens": _meta.get("cachedContentTokenCount") or 0,
    })
    try:
        cand = r.json()["candidates"][0]
        text = cand["content"]["parts"][0]["text"]
    except Exception:
        _report(f"Gemini {model}: ответ без текста — {r.text[:400]}")
        return None
    data = _clean_json(text)
    if data is None:
        # HTTP 200, но тело не разобралось — раньше это молчало полностью
        reason = str(cand.get("finishReason") or "")
        tail = f" · finishReason={reason}" if reason else ""
        _report(f"Gemini {model}: ответ не JSON{tail} — {text[:400]}")
        return None
    _clear_report()
    return data


def _anthropic_body(model: str, content: list, max_tokens: int,
                    thinking: str, system: str | None = None) -> dict:
    """Тело запроса к Anthropic. thinking=disabled отправляем явно: у моделей
    Claude 5 мышление включено по умолчанию, а для форматной задачи оно
    только съедает бюджет ответа.

    system идёт отдельным блоком с cache_control: кэш у Anthropic — это
    совпадение ПРЕФИКСА (порядок tools → system → messages), поэтому всё
    постоянное обязано лежать в system, а меняющееся от товара к товару —
    в messages. Метка на последнем блоке system кэширует его целиком.
    """
    body = {"model": model, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": content}]}
    if system:
        body["system"] = [{"type": "text", "text": system,
                           "cache_control": {"type": "ephemeral"}}]
    if thinking == "disabled":
        body["thinking"] = {"type": "disabled"}
    return body


def _call_anthropic(model: str, prompt: str, imgs: list[tuple[str, bytes]],
                    timeout: int, max_tokens: int = 8000,
                    thinking: str = "adaptive",
                    system: str | None = None) -> dict | None:
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
        json=_anthropic_body(model, content, max_tokens, thinking, system),
        timeout=timeout,
    )
    if r.status_code != 200:
        if _is_no_credit(r.status_code, r.text):
            _set_last_error("anthropic", "no_credit")
        _report(f"Anthropic HTTP {r.status_code} · {model}: {r.text[:400]}")
        return None
    _set_last_error("anthropic", None)
    body = r.json()
    _record_usage(body.get("usage") or {})
    text = "".join(b.get("text", "") for b in body.get("content", []))
    data = _clean_json(text)
    if data is None:
        # что РЕАЛЬНО пришло: типы блоков и расход токенов. «Пустой текст
        # при stop_reason=max_tokens» = весь бюджет ушёл в thinking
        stop = str(body.get("stop_reason") or "")
        blocks = ", ".join(sorted({str(b.get("type")) for b
                                   in body.get("content", [])})) or "нет блоков"
        usage = body.get("usage") or {}
        spent = (f"out={usage.get('output_tokens')}"
                 if usage.get("output_tokens") is not None else "")
        _report(f"Anthropic {model}: ответ не JSON · stop_reason={stop or '—'}"
                f" · блоки: {blocks} · max_tokens={max_tokens} {spent} — "
                + (text[:400] if text else "текста нет"))
        return None
    _clear_report()
    return data


def generate_json(task: str, prompt: str,
                  images: list[str] | None = None,
                  timeout: int = 240,
                  system: str | None = None) -> dict | None:
    """Вызов ИИ по задаче. Провайдер и модель берутся из Настроек.
    Возвращает распарсенный JSON или None (ошибка уже показана в UI).

    system — постоянная часть промпта (методология, правила). У Anthropic
    она уходит отдельным блоком с cache_control и при партии из нескольких
    товаров читается из кэша вместо повторной обработки.
    """
    provider, model = task_config(task)
    max_tokens, thinking = task_limits(task)
    imgs = _fetch_images(images or [])
    if images and not imgs:
        st.error("Не удалось загрузить ни одного изображения.")
        return None
    try:
        if provider == "anthropic":
            return _call_anthropic(model, prompt, imgs, timeout,
                                   max_tokens, thinking, system)
        return _call_gemini(model, prompt, imgs, timeout, max_tokens, system)
    except requests.Timeout:
        _report(f"{PROVIDER_NAME.get(provider, provider)} {model}: "
                f"нет ответа за {timeout} с (таймаут)")
        return None
    except Exception as e:
        _report(f"Ошибка вызова ИИ ({provider}/{model}): "
                f"{type(e).__name__}: {e}")
        return None 
