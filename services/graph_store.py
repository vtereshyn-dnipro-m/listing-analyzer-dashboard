# -*- coding: utf-8 -*-
"""
services/graph_store.py — запуск графа в базе: `ai_runs` и `ai_run_events`.

Соединение приходит снаружи (psycopg2 или `services/db.py::get_conn()`):
модуль не тянет Streamlit и годится задаче Databricks как есть.

Как хранится:

- **`ai_runs.run_state`** — текущее состояние по схеме канона; рядом в
  колонках то, по чему ищут: состояние жизненного цикла, terminal, текущий
  узел.
- **`ai_run_events`** — только дописывание (триггер базы). Событие 1 —
  создание запуска: начальный ledger бюджета. Дальше событие на каждый
  ПРИМЕНЁННЫЙ переход или исчерпание: квитанция перехода вместе с решением
  маршрутизатора, которое её обосновывает, и квитанция бюджета с новой
  ревизией ledger. Отдельной таблицы ledger нет: его текущая ревизия — в
  последнем событии, и переписать её задним числом триггер не даст. Решения
  без перехода (`RUN_BLOCKED` и прочие) событием не становятся: маршрутизатор
  состояния не меняет, а история — это история переходов.
- **Один шаг — одна транзакция.** Строка запуска берётся `FOR UPDATE`,
  новое событие, новое состояние и новая ревизия ledger пишутся вместе или
  не пишутся вовсе (правило 15 контракта записи). Второй шаг того же
  запуска ждёт первого и считается уже от его результата.
"""
from __future__ import annotations

import json

from services import graph_canon as gc
from services import graph_engine as ge
from services import graph_writer as gw

ROUTE_PASSPORT = "SKU_PASSPORT"


def _j(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def _obj(v):
    return json.loads(v) if isinstance(v, (str, bytes)) else v


def create_run(conn, graph: gc.Graph, state: dict, ledger: dict, *, route: str, sku_id: str,
               requested_action: str, passport_id: str | None = None,
               created_by: str | None = None) -> bool:
    """Завести запуск. Повтор с тем же run_id ничего не меняет и отвечает
    False — двойной запуск не создаёт второго."""
    gc.require_valid("run_state", state)
    gc.require_valid("ledger", ledger)
    if ledger["run_id"] != state["run_id"]:
        raise ValueError("ledger от другого запуска")
    init = {"kind": "RUN_INITIALIZED", "run_id": state["run_id"],
            "run_state_sha256": gc.sha256_json(state), "graph_version": graph.graph_version,
            "graph_sha256": graph.sha256, "created_at": state["created_at"]}
    with conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO ai_runs (run_id, route, sku_id, passport_id, requested_action, graph_version,
                                    graph_sha256, execution_mode, lifecycle_state, terminal_status,
                                    current_node_id, run_state, created_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
               ON CONFLICT (run_id) DO NOTHING""",
            (state["run_id"], route, sku_id, passport_id, requested_action, graph.graph_version,
             graph.sha256, state["execution_mode"], state["lifecycle_state"], state["terminal"]["status"],
             state["node_state"]["current_node_id"], _j(state), created_by))
        if cur.rowcount == 0:
            return False
        cur.execute(
            """INSERT INTO ai_run_events (run_id, seq, edge_id, from_node_id, to_node_id,
                                         receipt, receipt_sha256, budget_charge)
               VALUES (%s, 1, NULL, NULL, %s, %s::jsonb, %s, %s::jsonb)""",
            (state["run_id"], state["node_state"]["current_node_id"], _j(init), gc.sha256_json(init),
             _j({"ledger": ledger})))
        return True


def _ledger_of(charge: dict) -> dict:
    charge = _obj(charge)
    return charge["ledger"] if "ledger" in charge else charge["receipt"]["ledger"]


def load(cur, run_id: str, *, for_update: bool = False) -> tuple[dict, dict, int]:
    """(состояние, текущий ledger, номер последнего события)."""
    cur.execute("SELECT run_state FROM ai_runs WHERE run_id = %s" + (" FOR UPDATE" if for_update else ""),
                (run_id,))
    row = cur.fetchone()
    if row is None:
        raise LookupError(run_id)
    state = _obj(row[0])
    cur.execute("SELECT seq, budget_charge FROM ai_run_events WHERE run_id = %s ORDER BY seq DESC LIMIT 1",
                (run_id,))
    ev = cur.fetchone()
    if ev is None:
        raise LookupError(f"{run_id}: нет события создания — ledger неизвестен")
    return state, _ledger_of(ev[1]), int(ev[0])


def step(conn, graph: gc.Graph, run_id: str, *, now: str, expected_state_sha256: str | None = None,
         **kwargs) -> ge.Step:
    """Один шаг под блокировкой запуска. `expected_state_sha256` — защита от
    шага по устаревшему снимку: вызывающий видел одно состояние, а в базе
    уже другое — отказ без записи."""
    with conn, conn.cursor() as cur:
        state, ledger, last_seq = load(cur, run_id, for_update=True)
        if expected_state_sha256 and gc.sha256_json(state) != expected_state_sha256:
            raise ValueError("состояние запуска изменилось с момента чтения")
        result = ge.advance(graph, state, ledger, now=now, **kwargs)
        tr = result.transition
        if tr is None:
            return result
        edge = graph.edges[tr.receipt["edge_id"]]
        receipt = {"kind": "TRANSITION" if tr.verdict == "TRANSITION_APPLIED" else "FAILED_EXHAUSTED",
                   "receipt": tr.receipt, "router_decision": result.decision,
                   "receipt_ref": gw.receipt_ref(run_id, tr.sequence)}
        request = {k: v for k, v in result.budget_request.items() if k != "ledger"}
        cur.execute(
            """INSERT INTO ai_run_events (run_id, seq, edge_id, from_node_id, to_node_id,
                                         receipt, receipt_sha256, budget_charge)
               VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb)""",
            (run_id, last_seq + 1, edge["edge_id"], edge["source_node_id"],
             edge["target_node_id"] if tr.verdict == "TRANSITION_APPLIED" else None,
             _j(receipt), gc.sha256_json(receipt), _j({"request": request, "receipt": tr.budget_receipt})))
        cur.execute(
            """UPDATE ai_runs SET run_state = %s::jsonb, lifecycle_state = %s, terminal_status = %s,
                                  current_node_id = %s, updated_at = now()
               WHERE run_id = %s""",
            (_j(tr.state), tr.state["lifecycle_state"], tr.state["terminal"]["status"],
             tr.state["node_state"]["current_node_id"], run_id))
        return result
