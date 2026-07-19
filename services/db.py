# -*- coding: utf-8 -*-
"""
services/db.py — подключение к базе + product_matrix. v2 (Lakebase-ready).

Три режима подключения (порядок автоопределения в get_conn):

1. NOTEBOOK-режим (ноутбук Databricks, конвейер):
   доступен databricks.sdk И задан LISTING_LAKEBASE_ENDPOINT ->
   WorkspaceClient().postgres.generate_database_credential() -> psycopg2
   с OAuth-токеном (~1 час жизни, генерится на каждый вызов get_conn()).

2. DASHBOARD-режим (Streamlit Cloud):
   секция [databricks] в секретах (host, client_id, client_secret,
   pg_host, endpoint_name) -> service principal OAuth — как в Кабинете.

3. DSN-режим (локальная разработка):
   DATABASE_URL из env / .streamlit/secrets.toml -> psycopg2.connect(url).

ПРАВИЛО DDL (как в Кабинете): миграции делает ТОЛЬКО пайплайн.
ensure_all_schemas() вызывается из ячейки ноутбука. Страницы Streamlit
схему НЕ создают и НЕ меняют — только SELECT и разрешённые INSERT/UPDATE.
"""

from __future__ import annotations

import os
from typing import Optional

import psycopg2

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


def cfg(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.environ.get(name) or _load_secrets().get(name) or default


# ---------------------------------------------------------------- подключение

def _apply_schema(conn):
    """Все запросы без префикса идут в нашу схему."""
    with conn.cursor() as cur:
        cur.execute(f"SET search_path TO {DB_SCHEMA}, public")
    conn.commit()
    return conn


def _lakebase_notebook_conn():
    """Notebook-режим: OAuth-токен через Databricks SDK (паттерн Кабинета)."""
    from databricks.sdk import WorkspaceClient  # есть в рантайме Databricks
    w = WorkspaceClient()
    cred = w.postgres.generate_database_credential(
        endpoint=cfg("LISTING_LAKEBASE_ENDPOINT")
    )
    return psycopg2.connect(
        host=cfg("LISTING_LAKEBASE_HOST"),
        dbname=cfg("LISTING_LAKEBASE_DB", "databricks_postgres"),
        user=cfg("LISTING_LAKEBASE_USER"),
        password=cred.token,          # OAuth-токен ~1 час, свежий на каждый вызов
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


def _lakebase_sp_conn(d: dict):
    """Dashboard-режим: service principal OAuth (паттерн Streamlit-Кабинета)."""
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient(
        host=d["host"],
        client_id=d["client_id"],
        client_secret=d["client_secret"],
    )
    cred = w.postgres.generate_database_credential(endpoint=d["endpoint_name"])
    return psycopg2.connect(
        host=d["pg_host"],
        dbname=d.get("pg_database", "databricks_postgres"),
        user=d.get("pg_user", d["client_id"]),   # у SP пользователь = client_id
        password=cred.token,
        sslmode="require",
    )


def get_conn():
    """Единая точка подключения. Порядок:
    1) ноутбук Databricks (LISTING_LAKEBASE_* + ambient auth)
    2) дашборд Streamlit ([databricks] service principal — как Кабинет)
    3) DATABASE_URL (локальная разработка / обычный Postgres)"""
    if cfg("LISTING_LAKEBASE_ENDPOINT"):
        try:
            import databricks.sdk  # noqa: F401
            return _apply_schema(_lakebase_notebook_conn())
        except ImportError:
            pass
    d = _databricks_section()
    if d.get("client_id"):
        return _apply_schema(_lakebase_sp_conn(d))
    url = cfg("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Нет подключения: [databricks] в секретах (дашборд), "
            "LISTING_LAKEBASE_* (ноутбук) или DATABASE_URL (локально)"
        )
    return _apply_schema(psycopg2.connect(url))


# db_conn — старое имя, на него завязаны batch_fetch/analyze/diagnose
db_conn = get_conn


# ---------------------------------------------------------------- схема

DDL_MATRIX = """
CREATE TABLE IF NOT EXISTS product_matrix (
    id            BIGSERIAL PRIMARY KEY,
    sku_group     TEXT NOT NULL,
    asin          TEXT NOT NULL,
    marketplace   TEXT NOT NULL DEFAULT 'com',
    is_competitor BOOLEAN NOT NULL DEFAULT FALSE,
    added_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (asin, marketplace)
);
CREATE INDEX IF NOT EXISTS idx_matrix_sku ON product_matrix (sku_group);
"""


def ensure_all_schemas(conn) -> None:
    """ТОЛЬКО из ячейки ноутбука-пайплайна. Дашборд это не вызывает."""
    from services.batch_fetch import DDL as DDL_SNAPSHOTS
    from services.analyze import DDL as DDL_ANALYSIS
    from services.diagnose import DDL as DDL_DIAGNOSIS
    with conn, conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {DB_SCHEMA}")
        cur.execute(f"SET search_path TO {DB_SCHEMA}, public")
        cur.execute(DDL_MATRIX)
        cur.execute(DDL_SNAPSHOTS)
        cur.execute(DDL_ANALYSIS)
        cur.execute(DDL_DIAGNOSIS)


# ---------------------------------------------------------------- матрица

def add_matrix_rows(conn, rows: list[tuple[str, str, str, bool]]) -> int:
    """rows: (sku_group, asin, marketplace, is_competitor). Идемпотентно."""
    if not rows:
        return 0
    sql = """
    INSERT INTO product_matrix (sku_group, asin, marketplace, is_competitor)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (asin, marketplace) DO UPDATE SET
        sku_group = EXCLUDED.sku_group,
        is_competitor = EXCLUDED.is_competitor
    """
    with conn, conn.cursor() as cur:
        cur.executemany(sql, rows)
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
        out.append((sku or asin, asin, mp, comp))
    return out
