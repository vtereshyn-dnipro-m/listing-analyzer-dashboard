# -*- coding: utf-8 -*-
"""
tests/test_ai_errors.py — ошибка провайдера обязана доходить до экрана.

Регрессия на самый дорогой класс поломок в этом проекте: генерация молча
не работала, потому что ошибку глушили сразу три механизма — bare except,
st.rerun() поверх st.error и тихий None при HTTP 200 с неразобранным телом.
Диагностика заняла часы, сама починка — строку.

Запуск (pytest не нужен):  python tests/test_ai_errors.py
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd                                    # noqa: E402

import services.db                                     # noqa: E402
services.db.get_conn = lambda: type(
    "C", (), {"close": lambda self: None})()
pd.read_sql = lambda *a, **k: pd.DataFrame()

import requests                                        # noqa: E402
import services.ai as ai                               # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


class _Resp:
    def __init__(self, payload, code=200):
        self.status_code, self._p = code, payload
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self):
        return self._p


def _setup():
    """Провайдер anthropic, ключ есть, st подменён на сборщик сообщений."""
    ai.cfg = lambda name, default=None: "sk-ant-test"
    ai.get_setting = lambda k, d=None: {
        "provider.title_split": "anthropic",
        "model.title_split": "claude-sonnet-5",
        "ai.max_tokens.title_split": "8000",
        "ai.thinking.title_split": "disabled",
    }.get(k, d)
    ai.save_setting = lambda k, v: None
    shown: list[str] = []
    ai.st = type("S", (), {"error": staticmethod(shown.append),
                           "session_state": {}})()
    return shown


def call(resp=None, exc=None):
    shown = _setup()

    def post(*a, **k):
        if exc:
            raise exc
        return resp

    requests.post = post
    out = ai.generate_json("title_split", "prompt", timeout=120)
    return out, shown, ai.st.session_state.get(ai.LAST_CALL_KEY)


# 1. HTTP-ошибка: код, модель и тело — на экране
out, shown, saved = call(_Resp(
    {"error": {"message": "model: claude-sonnet-5 not found"}}, 404))
check("HTTP-ошибка показана с кодом, моделью и телом",
      out is None and shown and "404" in shown[0]
      and "claude-sonnet-5" in shown[0] and "not found" in shown[0])
check("текст ошибки сохранён и переживёт st.rerun()", saved == shown[0])
check("last_call_error() отдаёт тот же текст", ai.last_call_error() == shown[0])

# 2. HTTP 200 и неразобранное тело — раньше молчало полностью
out, shown, saved = call(_Resp({"content": [{"type": "thinking",
                                             "thinking": "..."}],
                                "stop_reason": "max_tokens",
                                "usage": {"output_tokens": 2000}}))
check("200 без текста: ошибка показана, а не тихий None",
      out is None and shown)
check("видно stop_reason", "stop_reason=max_tokens" in shown[0])
check("видно, какие блоки пришли", "блоки: thinking" in shown[0])
check("виден лимит и расход токенов",
      "max_tokens=8000" in shown[0] and "out=2000" in shown[0])

# 3. таймаут — отдельным понятным сообщением
out, shown, _ = call(exc=requests.Timeout("timed out"))
check("таймаут назван таймаутом с числом секунд",
      out is None and shown and "таймаут" in shown[0] and "120" in shown[0])

# 4. успех — ошибка гасится, чтобы старое сообщение не висело
out, shown, saved = call(_Resp({"content": [{"type": "text", "text":
    'Готово: {"title": "T", "highlights": "H", "dropped": []}'}]}))
check("JSON внутри прозы разбирается",
      out == {"title": "T", "highlights": "H", "dropped": []})
check("после успеха сохранённая ошибка стёрта", saved is None and not shown)

# 5. страница: провал партии виден ПОСЛЕ перерисовки
requests.post = lambda *a, **k: _Resp(
    {"error": {"message": "overloaded"}}, 529)
CAND = pd.DataFrame([dict(asin="B0TEST0001", marketplace="es",
                          title="Очень длинный тайтл " * 6,
                          fetched_at=pd.Timestamp("2026-08-26"),
                          main_image=None, sku_group="17500000")])


def fake_sql(sql, conn, **kw):
    s = str(sql)
    if "FROM diagnosis d" in s and "title_over_limit" in s:
        return CAND.copy()
    if "FROM synthesis_skill" in s:
        return pd.DataFrame([dict(scope="title_split", skill_text="м",
                                  version=1)])
    return pd.DataFrame()


pd.read_sql = fake_sql
from streamlit.testing.v1 import AppTest                # noqa: E402

at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
at.switch_page("pages/synthesis.py").run()
btn = next((b for b in at.button
            if "Сгенерировать партию" in str(b.label)), None)
check("кнопка партии на странице есть", btn is not None)
if btn is not None:
    btn.click().run()
    errs = " | ".join(str(e.value) for e in at.error)
    codes = " | ".join(str(c.value) for c in at.code)
    check("после rerun на экране виден провал партии",
          "Ничего не сгенерировано" in errs)
    check("после rerun виден ответ провайдера",
          "529" in codes and "overloaded" in codes)
    check("названо, на каком товаре упало", "B0TEST0001" in codes)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
