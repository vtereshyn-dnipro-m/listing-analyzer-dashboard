# -*- coding: utf-8 -*-
"""
tests/test_graph_engine.py — ядро движка графа AI Design.

Ядро — перенос эталонных скриптов канона (`10_Runtime_Registry/*.ps1`):
реестры, условия рёбер, маршрутизатор, бюджет, запись перехода, запись в
`ai_runs`. Провайдеров модели и файлового хранилища нет. Что ломается тихо
и потому заперто:

1. **Снимок канона читается только сошедшимся с манифестом.** Правка байта
   в реестре рёбер — отказ загрузки, а не другой граф.
2. **Условие ребра — грамматика, не `eval`.** Разбираются условия всех 87
   рёбер; вне грамматики ровно одно — E183 (`факт == факт`), и это
   расхождение канона, а не наше. Сравнение типизированное: `1` не равно
   `true`, `ready` не равно `READY`.
3. **Факт либо доказан, либо UNRESOLVED.** Внешний факт без сверки SHA
   источника не принимается; Evidence Bundle от другого состояния — отказ.
4. **Маршрутизатор не выбирает сам.** Два годных ребра — решение человека,
   ноль — блок с причиной; платный вызов без полномочия — не годен.
5. **Бюджет делает граф конечным.** Цикл «проверка → переделка» идёт по
   зарегистрированным рёбрам, повторно применяя то же ребро (правило 8
   контракта записи; эталонный скрипт этого не умеет), и останавливается
   `FAILED_EXHAUSTED` на пакетном пределе: target не активирован, блокер
   `LOOP_BUDGET_EXHAUSTED`, дальше — `NO_OP_TERMINAL`, обнулить нельзя.
6. **Двенадцать сценариев теневого прогона канона** проходятся с оракулом:
   три целиком, остальные останавливаются в известных местах — на фактах,
   которые канон велит выводить из состояния, а закрытой функции для них
   нет (правило 3 контракта сборщика). Список остановок заперт: появится
   функция или сменится канон — тест скажет, что поменялось.
7. **Запись в базу — одна транзакция на шаг.** Событие, состояние и
   ревизия ledger пишутся вместе; повторное создание запуска не плодит
   второго; шаг по устаревшему снимку отвергается.

Запуск (pytest не нужен):  python tests/test_graph_engine.py
"""
from __future__ import annotations

import copy
import json
import pathlib
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services import graph_budget as gb  # noqa: E402
from services import graph_canon as gc  # noqa: E402
from services import graph_engine as ge  # noqa: E402
from services import graph_gates as gg  # noqa: E402
from services import graph_router as gr  # noqa: E402
from services import graph_store as gs  # noqa: E402
from services import graph_writer as gw  # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


def raises(fn, exc=Exception) -> bool:
    try:
        fn()
    except exc:
        return True
    return False


NOW = "2026-10-15T10:00:00Z"
RUN = "RUN-21680000-T1"
SRC_SHA = "b" * 64
G = gc.load_graph()

LC = {"launch_control_id": "LC-T1", "delivery_route": "INTERNAL_PIPELINE", "review_mode": "HUMAN_REVIEW_REQUIRED",
      "mode": "END_TO_END_GENERATION", "human_review_checkpoint": "REQUIRED",
      "terminal_target": "READY_CONTENT_PACKAGE", "authority_ref": "test", "authorized_at": NOW}
PI = {"sku": "21680000", "model": "PW-14B", "variant": None, "market": "ES", "channel": "AMAZON",
      "locales": ["es-ES"], "product_root": "/Volumes/listing/passport/21680000"}
PT = {"artifact_id": "PASSPORT-21680000", "path": "/Volumes/listing/passport/21680000/passport.json",
      "version": "1.0", "sha256": "a" * 64, "status": "READY"}
BUD = {"retry": {"used": 0, "maximum": 3}, "round": {"used": 0, "maximum": 3},
       "cost": {"currency": "USD", "approved": 10, "spent": 0}, "time": {"started_at": NOW, "deadline_at": None}}


def fresh_state():
    return gw.new_run_state(G, run_id=RUN, execution_mode="GRAPH_SHADOW_RUN", launch_control=LC,
                            product_identity=PI, pinned_product_truth=PT, budgets=BUD, now=NOW)


def state_at(node):
    st = fresh_state()
    ns, es = st["node_state"], st["edge_state"]
    ns.update(active_node_ids=[node], current_node_id=node,
              pending_node_ids=sorted(n for n in G.nodes if n != node))
    es["available_edge_ids"] = [e["edge_id"] for e in G.outgoing([node])]
    es["unevaluated_edge_ids"] = sorted(e for e in G.edges if e not in es["available_edge_ids"])
    return st


def control(edge, *, present, authority="PASS"):
    return {"edge_id": edge["edge_id"],
            "observed_trigger": {"status": "PRESENT" if present else "ABSENT",
                                 "name": edge["trigger"] if present else None, "evidence_refs": ["t"]},
            "payload_result": {"status": "PASS", "evidence_refs": ["p"]},
            "required_receipt_results": [{"receipt_type": t, "status": "PASS", "receipt_ref": "r:" + t}
                                         for t in edge["required_source_receipts"]],
            "authority_result": {"status": authority, "evidence_refs": ["a"] if authority == "PASS" else []},
            "receiver_precheck": {"status": "PASS", "evidence_refs": ["r"]}}


def evidence(state, fact_id, value):
    p = G.providers[fact_id]
    return {"fact_id": fact_id, "value": value, "provider_kind": p["provider_kind"],
            "provider_artifact_type": p["authoritative_artifact_type"],
            "evaluator_class": p["allowed_evaluator_class"], "source_ref": "src://" + fact_id,
            "source_sha256": SRC_SHA, "bound_run_id": state["run_id"],
            "bound_run_state_sha256": gc.sha256_json(state), "freshness_status": "CURRENT",
            "evidence_refs": ["ev:" + fact_id]}


def bundle(state, facts=(), controls=()):
    return {"schema_version": "1.0", "bundle_id": "EVIDENCE-T1", "run_id": state["run_id"],
            "run_state_sha256": gc.sha256_json(state), "fact_evidence": list(facts),
            "edge_controls": list(controls), "created_at": NOW}


def oracle(state, edge_id, *, others_present=False):
    """Свидетельства, при которых ребро сценария годно, а остальные — нет
    (их триггер отсутствует). Факты состояния не подкладываются: их ядро
    выводит само или честно оставляет неразрешёнными."""
    edge, facts, seen = G.edges[edge_id], [], set()
    for a in gg.parse_guard(edge["guard_expression"]):
        vals = ({a.fact_id: a.expected} if a.operator == "EQ" else
                {a.fact_id: a.expected + 1} if a.operator == "GT" else
                {a.fact_id: a.expected[0]} if a.operator == "IN_SET" else
                {a.fact_id: "ORACLE", a.right_fact_id: ["ORACLE"]})
        for f, v in vals.items():
            if G.providers[f]["provider_kind"] != "RUN_STATE_DERIVATION" and f not in seen:
                seen.add(f)
                facts.append(evidence(state, f, v))
    ctl = [control(o, present=(o["edge_id"] == edge_id) or others_present)
           for o in G.outgoing(state["node_state"]["active_node_ids"])]
    return bundle(state, facts, ctl)


def src(_ref):
    return SRC_SHA


# ============================================================== 1. снимок
print("1. снимок канона сверяется с манифестом")
check(f"граф загружен: {len(G.nodes)} узлов, {len(G.edges)} рёбер", len(G.nodes) == 41 and len(G.edges) == 87)
check(f"версия графа — из файла контракта ({G.graph_version})", G.graph_version == "AI-DESIGN-GRAPH-2.6")
with tempfile.TemporaryDirectory() as tmp:
    copy_root = pathlib.Path(tmp) / "snap"
    shutil.copytree(gc.SNAPSHOT / "10_Runtime_Registry", copy_root / "10_Runtime_Registry")
    p = copy_root / gc.EDGE_REGISTRY
    p.write_bytes(p.read_bytes().replace(b'"RUN_CREATED"', b'"RUN_CREATEX"', 1))
    real = gc.SNAPSHOT
    gc.SNAPSHOT = copy_root
    gc.load_graph.cache_clear()
    try:
        tampered = raises(gc.load_graph, gc.CanonError)
    finally:
        gc.SNAPSHOT = real
        gc.load_graph.cache_clear()
    check("правка байта в реестре рёбер — отказ загрузки", tampered)
G = gc.load_graph()
check("файл вне манифеста не читается", raises(lambda: gc.read_bytes("10_Runtime_Registry/nope.json"), gc.CanonError))

# ============================================================ 2. грамматика
print("2. условие ребра — грамматика")
unparsed, no_provider = [], []
for e in G.edges.values():
    try:
        for f in gg.needed_facts(e["guard_expression"]):
            if f not in G.providers:
                no_provider.append((e["edge_id"], f))
    except gg.GuardGrammarError:
        unparsed.append(e["edge_id"])
check(f"вне грамматики только E183 (факт == факт): {unparsed}", unparsed == ["E183_RESOLVE_PROMPT_AGENT_RUNTIME"])
check(f"у каждого факта условий есть поставщик: {no_provider}", not no_provider)
check("неизвестный атом — отказ, а не eval", raises(lambda: gg.parse_guard("x == true OR y == true"), gg.GuardGrammarError))
check("атомы разобраны по видам",
      [a.operator for a in gg.parse_guard("a == true AND b > 0 AND c IN [X, Y] AND d IN e")]
      == ["EQ", "GT", "IN_SET", "MEMBER_OF"])


def one_atom(text, facts):
    gi = {"facts": [{"fact_id": k, "value": v, "evaluator_class": "DETERMINISTIC",
                     "freshness_status": "CURRENT", "evidence_refs": ["x"]} for k, v in facts.items()]}
    return gg._eval_atom(gg.parse_guard(text)[0], 1, gi)["status"]


check("1 не равно true (у эталона равно)", one_atom("a == true", {"a": 1}) == "FAIL")
check("true равно true", one_atom("a == true", {"a": True}) == "PASS")
check("ready не равно READY (регистр)", one_atom("a == READY", {"a": "ready"}) == "FAIL")
check("IN_SET с регистром", one_atom("a IN [READY, BLOCKED]", {"a": "ready"}) == "FAIL")
check("GT на булевом — UNRESOLVED", one_atom("a > 0", {"a": True}) == "UNRESOLVED")
check("GT на числе", one_atom("a > 2", {"a": 3}) == "PASS")
check("MEMBER_OF по списку", one_atom("a IN b", {"a": "X", "b": ["X", "Y"]}) == "PASS")
check("MEMBER_OF без списка — UNRESOLVED", one_atom("a IN b", {"a": "X", "b": "X"}) == "UNRESOLVED")
check("факта нет — UNRESOLVED", one_atom("a == true", {}) == "UNRESOLVED")

# ============================================================== 3. факты
print("3. факт доказан или UNRESOLVED")
S0 = fresh_state()
L0 = gb.new_ledger(G, RUN, package_id="PKG-21680000", now=NOW)
r = ge.advance(G, S0, L0, now=NOW)
e010 = [o for o in r.build_manifest["outputs"] if o["edge_id"] == gw.INIT_EDGE][0]
check("у начального состояния два факта идентичности выведены сами",
      e010["resolved_fact_ids"] == ["exact_product_identity_pinned", "graph_version_pinned"] and not e010["unresolved_fact_ids"])
check(f"без свидетельств E010 не годно, запуск стоит ({r.decision['outcome']}/{r.decision['reason_code']})",
      r.decision["outcome"] == "RUN_BLOCKED" and r.transition is None)
bad = bundle(S0)
bad["run_state_sha256"] = "c" * 64
check("Evidence Bundle от другого состояния — отказ", raises(lambda: gg.build_gate_inputs(G, S0, bad)))

S090 = state_at("N020_PASSPORT_COORDINATION")
e090 = G.edges["E090_REQUEST_IMAGE_COLLECTION"]
ext = [f for f in gg.needed_facts(e090["guard_expression"]) if G.providers[f]["provider_kind"] != "RUN_STATE_DERIVATION"]
b = oracle(S090, e090["edge_id"])
ins, man = gg.build_gate_inputs(G, S090, b, source_sha=None)
un = [o for o in man["outputs"] if o["edge_id"] == e090["edge_id"]][0]["unresolved_fact_ids"]
check(f"без проверки источника внешний факт не принят ({un})", set(ext) <= set(un) and ext)
ins, man = gg.build_gate_inputs(G, S090, b, source_sha=lambda ref: "d" * 64)
un = [o for o in man["outputs"] if o["edge_id"] == e090["edge_id"]][0]["unresolved_fact_ids"]
check("SHA источника не сошёлся — факт не принят", set(ext) <= set(un))
ins, man = gg.build_gate_inputs(G, S090, b, source_sha=src)
un = [o for o in man["outputs"] if o["edge_id"] == e090["edge_id"]][0]["unresolved_fact_ids"]
check("SHA сошёлся — факт принят", not un)
stale = copy.deepcopy(b)
for f in stale["fact_evidence"]:
    f["freshness_status"] = "STALE"
ins, man = gg.build_gate_inputs(G, S090, stale, source_sha=src)
check("устаревшее свидетельство не принято",
      set(ext) <= set([o for o in man["outputs"] if o["edge_id"] == e090["edge_id"]][0]["unresolved_fact_ids"]))
check("graph_version_compatible честно «нет»: реестр поставщиков 2.5, контракт 2.6",
      gg.state_fact("graph_version_compatible", S0, G) is False)

# ======================================================== 4. маршрутизатор
print("4. маршрутизатор не выбирает сам")
r = ge.advance(G, S0, L0, now=NOW, bundle=oracle(S0, gw.INIT_EDGE), source_sha=src)
check(f"одно годное ребро — EDGE_SELECTED ({r.decision['selected_edge_id']})",
      r.decision["outcome"] == "EDGE_SELECTED" and r.decision["selected_edge_id"] == gw.INIT_EDGE)
S1 = r.transition.state
check("после E010 активен координатор Паспорта",
      S1["node_state"]["active_node_ids"] == ["N020_PASSPORT_COORDINATION"]
      and S1["lifecycle_state"] == "WAITING_RECEIVER_ACCEPTANCE" and len(S1["transition_history"]) == 1)
check("исходное состояние не тронуто", S0["node_state"]["active_node_ids"] == [gw.INIT_NODE])
check("переход списал один автоматический переход",
      r.transition.budget_receipt["ledger"]["automatic_transitions"]["used"] == 1)

S20 = state_at("N020_PASSPORT_COORDINATION")
both = [o["edge_id"] for o in G.outgoing(["N020_PASSPORT_COORDINATION"])][:2]
bb = oracle(S20, both[0], others_present=True)
for ev in oracle(S20, both[1])["fact_evidence"]:
    if ev["fact_id"] not in {f["fact_id"] for f in bb["fact_evidence"]}:
        bb["fact_evidence"].append(ev)
r = ge.advance(G, S20, gb.new_ledger(G, RUN, package_id="P", now=NOW), now=NOW, bundle=bb, source_sha=src)
elig = [c["edge_id"] for c in r.decision["candidate_evaluations"] if c["eligible"]]
check(f"два годных ребра — решение человека, перехода нет ({elig})",
      len(elig) >= 2 and r.decision["outcome"] == "HUMAN_ROUTE_DECISION" and r.transition is None)

ins, _ = gg.build_gate_inputs(G, S20, bundle(S20))
evs = [gg.evaluate_gate(G, S20, gi, now=NOW) for gi in ins]
check("пропущенный кандидат — отказ маршрутизатора", raises(lambda: gr.decide(G, S20, evs[1:])))

S180 = state_at("N180_AI_CREATOR_PREFLIGHT")
pe = [e for e in G.edges.values() if e["target_node_id"] == gc.PROVIDER_EXECUTION_NODE][0]
Sp = state_at(pe["source_node_id"])
bp = oracle(Sp, pe["edge_id"])
for c in bp["edge_controls"]:
    if c["edge_id"] == pe["edge_id"]:
        c["authority_result"] = {"status": "NOT_REQUIRED", "evidence_refs": []}
ins, _ = gg.build_gate_inputs(G, Sp, bp, source_sha=src)
ev = gg.evaluate_gate(G, Sp, [g for g in ins if g["edge_id"] == pe["edge_id"]][0], now=NOW)
check(f"платный вызов с «полномочие не требуется» не годен ({pe['edge_id']})",
      not ev["eligible"] and "AUTHORITY_MISSING" in ev["rejection_reason_codes"])

# ================================================================ 5. бюджет
print("5. бюджет делает граф конечным")
st = state_at("N030_PASSPORT_COLLECTION")
led = gb.new_ledger(G, RUN, package_id="PKG", now=NOW)
loop = ["E030_VALIDATE_COLLECTOR_PACKAGE", "E035_REWORK_COLLECTOR_PACKAGE"]
applied, last, steps = [], None, 0
for i in range(40):
    eid = loop[i % 2]
    try:
        r = ge.advance(G, st, led, now=NOW, bundle=oracle(st, eid), source_sha=src)
    except ValueError as e:  # эталон: применённое ребро «структурно недоступно»
        print("       шаг упал:", e)
        last = None
        break
    steps += 1
    last = r
    if r.transition is None:
        break
    if r.transition.verdict != "TRANSITION_APPLIED":
        break
    applied.append(eid)
    st, led = r.transition.state, r.transition.budget_receipt["ledger"]
check(f"одно и то же ребро применяется повторно ({applied.count(loop[0])} раз E030)", applied.count(loop[0]) >= 2)
pm = gb.new_ledger(G, RUN, package_id="P", now=NOW)["package_rework"]["maximum"]
check(f"цикл остановлен бюджетом за {steps} шагов, а не перебором", last is not None and last.transition is not None
      and last.transition.verdict == "FAILED_EXHAUSTED"
      and last.transition.receipt["reason_code"] == "PACKAGE_REWORK_BUDGET_EXHAUSTED" and steps < 40)
check(f"переделок применено ровно по пределу ({applied.count(loop[1])} из {pm})", applied.count(loop[1]) == pm)
if last is None or last.transition is None:
    print("\nИТОГ:", f"{len(FAILS)} провалов: {FAILS}")
    sys.exit(1)
ex = last.transition.state
check("исчерпание: terminal FAILED_EXHAUSTED, target не активирован",
      ex["terminal"]["status"] == "FAILED_EXHAUSTED" and ex["terminal"]["is_terminal"]
      and ex["node_state"]["active_node_ids"] == st["node_state"]["active_node_ids"])
check("исчерпание: открыт блокер LOOP_BUDGET_EXHAUSTED",
      any(b["code"] == "LOOP_BUDGET_EXHAUSTED" and b["status"] == "OPEN" for b in ex["blockers"]))
led_x = last.transition.budget_receipt["ledger"]
r = ge.advance(G, ex, led_x, now=NOW, bundle=oracle(ex, loop[1]), source_sha=src)
check(f"после исчерпания — NO_OP_TERMINAL ({r.decision['outcome']})", r.decision["outcome"] == "NO_OP_TERMINAL" and r.transition is None)
req = gb.request(G.edges[loop[1]], led_x, request_id="X")
check("обнулить счётчики нельзя: COUNTER_RESET_REJECTED", gb.resolve(req, now=NOW)["verdict"] == "COUNTER_RESET_REJECTED")

tiny = gb.new_ledger(G, RUN, package_id="P", now=NOW)
tiny["automatic_transitions"]["maximum"] = 0
r = ge.advance(G, S0, tiny, now=NOW, bundle=oracle(S0, gw.INIT_EDGE), source_sha=src)
check("даже прямой переход списывается: предел 0 — RUN_AUTOMATIC_TRANSITION_BUDGET_EXHAUSTED",
      r.transition.verdict == "FAILED_EXHAUSTED"
      and r.transition.receipt["reason_code"] == "RUN_AUTOMATIC_TRANSITION_BUDGET_EXHAUSTED")
check("класс события по классу ребра: RETRY → REWORK, RESUME → CHECKPOINT_RESUME",
      gb.EVENT_CLASS["RETRY"] == "REWORK" and gb.EVENT_CLASS["RESUME"] == "CHECKPOINT_RESUME"
      and set(gb.EVENT_CLASS) == {e["edge_class"] for e in G.edges.values()})

# квитанция бюджета чужой ревизии не принимается
r = ge.advance(G, S0, L0, now=NOW, bundle=oracle(S0, gw.INIT_EDGE), source_sha=src)
old = copy.deepcopy(r.budget_request)
rec = gb.resolve(old, now=NOW)
rec_wrong = copy.deepcopy(rec)
rec_wrong["ledger"]["revision"] += 1
check("запись без квитанции текущей ревизии — отказ", raises(lambda: gw.apply(
    G, S0, r.decision, budget_request=old, budget_receipt=rec_wrong, ledger=L0, now=NOW)))

# ============================================================ 6. сценарии
print("6. двенадцать сценариев теневого прогона канона")
EXPECTED_STOPS = {
    "HAPPY_PATH_SINGLE_ASSET": ("E130_APPLY_MEDIA_DELTA_TO_PASSPORT", ["passport_delta_route"]),
    "EXTERNAL_CONTENT_TZ_LOCAL_HANDOFF": ("E160_VALIDATE_CONTENT_TZ", ["content_tz_self_check", "expected_deliverables_draft_exists"]),
    "PROMPT_AGENT_RELOAD_RECOVERY": ("E183_RESOLVE_PROMPT_AGENT_RUNTIME", "GRAMMAR"),
    "BATCH_CONTINUE_LOOP": ("E264_APPLY_CONTENT_OUTPUT_QA_POLICY", ["qa_evidence_complete"]),
    "CHECKPOINT_RESUME": ("E310_RESUME_AT_COORDINATOR", ["recovery_run_state"]),
    "CONTENT_TZ_REWORK": ("E160_VALIDATE_CONTENT_TZ", ["content_tz_self_check", "expected_deliverables_draft_exists"]),
    "PROVIDER_TECHNICAL_RETRY": ("E205_EVALUATE_PROVIDER_EXECUTION_AUTHORITY", ["sealed_execution_record_exists"]),
    "PROVIDER_AUTHORITY_PAUSE_RESUME": ("E205_EVALUATE_PROVIDER_EXECUTION_AUTHORITY", ["sealed_execution_record_exists"]),
    "HUMAN_BATCH_CONTINUE_EXCEPTION": ("E264_APPLY_CONTENT_OUTPUT_QA_POLICY", ["qa_evidence_complete"]),
}
scen, _ = gc.read_json(gc.REG + "AI_DESIGN_E2E_SHADOW_SCENARIOS.json")
stops, passport_ok = {}, True
for s in scen["scenarios"]:
    st = state_at(s["start_node_id"])
    led = gb.new_ledger(G, RUN, package_id="PKG", now=NOW)
    for eid in s["edge_ids"]:
        try:
            r = ge.advance(G, st, led, now=NOW, bundle=oracle(st, eid), source_sha=src)
        except gg.GuardGrammarError:
            stops[s["scenario_id"]] = (eid, "GRAMMAR")
            break
        if r.decision["selected_edge_id"] != eid:
            un = [o for o in r.build_manifest["outputs"] if o["edge_id"] == eid][0]["unresolved_fact_ids"]
            stops[s["scenario_id"]] = (eid, un)
            break
        st, led = r.transition.state, r.transition.budget_receipt["ledger"]
    else:
        check(f"{s['scenario_id']}: пройден целиком, {len(s['edge_ids'])} рёбер, конец в {s['terminal_node_id']}",
              s["terminal_node_id"] in st["node_state"]["active_node_ids"])
for sid, stop in sorted(stops.items()):
    check(f"{sid}: остановка {stop[0]} — {stop[1]}", EXPECTED_STOPS.get(sid) == stop)
check("остановок ровно столько, сколько известно", set(stops) == set(EXPECTED_STOPS))
happy = [s for s in scen["scenarios"] if s["scenario_id"] == "HAPPY_PATH_SINGLE_ASSET"][0]["edge_ids"]
check("путь Паспорта (E010…E120) проходит целиком: первая остановка — уже Image Collection",
      stops["HAPPY_PATH_SINGLE_ASSET"][0] == "E130_APPLY_MEDIA_DELTA_TO_PASSPORT"
      and happy.index("E130_APPLY_MEDIA_DELTA_TO_PASSPORT") > happy.index("E050_ACCEPT_AUDITED_PASSPORT"))


# ================================================================== 7. база
print("7. запись в ai_runs и ai_run_events")


class FakeCursor:
    def __init__(self, db):
        self.db, self.rows, self.rowcount = db, [], 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        self.db["log"].append(s.split(" ")[0])
        if s.startswith("INSERT INTO ai_runs"):
            run_id = params[0]
            if run_id in self.db["runs"]:
                self.rowcount = 0
                return
            self.db["runs"][run_id] = {"run_state": json.loads(params[11]), "lifecycle_state": params[8],
                                       "terminal_status": params[9], "current_node_id": params[10],
                                       "route": params[1], "graph_sha256": params[6]}
            self.rowcount = 1
        elif s.startswith("INSERT INTO ai_run_events"):
            if "VALUES (%s, 1," in s:
                run_id, seq, edge = params[0], 1, None
                rest = params[1:]
                row = {"to": rest[0], "receipt": json.loads(rest[1]), "sha": rest[2], "charge": json.loads(rest[3])}
            else:
                run_id, seq, edge = params[0], params[1], params[2]
                row = {"to": params[4], "receipt": json.loads(params[5]), "sha": params[6],
                       "charge": json.loads(params[7])}
            if (run_id, seq) in self.db["events"]:
                raise RuntimeError("duplicate key (run_id, seq)")
            row["edge_id"] = edge
            self.db["events"][(run_id, seq)] = row
            self.rowcount = 1
        elif s.startswith("SELECT run_state FROM ai_runs"):
            self.db["for_update"] = "FOR UPDATE" in s
            r = self.db["runs"].get(params[0])
            self.rows = [(copy.deepcopy(r["run_state"]),)] if r else []
        elif s.startswith("SELECT seq, budget_charge FROM ai_run_events"):
            evs = sorted(k[1] for k in self.db["events"] if k[0] == params[0])
            self.rows = [(evs[-1], copy.deepcopy(self.db["events"][(params[0], evs[-1])]["charge"]))] if evs else []
        elif s.startswith("UPDATE ai_runs"):
            r = self.db["runs"][params[4]]
            r.update(run_state=json.loads(params[0]), lifecycle_state=params[1], terminal_status=params[2],
                     current_node_id=params[3])
        elif s.startswith(("UPDATE ai_run_events", "DELETE")):
            raise RuntimeError("только дописывание")
        else:
            raise AssertionError(s)

    def fetchone(self):
        return self.rows[0] if self.rows else None


class FakeConn:
    def __init__(self):
        self.db = {"runs": {}, "events": {}, "log": []}
        self.commits = self.rollbacks = 0

    def __enter__(self):
        return self

    def __exit__(self, et, *a):
        if et is None:
            self.commits += 1
        else:
            self.rollbacks += 1
        return False

    def cursor(self):
        return FakeCursor(self.db)


conn = FakeConn()
S0 = fresh_state()
L0 = gb.new_ledger(G, RUN, package_id="PKG-21680000", now=NOW)
created = gs.create_run(conn, G, S0, L0, route=gs.ROUTE_PASSPORT, sku_id="21680000", requested_action="INITIAL_CREATE")
again = gs.create_run(conn, G, S0, L0, route=gs.ROUTE_PASSPORT, sku_id="21680000", requested_action="INITIAL_CREATE")
check("запуск заведён, повтор не создаёт второго", created and not again and len(conn.db["runs"]) == 1)
check("событие 1 — создание с начальным ledger",
      conn.db["events"][(RUN, 1)]["charge"]["ledger"]["revision"] == 1
      and conn.db["events"][(RUN, 1)]["receipt"]["kind"] == "RUN_INITIALIZED")
check("в строке запуска отпечаток графа", conn.db["runs"][RUN]["graph_sha256"] == G.sha256)

res = gs.step(conn, G, RUN, now=NOW, bundle=oracle(S0, gw.INIT_EDGE), source_sha=src)
row, ev2 = conn.db["runs"][RUN], conn.db["events"].get((RUN, 2))
check("шаг взял строку запуска FOR UPDATE", conn.db["for_update"])
check("шаг записал событие 2 с квитанцией и решением",
      ev2 is not None and ev2["edge_id"] == gw.INIT_EDGE and ev2["receipt"]["kind"] == "TRANSITION"
      and ev2["receipt"]["router_decision"]["outcome"] == "EDGE_SELECTED"
      and ev2["sha"] == gc.sha256_json(ev2["receipt"]))
check("в событии новая ревизия ledger", ev2["charge"]["receipt"]["ledger"]["revision"] == 2
      and "ledger" not in ev2["charge"]["request"])
check("строка запуска обновлена: узел, состояние, жизненный цикл",
      row["current_node_id"] == "N020_PASSPORT_COORDINATION" and row["lifecycle_state"] == "WAITING_RECEIVER_ACCEPTANCE"
      and row["run_state"] == res.transition.state)

st, led, seq = gs.load(FakeCursor(conn.db), RUN)
check("ledger читается из последнего события", led["revision"] == 2 and seq == 2)
n_events = len(conn.db["events"])
blocked = gs.step(conn, G, RUN, now=NOW)
check("шаг без перехода ничего не пишет", blocked.transition is None and len(conn.db["events"]) == n_events)
check("шаг по устаревшему снимку — отказ без записи",
      raises(lambda: gs.step(conn, G, RUN, now=NOW, expected_state_sha256=gc.sha256_json(S0)))
      and len(conn.db["events"]) == n_events)
check("неудачный шаг откатывает транзакцию", conn.rollbacks >= 1)

# ============================================================ 8. без лишнего
print("8. в ядре нет провайдеров, файлов и Streamlit")
code = "\n".join((ROOT / "services" / f"graph_{m}.py").read_text(encoding="utf-8")
                 for m in ("canon", "gates", "router", "budget", "writer", "engine", "store"))
for word in ("import streamlit", "services.ai", "services import ai", "open(", "write_text", "write_bytes",
             "requests", "httpx", "anthropic", "openai"):
    check(f"нет «{word}»", word not in code)
check("eval в ядре не используется", "eval(" not in code.replace("evaluate_gate(", "").replace("_eval_atom(", ""))

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
