# AI Design Run State

## Призначення

`ai_design_run_state` є єдиним persisted control-state конкретного запуску AI Design. Він замінює неформальне відновлення за історією чату, назвами папок або припущенням, що наявний файл уже прийнятий наступним етапом.

## Область застосування

Окремий Run State створюється для кожного exact product/SKU, variant, market, channel і locale set. Змішування двох продуктів або двох незалежних production scopes в одному state заборонено.

`ai_design_run_state.spec_fixture.json` існує лише для structural validation у `GRAPH_SPEC_ONLY`. Це не реальний запуск і не джерело Product Truth.

## Вхідні дані

Перед створенням live state потрібні:

- абсолютний `product_root`;
- exact SKU, model, variant, market, channel і locales;
- pinned graph contract, Node Registry, Edge Registry і Governance Mapping з SHA-256;
- pinned Passport/Product Truth path, version, SHA-256 і readiness status;
- затверджені retry, round, cost і time budgets.

## Правила виконання

1. Run State змінює лише Coordinator/Router після валідного edge transition або спеціалізований checkpoint node.
2. Усі registered nodes належать рівно одному bucket: completed, active, pending, blocked або not applicable.
3. Усі registered edges належать рівно одному bucket: applied, available, rejected або unevaluated.
4. `current_node_id` завжди входить до `active_node_ids`.
5. `OPEN` blocker вимагає `RUN_BLOCKED`; узагальнений `NEEDS_REVIEW` не дозволено.
6. Product artifacts повинні перебувати всередині exact `product_root`, мати content hash, creator node/run та provenance.
7. External side effect записується до ledger з authority, idempotency key, invocation ID, status і terminal receipt. Відсутній terminal receipt не дозволяє припускати результат.
8. Cost-bearing provider execution вимагає окремої `provider_execution_policy`: без неї run зупиняється у `WAITING_PROVIDER_AUTHORITY`; `PREAUTHORIZED_BOUNDED` діє лише в allowlist, call/cost/retry limits і строках authority.
9. Оновлена bounded authority може відновити run без повторного запуску незмінених Паспорта, Content TZ і Prompt Package; їхні pinned hashes мають залишатися чинними.
10. Generation authority не є publication authority: release залишається окремим human decision.
11. Перед provider execution Run State зберігає adapter-resolution receipt з exact registry hash, adapter ID/version, entrypoint, host capability binding і zero-side-effect verdict.
12. Зміна adapter availability повертає run тільки до `N187_PROVIDER_ADAPTER_RESOLUTION`; незмінені upstream content artifacts не перегенеровуються.
13. Run State зберігає exact provider fingerprint, admission status і receipt. `COMMISSIONING_REQUIRED` дозволяє не більше одного smoke call; `PRODUCTION_ADMITTED` діє лише для незміненого fingerprint і чинного bounded authority.
14. Після кожного asset QA `PASS` автоматичне продовження не потребує людського рішення, якщо наступний asset належить frozen manifest, усі ліміти чинні й circuit breaker закритий.
15. Unknown provider outcome, identity drift, integrity failure, повторюваний дефект, вичерпаний limit або fingerprint drift відкривають circuit breaker та забороняють наступний provider call.
16. Для кожного asset Run State окремо зберігає `provider_calls_used`, `technical_retries_used`, `regenerations_used` і `local_edits_used`.
17. Production limits: максимум один technical retry, одна regeneration, дві local edits і два provider calls на asset без human decision. Commissioning limits: retry `0`, regeneration `0`.
18. Run state зберігає versioned production budget: mode, primary allocation, recovery reserve, untouchable buffer, usage counters і zone `BUDGET_HEALTHY | BUDGET_TIGHT | BUDGET_EXHAUSTED`. Budget update не обнуляє usage; exhausted budget встановлює `WAITING_BUDGET_DECISION` до наступного side effect.
19. Resume дозволено лише через recovery receipt, bound до exact checkpoint/run/SKU/graph. `UNKNOWN | IN_FLIGHT` invocation не можна повторювати; bounded artifact change створює targeted re-entry, а зміна SKU/Product Truth або incompatible graph вимагає full restart.
20. Operational snapshot зберігає current node/asset, last checkpoint/progress, blocker, provider invocation state, budget zone, next action та owner. Observability є неблокуючим: `SLOW` не запускає retry, `STALLED` передає у recovery validation, `ORPHANED` — у reconciliation.
21. Side-effect ledger зберігає execution lease binding, owner, expiry, idempotency key та invocation state. Один exact asset/operation має не більше одного active lease; expired lease після provider acceptance не перевидається без reconciliation.
22. Run отримує production-complete state лише за immutable closeout receipt. `PARTIAL_OUTPUT_BLOCKED` зберігає всі QA-passed assets; `CLOSEOUT_RECONCILIATION_REQUIRED` не допускає human final content acceptance до закриття leases, invocations і budget ledger.
23. Graph migration або rollback створюють нову run revision із old/new version bindings та exact invalidation scope; usage, receipts і side-effect ledger не обнуляються.
24. Новий run може pin лише `PRODUCTION_ADMITTED` version із rollout registry. Canary version обмежена exact test run і не може автоматично масштабуватися або мігрувати active runs.
25. Incident state зберігає class, severity, quarantined assets, blast radius, containment, reconciliation і closure receipts. `QUARANTINED` artifact не може бути reused, included in closeout або released.
26. Retention state зберігає data class, hold, canonical-copy verification, archive path/hash і cleanup disposition. Physical deletion не є автоматичною дією run.
27. Queue state зберігає job priority, deadline, required fingerprint/adapter, capacity reservation, run quantum та invocation state. Execution lease запитується лише після `DISPATCH_READY`.
28. Readiness state окремо фіксує static, shadow, failure-injection, commissioning, canary та production-review evidence. `PRODUCTION_READY` не дорівнює provider-call або publication authority.
18. `UNKNOWN` provider outcome не витрачає новий attempt автоматично та блокує повтор до terminal reconciliation.
9. Resume можливий лише з валідного checkpoint, сумісної graph version та reconciliation side effects.
10. Кожний content run має immutable `launch_control`: `CONTENT_TZ_ONLY | END_TO_END_GENERATION`, незалежний `human_review_checkpoint` і відповідний `terminal_target`.
11. Зміна `CONTENT_TZ_ONLY → END_TO_END_GENERATION` у межах завершеного run заборонена. Для генерації створюється нова revision або новий run із новим Content TZ та актуальними pinned inputs.
10. Зміна pinned graph або Product Truth не переписує state мовчки: потрібні invalidation та migration/re-entry receipt. `graph_version` є окремою compatibility version і не дорівнює file-baseline ID; documentation-only baseline не змушує мігрувати активний run.

## Стани

- `RUN_ACTIVE` — виконується зареєстрований node;
- `WAITING_RECEIVER_ACCEPTANCE` — handoff очікує приймання;
- `WAITING_HUMAN_DECISION` — очікується named human decision;
- `RUN_REWORK` — виконується bounded correction loop;
- `RUN_BLOCKED` — існує відкритий blocker із owner та recovery route;
- `RUN_COMPLETED` — terminal receipt зафіксовано.

Terminal status окремо фіксує `NOT_TERMINAL`, `COMPLETED`, `CANCELLED` або `FAILED_EXHAUSTED`. `RUN_COMPLETED` не означає publication або marketplace upload.

## Acceptance tests

```powershell
& "C:\Users\ystep\Documents\DM AMAZON\AI Design Conveyor\10_Runtime_Registry\Test-AIDesignRunState.ps1" -RunStatePath "<absolute path to run state.json>"
```

Validator перевіряє JSON Schema, повний node/edge partition, registry references, pinned graph hashes, product-root boundary, Product Truth identity, lifecycle/blocker/terminal consistency, budgets, side-effect authority, checkpoint і resume cursor.

## Блокери

Live state не приймається при missing/changed Product Truth, graph hash drift, невідомому node/edge, неповному partition, artifact поза `product_root`, cost overrun, side effect без authority/idempotency/receipt або resume без валідного checkpoint.

## Межі доказовості

Schema і validator доводять цілісність state record, але не виконують nodes, не оцінюють семантичну якість контенту і не надають generation, publication або commercial authority.

