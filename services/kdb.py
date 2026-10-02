# -*- coding: utf-8 -*-
"""services/kdb.py — второе соединение: база Кабинета, и только ради входа.

Listing Suite живёт в своём Lakebase (`listing_data`, `services/db.py`). Но «кто это
и что ему можно» лежит в базе Кабинета: один список людей на два продукта. Своя копия
списка в `listing_data` расходилась бы с кабинетной молча — и обнаружилось бы это в
день, когда кого-то уволили, а доступ остался.

Поэтому здесь ВТОРОЕ соединение, к другому эндпоинту, и ходит оно ровно в шесть
таблиц: `app_users`, `app_user_countries`, `app_permissions`, `reorder_params` на
чтение, `app_login_log`, `app_action_log` на запись, плюс `qa_tokens` для тестовой
ссылки. Бизнес-данных здесь нет и быть не должно — кросс-проектных запросов мы не
делаем.

Принципал тот же, что у своей базы (`[databricks]`): `583bf6d1-…`
(kabinet-dashboard-sp) работает в обоих Lakebase, поэтому гранты в `kabinet_data` у
него уже есть. Отличается только адрес: `pg_host` и `endpoint_name` Кабинета лежат в
секции `[kabinet_db]`.

Пул — как в Кабинете: соединение стоит около двух секунд (REST-вызов за токен плюс
TLS), и открывать его на каждый запрос значило бы платить эти секунды на каждом
прогоне страницы.
"""
from __future__ import annotations

import time

import psycopg2
import psycopg2.extensions
import psycopg2.pool
import streamlit as st

_TOKEN_TTL_S = 50 * 60     # токен живёт час; держим 50 минут
_POOL_MAX = 4              # вход — редкие короткие запросы, восьми здесь не нужно
_PROBE_AFTER_IDLE_S = 60

# Что сказать, когда адреса нет. Текст один на все места: сообщение об отсутствующей
# настройке — это инструкция, а не жалоба.
# ПЕРВАЯ строка обязана быть самодостаточной: в журнал и на экран уезжает именно она
# (остальное обрезается), и «Нет адреса базы Кабинета» без имени секции заставляло бы
# искать настройку наугад.
NEED_SECRETS = (
    "Нет секции [kabinet_db] в секретах: нужны pg_host и endpoint_name базы Кабинета.\n"
    "[kabinet_db]\n"
    'pg_host = "ep-….database.us-east-1.cloud.databricks.com"\n'
    'endpoint_name = "projects/kabinet-dashboard/branches/production/endpoints/primary"\n'
    "Хост и клиент берутся из [databricks] — тот же принципал."
)


# Последняя причина, по которой подключиться не удалось. Модульная переменная, а не
# кеш Streamlit: она нужна тому же прогону, который её записал, и переживает прогоны в
# том же процессе.
#
# Зачем это вообще: `mode()` при любой неудаче отдаёт раскатку — чтобы нехватка
# настройки не отбирала у людей кнопки. Но «раскатка по настройке» и «раскатка потому
# что не прочитали» — РАЗНЫЕ вещи, и неразличимы они были только из-за того, что
# причина нигде не оставалась. Молчание тут стоило одного круга «ребут — не работает —
# почему».
_БЕДА = {"что": "", "когда": 0.0}


def последняя_беда() -> str:
    """Текст последней неудачи подключения или пустая строка."""
    return _БЕДА["что"]


def _запомнить(e: Exception) -> None:
    _БЕДА["что"] = f"{type(e).__name__}: {str(e).splitlines()[0][:200]}"
    _БЕДА["когда"] = time.time()
    # в лог приложения тоже: на Streamlit Cloud это первое место, куда смотрят
    print(f"[kabinet_db] подключиться не удалось — {_БЕДА['что']}", flush=True)


def _получилось() -> None:
    _БЕДА["что"], _БЕДА["когда"] = "", 0.0


def _sec(section: str) -> dict:
    try:
        if section in st.secrets:
            return dict(st.secrets[section])
    except Exception:
        pass
    # локальная разработка: secrets.toml читает services.db, им и пользуемся
    try:
        from services.db import _load_secrets
        return dict(_load_secrets().get(section) or {})
    except Exception:
        return {}


def configured() -> bool:
    """Настроено ли подключение. Отдельной функцией, потому что об этом спрашивают
    до первого запроса: страница должна сказать «вход не настроен», а не упасть."""
    d, k = _sec("databricks"), _sec("kabinet_db")
    return bool(d.get("client_id") and k.get("pg_host") and k.get("endpoint_name"))


@st.cache_resource(show_spinner=False)
def _token_box() -> dict:
    # не cache_data: страницы зовут st.cache_data.clear() после сохранений, и токен
    # вылетал бы вместе с данными — лишний вызов в Databricks на каждое сохранение
    return {"token": None, "at": 0.0}


def _token(force: bool = False) -> str:
    box = _token_box()
    if force or box["token"] is None or time.time() - box["at"] > _TOKEN_TTL_S:
        from databricks.sdk import WorkspaceClient
        d, k = _sec("databricks"), _sec("kabinet_db")
        if not configured():
            raise RuntimeError(NEED_SECRETS)
        w = WorkspaceClient(host=d["host"], client_id=d["client_id"],
                            client_secret=d["client_secret"])
        box["token"] = w.postgres.generate_database_credential(
            endpoint=k["endpoint_name"]).token
        box["at"] = time.time()
    return box["token"]


class _Pool(psycopg2.pool.ThreadedConnectionPool):
    def __init__(self, keep_idle: int, maxconn: int, **kwargs):
        # minconn у psycopg2 — это и «открыть при старте», и «сколько держать»:
        # putconn закрывает всё сверх minconn. Открывать заранее не хотим, держать —
        # хотим, поэтому создаём с нулём и поднимаем порог после.
        super().__init__(0, maxconn, **kwargs)
        self.minconn = keep_idle
        self.last_used = {}

    def _connect(self, key=None):
        self._kwargs["password"] = _token()
        return super()._connect(key)


@st.cache_resource(show_spinner=False)
def _pool() -> _Pool:
    d, k = _sec("databricks"), _sec("kabinet_db")
    if not configured():
        raise RuntimeError(NEED_SECRETS)
    return _Pool(
        _POOL_MAX, _POOL_MAX,
        host=k["pg_host"], port=5432,
        dbname=k.get("pg_database", "databricks_postgres"),
        user=k.get("pg_user", d["client_id"]),   # у сервис-принципала пользователь = client_id
        password="", sslmode="require",
    )


class Pooled:
    """Соединение из пула с интерфейсом psycopg2. `close()` возвращает в пул."""

    def __init__(self, pool, conn):
        self._pool, self._conn = pool, conn

    def cursor(self, *a, **k):
        return self._conn.cursor(*a, **k)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        conn, self._conn = self._conn, None
        if conn is None:
            return
        if self._pool is None:
            conn.close()
            return
        try:
            if conn.closed:
                self._pool.putconn(conn, close=True)
            else:
                if conn.status != psycopg2.extensions.STATUS_READY:
                    conn.rollback()     # незакрытая транзакция не должна достаться следующему
                self._pool.last_used[id(conn)] = time.time()
                self._pool.putconn(conn)
        except Exception:
            try:
                self._pool.putconn(conn, close=True)
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()

    def __getattr__(self, name):
        if name.startswith("_"):     # иначе обращение к ещё не заданному _conn зацикливается
            raise AttributeError(name)
        return getattr(self._conn, name)


def _direct():
    d, k = _sec("databricks"), _sec("kabinet_db")
    return psycopg2.connect(
        host=k["pg_host"], port=5432,
        dbname=k.get("pg_database", "databricks_postgres"),
        user=k.get("pg_user", d["client_id"]),
        password=_token(), sslmode="require")


def get_conn():
    """Соединение с базой Кабинета. Бросает RuntimeError, если адрес не настроен —
    молча отдавать «прав нет» нельзя, это читалось бы как снятый доступ.

    Любая неудача запоминается (`последняя_беда()`) и уходит в лог приложения: выше
    она превратится в раскатку, и без этого следа «вход не включили» и «вход не
    прочитался» выглядели бы одинаково."""
    try:
        return _получить()
    except Exception as e:
        _запомнить(e)
        raise


def _получить():
    try:
        pool = _pool()
    except RuntimeError:
        raise
    except Exception:
        return Pooled(None, _direct())
    for attempt in range(3):
        try:
            conn = pool.getconn()
        except psycopg2.pool.PoolError:
            return Pooled(None, _direct())
        except psycopg2.OperationalError as e:
            if attempt == 0 and "password" in str(e).lower():
                _token(force=True)
                continue
            raise
        try:
            if conn.closed:
                raise psycopg2.InterfaceError("closed")
            if time.time() - pool.last_used.get(id(conn), 0) > _PROBE_AFTER_IDLE_S:
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.close()
                conn.rollback()
            _получилось()
            return Pooled(pool, conn)
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            try:
                pool.putconn(conn, close=True)
            except Exception:
                pass
    return Pooled(None, _direct())
