# AI Design Execution Graph Contract

Версія: `0.1`  
Статус: `SPECIFICATION_READY_NOT_RUNTIME_BOUND`  
Дата набуття чинності: 01.10.2026

## Призначення

Контракт формалізує чинний AI Design Content Creation Pipeline як execution graph: bounded nodes виконують роботу, typed edges визначають дозволені переходи, structured state переносить факти та рішення, checkpoints підтримують безпечне відновлення, а human gates зберігають decision authority. Контракт не створює нових агентів і не надає write, spend, provider, publication або Product Truth mutation authority.

## Область застосування

Застосовується до нового або істотно зміненого наскрізного запуску SKU Passport → Marketing Book → Content TZ → Prompt Package → production → QA → release → measurement/learning, якщо є branching, parallel execution, evaluator loop, pause/resume, зовнішній side effect або кілька owners.

Linear bounded route залишається допустимим і отримує `GRAPH_NOT_REQUIRED`, якщо graph не дає вимірюваної переваги. Чинний Pipeline, R01–R41, Product Truth, Agent Session Contract, handoff/writeback contracts, package conformance і human approvals залишаються нормативними джерелами; цей документ не послаблює їх.

## Вхідні дані та graph manifest

```yaml
ai_design_execution_graph:
  graph_id:
  graph_version:
  status: SPECIFICATION_READY_NOT_RUNTIME_BOUND | SHADOW_READY | CONTROLLED_RUNTIME | BLOCKED
  sku_scope:
    sku_id:
    variant_id:
    market:
    locale:
    channel:
  pinned_inputs:
    sku_passport_ref_and_hash:
    marketing_book_ref_and_hash:
    content_tz_ref_and_hash:
    evidence_snapshot_ref_and_hash:
  baseline_route_ref:
  node_registry: []
  edge_registry: []
  state_schema_version:
  reducer_registry: []
  checkpoint_policy_ref:
  session_control_profile_ref:
  permission_profile_ref:
  human_gate_registry: []
  budget:
    max_graph_rounds:
    max_parallel_branches:
    max_tool_hops:
    max_cost:
    max_elapsed_time:
  terminal_receipt_ref:
```

## Node contract

Кожний node є bounded unit of work, а не обов’язково окремим агентом.

```yaml
ai_design_graph_node:
  node_id:
  node_type: DETERMINISTIC | AGENTIC | HUMAN_GATE | EXTERNAL_EVENT | SIDE_EFFECT
  owner:
  responsibility:
  input_schema_ref:
  output_schema_ref:
  allowed_tools: []
  forbidden_side_effects: []
  prerequisite_edges: []
  success_statuses: []
  blocker_statuses: []
  timeout:
  retry_policy:
  evidence_receipt_ref:
  verifier:
```

Schema/hash validation, Product Truth comparison, rights/claim checks, channel constraints і arithmetic залишаються deterministic, якщо не потребують judgment. Новий agent node допускається лише після boundary decision і conformance receipt.

## Typed Edge Contract

Кожний застосовний маршрут R01–R41 стає edge або edge guard, але чинний semantic зміст маршруту не переписується.

```yaml
ai_design_graph_edge:
  edge_id:
  source_node:
  target_node:
  edge_type: DIRECT | CONDITIONAL | PARALLEL | LOOP | ERROR | HUMAN | EVENT
  trigger:
  guard:
  input_payload_schema:
  state_delta_schema:
  required_receipts: []
  permission_or_approval:
  timeout:
  retry_limit:
  failure_route:
  observable_transition_receipt:
```

Стрілка без trigger, guard, payload, owner, failure route та receipt не є executable edge. Unknown applicability не дорівнює `NOT_APPLICABLE`.

## Authoritative run state

```yaml
ai_design_run_state:
  run_id:
  graph_id_and_version:
  task_identity:
  current_node:
  current_edge:
  completed_nodes: []
  pending_nodes: []
  failed_or_blocked_nodes: []
  pinned_input_hashes: {}
  evidence_gaps: []
  active_hypotheses: []
  decisions_and_approvals: []
  artifact_refs_and_hashes: []
  branch_states: []
  reducer_results: []
  retry_counters: {}
  budget_usage:
  external_effect_receipts: []
  current_checkpoint_ref:
  resume_cursor:
  terminal_status:
```

Conversation history не є authoritative state. Product Truth, SKU/variant/market identity, approved brief, rights/claims, human approvals і immutable references не можуть бути переписані downstream node або reducer.

## Parallel Branch і Fan-In

Parallel execution дозволена лише для незалежних branches зі спільним immutable snapshot. Кожна branch має `branch_id`, bounded scope, власні outputs/evidence, budget і terminal status.

Reducer визначає merge keys, ordering, duplicate/conflict policy, provenance, quorum/completion, missing-branch behavior і reviewer. `last-writer-wins` заборонено. Missing branch, stale snapshot, rights/Product Truth conflict або incompatible verdict дає `FAN_IN_INCOMPLETE | SHARED_SNAPSHOT_MISMATCH | STATE_CONFLICT`, а не умовний success.

## Session Control Profile

Shared graph contract використовує capability intents; literal CLI/UI commands належать versioned host adapter.

```yaml
session_control_profile:
  profile_id:
  host_adapter_id_and_version:
  supported_intents:
    INSPECT_CONTEXT:
    COMPACT_WITH_FOCUS:
    RESET_FOR_NEW_TASK:
    RECORD_DURABLE_RULE:
    PLAN_BEFORE_MUTATION:
    REVIEW_CHANGESET:
    FORK_EXPERIMENT:
    RUN_IN_BACKGROUND:
    ISOLATE_WORKSPACE:
    INSPECT_COST:
    SET_EFFORT:
    RUN_FINAL_CHECK:
  unsupported_intents: []
  fallback_by_intent: {}
  current_state: CONTINUE | COMPACT | RESET | FORK | BACKGROUND | ISOLATED_WORKSPACE | REVIEW | STOP
  context_budget_observation:
  durable_state_ref:
  unresolved_blockers: []
  plan_ref:
  mutation_scope: []
  isolation_ref:
  effort_and_cost_budget:
  changeset_or_artifact_refs: []
  deterministic_checks: []
  reviewer:
  next_state:
  verdict: PASS | REPLAN | HANDOFF_REQUIRED | REVIEW_REQUIRED | BLOCKED
```

Правила:

1. `CONTINUE | COMPACT | RESET` обираються за task identity, admitted facts, blockers, artifact pointers і remaining context budget. Context percentage сам по собі не визначає перехід.
2. Compaction зберігає accepted decisions, provenance, blockers, approvals і resume cursor. Reset дозволений лише після checkpoint/handoff або для нового task.
3. Multi-file, consequential або assumption-heavy mutation потребує plan; merge/delivery — actual changeset/artifact review і applicable tests.
4. Fork/background/isolation не розширюють tools, permissions або authority. Parallel writer має окремий workspace/state і explicit merge/discard verdict.
5. Effort, tool depth, latency й cost є task budgets. Підвищення effort без measured quality lift або blocker resolution веде до replan/downgrade/escalation.
6. Visible reasoning або extended-thinking UI не є verification evidence. Приймаються source/diff, deterministic checks, tests, receipts, reviewer verdict і observed external state.

## Checkpoint, retry та side effects

Checkpoint містить graph/state version, current node/edge, input/artifact hashes, completed/pending work, approvals, budgets, retry counters, external IDs/effects і resume cursor.

External write, send, generation charge, upload, publication, spend або state mutation потребує idempotency key, permission owner, pre/post checkpoint, effect receipt, verification та recovery/compensation route. Resume не повторює вже підтверджений irreversible effect. Unsafe replay дає `SIDE_EFFECT_REPLAY_UNSAFE`.

## Ролі та відповідальність

- AI Design Coordinator: обирає лише дозволений route, підтримує graph/state registry і не виконує specialist work.
- Node owner: виконує bounded contract і повертає evidence/terminal receipt.
- Deterministic verifier: перевіряє schema, identity, hash, arithmetic і policy assertions.
- Content Standard Auditor / domain verifier: перевіряє зміст у визначеній межі, не self-approves власний output.
- Human release owner: приймає consequential release/publication/spend decision.
- Runtime owner: підтверджує host adapter, checkpoint, retry, isolation та observed external state.
- Independent evaluator: порівнює graph із чинним linear/coordinator baseline.

## Стани та вердикти

Graph lifecycle: `SPECIFICATION_READY_NOT_RUNTIME_BOUND → SHADOW_READY → CONTROLLED_RUNTIME`.

Run states: `PLANNED | RUNNING | WAITING_HUMAN | FAN_IN_PENDING | REVIEW_REQUIRED | RECOVERY_REQUIRED | BLOCKED | COMPLETED_WITH_RECEIPT`.

Design verdicts: `GRAPH_NOT_REQUIRED | MANUAL_PILOT_REQUIRED | GRAPH_APPROVED | REWORK | BLOCKED`.

Runtime blockers: `EDGE_CONTRACT_MISSING | ROUTING_UNCERTAIN | FALSE_NARROW_ROUTE | PARALLEL_DEPENDENCY_CONFLICT | REDUCER_CONTRACT_MISSING | FAN_IN_INCOMPLETE | STATE_CONFLICT | SHARED_SNAPSHOT_MISMATCH | LOOP_STOP_RULE_MISSING | NO_MEANINGFUL_IMPROVEMENT | CONTEXT_STATE_LOSS | HOST_INTENT_UNSUPPORTED | SIDE_EFFECT_REPLAY_UNSAFE`.

## Acceptance tests

- output, scope, baseline route і applicable R01–R41 transitions визначені;
- кожний node/edge має typed contract, owner, failure route та receipt;
- deterministic task не перетворено на LLM node без documented justification;
- low-confidence/false-narrow route переходить у broad route, review або block;
- overlapping parallel writes дають deterministic merge або explicit conflict незалежно від finish order;
- missing/timeout branch не маскується як complete;
- evaluator loop завершується за `MAX_ROUNDS` або `NO_MEANINGFUL_IMPROVEMENT`;
- compaction/reset/re-entry зберігає authoritative state та pinned hashes;
- unsupported host intent має validated fallback або block;
- checkpoint replay не дублює зовнішній effect;
- Product Truth, rights, claims, channel і human-release gates не обходяться;
- shadow graph перевершує або обґрунтовано дорівнює baseline за task success, evidence completeness, missed blockers, rework, latency, cost і reviewer load;
- terminal status має persisted receipt; session message не є доказом завершення.

## Метрики

Task success і evidence completeness проти baseline; false-narrow route rate; fan-in conflict/duplicate/missing rate; graph rounds і no-progress exits; context-state-loss rate; compaction recovery; duplicate-work rate; unsupported-host-intent rate; plan-before-mutation coverage; unreviewed-change rate; workspace collision; retry/recovery success; duplicate side effects; latency/cost per path; human-gate load; reviewer overturn; blocked publication/spend attempts.

## Блокери

Missing Product Truth/version/hash; невизначений route/owner; node без schema або verifier; edge без guard/failure route; parallel branch без independence proof; reducer без conflict/missing policy; context transition без checkpoint; unsupported host action без fallback; retry side effect без idempotency/effect receipt; author-only verification; missing human authority; graph без baseline comparison; runtime binding без fixtures.

## Межі доказовості

Документ визначає specification і acceptance boundary, але не доводить runtime implementation, provider availability, business lift або publication readiness. R01–R41 залишаються чинними semantic requirements; повне machine mapping, runner, schemas, fixtures і shadow results потребують окремої реалізації та перевірки. Framework або кількість agents не є доказом graph quality.

## Рішення щодо застосування

Застосовувати найменший graph, який робить routing, state, recovery, parallel merge, stopping і authority явними. Максимальна graph discipline означає повну типізацію переходів та доказів, а не максимальну кількість агентів.

