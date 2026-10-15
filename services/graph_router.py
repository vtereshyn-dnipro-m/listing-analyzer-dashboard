# -*- coding: utf-8 -*-
"""
services/graph_router.py — выбор ребра по проверкам (перенос
`New-AIDesignRouterDecision.ps1`, контракт `AI_DESIGN_ROUTER_DECISION_CONTRACT.md`).

Маршрутизатор ничего не исполняет и состояние не меняет. Правила закрытые:

- кандидаты — ВСЕ исходящие рёбра всех активных узлов; набор проверок
  обязан совпасть с ними точно, пропущенное ребро — отказ, а не «выбрали из
  того, что есть» (правило 2: нельзя спрятать кандидата ради однозначности);
- одно годное ребро — `EDGE_SELECTED`; два и больше — `HUMAN_ROUTE_DECISION`,
  без «первого совпадения» и без предпочтений; ни одного — `RUN_BLOCKED`
  с причиной по порядку эталона; завершённый запуск — `NO_OP_TERMINAL`.
"""
from __future__ import annotations

from services import graph_canon as gc

ROUTER_VERSION = "1.0"


def decide(graph: gc.Graph, state: dict, evaluations: list[dict]) -> dict:
    gc.require_valid("run_state", state)
    state_hash = gc.sha256_json(state)
    active = list(state["node_state"]["active_node_ids"])
    expected = [e["edge_id"] for e in graph.outgoing(active)]
    for ev in evaluations:
        gc.require_valid("gate_evaluation", ev)
    got = sorted(ev["edge_id"] for ev in evaluations)
    if len(set(got)) != len(got):
        raise ValueError("две проверки одного ребра")
    if got != expected:
        raise ValueError(f"набор проверок не совпал с кандидатами: ждали {expected}, есть {got}")

    by_edge = {ev["edge_id"]: ev for ev in evaluations}
    available = set(state["edge_state"]["available_edge_ids"])
    candidates = []
    for edge_id in expected:
        edge, g = graph.edges[edge_id], by_edge[edge_id]
        if (g["run_id"] != state["run_id"] or g["graph_version"] != state["pinned_graph"]["graph_version"]
                or g["run_state_sha256"].lower() != state_hash):
            raise ValueError(f"{edge_id}: проверка от другого состояния запуска")
        candidates.append({
            "edge_id": edge_id, "source_node_id": edge["source_node_id"],
            "target_node_id": edge["target_node_id"], "registered": True,
            "state_available": edge_id in available,
            "gate_evaluation_ref": g["input_ref"].replace("gate-input://", "gate-evaluation://"),
            "gate_evaluation_sha256": gc.sha256_json(g),
            "trigger_result": g["trigger_result"], "guard_result": g["guard_result"],
            "payload_result": g["payload_result"], "required_receipt_results": list(g["required_receipt_results"]),
            "authority_result": g["authority_result"], "receiver_precheck": g["receiver_precheck"],
            "eligible": bool(g["eligible"]), "rejection_reason_codes": list(g["rejection_reason_codes"])})

    eligible = [c for c in candidates if c["eligible"]]
    selected, blocker, human = None, None, False
    if state["terminal"]["is_terminal"]:
        outcome, reason = "NO_OP_TERMINAL", "TERMINAL_STATE"
    elif len(eligible) == 1:
        outcome, reason, selected = "EDGE_SELECTED", "SINGLE_ELIGIBLE_EDGE", eligible[0]["edge_id"]
    elif len(eligible) > 1:
        outcome, reason, human = "HUMAN_ROUTE_DECISION", "MULTIPLE_ELIGIBLE_EDGES", True
    else:
        outcome = "RUN_BLOCKED"
        if not expected:
            reason, blocker = "NO_REGISTERED_EDGE", "UNROUTABLE_CASE"
        elif any(c["guard_result"]["status"] == "UNRESOLVED" or c["trigger_result"]["status"] == "UNRESOLVED" for c in candidates):
            reason = blocker = "GUARD_UNRESOLVED"
        elif any(c["payload_result"]["status"] in ("FAIL", "UNRESOLVED") for c in candidates):
            reason = blocker = "REQUIRED_PAYLOAD_INVALID"
        elif any(r["status"] != "PASS" for c in candidates for r in c["required_receipt_results"]):
            reason = blocker = "REQUIRED_RECEIPT_MISSING"
        elif any(c["authority_result"]["status"] in ("FAIL", "UNRESOLVED") for c in candidates):
            reason, blocker = "AUTHORITY_MISSING", "SIDE_EFFECT_AUTHORITY_MISSING"
        elif any(c["receiver_precheck"]["status"] in ("FAIL", "UNRESOLVED") for c in candidates):
            reason, blocker = "RECEIVER_NOT_READY", "RECEIVER_NOT_ACCEPTED"
        else:
            reason, blocker = "NO_ELIGIBLE_EDGE", "UNROUTABLE_CASE"

    gate_hashes = sorted(c["gate_evaluation_sha256"] for c in candidates)
    key = gc.sha256_text(state_hash + "|" + "|".join(gate_hashes))
    created = max((ev["evaluated_at"] for ev in evaluations), default=state["updated_at"])
    decision = {"schema_version": "1.0", "decision_id": f"ROUTE-{state['run_id']}-{key[:12].upper()}",
                "run_id": state["run_id"], "graph_version": state["pinned_graph"]["graph_version"],
                "run_state_sha256": state_hash, "router_version": ROUTER_VERSION,
                "active_node_ids": active, "candidate_evaluations": candidates, "outcome": outcome,
                "selected_edge_id": selected, "reason_code": reason, "blocker_code": blocker,
                "human_decision_required": human, "decision_created_at": created}
    gc.require_valid("router_decision", decision)
    return decision
