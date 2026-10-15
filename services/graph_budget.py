# -*- coding: utf-8 -*-
"""
services/graph_budget.py — бюджет переходов и гарантированное завершение
(перенос `Resolve-AIDesignTerminationBudget.ps1`, контракт
`AI_DESIGN_REWORK_BUDGET_AND_TERMINATION_CONTRACT.md`, политика
`AI_DESIGN_REWORK_TERMINATION_POLICY.json`).

Это то, что делает «граф, не циклы» правдой: обратные рёбра (E035, E050,
E080 и другие) — обычные зарегистрированные рёбра, а конечность обеспечивает
счётчик, который нельзя обнулить. Каждый автоматический переход списывает
один из 250 на запуск; переход по ребру класса, отличного от FORWARD, ещё и
из пакетного бюджета переделок. Перерасход — `FAILED_EXHAUSTED`, и target
не активируется.

**Класс события по классу ребра — наше решение, канон его не задаёт.**
У реестра рёбер шесть классов (FORWARD, CONDITIONAL, CHECKPOINT, REWORK,
RETRY, RESUME), у запроса бюджета — восемь классов событий. Сопоставление
выбрано так, чтобы при сомнении списывать БОЛЬШЕ, а не меньше: RETRY идёт
как REWORK (повтор и есть переделка той же работы), RESUME — как
CHECKPOINT_RESUME со счётчиком на запуск. Человеческое ожидание
(`HUMAN_WAIT`) записью перехода не бывает: запись применяет только
`EDGE_SELECTED`, а ожидание — это отсутствие перехода. Сопоставление
ушло владельцу вопросом вместе с остальными расхождениями движка.
"""
from __future__ import annotations

import copy

from services import graph_canon as gc

EVENT_CLASS = {
    "FORWARD": "FORWARD",
    "CONDITIONAL": "FORWARD",
    "CHECKPOINT": "FORWARD",
    "REWORK": "REWORK",
    "RETRY": "REWORK",
    "RESUME": "CHECKPOINT_RESUME",
}

ALLOW = "TERMINATION_BUDGET_ALLOW"


def event_class(edge: dict) -> str:
    try:
        return EVENT_CLASS[edge["edge_class"]]
    except KeyError:
        # Неизвестный класс — блок до записи (раздел «Блокери» контракта).
        raise ValueError(f"{edge['edge_id']}: класс ребра {edge['edge_class']!r} без класса события") from None


def new_ledger(graph: gc.Graph, run_id: str, *, package_id: str, now: str,
               mandatory_assets: int = 0, incident_id: str | None = None) -> dict:
    """Ledger запуска по политике. Пакетный предел — max(минимум,
    коэффициент × обязательные ассеты). Инцидент «возобновление» ведётся
    на запуск: политика задаёт `checkpoint_resumes_per_run`."""
    lim = graph.policy["limits"]
    pol = graph.pins["termination_policy"]
    package_max = max(lim["rework_transitions_per_package_minimum"],
                      lim["rework_transitions_per_mandatory_asset_coefficient"] * mandatory_assets)
    led = {"schema_version": "1.0", "ledger_id": "REWORKLEDGER-" + run_id[4:],
           "run_id": run_id, "package_id": package_id, "revision": 1,
           "policy_binding": {"ref": "AI Design Conveyor/" + pol.path, "sha256": pol.sha256},
           "automatic_transitions": {"used": 0, "maximum": lim["automatic_transitions_per_run"]},
           "package_rework": {"used": 0, "maximum": package_max},
           "asset_budgets": {}, "incident_budgets": {
               incident_id or run_id: {
                   "reclassifications": {"used": 0, "maximum": lim["reclassifications_per_defect"]},
                   "checkpoint_resumes": {"used": 0, "maximum": lim["checkpoint_resumes_per_run"]},
                   "owner_approved_resumes": {"used": 0, "maximum": lim["owner_approved_resumes_per_incident"]}}},
           "defect_registry": {},
           "terminal": {"is_terminal": False, "status": "NOT_TERMINAL", "reason_code": None},
           "updated_at": now}
    gc.require_valid("ledger", led)
    return led


def asset_budget(graph: gc.Graph) -> dict:
    lim = graph.policy["limits"]
    return {"rework": {"used": 0, "maximum": lim["rework_transitions_per_asset"]},
            "distinct_defect_fingerprints": {"used": 0, "maximum": lim["distinct_defect_fingerprints_per_asset"]},
            "upstream_reentries": {"used": 0, "maximum": lim["upstream_reentries_per_asset"]},
            "qa_evidence_refreshes": {"used": 0, "maximum": lim["qa_evidence_refreshes_per_asset"]}}


def request(edge: dict, ledger: dict, *, request_id: str, asset_id=None, incident_id=None,
            fingerprint=None, new_evidence: bool = False) -> dict:
    ec = event_class(edge)
    if ec == "CHECKPOINT_RESUME" and incident_id is None:
        incident_id = ledger["run_id"]
    req = {"schema_version": "1.0", "request_id": request_id, "edge_id": edge["edge_id"],
           "event_class": ec, "asset_id": asset_id, "incident_id": incident_id,
           "normalized_defect_fingerprint": fingerprint, "new_evidence": new_evidence,
           "automatic_transition": True, "ledger": ledger}
    gc.require_valid("budget_request", req)
    return req


def resolve(req: dict, *, now: str) -> dict:
    """Квитанция бюджета с НОВОЙ ревизией ledger. Исходный ledger не трогаем."""
    gc.require_valid("budget_request", req)
    led = copy.deepcopy(req["ledger"])
    verdict, reason = ALLOW, None

    def stop(code, v="TERMINATION_BUDGET_EXHAUSTED"):
        nonlocal verdict, reason
        verdict, reason = v, code
        led["terminal"] = {"is_terminal": True, "status": "FAILED_EXHAUSTED", "reason_code": code}

    def bump(counter, code):
        counter["used"] += 1
        if counter["used"] > counter["maximum"]:
            stop(code)

    ec = req["event_class"]
    if led["terminal"]["is_terminal"]:
        stop("COUNTER_RESET_REJECTED", "COUNTER_RESET_REJECTED")
    elif not req["automatic_transition"]:
        if ec != "HUMAN_WAIT":
            stop("ZERO_PROGRESS_TRANSITION_REJECTED", "ZERO_PROGRESS_TRANSITION_REJECTED")
    else:
        bump(led["automatic_transitions"], "RUN_AUTOMATIC_TRANSITION_BUDGET_EXHAUSTED")
        if verdict == ALLOW and ec != "FORWARD":
            bump(led["package_rework"], "PACKAGE_REWORK_BUDGET_EXHAUSTED")
        if verdict == ALLOW and req["asset_id"]:
            a = led["asset_budgets"].get(req["asset_id"])
            if a is None:
                raise ValueError("ASSET_BUDGET_MISSING")
            if ec == "REWORK":
                bump(a["rework"], "ASSET_REWORK_BUDGET_EXHAUSTED")
            if ec == "UPSTREAM_REENTRY":
                bump(a["upstream_reentries"], "UPSTREAM_REENTRY_LIMIT_EXHAUSTED")
            if ec == "QA_EVIDENCE_REFRESH":
                bump(a["qa_evidence_refreshes"], "QA_EVIDENCE_REFRESH_LIMIT_EXHAUSTED")
            fp = req["normalized_defect_fingerprint"]
            if verdict == ALLOW and fp and fp not in led["defect_registry"]:
                led["defect_registry"][fp] = {"normalized_fingerprint": fp, "asset_id": req["asset_id"],
                                              "first_seen_at": now, "occurrences": 1}
                bump(a["distinct_defect_fingerprints"], "DISTINCT_DEFECT_BUDGET_EXHAUSTED")
        if verdict == ALLOW and req["incident_id"]:
            i = led["incident_budgets"].get(req["incident_id"])
            if i is None:
                raise ValueError("INCIDENT_BUDGET_MISSING")
            if ec == "RECLASSIFICATION":
                if not req["new_evidence"]:
                    stop("ZERO_PROGRESS_TRANSITION_REJECTED", "ZERO_PROGRESS_TRANSITION_REJECTED")
                else:
                    bump(i["reclassifications"], "RECLASSIFICATION_LIMIT_EXHAUSTED")
            if ec == "CHECKPOINT_RESUME":
                bump(i["checkpoint_resumes"], "CHECKPOINT_RESUME_LIMIT_EXHAUSTED")
            if ec == "OWNER_APPROVED_RESUME":
                bump(i["owner_approved_resumes"], "OWNER_RESUME_LIMIT_EXHAUSTED")

    led["revision"] += 1
    led["updated_at"] = now
    receipt = {"schema_version": "1.0", "receipt_id": f"TERMBUDGET-{req['request_id']}",
               "request_id": req["request_id"], "edge_id": req["edge_id"], "verdict": verdict,
               "reason_code": reason, "ledger": led, "evaluated_at": now}
    gc.require_valid("budget_receipt", receipt)
    return receipt
