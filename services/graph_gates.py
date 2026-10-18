# -*- coding: utf-8 -*-
"""
services/graph_gates.py — входы проверок рёбер и сама проверка.

Перенос двух эталонных скриптов канона: `New-AIDesignGateInputs.ps1`
(сборка входа для каждого исходящего ребра активных узлов) и
`Invoke-AIDesignGateEvaluation.ps1` (вердикт по ребру). Контракты —
`AI_DESIGN_GATE_FACT_RESOLVER_CONTRACT.md` и
`AI_DESIGN_ROUTER_DECISION_CONTRACT.md`.

**Условие ребра — не код.** Контракт маршрутизатора прямо запрещает `eval`
текста `guard_expression`. Условие — это грамматика из четырёх видов атомов,
соединённых `AND`, и любой другой текст — отказ разбора, а не «как-нибудь
посчитаем». Тест разбирает условия ВСЕХ рёбер реестра: новый вид атома в
каноне упадёт здесь, а не на живом запуске.

| атом | пример | оператор |
|---|---|---|
| `x == литерал` | `exact_passport_available == true` | EQ |
| `x > число` | `remaining > 0` | GT |
| `x IN [A, B]` | `passport_readiness IN [READY, READY_WITH_LIMITATIONS]` | IN_SET |
| `x IN y` | `asset_id IN approved_remaining_asset_ids` | MEMBER_OF |

**Сравнение строже эталона, и это намеренно.** PowerShell приводит типы:
`$true -eq 1` у него истина, `-contains` не различает регистр. Здесь булево
равно только булеву, число — числу, строка сравнивается с учётом регистра.
Расхождение может только закрыть ребро, а не открыть: факт `1` не пройдёт
атом `== true`. Открыть ребро по совпадению типов — ровно та тихая поломка,
от которой граф и защищают.

**Факт либо доказан, либо UNRESOLVED.** Факты состояния (`RUN_STATE_DERIVATION`)
считаются закрытыми функциями — ровно девять, как у эталона (правило 3
контракта: «только для явно поддержанных»). Остальные факты этого вида
(в реестре их 83) остаются неразрешёнными, пока для них не появится своя
функция, и ребро стоит с `GUARD_UNRESOLVED`. Внешний факт берётся из
Evidence Bundle только при точном совпадении с реестром поставщиков,
привязке к запуску и SHA состояния, свежести `CURRENT` и сошедшемся SHA
источника. SHA источника проверяет вызывающий (`source_sha`): у ядра нет
файлового хранилища, и без проверяющего факт не принимается вовсе.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from services import graph_canon as gc

EVALUATOR_VERSION = "1.0"
BUILDER_VERSION = "1.0"

_IDENT = r"[a-z][a-z0-9_]*"
_EQ = re.compile(rf"^(?P<left>{_IDENT})\s*==\s*(?P<right>true|false|-?[0-9]+(?:\.[0-9]+)?|[A-Z][A-Z0-9_]*)$")
_GT = re.compile(rf"^(?P<left>{_IDENT})\s*>\s*(?P<right>-?[0-9]+(?:\.[0-9]+)?)$")
_IN_SET = re.compile(rf"^(?P<left>{_IDENT})\s+IN\s+\[(?P<items>[A-Z0-9_, ]+)\]$")
_MEMBER = re.compile(rf"^(?P<left>{_IDENT})\s+IN\s+(?P<right>{_IDENT})$")
_AND = re.compile(r"\s+AND\s+")


class GuardGrammarError(ValueError):
    """Текст условия вне грамматики — ребро не вычисляется вовсе."""


@dataclass(frozen=True)
class Atom:
    fact_id: str
    operator: str
    expected: object = None
    right_fact_id: str | None = None


def _literal(token: str):
    if token == "true":
        return True
    if token == "false":
        return False
    if re.fullmatch(r"-?[0-9]+", token):
        return int(token)
    if re.fullmatch(r"-?[0-9]+\.[0-9]+", token):
        return float(token)
    return token


def parse_guard(expr: str) -> list[Atom]:
    atoms = []
    for text in _AND.split(expr.strip()):
        text = text.strip()
        if m := _EQ.match(text):
            atoms.append(Atom(m["left"], "EQ", _literal(m["right"])))
        elif m := _GT.match(text):
            atoms.append(Atom(m["left"], "GT", _literal(m["right"])))
        elif m := _IN_SET.match(text):
            atoms.append(Atom(m["left"], "IN_SET", [_literal(t.strip()) for t in m["items"].split(",")]))
        elif m := _MEMBER.match(text):
            atoms.append(Atom(m["left"], "MEMBER_OF", right_fact_id=m["right"]))
        else:
            raise GuardGrammarError(f"атом вне грамматики: {text!r}")
    return atoms


def needed_facts(expr: str) -> list[str]:
    out = set()
    for a in parse_guard(expr):
        out.add(a.fact_id)
        if a.right_fact_id:
            out.add(a.right_fact_id)
    return sorted(out)


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def same(a, b) -> bool:
    """Типизированное равенство: булево ≠ числу, строка — с регистром."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a is b
    if _is_num(a) and _is_num(b):
        return a == b
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    return False


def _contains(items, value) -> bool:
    return any(same(x, value) for x in items)


# ------------------------------------------------------ факты состояния ---

def _blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def state_fact(fact_id: str, state: dict, graph: gc.Graph):
    """Девять закрытых функций эталона. None — факт этим путём не выводится."""
    pi = state.get("product_identity") or {}
    pt = state.get("pinned_product_truth") or {}
    b = state.get("budgets") or {}
    if fact_id == "exact_product_identity_pinned":
        return not (_blank(pi.get("sku")) or _blank(pi.get("model")) or _blank(pi.get("product_root")))
    if fact_id == "graph_version_pinned":
        pg = state.get("pinned_graph") or {}
        return not _blank(pg.get("graph_version")) and len(pg) >= 5
    if fact_id == "exact_passport_available":
        return not (_blank(pt.get("path")) or _blank(pt.get("sha256")))
    if fact_id == "passport_readiness":
        return str(pt.get("status") or "")
    if fact_id == "attempts_remaining":
        r = b.get("retry") or {}
        return int(r.get("used", 0)) < int(r.get("maximum", 0))
    if fact_id == "cost_remaining":
        c = b.get("cost") or {}
        return Decimal(str(c.get("spent", 0))) < Decimal(str(c.get("approved", 0)))
    if fact_id == "graph_version_compatible":
        # С версией РЕЕСТРА ПОСТАВЩИКОВ, как у эталона. Сейчас реестр
        # говорит 2.5 при контракте 2.6 — и ответ честно «нет»
        # (canon/REFERENCE_DRIFT.md, ушло владельцу).
        return str((state.get("pinned_graph") or {}).get("graph_version")) == graph.provider_graph_version
    if fact_id == "run_state_consistent":
        # Состояние уже прошло схему до этой точки — как у эталона.
        return True
    if fact_id == "side_effects_reconciled":
        return not any(se.get("status") == "UNKNOWN"
                       or se.get("reconciliation_status") in ("PENDING", "UNRESOLVED")
                       for se in state.get("side_effect_ledger") or [])
    return None


DERIVABLE = ("exact_product_identity_pinned", "graph_version_pinned", "exact_passport_available",
             "passport_readiness", "attempts_remaining", "cost_remaining",
             "graph_version_compatible", "run_state_consistent", "side_effects_reconciled")


# --------------------------------------------------------- сборка входа ---

def _check(status: str, refs=()) -> dict:
    return {"status": status, "evidence_refs": list(refs)}


def build_gate_inputs(graph: gc.Graph, state: dict, bundle: dict | None = None, *,
                      source_sha=None) -> tuple[list[dict], dict]:
    """Входы проверок для всех исходящих рёбер активных узлов и сводка сборки.

    `source_sha(ref) -> sha | None` — проверка источника внешнего факта у
    вызывающего. Нет проверяющего — внешний факт не принимается."""
    gc.require_valid("run_state", state)
    state_hash = gc.sha256_json(state)
    run_id = state["run_id"]
    if bundle is not None:
        gc.require_valid("evidence_bundle", bundle)
        if bundle["run_id"] != run_id or bundle["run_state_sha256"].lower() != state_hash:
            raise ValueError("Evidence Bundle не привязан к текущему состоянию запуска")
    active = list(state["node_state"]["active_node_ids"])
    outgoing = graph.outgoing(active)
    evidence = (bundle or {}).get("fact_evidence", [])
    controls = (bundle or {}).get("edge_controls", [])
    requested_at = bundle["created_at"] if bundle else state["updated_at"]

    inputs, outputs, all_unresolved = [], [], set()
    for edge in outgoing:
        facts, unresolved = [], []
        for fid in needed_facts(edge["guard_expression"]):
            provider = graph.providers.get(fid)
            if provider is None:
                raise ValueError(f"{edge['edge_id']}: у факта {fid} нет поставщика в реестре")
            fact = None
            if provider["provider_kind"] == "RUN_STATE_DERIVATION":
                value = state_fact(fid, state, graph)
                if value is not None:
                    fact = {"fact_id": fid, "value": value, "evaluator_class": "DETERMINISTIC",
                            "freshness_status": "CURRENT", "evidence_refs": [f"RUN_STATE_SHA256:{state_hash}"]}
            else:
                cands = [ev for ev in evidence if ev["fact_id"] == fid]
                if len(cands) > 1:
                    raise ValueError(f"два свидетельства для факта {fid}")
                if cands and _evidence_ok(cands[0], provider, run_id, state_hash, source_sha):
                    ev = cands[0]
                    fact = {"fact_id": fid, "value": ev["value"], "evaluator_class": ev["evaluator_class"],
                            "freshness_status": "CURRENT", "evidence_refs": list(ev["evidence_refs"])}
            if fact is None:
                unresolved.append(fid)
                all_unresolved.add(fid)
            else:
                facts.append(fact)

        ctl = [c for c in controls if c["edge_id"] == edge["edge_id"]]
        if len(ctl) > 1:
            raise ValueError(f"два управляющих записи для {edge['edge_id']}")
        required = list(edge["required_source_receipts"])
        if ctl:
            c = ctl[0]
            extra = [r["receipt_type"] for r in c["required_receipt_results"] if r["receipt_type"] not in required]
            if extra:
                raise ValueError(f"{edge['edge_id']}: лишние квитанции {','.join(extra)}")
            receipts = []
            for t in required:
                m = [r for r in c["required_receipt_results"] if r["receipt_type"] == t]
                receipts.append(m[0] if len(m) == 1 else {"receipt_type": t, "status": "MISSING", "receipt_ref": None})
            trigger, payload = c["observed_trigger"], c["payload_result"]
            authority, receiver = c["authority_result"], c["receiver_precheck"]
        else:
            trigger = {"status": "UNRESOLVED", "name": None, "evidence_refs": []}
            payload = _check("UNRESOLVED")
            receipts = [{"receipt_type": t, "status": "MISSING", "receipt_ref": None} for t in required]
            authority = _check("UNRESOLVED" if edge["target_node_id"] == gc.PROVIDER_EXECUTION_NODE else "NOT_REQUIRED")
            receiver = _check("UNRESOLVED")

        eval_id = "GATE-" + run_id[4:] + "-" + gc.sha256_text(f"{run_id}|{state_hash}|{edge['edge_id']}")[:12].upper()
        gi = {"schema_version": "1.0", "evaluation_id": eval_id, "run_id": run_id,
              "graph_version": state["pinned_graph"]["graph_version"], "run_state_sha256": state_hash,
              "edge_id": edge["edge_id"], "observed_trigger": trigger, "facts": facts,
              "payload_result": payload, "required_receipt_results": receipts,
              "authority_result": authority, "receiver_precheck": receiver, "requested_at": requested_at}
        gc.require_valid("gate_input", gi)
        inputs.append(gi)
        outputs.append({"edge_id": edge["edge_id"], "sha256": gc.sha256_json(gi),
                        "resolved_fact_ids": sorted(f["fact_id"] for f in facts),
                        "unresolved_fact_ids": sorted(unresolved)})

    build_id = "GATEBUILD-" + run_id[4:] + "-" + gc.sha256_text(
        state_hash + "|" + "|".join(e["edge_id"] for e in outgoing))[:12].upper()
    manifest = {"schema_version": "1.0", "build_id": build_id, "run_id": run_id,
                "run_state_sha256": state_hash, "active_node_ids": active, "outputs": outputs,
                "unresolved_fact_ids": sorted(all_unresolved), "external_side_effects_executed": 0,
                "created_at": requested_at, "builder_version": BUILDER_VERSION}
    return inputs, manifest


def _evidence_ok(ev, provider, run_id, state_hash, source_sha) -> bool:
    if not (ev["provider_kind"] == provider["provider_kind"]
            and ev["provider_artifact_type"] == provider["authoritative_artifact_type"]
            and ev["evaluator_class"] == provider["allowed_evaluator_class"]
            and ev["bound_run_id"] == run_id
            and ev["bound_run_state_sha256"].lower() == state_hash
            and ev["freshness_status"] == "CURRENT"):
        return False
    if source_sha is None:
        return False
    try:
        got = source_sha(ev["source_ref"])
    except Exception:  # noqa: BLE001 — непроверяемый источник = факт не доказан
        return False
    return bool(got) and got.lower() == ev["source_sha256"].lower()


# ------------------------------------------------------------- проверка ---

def _find(gate_input, fact_id):
    m = [f for f in gate_input["facts"] if f["fact_id"] == fact_id]
    return m[0] if len(m) == 1 else None


def _eval_atom(atom: Atom, index: int, gate_input: dict) -> dict:
    fact = _find(gate_input, atom.fact_id)
    status, actual, refs, expected = "UNRESOLVED", None, [], atom.expected
    if fact is not None:
        actual, refs = fact["value"], list(fact["evidence_refs"])
        if fact["freshness_status"] == "CURRENT":
            if atom.operator == "EQ":
                status = "PASS" if same(actual, expected) else "FAIL"
            elif atom.operator == "GT":
                if _is_num(actual):
                    status = "PASS" if actual > expected else "FAIL"
            elif atom.operator == "IN_SET":
                status = "PASS" if _contains(expected, actual) else "FAIL"
            elif atom.operator == "MEMBER_OF":
                right = _find(gate_input, atom.right_fact_id)
                if right is not None:
                    expected = right["value"] if isinstance(right["value"], list) else [right["value"]]
                    refs += right["evidence_refs"]
                    if right["freshness_status"] == "CURRENT" and isinstance(right["value"], list):
                        status = "PASS" if _contains(right["value"], actual) else "FAIL"
    return {"atom_id": f"ATOM-{index:02d}", "fact_id": atom.fact_id, "operator": atom.operator,
            "expected_value": expected, "actual_value": actual, "status": status,
            "evidence_refs": sorted(set(refs))}


def evaluate_gate(graph: gc.Graph, state: dict, gate_input: dict, *, now: str,
                  input_ref: str | None = None) -> dict:
    gc.require_valid("gate_input", gate_input)
    state_hash = gc.sha256_json(state)
    if (gate_input["run_id"] != state["run_id"]
            or gate_input["graph_version"] != state["pinned_graph"]["graph_version"]
            or gate_input["run_state_sha256"].lower() != state_hash):
        raise ValueError("вход проверки не привязан к этому состоянию запуска")
    edge = graph.edges.get(gate_input["edge_id"])
    if edge is None:
        raise ValueError(f"{gate_input['edge_id']}: ребро не зарегистрировано")
    if edge["source_node_id"] not in state["node_state"]["active_node_ids"]:
        raise ValueError(f"{edge['edge_id']}: источник ребра не активен")
    if edge["edge_id"] not in state["edge_state"]["available_edge_ids"]:
        raise ValueError(f"{edge['edge_id']}: ребро структурно недоступно")

    tr = gate_input["observed_trigger"]
    t_status = ("UNRESOLVED" if tr["status"] == "UNRESOLVED"
                else "PASS" if tr["status"] == "PRESENT" and tr["name"] == edge["trigger"] else "FAIL")
    atoms = [_eval_atom(a, i + 1, gate_input) for i, a in enumerate(parse_guard(edge["guard_expression"]))]
    g_status = ("FAIL" if any(a["status"] == "FAIL" for a in atoms)
                else "UNRESOLVED" if any(a["status"] == "UNRESOLVED" for a in atoms) else "PASS")

    if sorted(edge["required_source_receipts"]) != sorted(r["receipt_type"] for r in gate_input["required_receipt_results"]):
        raise ValueError(f"{edge['edge_id']}: набор квитанций не совпал с реестром рёбер")
    reasons = set()
    reasons |= {"FAIL": {"TRIGGER_FALSE"}, "UNRESOLVED": {"TRIGGER_UNRESOLVED"}}.get(t_status, set())
    reasons |= {"FAIL": {"GUARD_FALSE"}, "UNRESOLVED": {"GUARD_UNRESOLVED"}}.get(g_status, set())
    reasons |= {"FAIL": {"PAYLOAD_INVALID"}, "UNRESOLVED": {"PAYLOAD_UNRESOLVED"}}.get(gate_input["payload_result"]["status"], set())
    rs = [r["status"] for r in gate_input["required_receipt_results"]]
    if "MISSING" in rs:
        reasons.add("RECEIPT_MISSING")
    if "INVALID" in rs:
        reasons.add("RECEIPT_INVALID")
    reasons |= {"FAIL": {"AUTHORITY_MISSING"}, "UNRESOLVED": {"AUTHORITY_UNRESOLVED"}}.get(gate_input["authority_result"]["status"], set())
    reasons |= {"FAIL": {"RECEIVER_NOT_READY"}, "UNRESOLVED": {"RECEIVER_UNRESOLVED"}}.get(gate_input["receiver_precheck"]["status"], set())
    # Платный вызов провайдера: «не требуется» запрещено (правило 9 контракта).
    if edge["target_node_id"] == gc.PROVIDER_EXECUTION_NODE and gate_input["authority_result"]["status"] != "PASS":
        reasons.add("AUTHORITY_MISSING")

    out = {"schema_version": "1.0", "evaluation_id": gate_input["evaluation_id"],
           "input_ref": input_ref or f"gate-input://{gate_input['evaluation_id']}",
           "input_sha256": gc.sha256_json(gate_input), "run_id": gate_input["run_id"],
           "graph_version": gate_input["graph_version"], "run_state_sha256": gate_input["run_state_sha256"],
           "edge_id": edge["edge_id"], "trigger_result": _check(t_status, tr["evidence_refs"]),
           "guard_result": _check(g_status, sorted({r for a in atoms for r in a["evidence_refs"]})),
           "atom_results": atoms, "payload_result": gate_input["payload_result"],
           "required_receipt_results": list(gate_input["required_receipt_results"]),
           "authority_result": gate_input["authority_result"], "receiver_precheck": gate_input["receiver_precheck"],
           "eligible": not reasons, "rejection_reason_codes": sorted(reasons),
           "evaluated_at": now, "evaluator_version": EVALUATOR_VERSION}
    gc.require_valid("gate_evaluation", out)
    return out
