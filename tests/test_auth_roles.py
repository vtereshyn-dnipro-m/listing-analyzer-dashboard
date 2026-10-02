# -*- coding: utf-8 -*-
"""
tests/test_auth_roles.py — вход и роли: что можно каждой роли и чего нельзя никому.

Проверяется ПОВЕДЕНИЕ, а не наличие функций, и ровно те места, которые ломаются тихо:

  · три режима. Раскатка (2) обязана вести себя как до появления входа — иначе
    кнопки пропадут у всех ещё до того, как вход включили; авария (0) — как
    «Просмотр» у всех; нечитаемая база — как раскатка, потому что нехватка
    настройки не должна отбирать у людей кнопки;
  · QA-агент. Ему запрещено ВСЁ жёстко, в обход матрицы, и разрешена ровно
    видимость страниц — иначе проверять нечего. Галочка в матрице, случайно
    поставленная «Просмотру», не должна открывать роботу кнопки, тратящие деньги;
  · пустая роль в Listing Suite. Это «доступа нет», а не «Просмотр»: карточка в
    общем списке людей есть, а в этот продукт человек не входит;
  · матрица из базы главнее кода, а действие, которого в базе нет, запрещено всем:
    новая кнопка не должна заработать раньше, чем кто-то решил, кому она доступна;
  · отправка в Amazon начинается с утверждающего — контент-менеджеру она закрыта.

База подменяется целиком, сеть не трогается.

Запуск (pytest не нужен):  python tests/test_auth_roles.py
"""
from __future__ import annotations

import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# --- подмена базы: соединение, которое отвечает заранее заданным ---------------
ОТВЕТЫ: dict = {"mode": 1, "matrix": [], "user": None}


class _Cur:
    def __init__(self):
        self._rows = []

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if "ls_auth_enabled" in s:
            self._rows = [] if ОТВЕТЫ["mode"] is None else [(ОТВЕТЫ["mode"],)]
        elif "app_permissions" in s:
            self._rows = list(ОТВЕТЫ["matrix"])
        elif "app_users" in s:
            self._rows = [] if ОТВЕТЫ["user"] is None else [ОТВЕТЫ["user"]]
        elif "qa_access_enabled" in s:
            self._rows = [(0,)]
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


import services.kdb as kdb                                  # noqa: E402
kdb.get_conn = lambda: _Conn()

import auth                                                 # noqa: E402
auth.get_conn = lambda: _Conn()

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


def сброс(**kw):
    """Новый прогон страницы: кеши и «кто сейчас» живут в session_state."""
    ОТВЕТЫ.update(kw)
    auth.st.session_state = {}
    auth.st.query_params = {}
    auth.mode.clear()
    auth._matrix.clear()
    auth._load_user.clear()


# Streamlit в тестах: сессия — обычный словарь, рисование — заглушки
auth.st.session_state = {}
auth.st.query_params = {}
auth.st.error = lambda *a, **k: None
auth.st.user = types.SimpleNamespace(is_logged_in=False, email="", name="")


def как(роль, вошёл=True, робот=False):
    """Поставить текущего человека напрямую: экран входа здесь не проверяется."""
    auth.st.session_state["_auth_user"] = auth.User(
        email="" if робот else "кто@dniprom.com", role=роль,
        logged_in=вошёл, known=not робот, is_qa=робот)


# --- 1. режимы ----------------------------------------------------------------
сброс(mode=2)
как(auth.VIEWER)
check("раскатка: кнопки у всех, как было", auth.can("ls.amazon.push"))

сброс(mode=0)
как(auth.ADMIN)
check("авария: нельзя даже администратору", not auth.can("ls.content.edit"))

сброс(mode=None)      # строки в настройках нет
как(auth.VIEWER)
check("нет настройки — ведём себя как на раскатке", auth.can("ls.content.edit"))


class _Мёртвая:
    def cursor(self):
        raise RuntimeError("база недоступна")

    def close(self):
        pass


_живой = kdb.get_conn
kdb.get_conn = lambda: _Мёртвая()
auth.get_conn = kdb.get_conn
auth.mode.clear()
check("база недоступна — тоже раскатка, а не отказ", auth.mode() == auth.MODE_ROLLOUT)
kdb.get_conn = _живой
auth.get_conn = _живой

# --- 2. матрица из базы -------------------------------------------------------
БАЗА = [("ls.content.edit", "content_manager"), ("ls.content.edit", "approver"),
        ("ls.content.edit", "admin"),
        ("ls.amazon.push", "approver"), ("ls.amazon.push", "admin"),
        ("ls.method.edit", "approver"), ("ls.method.edit", "admin"),
        ("ls.settings.edit", "admin")] + [
       ("ls.page." + k, r) for k, *_ in auth.PAGES for r in auth.ROLES]

сброс(mode=1, matrix=БАЗА)
как(auth.CONTENT_MANAGER)
check("контент-менеджер правит контент", auth.can("ls.content.edit"))
check("и НЕ отправляет в Amazon", not auth.can("ls.amazon.push"))
check("и не лезет в настройки", not auth.can("ls.settings.edit"))

сброс(mode=1, matrix=БАЗА)
как(auth.APPROVER)
check("утверждающий отправляет в Amazon", auth.can("ls.amazon.push"))
check("и правит методику", auth.can("ls.method.edit"))
check("и не лезет в настройки", not auth.can("ls.settings.edit"))

сброс(mode=1, matrix=БАЗА)
как(auth.VIEWER)
check("«Просмотр» не правит ничего", not any(
    auth.can(a) for a in ("ls.content.edit", "ls.amazon.push",
                          "ls.method.edit", "ls.settings.edit")))
check("но страницы видит", auth.can("ls.page.synthesis"))

# действие, которого в базе нет, запрещено всем — даже администратору
сброс(mode=1, matrix=[("ls.content.edit", "admin")])
как(auth.ADMIN)
check("нового действия нет в базе — запрещено всем", not auth.can("ls.amazon.push"))

# пустая таблица — работаем по матрице из кода
сброс(mode=1, matrix=[])
как(auth.APPROVER)
check("пустая матрица — правила из кода", auth.can("ls.amazon.push"))

# --- 3. QA-агент --------------------------------------------------------------
сброс(mode=1, matrix=[(a, r) for a in ("ls.content.edit", "ls.amazon.push",
                                       "ls.method.edit", "ls.settings.edit")
                      for r in auth.ROLES])
как(auth.VIEWER, робот=True)
check("роботу запрещено всё, даже когда матрица всё разрешила",
      not any(auth.can(a) for a in ("ls.content.edit", "ls.amazon.push",
                                    "ls.method.edit", "ls.settings.edit")))
check("а страницы ему видны — иначе проверять нечего",
      all(auth.can(a) for a in auth.PAGE_ACTIONS))

сброс(mode=2, matrix=[])
как(auth.VIEWER, робот=True)
check("и в раскатке роботу по-прежнему нельзя", not auth.can("ls.amazon.push"))

# --- 4. пустая роль в Listing Suite ------------------------------------------
сброс(mode=1, matrix=БАЗА, user=("", True, None, False))
auth.st.session_state = {}
auth.st.query_params = {}
auth.st.user = types.SimpleNamespace(is_logged_in=True, email="кто@dniprom.com",
                                     name="Кто-то")
u = auth.current()
check("пустая ls_role — человек не «Просмотр», а без доступа", not u.known)
check("и права ему не даются", not auth.can("ls.page.synthesis"))

сброс(mode=1, matrix=БАЗА, user=("approver", True, None, False))
auth.st.session_state = {}
auth.st.query_params = {}
u = auth.current()
check("роль из базы читается", u.known and u.role == auth.APPROVER)

сброс(mode=1, matrix=БАЗА, user=("approver", True, None, True))   # срок истёк
auth.st.session_state = {}
auth.st.query_params = {}
check("истёкший срок виден в строке человека",
      bool(auth._load_user("кто@dniprom.com")["expired"]))

# --- 5. список страниц и список прав — один и тот же -------------------------
check("у каждой страницы есть право видимости",
      all(("ls.page." + k) in auth._MATRIX for k, *_ in auth.PAGES))
check("лишних прав видимости нет",
      {a for a in auth._MATRIX if a.startswith("ls.page.")}
      == {"ls.page." + k for k, *_ in auth.PAGES})

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
