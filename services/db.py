# -*- coding: utf-8 -*-
"""
services/db.py — подключение к базе + product_matrix. v2 (Lakebase-ready).

Три режима подключения (порядок автоопределения в get_conn):

1. NOTEBOOK-режим (ноутбук Databricks, конвейер):
   доступен databricks.sdk И задан LISTING_LAKEBASE_ENDPOINT ->
   WorkspaceClient().postgres.generate_database_credential() -> psycopg2
   с OAuth-токеном (~1 час жизни).

ПУЛ СОЕДИНЕНИЙ (21.09). Одно соединение с Lakebase стоит дорого:
generate_database_credential — REST-вызов в Databricks (~1 с) плюс
TLS-рукопожатие с Postgres (~0,5–1 с). До 21.09 get_conn() делал это
на КАЖДЫЙ вызов, а движок pandas стоял на NullPool — то есть на каждый
pd.read_sql. Замер по AppTest с фикстурами тестов: первый показ
страницы — 6–9 соединений, Синтез с открытой карточкой — 15–18,
партия — 41; на Кабинете тот же класс дал 40 секунд из 56 на первом
показе «Справочников». Теперь: токен кешируется на 50 минут
(_pg_token), физические соединения живут в QueuePool SQLAlchemy
(get_engine), а get_conn() выдаёт соединение ИЗ ПУЛА — close() у него
возвращает в пул, а не рвёт. Интерфейс страниц прежний:
conn = get_conn(); …; conn.close(). Для нового физического соединения
токен берётся свежий, если кешу больше 50 минут: Postgres проверяет
пароль только при подключении, уже открытые живут дальше.

2. DASHBOARD-режим (Streamlit Cloud):
   секция [databricks] в секретах (host, client_id, client_secret,
   pg_host, endpoint_name) -> service principal OAuth — как в Кабинете.

3. DSN-режим (локальная разработка):
   DATABASE_URL из env / .streamlit/secrets.toml -> psycopg2.connect(url).

ПРАВИЛО DDL: приложение схему НЕ создаёт и НЕ меняет — только SELECT
и разрешённые INSERT/UPDATE. Миграции идут отдельными .sql файлами
из migrations/ и применяются через Databricks.

Здесь раньше жила ensure_all_schemas() — «единая точка миграций», которая
не работала: все три её импорта падали, и четыре миграции за неделю прошли
мимо неё. Мёртвый механизм хуже отсутствующего — он создаёт ощущение,
что схема под контролем, и его убрали намеренно.
"""

from __future__ import annotations

import os
from typing import Optional

import psycopg2
import streamlit as st

DB_SCHEMA = "listing_data"   # все наши таблицы живут здесь


# ---------------------------------------------------------------- конфиг

_SECRETS: dict = {}


def _load_secrets() -> dict:
    global _SECRETS
    if _SECRETS:
        return _SECRETS
    path = os.path.join(".streamlit", "secrets.toml")
    if os.path.exists(path):
        try:
            try:
                import tomllib
                with open(path, "rb") as f:
                    _SECRETS = tomllib.load(f)
            except ModuleNotFoundError:
                import toml
                _SECRETS = toml.load(path)
        except Exception:
            _SECRETS = {}
    return _SECRETS


def cfg_source(name: str,
               default: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    """(значение, источник): env -> secrets.toml на диске -> st.secrets ->
    default. Источник нужен диагностике в Настройках — «а тот ли ключ
    подставился» иначе не проверить, не читая логи."""
    if name in os.environ:
        return os.environ[name], "env"

    val = _load_secrets().get(name)
    if val is not None:
        return val, "secrets.toml"

    try:
        import streamlit as st
        if name in st.secrets:
            return st.secrets[name], "st.secrets"
    except Exception:
        pass

    return default, None


def cfg(name: str, default: Optional[str] = None) -> Optional[str]:
    """Читает секрет: env -> secrets.toml на диске -> st.secrets (Streamlit Cloud) -> default.
    Третий шаг нужен, потому что на Streamlit Cloud секреты не всегда доступны
    как обычный файл на диске — только через встроенный st.secrets."""
    return cfg_source(name, default)[0]


# ---------------------------------------------------------------- подключение

def _apply_schema(conn):
    """Все запросы без префикса идут в нашу схему."""
    with conn.cursor() as cur:
        cur.execute(f"SET search_path TO {DB_SCHEMA}, public")
    conn.commit()
    return conn


TOKEN_TTL_S = 50 * 60      # токен Lakebase живёт час; свежий — за десять минут до


@st.cache_resource(show_spinner=False)
def _token_box() -> dict:
    # cache_resource, а не cache_data: страницы после записи зовут
    # cache_data.clear(), и токен вылетал бы вместе с данными —
    # лишний REST-вызов в Databricks на каждое сохранение
    return {"token": None, "at": 0.0, "key": None}


def _pg_token(fetch, key: str, force: bool = False) -> str:
    """Временный пароль Lakebase из кеша; `fetch()` зовётся, когда кеша
    нет, он старше TOKEN_TTL_S, от другого подключения или force."""
    import time
    box = _token_box()
    if (force or box["token"] is None or box["key"] != key
            or time.time() - box["at"] > TOKEN_TTL_S):
        box["token"], box["at"], box["key"] = fetch(), time.time(), key
    return box["token"]


def _lakebase_notebook_conn(force_token: bool = False):
    """Notebook-режим: OAuth-токен через Databricks SDK (паттерн Кабинета)."""
    from databricks.sdk import WorkspaceClient  # есть в рантайме Databricks
    endpoint = cfg("LISTING_LAKEBASE_ENDPOINT")

    def fetch():
        return WorkspaceClient().postgres.generate_database_credential(endpoint=endpoint).token

    return psycopg2.connect(
        host=cfg("LISTING_LAKEBASE_HOST"),
        dbname=cfg("LISTING_LAKEBASE_DB", "databricks_postgres"),
        user=cfg("LISTING_LAKEBASE_USER"),
        password=_pg_token(fetch, f"nb:{endpoint}", force_token),
        sslmode="require",
    )


def _databricks_section() -> dict:
    """Секция [databricks] из секретов (Streamlit Cloud) — как у Кабинета."""
    s = _load_secrets().get("databricks")
    if s:
        return dict(s)
    try:
        import streamlit as st
        if "databricks" in st.secrets:
            return dict(st.secrets["databricks"])
    except Exception:
        pass
    return {}


def _lakebase_sp_conn(d: dict, force_token: bool = False):
    """Dashboard-режим: service principal OAuth (паттерн Streamlit-Кабинета)."""
    from databricks.sdk import WorkspaceClient

    def fetch():
        w = WorkspaceClient(host=d["host"], client_id=d["client_id"],
                            client_secret=d["client_secret"])
        return w.postgres.generate_database_credential(endpoint=d["endpoint_name"]).token

    return psycopg2.connect(
        host=d["pg_host"],
        dbname=d.get("pg_database", "databricks_postgres"),
        user=d.get("pg_user", d["client_id"]),   # у SP пользователь = client_id
        password=_pg_token(fetch, f"sp:{d['host']}:{d['endpoint_name']}", force_token),
        sslmode="require",
    )


def _is_auth_error(e: Exception) -> bool:
    return "password" in str(e).lower() or "authentication" in str(e).lower()


def connect_physical():
    """НОВОЕ физическое соединение — то, что стоит секунду-полторы.
    Зовёт только пул (creator движка); страницы сюда не ходят. Порядок:
    1) ноутбук Databricks (LISTING_LAKEBASE_* + ambient auth)
    2) дашборд Streamlit ([databricks] service principal — как Кабинет)
    3) DATABASE_URL (локальная разработка / обычный Postgres)
    Протухший кешированный токен даёт отказ авторизации — тогда токен
    берётся заново и попытка одна."""
    if cfg("LISTING_LAKEBASE_ENDPOINT"):
        try:
            import databricks.sdk  # noqa: F401
        except ImportError:
            pass
        else:
            try:
                return _apply_schema(_lakebase_notebook_conn())
            except psycopg2.OperationalError as e:
                if not _is_auth_error(e):
                    raise
                return _apply_schema(_lakebase_notebook_conn(force_token=True))
    d = _databricks_section()
    if d.get("client_id"):
        try:
            return _apply_schema(_lakebase_sp_conn(d))
        except psycopg2.OperationalError as e:
            if not _is_auth_error(e):
                raise
            return _apply_schema(_lakebase_sp_conn(d, force_token=True))
    url = cfg("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Нет подключения: [databricks] в секретах (дашборд), "
            "LISTING_LAKEBASE_* (ноутбук) или DATABASE_URL (локально)"
        )
    return _apply_schema(psycopg2.connect(url))


POOL_SIZE = 8            # одновременных соединений на процесс; сверх — ждём до 30 с
POOL_RECYCLE_S = 45 * 60  # физическое соединение не старше токена: пересоздаётся раньше, чем он истечёт


@st.cache_resource(show_spinner=False)
def get_engine():
    """Движок SQLAlchemy с ПУЛОМ — для pandas и для get_conn().

    pandas официально поддерживает только SQLAlchemy-подключения; с голым
    psycopg2 он работает, но предупреждает на каждый вызов, и лог тонет
    в этих строках так, что настоящих ошибок не видно.

    creator=connect_physical оставляет всю нашу логику на месте: три
    режима подключения, OAuth-токен Lakebase и search_path продолжают
    работать как работали — на КАЖДОЕ ФИЗИЧЕСКОЕ соединение, а не на
    каждый запрос. Раньше здесь стоял NullPool «чтобы соединение не
    пережило токен»: но Postgres проверяет пароль только при подключении,
    и открытое соединение живёт дальше; пережить токен может только
    попытка ОТКРЫТЬ новое — её страхует pool_recycle (соединение
    пересоздаётся раньше истечения токена) и свежий токен в creator.

    pool_pre_ping — «SELECT 1» перед выдачей: соединение, пролежавшее
    в пуле, сервер мог закрыть; лишний круг до базы дешевле, чем
    OperationalError посреди страницы. Один процесс Cloud обслуживает
    все сессии, пул общий — POOL_SIZE соединений на всех.
    """
    from sqlalchemy import create_engine
    return create_engine("postgresql+psycopg2://", creator=connect_physical,
                         pool_size=POOL_SIZE, max_overflow=2, pool_timeout=30,
                         pool_pre_ping=True, pool_recycle=POOL_RECYCLE_S)


class PooledConnection:
    """Соединение из пула с ПОВЕДЕНИЕМ psycopg2.

    Обёртка нужна из-за одной разницы: у psycopg2 `with conn:` — это
    commit при выходе (или rollback при исключении) БЕЗ закрытия, и так
    написаны все записи в проекте (`with conn, conn.cursor() as cur:`,
    потом `conn.close()`). У прокси SQLAlchemy `__exit__` — это close():
    соединение ушло бы в пул без коммита, reset_on_return откатил бы
    транзакцию, и запись молча терялась бы. Здесь семантика psycopg2,
    а close() возвращает соединение в пул, не рвёт.
    """

    def __init__(self, fairy):
        self._fairy = fairy

    def cursor(self, *a, **k):
        return self._fairy.cursor(*a, **k)

    def commit(self):
        self._fairy.dbapi_connection.commit()

    def rollback(self):
        self._fairy.dbapi_connection.rollback()

    def close(self):
        fairy, self._fairy = self._fairy, None
        if fairy is not None:
            fairy.close()          # в пул; незавершённая транзакция откатывается там

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._fairy.dbapi_connection, name)

    def __del__(self):
        try:
            self.close()           # забытое соединение возвращается в пул, а не висит до GC пула
        except Exception:
            pass


def get_conn():
    """Соединение ИЗ ПУЛА с интерфейсом psycopg2: cursor / commit /
    rollback / close и `with conn:` = commit. close() возвращает его
    в пул, а не рвёт. Единственная точка входа для записи; чтение
    через pandas — get_engine()."""
    return PooledConnection(get_engine().raw_connection())


def safe_read(sql: str, params=None) -> tuple:
    """Чтение, которое отличает «пусто» от «сломалось».

    Возвращает (df, причина). Пустой DataFrame с причиной None — это
    «в базе ничего нет»; пустой с причиной — «прочитать не удалось».
    Разница не академическая: на пустых данных страницы говорят
    «Данных ещё нет — соберите товары в Матрице», то есть при
    недоступной базе ПОСЫЛАЮТ ЧЕЛОВЕКА ЗАВОДИТЬ ЗАНОВО то, что в базе
    уже лежит. Молчание тут хуже ошибки: ошибку видно, а это выглядит
    нормальной работой.

    Импорт pandas внутри функции намеренно: services/db.py тянется
    ноутбуком, где pandas может не стоять, а подключение нужно.
    """
    import pandas as pd
    try:
        return pd.read_sql(sql, get_engine(), params=params), None
    except Exception as e:
        return pd.DataFrame(), f"{type(e).__name__}: {e}"


def table_exists(name: str) -> bool | None:
    """Есть ли таблица в базе. None — проверить не удалось.

    Нужно там, где «таблицы нет» и «таблица пустая» значат разное.
    Живой пример: реестр политик Amazon. Страница «Методология»
    говорила «Новых изменений нет — все источники соответствуют
    текущим методологиям», а таблицы `policy_alerts` в базе не
    существует вовсе — то есть утверждение о политиках делалось на
    пустом месте, без единой проверки.

    Три состояния различаются намеренно: True — таблица есть (пусто
    значит пусто), False — таблицы нет (слежение не настроено),
    None — судить не по чему.
    """
    df, err = safe_read("SELECT to_regclass(%(n)s) AS t",
                        params={"n": name})
    if err or df.empty:
        return None
    return df.iloc[0]["t"] is not None


# ---------------------------------------------------------------- матрица

def missing_columns(table: str, columns: list[str]) -> list[str] | None:
    """Какие из колонок в таблице ЕЩЁ нет. None — судить не по чему.

    Нужно там, где код и миграция едут порознь: код в main оказывается
    на Cloud раньше, чем .sql — в Databricks, и страница, читающая
    новую колонку, падает целиком с «column does not exist». Так
    18.09 умер Каталог на четырёх колонках Buy Box и BSR. Страница
    обязана работать со старой схемой и сказать словами, какой
    миграции не хватает — а не лежать до её применения.
    """
    df, err = safe_read(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = %(s)s AND table_name = %(t)s
          AND column_name = ANY(%(c)s)
        """, {"s": DB_SCHEMA, "t": table, "c": list(columns)})
    if err:
        return None
    have = set(df["column_name"]) if not df.empty else set()
    return [c for c in columns if c not in have]


def add_matrix_rows(conn, rows: list[tuple[str, str, str, bool]]) -> int:
    """rows: (sku_group, asin, marketplace, is_competitor). Идемпотентно."""
    if not rows:
        return 0
    # SKU, если его не ввели, берётся из зеркала каталога Amazon
    # (catalog_source) по той же паре; нет и там — пустая строка
    # (колонка NOT NULL). ASIN на его место не подставляется никогда:
    # ASIN в колонке SKU — это ложь, которую не отличить от правды.
    # При повторе пары пустой ввод не затирает уже известный SKU.
    sql = """
    INSERT INTO product_matrix (sku_group, asin, marketplace, is_competitor)
    VALUES (COALESCE(NULLIF(%(sku)s, ''),
                     (SELECT c.sku_group FROM catalog_source c
                       WHERE c.asin = %(asin)s AND c.marketplace = %(mp)s
                         AND c.sku_group IS NOT NULL AND c.sku_group <> ''
                       LIMIT 1),
                     ''),
            %(asin)s, %(mp)s, %(comp)s)
    ON CONFLICT (asin, marketplace) DO UPDATE SET
        sku_group = COALESCE(NULLIF(EXCLUDED.sku_group, ''), product_matrix.sku_group),
        is_competitor = EXCLUDED.is_competitor
    """
    with conn, conn.cursor() as cur:
        cur.executemany(sql, [{"sku": str(sku or "").strip(), "asin": asin,
                               "mp": mp, "comp": comp}
                              for sku, asin, mp, comp in rows])
    return len(rows)


def list_sku_groups(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT sku_group FROM product_matrix ORDER BY 1")
        return [r[0] for r in cur.fetchall()]


def get_matrix_for_sku(conn, sku_group: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT sku_group, asin, marketplace, is_competitor "
            "FROM product_matrix WHERE sku_group = %s "
            "ORDER BY is_competitor, marketplace, asin",
            (sku_group,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def all_our_asins(conn) -> list[tuple[str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT asin, marketplace FROM product_matrix "
            "WHERE is_competitor = FALSE ORDER BY sku_group, marketplace, asin"
        )
        return [(r[0], r[1]) for r in cur.fetchall()]


# ---------------------------------------------------------------- парсер ввода

def parse_asin_lines(text: str) -> list[tuple[str, str, str, bool]]:
    """Терпимый парсер пачки: строки вида
       'sku, asin, mp[, comp]' / голый ASIN / URL amazon.
       -> (sku_group, asin, marketplace, is_competitor)"""
    import re
    out: list[tuple[str, str, str, bool]] = []
    asin_re = re.compile(r"\b(B0[A-Z0-9]{8})\b", re.I)
    mp_re = re.compile(r"amazon\.([a-z.]{2,6})/", re.I)
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = asin_re.search(line)
        if not m:
            continue
        asin = m.group(1).upper()
        mp = "com"
        mm = mp_re.search(line)
        if mm:
            mp = mm.group(1).lower()
        sku, comp = "", False
        if "," in line and "amazon." not in line.lower():
            parts = [p.strip() for p in line.split(",")]
            if parts and not asin_re.fullmatch(parts[0]):
                sku = parts[0]
            if len(parts) > 2 and parts[2]:
                mp = parts[2].lower()
            if len(parts) > 3:
                comp = parts[3].strip().lower() in ("1", "true", "comp", "competitor", "конкурент")
        # Пусто — значит пусто. Раньше стояло `sku or asin`, и голый ASIN
        # записывался в sku_group как есть: в Каталоге и выгрузке у товара
        # «sku B0G4S9SJ3M», то есть ASIN, выдающий себя за SKU. Настоящий
        # SKU подставляет add_matrix_rows из зеркала каталога.
        out.append((sku, asin, mp, comp))
    return out 
