# -*- coding: utf-8 -*-
"""
tests/test_collect_button.py — сбор по выбранным рынкам из Каталога.

Кнопка запускает job Databricks «Listing Suite Auto Collector» по
отмеченным рынкам. Три вещи, каждая из которых ломается тихо:

  · число в подписи. «566 товаров» обязано быть тем, что job соберёт:
    только активные пары выбранных рынков, свёрнутые не в счёт.
    Иначе кнопка обещает одно, а собирает другое;
  · второй запуск поверх идущего. У job'а max_concurrent_runs = 1, и
    Databricks поставил бы второй run в очередь молча — два сбора
    подряд по тем же парам. Кнопка обязана быть неактивна, пока run
    идёт, в том числе начатый не отсюда;
  · что ушло в job. Рынки и force=1 — иначе ноутбук пропустит прогон
    как «уже собрано сегодня».

Databricks подменяется целиком, база — через pd.read_sql. Сеть
не трогается.

Запуск (pytest не нужен):  python tests/test_collect_button.py
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys
import types

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import services.db                                     # noqa: E402
services.db.get_conn = lambda: type("C", (), {"close": lambda self: None})()
import services.collector as col                       # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


# ---------------------------------------------------------------- Databricks
CALLS: list = []
ACTIVE: list = []          # что вернёт list_runs(active_only=True)
RUN_STATE = {"life": "RUNNING", "result": "", "exit": None}


class _State:
    def __init__(self, life, result):
        self.life_cycle_state = types.SimpleNamespace(value=life)
        self.result_state = types.SimpleNamespace(value=result)


class _Run:
    def __init__(self, run_id, life="RUNNING", result="", start_ms=None):
        self.run_id = run_id
        self.state = _State(life, result)
        self.start_time = start_ms or int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
        self.run_page_url = f"https://dbc/run/{run_id}"
        self.tasks = [types.SimpleNamespace(task_key="auto_collect", run_id=run_id + 1)]


class _Jobs:
    def list_runs(self, job_id, active_only, limit):
        CALLS.append(("list_runs", job_id, active_only))
        return list(ACTIVE)

    def run_now(self, job_id, notebook_params):
        CALLS.append(("run_now", job_id, dict(notebook_params)))
        return types.SimpleNamespace(run_id=777)

    def get_run(self, run_id):
        CALLS.append(("get_run", run_id))
        return _Run(run_id, RUN_STATE["life"], RUN_STATE["result"])

    def get_run_output(self, run_id):
        return types.SimpleNamespace(notebook_output=types.SimpleNamespace(
            result=RUN_STATE["exit"]))


class _Client:
    jobs = _Jobs()


col.client = lambda: _Client()

# ---------------------------------------------------------------- база
RAW = json.dumps({"images": ["a"], "number_of_videos": 1, "aplus": True,
                  "average_rating": "4,5", "price": "10", "sold_by": "Dnipro-M"})
NOW = pd.Timestamp.now("UTC")


def product(asin, mp, status="active"):
    return dict(sku_group=f"175{asin}", asin=asin, marketplace=mp, is_competitor=False,
                status=status, collection_tier="weekly", weekly_day=3,
                fetched_at=NOW - pd.Timedelta(days=2), ok=True, title="T", in_stock=True,
                review_count=1, is_amazon_choice=False, raw=RAW)


# ES: три активных и одна свёрнутая; DE: две активных
CAT = pd.DataFrame([product("B0ES1", "es"), product("B0ES2", "es"), product("B0ES3", "es"),
                    product("B0ESW", "es", "wound_down"),
                    product("B0DE1", "de"), product("B0DE2", "de")])
SNAP_SINCE = {"n": 0}


def fake_sql(sql, conn=None, **kw):
    q = str(sql)
    if "FROM product_matrix m" in q and "is_amazon_choice" in q:
        return CAT.copy()
    if "marketplace = ANY" in q and "count(*) AS pairs" in q:
        mps = kw.get("params", {}).get("mps", [])
        act = CAT[CAT["marketplace"].isin(mps)] if "status = 'active'" not in q else CAT[(CAT["status"] == "active") & CAT["marketplace"].isin(mps)]
        return act.groupby("marketplace").size().reset_index(name="pairs")
    if "FROM listing_snapshots" in q and "fetched_at >=" in q:
        return pd.DataFrame([{"n": SNAP_SINCE["n"]}])
    return pd.DataFrame()


pd.read_sql = fake_sql
from streamlit.testing.v1 import AppTest              # noqa: E402
import streamlit as st                                 # noqa: E402


def page():
    st.cache_data.clear()      # кэш активного run'а (ttl 20 c) общий на процесс
    a = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
    a.switch_page("pages/catalog.py").run()
    return a


def btn(a):
    return next((b for b in a.button if b.key == "collect-go"), None)


def running_shown(a) -> bool:
    texts = [str(getattr(x, "text", "")) for x in a.get("progress")] + [str(x.value) for x in a.info]
    return any("Сбор идёт" in v for v in texts)


def box(a, mp):
    return next(c for c in a.checkbox if c.key == f"collect-mp-{mp}")


# --- 1. число видно ДО нажатия и считает только активные пары
# Ряд галочек без подписи читался как список кодов; число запросов
# стоит рядом с галочками, а не только в кнопке — кнопка бывает
# неактивна (идёт утренний прогон), а знать объём нужно всё равно.
def plan_text(a) -> str:
    return next((str(m.value) for m in a.markdown
                 if "товар" in str(m.value) and "white-space" in str(m.value)), "")


at = page()
check("страница отрисована", not at.exception)
check("над галочками сказано, что это и что выбирать",
      any("Собрать данные сейчас" in str(m.value) and "выберите рынки" in str(m.value)
          for m in at.markdown))
check("без отмеченных рынков кнопка неактивна", btn(at) is not None and btn(at).disabled)
check("и сказано, что рынки не выбраны", any("не выбраны" in str(c.value) for c in at.caption))
box(at, "es").set_value(True).run()
check(f"ES: 3 активных, свёрнутая не в счёт ({plan_text(at)})",
      "ES · 3 товара" in plan_text(at) and not btn(at).disabled)
box(at, "de").set_value(True).run()
check(f"ES + DE: 5 товаров и разбивка по рынкам ({plan_text(at)})",
      "DE, ES · 5 товаров" in plan_text(at) and "DE 2" in plan_text(at) and "ES 3" in plan_text(at))

# --- 2. запуск: рынки и force уходят в job, второй раз — нет
CALLS.clear()
btn(at).click().run()
_run = next((c for c in CALLS if c[0] == "run_now"), None)
check("run_now вызван для нашего job'а", _run is not None and _run[1] == col.JOB_ID)
check(f"ушли рынки и force ({_run[2] if _run else None})",
      _run is not None and _run[2] == {"marketplaces": "de,es", "force": "1"})
check("перед запуском спрошен активный run",
      any(c[0] == "list_runs" and c[2] is True for c in CALLS))
check("пока идёт — кнопка неактивна", btn(at).disabled)
check("и ход показан", running_shown(at))
# Повторное нажатие невозможно физически: AppTest, как и браузер,
# отказывается кликать неактивную кнопку — это и есть гарантия.

# --- 3. ход из базы: пока ноль — сказано, почему
check("собрано 0 из 5 и объяснение про одну транзакцию",
      any("0 из 5" in str(getattr(x, "text", "")) for x in at.get("progress"))
      and any("одной транзакцией" in str(c.value) for c in at.caption))
SNAP_SINCE["n"] = 3
at.run()
check("снапшоты появились — ход двинулся",
      any("3 из 5" in str(getattr(x, "text", "")) for x in at.get("progress")))

# --- 4. финал: skipped — предупреждение про ноутбук; успех — итог
RUN_STATE.update(life="TERMINATED", result="SUCCESS", exit="skipped")
at.run()
check("ноутбук ответил «skipped» — сказано, что он не принимает параметры",
      any("skipped" in str(w.value) for w in at.warning))
check("кнопка снова доступна", not btn(at).disabled)

# --- 5. run, начатый НЕ отсюда (утренний прогон), тоже блокирует кнопку
RUN_STATE.update(life="RUNNING", result="", exit=None)
ACTIVE[:] = [_Run(555)]
at = page()
box(at, "es").set_value(True).run()
check("чужой активный run найден — кнопка неактивна", btn(at).disabled)
check("и показан как идущий", running_shown(at))
ACTIVE.clear()

# --- 6. без секции [databricks] — честная подпись, не пустота
col.client = lambda: None
at = page()
box(at, "es").set_value(True).run()
check("без клиента кнопка неактивна и причина названа",
      btn(at).disabled and any("[databricks]" in str(c.value) for c in at.caption))

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
