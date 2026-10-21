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
  · пустая роль в Listing Suite. Сама по себе это «доступа нет», а не «Просмотр»;
  · рабочая почта @dniprom.com входит сама (решение владельца 13.10.2026): нет карточки —
    заводится «Просмотр» в обоих продуктах, пустая роль здесь — становится «Просмотром»;
    выключенная карточка и чужой домен не пускаются;
  · матрица из базы главнее кода, а действие, которого в базе нет, запрещено всем:
    новая кнопка не должна заработать раньше, чем кто-то решил, кому она доступна;
  · отправка в Amazon начинается с утверждающего — контент-менеджеру она закрыта;
  · вход старше auth_max_login_hours уходит на повторный вход через Google, а карточка
    привязана к Google ID: адрес у другого аккаунта — прежняя карточка в архив, новый
    человек входит «Просмотром» (14.10.2026).

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
ОТВЕТЫ: dict = {"mode": 1, "matrix": [], "user": None, "bind": "ok"}
ЗАВЕДЕНО: list = []      # почты, для которых приложение выполнило INSERT в app_users


class _Cur:
    def __init__(self):
        self._rows = []

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if "ls_auth_enabled" in s:
            self._rows = [] if ОТВЕТЫ["mode"] is None else [(ОТВЕТЫ["mode"],)]
        elif "app_user_bind_sub" in s:
            r = ОТВЕТЫ["bind"]
            if r.startswith("archived:"):
                ОТВЕТЫ["user"] = None        # карточку унесли в архив — по почте её больше нет
            self._rows = [(r,)]
        elif "app_permissions" in s:
            self._rows = list(ОТВЕТЫ["matrix"])
        elif s.startswith("INSERT INTO kabinet_data.app_users"):
            ЗАВЕДЕНО.append(params[0])
            u = ОТВЕТЫ["user"]
            ОТВЕТЫ["user"] = ("viewer", True, None, False) if u is None else ((u[0] or "viewer"),) + tuple(u[1:])
            self._rows = []
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
      all(auth.can(a) for a in auth.PAGE_ACTIONS if a != "ls.page.textgen"))
check("кроме генератора текстов — решение владельца 21.10.2026",
      not auth.can("ls.page.textgen"))

сброс(mode=2, matrix=[])
как(auth.VIEWER, робот=True)
check("и в раскатке роботу по-прежнему нельзя", not auth.can("ls.amazon.push"))
check("и генератора в раскатке ему тоже не видно", not auth.can("ls.page.textgen"))

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

# --- 4а. рабочая почта входит сама ---------------------------------------------
ОТКАЗЫ: list = []
auth._screen = lambda *a, **k: ОТКАЗЫ.append(a)
auth._telegram = lambda text: None
auth.notify_unknown = lambda *a, **k: None


ВЫХОДЫ: list = []
ВХОДЫ: list = []
auth.st.logout = lambda: ВЫХОДЫ.append(1)
_log_login_orig = auth._log_login
auth._log_login = lambda email, result, reason="": ВХОДЫ.append(result)


def войти(почта, user, возраст_ч=1.0, bind="ok"):
    import time
    ЗАВЕДЕНО.clear(); ОТКАЗЫ.clear(); ВЫХОДЫ.clear(); ВХОДЫ.clear()
    сброс(mode=1, matrix=БАЗА, user=user, bind=bind)
    auth._max_login_hours.clear()
    auth.st.user = types.SimpleNamespace(is_logged_in=True, email=почта, name="Новый",
                                         sub="sub-1", iat=time.time() - возраст_ч * 3600)
    auth.guard()
    return auth.current()


u = войти("новый@dniprom.com", None)
check("рабочая почта без карточки — карточка заведена", ЗАВЕДЕНО == ["новый@dniprom.com"])
check("и человек вошёл «Просмотром», без экрана отказа", not ОТКАЗЫ and u.known and u.role == auth.VIEWER)

u = войти("кто@dniprom.com", ("", True, None, False))
check("рабочая почта с пустой ролью — получает «Просмотр»", ЗАВЕДЕНО and not ОТКАЗЫ and u.role == auth.VIEWER)

u = войти("кто@dniprom.com", ("approver", True, None, False))
check("назначенная роль не понижается", not ЗАВЕДЕНО and u.role == auth.APPROVER)

u = войти("кто@dniprom.com", ("", False, None, False))
check("выключенная карточка — отказ, роль не выдаётся", not ЗАВЕДЕНО and ОТКАЗЫ)

u = войти("кто@dniprom.com", ("", True, None, True))
check("истёкший срок — отказ, роль не выдаётся", not ЗАВЕДЕНО and ОТКАЗЫ)

u = войти("чужой@gmail.com", None)
check("чужой домен без карточки — отказ, карточка не заводится", not ЗАВЕДЕНО and ОТКАЗЫ)

# --- 4б. срок входа и Google ID -------------------------------------------------
u = войти("кто@dniprom.com", ("approver", True, None, False), возраст_ч=200)
check("вход старше 168 ч — повторный вход через Google, внутрь не пускаем",
      ВЫХОДЫ == [1] and "relogin" in ВХОДЫ and "ok" not in ВХОДЫ)

u = войти("кто@dniprom.com", ("approver", True, None, False), возраст_ч=100)
check("вход моложе 168 ч — без повторного входа", not ВЫХОДЫ and u.role == auth.APPROVER)

u = войти("кто@dniprom.com", ("approver", True, None, False), bind="archived:кто@dniprom.com~20261014-1200")
check("адрес у другого Google-аккаунта — роли прежнего не достаются, новый входит «Просмотром»",
      "reassigned" in ВХОДЫ and ЗАВЕДЕНО == ["кто@dniprom.com"] and u.role == auth.VIEWER and not ОТКАЗЫ)

u = войти("чужой@gmail.com", ("approver", True, None, False), bind="archived:чужой@gmail.com~20261014-1200")
check("исключение вне домена у другого Google-аккаунта — отказ, карточка не заводится",
      not ЗАВЕДЕНО and ОТКАЗЫ)

# --- 5. список страниц и список прав — один и тот же -------------------------
check("у каждой страницы есть право видимости",
      all(("ls.page." + k) in auth._MATRIX for k, *_ in auth.PAGES))
check("лишних прав видимости нет",
      {a for a in auth._MATRIX if a.startswith("ls.page.")}
      == {"ls.page." + k for k, *_ in auth.PAGES})

# --- 6. роль пилота «Генератор текстов» (21.10.2026) -------------------------
# Видит ОДНУ страницу и одно действие — ls.textgen.accept; сам генератор и это
# действие — только она и админ.
ДЕЙСТВИЯ = ("ls.admin", "ls.content.edit", "ls.amazon.push", "ls.method.edit",
            "ls.settings.edit")
for матрица, где in (([], "по коду"),
                     ([(a, r) for a, роли in auth._MATRIX.items() for r in роли], "по базе")):
    сброс(mode=1, matrix=матрица)
    как(auth.TEXTGEN)
    check(f"пилот видит генератор ({где})", auth.can("ls.page.textgen"))
    check(f"и больше ни одной страницы ({где})",
          not any(auth.can(a) for a in auth.PAGE_ACTIONS if a != "ls.page.textgen"))
    check(f"и ни одного прежнего действия ({где})", not any(auth.can(a) for a in ДЕЙСТВИЯ))
    check(f"принимает тексты и грузит паспорт ({где})", auth.can("ls.textgen.accept"))
    сброс(mode=1, matrix=матрица)
    как(auth.ADMIN)
    check(f"администратор видит генератор ({где})", auth.can("ls.page.textgen"))
    check(f"администратор принимает тексты ({где})", auth.can("ls.textgen.accept"))
    for роль in (auth.VIEWER, auth.CONTENT_MANAGER, auth.APPROVER):
        сброс(mode=1, matrix=матрица)
        как(роль)
        check(f"{роль} генератор не видит ({где})", not auth.can("ls.page.textgen"))
        check(f"{роль} тексты не принимает ({где})", not auth.can("ls.textgen.accept"))
        check(f"{роль} прочие страницы видит, как раньше ({где})",
              auth.can("ls.page.synthesis") and auth.can("ls.page.content"))

# до SQL-файла строки ls.page.textgen в базе нет — генератор не видит никто
сброс(mode=1, matrix=[r for r in БАЗА if r[0] != "ls.page.textgen"])
как(auth.ADMIN)
check("без строки в базе генератор не видит даже администратор", not auth.can("ls.page.textgen"))
# до SQL права ls.textgen.accept строки в базе нет — кнопки выключены у всех
сброс(mode=1, matrix=[(a, r) for a, роли in auth._MATRIX.items() for r in роли if a != "ls.textgen.accept"])
как(auth.ADMIN)
check("без строки ls.textgen.accept в базе не принимает даже администратор", not auth.can("ls.textgen.accept"))

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
