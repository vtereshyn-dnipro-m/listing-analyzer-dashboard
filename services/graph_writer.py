# -*- coding: utf-8 -*-
"""
services/graph_writer.py — начальное состояние запуска и запись перехода
(перенос `New-AIDesignControlledRunState.ps1` и
`Invoke-AIDesignStateTransition.ps1`, контракт
`AI_DESIGN_STATE_TRANSITION_WRITER_CONTRACT.md`).

Запись применяет РОВНО одно `EDGE_SELECTED` к состоянию и выдаёт новое
состояние и квитанцию. Ничего внешнего не делает, ребро не выбирает, узел не
исполняет. Два места, где перенос сознательно расходится с эталонным
скриптом, — оба в пользу контракта:

1. **Бюджет — обязательный вход записи.** Контракт (правила 13–16)
   требует квитанцию `TERMINATION_BUDGET_ALLOW`, привязанную к текущей
   ревизии ledger, а эталонный скрипт бюджет не вызывает вовсе. Без этого
   обратные рёбра были бы обычными циклами без предела. Здесь квитанция
   сверяется с запросом, ребром и ревизией; любой другой вердикт — переход
   НЕ применяется, запуск получает `FAILED_EXHAUSTED` и блокер
   `LOOP_BUDGET_EXHAUSTED`, target не активируется.
2. **Применённое ребро остаётся доступным, если его источник снова
   активен.** Контракт (правило 8): после перехода доступны исходящие рёбра
   активных узлов. Эталон вычитает из них уже применённые — и тогда ребро
   переделки срабатывает один раз за запуск, а бюджет «3 переделки на
   ассет» недостижим. `applied_edge_ids` остаётся историей.

Оба расхождения ушли владельцу канона вопросами.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass

from services import graph_budget as gb
from services import graph_canon as gc

WRITER_VERSION = "1.0"
INIT_NODE = "N010_RUN_INITIALIZATION"
INIT_EDGE = "E010_INITIALIZE_PASSPORT_ROUTE"


def _uniq(values) -> list:
    return sorted({v for v in values if v not in (None, "")})


def new_run_state(graph: gc.Graph, *, run_id: str, execution_mode: str, launch_control: dict,
                  product_identity: dict, pinned_product_truth: dict, budgets: dict, now: str) -> dict:
    """Начальное состояние — как у эталона: активен только N010, доступно
    только E010. `pinned_product_truth` обязателен: схема канона требует
    существующий Паспорт (путь, версия, SHA). Запуск первичного создания
    этим не представим — расхождение названо владельцу, и до его ответа
    ядро такой запуск не заводит."""
    pending = sorted(n for n in graph.nodes if n != INIT_NODE)
    state = {
        "schema_version": "1.0", "run_id": run_id, "execution_mode": execution_mode,
        "lifecycle_state": "RUN_ACTIVE", "launch_control": launch_control,
        "product_identity": product_identity, "pinned_graph": graph.pinned_graph(),
        "pinned_product_truth": pinned_product_truth,
        "node_state": {"current_node_id": INIT_NODE, "completed_node_ids": [], "active_node_ids": [INIT_NODE],
                       "pending_node_ids": pending, "blocked_node_ids": [], "not_applicable_node_ids": []},
        "edge_state": {"applied_edge_ids": [], "available_edge_ids": [INIT_EDGE], "rejected_edge_ids": [],
                       "unevaluated_edge_ids": sorted(e for e in graph.edges if e != INIT_EDGE)},
        "artifacts": [], "evidence_gaps": [], "conflicts": [], "blockers": [], "approvals": [],
        "budgets": budgets, "side_effect_ledger": [], "receipt_refs": [], "transition_history": [],
        "latest_checkpoint": None, "resume_cursor": None,
        "terminal": {"is_terminal": False, "status": "NOT_TERMINAL", "terminal_receipt_ref": None},
        "created_at": now, "updated_at": now}
    gc.require_valid("run_state", state)
    return state


@dataclass
class Transition:
    verdict: str                 # TRANSITION_APPLIED | FAILED_EXHAUSTED
    state: dict                  # новое состояние (исходное не тронуто)
    receipt: dict                # квитанция перехода или исчерпания
    budget_receipt: dict
    sequence: int


def receipt_ref(run_id: str, sequence: int) -> str:
    return f"ai_run_events://{run_id}/transition/{sequence:04d}"


def apply(graph: gc.Graph, state: dict, decision: dict, *, budget_request: dict,
          budget_receipt: dict, ledger: dict, now: str) -> Transition:
    gc.require_valid("run_state", state)
    gc.require_valid("router_decision", decision)
    input_hash = gc.sha256_json(state)
    if decision["outcome"] != "EDGE_SELECTED" or not decision["selected_edge_id"]:
        raise ValueError("запись принимает только EDGE_SELECTED")
    if decision["run_state_sha256"].lower() != input_hash:
        raise ValueError("решение маршрутизатора от другого состояния")
    edge = graph.edges.get(decision["selected_edge_id"])
    if edge is None:
        raise ValueError("выбранное ребро не зарегистрировано")
    if edge["edge_id"] not in state["edge_state"]["available_edge_ids"]:
        raise ValueError("выбранное ребро больше не доступно")
    if edge["source_node_id"] not in state["node_state"]["active_node_ids"]:
        raise ValueError("источник выбранного ребра больше не активен")
    for b in state["blockers"]:
        if b["status"] == "OPEN" and edge["edge_id"] not in b["allowed_recovery_edge_ids"]:
            raise ValueError(f"открытый блокер {b['blocker_id']} не разрешает это ребро")

    # Квитанция бюджета: та же заявка, то же ребро, следующая ревизия ТЕКУЩЕГО ledger.
    gc.require_valid("budget_request", budget_request)
    gc.require_valid("budget_receipt", budget_receipt)
    if (budget_request["ledger"] != ledger or budget_receipt["request_id"] != budget_request["request_id"]
            or budget_receipt["edge_id"] != edge["edge_id"] or budget_request["edge_id"] != edge["edge_id"]
            or budget_receipt["ledger"]["revision"] != ledger["revision"] + 1
            or budget_receipt["ledger"]["run_id"] != state["run_id"]):
        raise ValueError("квитанция бюджета не привязана к этому переходу и ревизии ledger")

    sequence = len(state["transition_history"]) + 1
    ref = receipt_ref(state["run_id"], sequence)
    nxt = copy.deepcopy(state)
    ns, es = nxt["node_state"], nxt["edge_state"]

    if budget_receipt["verdict"] != gb.ALLOW:
        nxt["terminal"] = {"is_terminal": True, "status": "FAILED_EXHAUSTED", "terminal_receipt_ref": ref}
        nxt["lifecycle_state"] = "RUN_BLOCKED"
        nxt["blockers"].append({
            "blocker_id": f"BLK-{state['run_id'][4:]}-{len(state['blockers']) + 1:03d}",
            "code": "LOOP_BUDGET_EXHAUSTED", "owner": "AI Design Coordinator",
            "evidence_refs": [f"TERMINATION_BUDGET:{budget_receipt['receipt_id']}",
                              f"REASON:{budget_receipt['reason_code']}"],
            "affected_node_ids": [edge["source_node_id"]], "affected_edge_ids": [edge["edge_id"]],
            "allowed_recovery_edge_ids": [], "status": "OPEN"})
        nxt["receipt_refs"] = _uniq(nxt["receipt_refs"] + [ref])
        nxt["updated_at"] = now
        gc.require_valid("run_state", nxt)
        receipt = {"schema_version": "1.0", "verdict": "FAILED_EXHAUSTED", "run_id": state["run_id"],
                   "decision_id": decision["decision_id"], "edge_id": edge["edge_id"],
                   "budget_verdict": budget_receipt["verdict"], "reason_code": budget_receipt["reason_code"],
                   "input_state_sha256": input_hash, "output_state_sha256": gc.sha256_json(nxt),
                   "target_activated": False, "applied_at": now, "writer_version": WRITER_VERSION}
        return Transition("FAILED_EXHAUSTED", nxt, receipt, budget_receipt, sequence)

    delta = edge["state_delta"]
    if delta["complete_source_node"]:
        ns["active_node_ids"] = [n for n in ns["active_node_ids"] if n != edge["source_node_id"]]
        ns["completed_node_ids"] = _uniq(ns["completed_node_ids"] + [edge["source_node_id"]])
    if delta["activate_target_node"]:
        t = edge["target_node_id"]
        for k in ("completed_node_ids", "pending_node_ids", "blocked_node_ids", "not_applicable_node_ids"):
            ns[k] = [n for n in ns[k] if n != t]
        ns["active_node_ids"] = _uniq(ns["active_node_ids"] + [t])
        ns["current_node_id"] = t
    ns["active_node_ids"] = _uniq(ns["active_node_ids"])

    es["applied_edge_ids"] = _uniq(es["applied_edge_ids"] + [edge["edge_id"]])
    es["rejected_edge_ids"] = [e for e in es["rejected_edge_ids"] if e != edge["edge_id"]]
    for b in nxt["blockers"]:
        if b["status"] == "OPEN" and edge["edge_id"] in b["allowed_recovery_edge_ids"]:
            b["status"] = "RESOLVED"
    still_open = any(b["status"] == "OPEN" for b in nxt["blockers"])
    nxt["lifecycle_state"] = "RUN_BLOCKED" if still_open else delta["set_run_state"]
    # Правило 8 контракта: доступны исходящие рёбра активных узлов
    # (применённые — тоже, см. докстринг модуля).
    outgoing = [e["edge_id"] for e in graph.outgoing(ns["active_node_ids"])]
    es["available_edge_ids"] = _uniq(e for e in outgoing if e not in es["rejected_edge_ids"])
    es["unevaluated_edge_ids"] = _uniq(e for e in graph.edges if e not in es["applied_edge_ids"]
                                       and e not in es["rejected_edge_ids"] and e not in es["available_edge_ids"])

    decision_hash = gc.sha256_json(decision)
    transition_id = f"TRANSITION-{state['run_id']}-{sequence:04d}"
    checkpoint_id = f"CHECKPOINT-{state['run_id']}-{sequence:04d}"
    nxt["transition_history"].append({
        "transition_id": transition_id, "decision_id": decision["decision_id"], "edge_id": edge["edge_id"],
        "source_node_id": edge["source_node_id"], "target_node_id": edge["target_node_id"],
        "input_state_sha256": input_hash, "decision_sha256": decision_hash, "receipt_ref": ref, "applied_at": now})
    nxt["receipt_refs"] = _uniq(nxt["receipt_refs"] + [ref])
    nxt["updated_at"] = now

    # Хэш точки восстановления — до вложения самой точки и курсора
    # (раздел «Checkpoint semantics»: без циклического самохэша).
    payload_hash = gc.sha256_json(nxt)
    artifact_hash = gc.sha256_json(nxt["artifacts"])
    side_hash = gc.sha256_json(nxt["side_effect_ledger"])
    nxt["latest_checkpoint"] = {"checkpoint_id": checkpoint_id, "state_sha256": payload_hash,
                                "artifact_binding_sha256": artifact_hash, "side_effect_ledger_sha256": side_hash,
                                "created_at": now, "created_by_node_id": edge["target_node_id"], "receipt_ref": ref}
    reconcile = any(se["status"] in ("STARTED", "UNKNOWN") or se["reconciliation_status"] in ("PENDING", "UNRESOLVED")
                    for se in nxt["side_effect_ledger"])
    nxt["resume_cursor"] = ({"checkpoint_id": checkpoint_id, "resume_node_id": edge["target_node_id"],
                             "allowed_resume_edge_ids": list(es["available_edge_ids"]),
                             "reconciliation_required": reconcile} if es["available_edge_ids"] else None)
    gc.require_valid("run_state", nxt)
    output_hash = gc.sha256_json(nxt)

    receipt = {"schema_version": "1.0", "transition_id": transition_id, "run_id": state["run_id"],
               "graph_version": state["pinned_graph"]["graph_version"], "decision_id": decision["decision_id"],
               "edge_id": edge["edge_id"], "source_node_id": edge["source_node_id"],
               "target_node_id": edge["target_node_id"],
               "input_state_path": f"ai_runs://{state['run_id']}/state/{input_hash}", "input_state_sha256": input_hash,
               "decision_path": ref + "/decision", "decision_sha256": decision_hash,
               "edge_registry_sha256": graph.pins["edge_registry"].sha256,
               "output_state_path": f"ai_runs://{state['run_id']}/state/{output_hash}",
               "output_state_sha256": output_hash, "checkpoint_id": checkpoint_id,
               "checkpoint_payload_sha256": payload_hash, "artifact_binding_sha256": artifact_hash,
               "side_effect_ledger_sha256": side_hash,
               "state_delta_applied": {"lifecycle_state": nxt["lifecycle_state"],
                                       "source_completed": bool(delta["complete_source_node"]),
                                       "target_activated": bool(delta["activate_target_node"]),
                                       "artifact_status_updates": list(delta["artifact_status_updates"])},
               "verdict": "TRANSITION_APPLIED", "applied_at": now, "writer_version": WRITER_VERSION}
    gc.require_valid("transition_receipt", receipt)
    return Transition("TRANSITION_APPLIED", nxt, receipt, budget_receipt, sequence)
