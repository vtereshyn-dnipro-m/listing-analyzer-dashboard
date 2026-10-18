"""T-7 (19.10.2026): токен бота Telegram не попадает в текст ошибки _telegram — её пишут в журнал «Доступа»."""
import base64
import sys
import types

import pytest
import requests

import auth

TOKEN = "1234567890:AAH-ab_cdEfGh12345"


def test_network_error_has_no_token(monkeypatch):
    class _Secrets:
        @staticmethod
        def get_secret(scope, key):
            val = {"telegram-bot-token": TOKEN, "telegram-chat-id": "42"}[key]
            return types.SimpleNamespace(value=base64.b64encode(val.encode()).decode())

    class _WC:
        def __init__(self, **kw):
            self.secrets = _Secrets()

    fake_kdb = types.SimpleNamespace(_sec=lambda name: {"host": "h", "client_id": "c", "client_secret": "s"})
    monkeypatch.setitem(sys.modules, "services.kdb", fake_kdb)
    monkeypatch.setattr("databricks.sdk.WorkspaceClient", _WC)

    def boom(*a, **k):
        raise requests.ConnectionError(f"Max retries exceeded with url: /bot{TOKEN}/sendMessage")

    monkeypatch.setattr(requests, "post", boom)
    with pytest.raises(RuntimeError) as exc:
        auth._telegram("x")
    assert "AAH-ab" not in str(exc.value)
    assert "bot<токен>" in str(exc.value)
    assert exc.value.__cause__ is None and exc.value.__suppress_context__
