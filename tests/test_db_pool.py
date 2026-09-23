# -*- coding: utf-8 -*-
"""
tests/test_db_pool.py — соединение с Lakebase переиспользуется, а не
открывается заново на каждый запрос.

Одно соединение стоит секунду-полторы: `generate_database_credential` —
REST-вызов в Databricks, плюс TLS-рукопожатие с Postgres. До 21.09
и токен, и соединение брались НА КАЖДЫЙ запрос (движок стоял на
NullPool), и первый показ Каталога открывал 11 соединений, Матрицы —
10, Методологии — 9. На Кабинете тот же класс дал 40 секунд из 56.

Проверяется не «есть ли пул», а ПОВЕДЕНИЕ, в котором легко ошибиться:

1. Двадцать пять обращений подряд — одно физическое соединение.
2. `close()` возвращает соединение в пул, а не рвёт; после него
   ничего не «занято» — иначе восьми хватит на восемь действий,
   а девятое встанет в очередь на 30 секунд.
3. `with conn:` — это КОММИТ без закрытия, как у psycopg2. У прокси
   SQLAlchemy `__exit__` — это close(): соединение ушло бы в пул без
   коммита, транзакция откатилась бы при возврате, и запись пропала
   бы МОЛЧА. Так написаны все записи проекта.
4. Исключение внутри `with` — откат, не коммит.
5. `search_path` выставляется на каждом ФИЗИЧЕСКОМ соединении:
   иначе второй запрос из пула пошёл бы в public и не нашёл таблиц.
6. Токен берётся один раз на все соединения, а на отказ авторизации
   (кеш пережил срок) — заново, и попытка ровно одна.

psycopg2 подменён целиком: сеть и база не трогаются.

Запуск (pytest не нужен):  python tests/test_db_pool.py
"""
from __future__ import annotations

import pathlib
import sys

import psycopg2
import psycopg2.extensions
import psycopg2.extras

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


# ------------------------------------------------- поддельный psycopg2
class Cur:
    def __init__(self, conn):
        self.conn = conn
        self.connection = conn          # диалект читает cursor.connection.notices
        self.description = None
        self._rows: list = []
        self.rowcount = -1
        self.arraysize = 1

    def execute(self, q, params=None):
        self.conn.log.append(str(q))
        q1 = " ".join(str(q).split()).lower()

        def one(val):
            self.description = [("x", None, None, None, None, None, None)]
            self._rows = [(val,)]

        if "version()" in q1:
            one("PostgreSQL 16.4")
        elif "standard_conforming_strings" in q1:
            one("on")
        elif "current_schema" in q1:
            one("listing_data")
        elif "transaction_isolation" in q1 or "transaction isolation" in q1:
            one("read committed")
        elif "select 1" in q1:
            one(1)
        elif q1.startswith("show "):
            one("on")
        else:
            self.description = None
            self._rows = []

    def executemany(self, q, seq):
        self.conn.log.append(str(q))

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def fetchmany(self, n=None):
        return list(self._rows)

    def __iter__(self):
        return iter(self._rows)

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


class Conn:
    opened: list = []

    def __init__(self, **kw):
        Conn.opened.append(self)
        self.kw = kw
        self.log: list = []
        self.closed = 0
        self.commits = 0
        self.rollbacks = 0
        self.notices: list = []
        self.autocommit = False
        self.isolation_level = psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED

    def cursor(self, *a, **k):
        return Cur(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = 1

    def set_isolation_level(self, lvl):
        self.isolation_level = lvl

    def set_client_encoding(self, enc):
        pass

    @property
    def status(self):
        return psycopg2.extensions.STATUS_READY

    @property
    def info(self):
        class _Info:
            server_version = 160004

            @staticmethod
            def parameter_status(name):
                return "UTF8"
        return _Info()

    def get_dsn_parameters(self):
        return {}

    def __enter__(self):
        return self

    def __exit__(self, t, e, tb):
        self.commit() if t is None else self.rollback()


AUTH_FAIL = {"n": 0}          # сколько ещё раз connect() ответит «пароль не тот»


def fake_connect(*a, **kw):
    if AUTH_FAIL["n"] > 0:
        AUTH_FAIL["n"] -= 1
        raise psycopg2.OperationalError("FATAL: password authentication failed")
    return Conn(**kw)


psycopg2.connect = fake_connect
# диалект SQLAlchemy на каждое новое соединение регистрирует типы
# на РЕАЛЬНОМ psycopg2-соединении; поддельному это не нужно
for _name in ("register_uuid", "register_default_json",
              "register_default_jsonb", "register_hstore"):
    setattr(psycopg2.extras, _name, lambda *a, **k: None)

import os                                                # noqa: E402
os.environ["DATABASE_URL"] = "postgresql://fake/db"

import pandas as pd                                      # noqa: E402
import services.db as db                                 # noqa: E402

# --- 1. много обращений — одно соединение
Conn.opened.clear()
for _ in range(20):
    pd.read_sql("SELECT 1 AS a", db.get_engine())
for _ in range(5):
    c = db.get_conn()
    with c, c.cursor() as cur:
        cur.execute("INSERT INTO product_matrix VALUES (1)")
    c.close()
check(f"25 обращений — одно физическое соединение ({len(Conn.opened)})",
      len(Conn.opened) == 1)
check("и оно живо: close() страницы его не рвёт",
      Conn.opened[0].closed == 0)

# --- 2. ничего не «занято» после close(): иначе девятое действие
# встанет в очередь на 30 секунд при восьми в пуле
check(f"после возврата занятых нет ({db.get_engine().pool.status()})",
      "Checked out connections: 0" in db.get_engine().pool.status())
_held = [db.get_conn() for _ in range(3)]
check("пока держим три — занято три",
      "Checked out connections: 3" in db.get_engine().pool.status())
for c in _held:
    c.close()
check("отпустили — снова ноль",
      "Checked out connections: 0" in db.get_engine().pool.status())

# --- 3. `with conn:` — КОММИТ без закрытия (семантика psycopg2).
# У прокси SQLAlchemy __exit__ это close(): соединение вернулось бы
# в пул без коммита, транзакция откатилась бы, и запись пропала молча.
conn = db.get_conn()
phys = conn._fairy.dbapi_connection
before = phys.commits
with conn, conn.cursor() as cur:
    cur.execute("INSERT INTO synthesis_changes VALUES (1)")
check("после `with conn:` есть коммит", phys.commits == before + 1)
check("и соединение ещё в руках, не возвращено в пул",
      "Checked out connections: 1" in db.get_engine().pool.status())
conn.close()

# --- 4. исключение внутри `with` — откат, не коммит
conn = db.get_conn()
phys = conn._fairy.dbapi_connection
c0, r0 = phys.commits, phys.rollbacks
try:
    with conn, conn.cursor() as cur:
        cur.execute("INSERT INTO synthesis_changes VALUES (2)")
        raise RuntimeError("сбой посреди записи")
except RuntimeError:
    pass
check("исключение в `with` — откат, коммита нет",
      phys.rollbacks == r0 + 1 and phys.commits == c0)
conn.close()

# --- 5. search_path — на каждом ФИЗИЧЕСКОМ соединении
# Без него запрос из пула пошёл бы в public и не нашёл наших таблиц.
check("search_path выставлен на физическом соединении",
      any("search_path" in q and db.DB_SCHEMA in q for q in Conn.opened[0].log))

# --- 6. токен: один на все соединения, но не вечный
CALLS = {"n": 0}


def fetch():
    CALLS["n"] += 1
    return f"token-{CALLS['n']}"


db._token_box().update({"token": None, "at": 0.0, "key": None})
tokens = [db._pg_token(fetch, "sp:host:endpoint") for _ in range(5)]
check(f"пять соединений — один запрос токена ({CALLS['n']})",
      CALLS["n"] == 1 and len(set(tokens)) == 1)
check("другое подключение — свой токен",
      db._pg_token(fetch, "nb:other") != tokens[0] and CALLS["n"] == 2)
import time                                              # noqa: E402
db._token_box()["at"] = time.time() - db.TOKEN_TTL_S - 1
db._pg_token(fetch, "nb:other")
check(f"токен старше {db.TOKEN_TTL_S // 60} минут берётся заново", CALLS["n"] == 3)
# У Lakebase токен живёт час. Кеш обязан истекать РАНЬШЕ — иначе новое
# соединение однажды пойдёт с мёртвым паролем; и соединение в пуле
# не должно жить дольше, чем кеш токена плюс его запас.
check(f"кеш токена ({db.TOKEN_TTL_S // 60} мин) истекает раньше часа",
      db.TOKEN_TTL_S <= 55 * 60)
check(f"соединение в пуле пересоздаётся ({db.POOL_RECYCLE_S // 60} мин) "
      f"не позже, чем истекает кеш токена",
      0 < db.POOL_RECYCLE_S <= db.TOKEN_TTL_S)

# --- 6б. протухший токен: соединение открывается заново, попытка ОДНА.
# Кеш пережил срок (процесс Cloud живёт сутками), Postgres отвечает
# «password authentication failed» — надо взять свежий токен и
# повторить РОВНО раз: цикл повторов на живой ошибке — это минуты
# ожидания вместо одной понятной строки.
SP = {"host": "https://dbc", "client_id": "sp-id", "client_secret": "x",
      "endpoint_name": "lakebase", "pg_host": "pg.example"}
db._databricks_section = lambda: dict(SP)


class _FakeCred:
    token = "sp-token"


class _FakeWorkspace:
    def __init__(self, **kw):
        _FakeWorkspace.calls += 1
        self.postgres = type("P", (), {
            "generate_database_credential": staticmethod(lambda endpoint: _FakeCred())})()


_FakeWorkspace.calls = 0
import types                                              # noqa: E402
_sdk = types.ModuleType("databricks.sdk")
_sdk.WorkspaceClient = _FakeWorkspace
_pkg = types.ModuleType("databricks")
_pkg.sdk = _sdk
sys.modules.setdefault("databricks", _pkg)
sys.modules["databricks.sdk"] = _sdk

db._token_box().update({"token": None, "at": 0.0, "key": None})
Conn.opened.clear()
AUTH_FAIL["n"] = 1
c = db.connect_physical()
check(f"отказ авторизации — свежий токен и ОДНА повторная попытка "
      f"(соединений {len(Conn.opened)}, запросов токена {_FakeWorkspace.calls})",
      len(Conn.opened) == 1 and AUTH_FAIL["n"] == 0 and _FakeWorkspace.calls == 2)
c.close()
AUTH_FAIL["n"] = 2
try:
    db.connect_physical()
    _second = "не упало"
except psycopg2.OperationalError:
    _second = "упало"
check("второй отказ подряд не уходит в цикл повторов — ошибка наверх",
      _second == "упало")
AUTH_FAIL["n"] = 0
db._databricks_section = lambda: {}

# --- 7. страницы соединение не создают: их точка входа — get_conn/get_engine
_src = (ROOT / "pages").glob("*.py")
_direct = [p.name for p in _src
           if "psycopg2.connect" in p.read_text(encoding="utf-8")]
check(f"ни одна страница не зовёт psycopg2.connect напрямую ({_direct})",
      not _direct)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
