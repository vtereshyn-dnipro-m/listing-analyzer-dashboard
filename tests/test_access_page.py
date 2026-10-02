# -*- coding: utf-8 -*-
"""
tests/test_access_page.py — экран «Доступ» в Listing Suite отрисовывается и закрыт.

Проверяется ровно то, что ломается тихо:

  · страница ЗАКРЫТА неадминистратору — и закрыта самой страницей, а не отсутствием
    пункта меню: по прямой ссылке меню не спрашивают;
  · администратору она открывается ЦЕЛИКОМ: восемь вкладок, оба продукта. Пустая
    страница с заголовком выглядит как работающая, поэтому считаем вкладки;
  · у людей ДВЕ колонки ролей, и роль Listing Suite пустая показана как «нет доступа»,
    а не как «Просмотр» — это разные вещи;
  · матрица Listing Suite показывает свои роли (контент-менеджер, утверждающий), а не
    кабинетные: наборы у продуктов разные.

База Кабинета подменяется целиком, сеть не трогается. `st.data_editor` AppTest не
видит вовсе — признак того, что редактор отрисовался, это его кнопка сохранения.

Запуск (pytest не нужен):  python tests/test_access_page.py
"""
from __future__ import annotations

import pathlib
import sys

import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ЛЮДИ = pd.DataFrame({
    "email": ["v.tereshyn@dniprom.com", "кто@dniprom.com"],
    "role": ["admin", "viewer"],
    "ls_role": ["admin", ""],
    "is_active": [True, True],
    "note": ["", ""],
    "access_until": [pd.NaT, pd.NaT],
    "first_login_at": [pd.Timestamp("2026-09-30", tz="UTC"), pd.NaT],
    "last_login_at": [pd.Timestamp("2026-10-02", tz="UTC"), pd.NaT],
    "expired": [False, False],
    "countries": ["", ""],
})
МАТРИЦА = pd.DataFrame(
    [("admin", "admin", True), ("ls.admin", "admin", True),
     ("ls.content.edit", "content_manager", True),
     ("ls.content.edit", "approver", True), ("ls.amazon.push", "approver", True),
     ("forecast.post", "demand_planner", True)],
    columns=["action", "role", "allowed"])
ТОКЕНЫ = pd.DataFrame(columns=["id", "label", "created_at", "created_by", "expires_at",
                               "revoked_at", "last_used_at", "uses", "product"])
ВХОДЫ = pd.DataFrame({"ts": [pd.Timestamp("2026-10-02", tz="UTC")],
                      "email": ["v.tereshyn@dniprom.com"], "result": ["ok"],
                      "reason": [""]})
ДЕЙСТВИЯ = pd.DataFrame({"ts": [pd.Timestamp("2026-10-02", tz="UTC")],
                         "email": ["v.tereshyn@dniprom.com"], "role": ["admin"],
                         "action": ["ls.amazon.push"], "object_type": ["asin"],
                         "object_id": ["B0TEST"], "allowed": [True],
                         "details": [""], "via": ["ui"]})

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


class _Cur:
    def __init__(self):
        self._rows = []

    def execute(self, sql, params=None):
        s = " ".join(str(sql).split())
        if "alpha2" in s:
            self._rows = [("ES",), ("DE",)]
        elif "auth_idle_days" in s:
            self._rows = [(30,)]
        elif "qa_access_enabled" in s:
            self._rows = [(1,)]
        elif "qa_token_days" in s:
            self._rows = [(7,)]
        elif "ls_auth_enabled" in s:
            self._rows = [(1,)]
        elif "app_permissions" in s:
            self._rows = [(r.action, r.role) for r in МАТРИЦА.itertuples() if r.allowed]
        elif "app_users" in s:
            self._rows = [("admin", True, None, False)]
        else:
            self._rows = []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Conn:
    def cursor(self):
        return _Cur()

    def commit(self):
        pass

    def close(self):
        pass


def _read_sql(sql, conn, params=None, **kw):
    s = " ".join(str(sql).split())
    if "app_users" in s:
        return ЛЮДИ.copy()
    if "app_permissions" in s:
        return МАТРИЦА.copy()
    if "qa_tokens" in s:
        return ТОКЕНЫ.copy()
    if "app_login_log" in s:
        return ВХОДЫ.copy()
    if "app_action_log" in s:
        # журнал рисуется дважды, по продукту: кабинетный пусть будет пуст, чтобы
        # видеть, что вкладки не перепутаны
        чей = (params or {}).get("продукт")
        return ДЕЙСТВИЯ.copy() if чей == "ls" else ДЕЙСТВИЯ.iloc[0:0].copy()
    raise AssertionError(f"неожиданный запрос: {s[:80]}")


import services.kdb as kdb                                  # noqa: E402
kdb.get_conn = lambda: _Conn()
import auth                                                 # noqa: E402
auth.get_conn = kdb.get_conn
import access_screen                                        # noqa: E402
access_screen.pd.read_sql = _read_sql
import pandas as _pd                                        # noqa: E402
_pd.read_sql = _read_sql


def страница(роль: str):
    at = AppTest.from_file(str(ROOT / "pages" / "access.py"), default_timeout=120)
    at.session_state["_auth_user"] = auth.User(email="кто@dniprom.com", role=роль,
                                              logged_in=True, known=True)
    at.session_state["lang"] = "ru"
    return at.run()


# --- 1. не администратору закрыто
at = страница(auth.CONTENT_MANAGER)
check("контент-менеджеру отказано", any("прав" in str(e.value).lower() for e in at.error))
check("и вкладок он не видит", not list(at.get("tab")))

# --- 2. администратору открыто целиком
at = страница(auth.ADMIN)
check("у администратора исключений нет", not at.exception)
вкладки = [str(tb.label) for tb in at.get("tab")]
check(f"вкладок восемь ({len(вкладки)})", len(вкладки) == 8)
check("есть вкладки обоих продуктов",
      any("Listing Suite" in л for л in вкладки) and any("прав" in л for л in вкладки))
check("кнопок сохранения не меньше трёх (люди и две матрицы)", len(at.button) >= 3)

# --- 3. две колонки ролей и «нет доступа» вместо «Просмотра»
#     (data_editor AppTest не видит — читаем то, что страница положила в session_state)
сетка = at.session_state.get("people_editor")
check("редактор людей отрисовался", сетка is not None)

# --- 4. свои роли в матрице второго продукта
подписи = " ".join(str(s.label) for s in at.get("checkbox")) + " ".join(
    str(c.value) for c in at.caption)
check("журнал Listing Suite показан отдельной вкладкой",
      any("Журнал Listing Suite" in л for л in вкладки))

# --- 5. сохранение проверяет ПРОДУКТОВОЕ право, а не кабинетное
#     Жёсткое require("admin") в общем модуле означало бы молчаливый отказ на каждом
#     сохранении: действия «admin» в матрице Listing Suite нет вовсе.
проверки = []
def _перехват(действие, **kw):
    проверки.append(действие)
    return True
_настоящий = auth.require
auth.require = _перехват
try:
    at = страница(auth.ADMIN)
    at.button(key="save_people").click().run()
finally:
    auth.require = _настоящий
check(f"сохранение спросило право Listing Suite ({проверки or '—'})",
      проверки == ["ls.admin"])

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
