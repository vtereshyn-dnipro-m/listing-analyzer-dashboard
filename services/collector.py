# -*- coding: utf-8 -*-
"""
services/collector.py — запуск сбора по выбранным рынкам и его ход.

Сбор делает job Databricks «Listing Suite Auto Collector»
(JOB_ID, 13:00 Kyiv). Отсюда он запускается вручную по выбранным
рынкам: `run_now` с `notebook_params` — ноутбук читает их через
`dbutils.widgets` (см. patch в CLAUDE.md, раздел Каталога).

Три правила, и все три — про честность, а не про удобство.

НЕ ЗАПУСКАТЬ ПОВЕРХ ИДУЩЕГО. У job'а `max_concurrent_runs = 1`, и
второй запуск Databricks поставил бы в очередь молча; человек нажал
бы кнопку дважды и получил бы два сбора подряд, второй — по тем же
парам. Поэтому перед запуском спрашивается активный run, и кнопка
при нём неактивна с указанием, когда начат.

СВЁРНУТЫЕ НЕ СЧИТАЮТСЯ. Число в подписи кнопки — активные пары
выбранных рынков (`status = 'active'`), потому что ноутбук берёт
только их. «566 товаров» обязано совпасть с тем, что он соберёт.

ХОД — ПО БАЗЕ, НЕ ПО ОБЕЩАНИЮ. Собрано = снапшоты выбранных рынков
с меткой не раньше старта run'а. Это работает только если ноутбук
коммитит по паре, а не одной транзакцией в конце (см. тот же patch);
до правки ход будет «0 из N» до самого финала, и панель говорит это
вслух, а не рисует полоску.

Клиент Databricks берётся из той же секции `[databricks]` секретов,
что и подключение к Lakebase; сервисному принципалу нужно право
CAN_MANAGE_RUN на job — иначе `run_now` ответит 403, и это тоже
должно дойти до экрана словами.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from services.db import _databricks_section, get_engine

JOB_ID = 89677076782805
TASK_KEY = "auto_collect"


def client():
    """WorkspaceClient по секретам приложения. None — секции нет (локально)."""
    d = _databricks_section()
    if not d.get("host") or not d.get("client_id"):
        return None
    from databricks.sdk import WorkspaceClient
    return WorkspaceClient(host=d["host"], client_id=d["client_id"],
                           client_secret=d["client_secret"])


def planned(markets: list[str]) -> tuple[pd.DataFrame, str | None]:
    """Активные пары по рынкам — то, что job реально соберёт.

    `status = 'active'` — то же условие, что в ноутбуке; свёрнутые
    не считаются, иначе подпись обещала бы больше, чем будет.
    """
    if not markets:
        return pd.DataFrame(columns=["marketplace", "pairs"]), None
    try:
        df = pd.read_sql(
            """
            SELECT marketplace, count(*) AS pairs
            FROM product_matrix
            WHERE status = 'active' AND marketplace = ANY(%(mps)s)
            GROUP BY marketplace ORDER BY marketplace
            """, get_engine(), params={"mps": list(markets)})
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"{type(e).__name__}: {e}"


def active_run() -> tuple[dict | None, str | None]:
    """Идущий run job'а: {run_id, started_at, state} или None. Ошибка — словами."""
    w = client()
    if w is None:
        return None, "no-client"
    try:
        for r in w.jobs.list_runs(job_id=JOB_ID, active_only=True, limit=1):
            return _run_dict(r), None
        return None, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def start(markets: list[str]) -> tuple[dict | None, str | None]:
    """Запустить сбор по рынкам. Возвращает run или причину отказа.

    `force=1` обходит проверку «уже собрано сегодня» в ноутбуке —
    ручной запуск по определению идёт поверх утреннего.
    """
    w = client()
    if w is None:
        return None, "no-client"
    running, err = active_run()
    if err and err != "no-client":
        return None, err
    if running:
        return None, "already-running"
    try:
        resp = w.jobs.run_now(
            job_id=JOB_ID,
            notebook_params={"marketplaces": ",".join(sorted(markets)),
                             "force": "1"})
        return {"run_id": int(resp.run_id),
                "started_at": dt.datetime.now(dt.timezone.utc),
                "state": "PENDING", "markets": sorted(markets)}, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def run_state(run_id: int) -> tuple[dict | None, str | None]:
    """Состояние run'а и, когда он завершён, что ответил ноутбук."""
    w = client()
    if w is None:
        return None, "no-client"
    try:
        r = w.jobs.get_run(run_id=int(run_id))
        d = _run_dict(r)
        if d["state"] not in ("PENDING", "RUNNING", "TERMINATING", "QUEUED", "BLOCKED"):
            d["exit"] = _exit_value(w, r)
        return d, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def collected_since(started_at, markets: list[str]) -> tuple[int, str | None]:
    """Сколько снапшотов выбранных рынков записано с момента старта."""
    try:
        df = pd.read_sql(
            """
            SELECT count(*) AS n FROM listing_snapshots
            WHERE fetched_at >= %(t)s AND marketplace = ANY(%(mps)s)
            """, get_engine(),
            params={"t": pd.Timestamp(started_at), "mps": list(markets)})
        return int(df.iloc[0]["n"]) if not df.empty else 0, None
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------- внутреннее
def _run_dict(r) -> dict:
    st = getattr(r, "state", None)
    life = getattr(getattr(st, "life_cycle_state", None), "value", None) or ""
    result = getattr(getattr(st, "result_state", None), "value", None) or ""
    started = getattr(r, "start_time", None)
    return {
        "run_id": int(getattr(r, "run_id", 0) or 0),
        "started_at": (dt.datetime.fromtimestamp(started / 1000, tz=dt.timezone.utc)
                       if started else None),
        "state": life or "UNKNOWN",
        "result": result,
        "url": getattr(r, "run_page_url", None),
    }


def _exit_value(w, r) -> str | None:
    """`dbutils.notebook.exit(...)` задачи — итог словами или «skipped»."""
    try:
        tasks = getattr(r, "tasks", None) or []
        task_run_id = next((t.run_id for t in tasks
                            if getattr(t, "task_key", "") == TASK_KEY), None)
        if task_run_id is None and tasks:
            task_run_id = tasks[0].run_id
        if task_run_id is None:
            return None
        out = w.jobs.get_run_output(run_id=int(task_run_id))
        nb = getattr(out, "notebook_output", None)
        return getattr(nb, "result", None)
    except Exception:
        return None
