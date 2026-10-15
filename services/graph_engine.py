# -*- coding: utf-8 -*-
"""
services/graph_engine.py — один шаг графа: входы → проверки → решение →
бюджет → запись. Чистая функция над состоянием и ledger; база — в
`services/graph_store.py`, провайдеров модели и файлов здесь нет.

Шаг — это ровно один переход или ни одного. Повторять шаги до конца
маршрута — дело вызывающего (задача Databricks), и он делает это ПО
РЕШЕНИЯМ: `RUN_BLOCKED`, `HUMAN_ROUTE_DECISION` и `NO_OP_TERMINAL`
останавливают его так же, как исчерпанный бюджет. Цикла «пока не дойдём»
в ядре нет — конечность держит бюджет (`services/graph_budget.py`).
"""
from __future__ import annotations

from dataclasses import dataclass

from services import graph_budget as gb
from services import graph_canon as gc
from services import graph_gates as gg
from services import graph_router as gr
from services import graph_writer as gw


@dataclass
class Step:
    gate_inputs: list
    build_manifest: dict
    evaluations: list
    decision: dict
    transition: gw.Transition | None
    budget_request: dict | None


def advance(graph: gc.Graph, state: dict, ledger: dict, *, now: str, bundle: dict | None = None,
            source_sha=None, asset_id: str | None = None, incident_id: str | None = None,
            fingerprint: str | None = None, new_evidence: bool = False) -> Step:
    inputs, manifest = gg.build_gate_inputs(graph, state, bundle, source_sha=source_sha)
    evaluations = [gg.evaluate_gate(graph, state, gi, now=now) for gi in inputs]
    decision = gr.decide(graph, state, evaluations)
    if decision["outcome"] != "EDGE_SELECTED":
        return Step(inputs, manifest, evaluations, decision, None, None)
    edge = graph.edges[decision["selected_edge_id"]]
    sequence = len(state["transition_history"]) + 1
    req = gb.request(edge, ledger, request_id=f"{state['run_id']}-T{sequence:04d}",
                     asset_id=asset_id, incident_id=incident_id, fingerprint=fingerprint,
                     new_evidence=new_evidence)
    receipt = gb.resolve(req, now=now)
    tr = gw.apply(graph, state, decision, budget_request=req, budget_receipt=receipt, ledger=ledger, now=now)
    return Step(inputs, manifest, evaluations, decision, tr, req)
