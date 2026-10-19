# -*- coding: utf-8 -*-
"""
tests/test_telegram_token_redaction.py — токен бота Telegram не попадает в
текст ошибки `_telegram` (T-7, 19.10.2026, #137).

`requests` кладёт URL запроса — с токеном бота — в текст исключения при
сетевом сбое. Четыре вызывающих `_telegram` в `auth.py` пишут `str(e)[:120]`
в общий журнал действий, а его видно на экране «Доступ». Поэтому
проверяется:

1. в тексте ошибки нет токена, а вместо него `bot<токен>`;
2. исходное исключение не прицеплено (`__cause__` пуст, контекст погашен):
   иначе токен вернулся бы через трассировку.

Сеть, секреты и база Кабинета подменены. Подмены возвращаются после проверки.

Запуск (pytest не нужен):  python tests/test_telegram_token_redaction.py
"""
from __future__ import annotations

import base64
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402

import auth  # noqa: E402  — до подмены services.kdb: auth берёт его при вызове

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


TOKEN = "1234567890:AAH-ab_cdEfGh12345"


class _Secrets:
    @staticmethod
    def get_secret(scope, key):
        val = {"telegram-bot-token": TOKEN, "telegram-chat-id": "42"}[key]
        return types.SimpleNamespace(value=base64.b64encode(val.encode()).decode())


class _WC:
    def __init__(self, **kw):
        self.secrets = _Secrets()


def boom(*a, **k):
    raise requests.ConnectionError(f"Max retries exceeded with url: /bot{TOKEN}/sendMessage")


import databricks.sdk as dbsdk  # noqa: E402

saved = {"kdb": sys.modules.get("services.kdb"), "wc": dbsdk.WorkspaceClient, "post": requests.post}
sys.modules["services.kdb"] = types.SimpleNamespace(
    _sec=lambda name: {"host": "h", "client_id": "c", "client_secret": "s"})
dbsdk.WorkspaceClient = _WC
requests.post = boom
try:
    err = None
    try:
        auth._telegram("x")
    except Exception as e:  # noqa: BLE001 — любое исключение сверяется ниже по типу
        err = e
    check(f"сбой сети — RuntimeError, а не исключение requests ({type(err).__name__})",
          type(err) is RuntimeError)
    text = str(err) if err else ""
    check(f"токена в тексте ошибки нет ({text[:80]})", err is not None and "AAH-ab" not in text and TOKEN not in text)
    check("вместо токена — bot<токен>", "bot<токен>" in text)
    check("исходное исключение не прицеплено (контекст погашен)",
          err is not None and err.__cause__ is None and err.__suppress_context__)
finally:
    if saved["kdb"] is None:
        sys.modules.pop("services.kdb", None)
    else:
        sys.modules["services.kdb"] = saved["kdb"]
    dbsdk.WorkspaceClient = saved["wc"]
    requests.post = saved["post"]

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
