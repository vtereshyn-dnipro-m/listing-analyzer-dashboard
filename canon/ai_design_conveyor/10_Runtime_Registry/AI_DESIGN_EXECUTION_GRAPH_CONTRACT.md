# AI_DESIGN_EXECUTION_GRAPH_CONTRACT

Версия: `2.6`  
Статус: `ACTIVE_GRAPH_MODEL_CONTRACT`  
Дата вступления в силу: `2026-10-03`

## Призначення

Установить единую исполняемую модель AI Design как версионированного направленного графа. Контракт определяет сущности, полномочия, состояния и обязательные поля будущих Node Registry, Edge Registry, Run State, Artifact Lineage и graph runner.

Контракт не заменяет действующие инструкции агентов, Product Truth, Marketing Book, channel standards, handoff contracts или human release. Он определяет, как эти компоненты могут быть связаны и исполнены без скрытых переходов, потери состояния и повторения side effects.

## Область применения

Контракт применяется к маршруту:

`SKU Passport → Image Collector по условию → Passport media delta → Content TZ Agent → Image/Video Prompt Agent → AI Creator → Content Output QA → human final content acceptance`.

R01–R41 действующего AI Design Pipeline остаются нормативной картой условий. До создания и проверки Edge Registry они не считаются автоматически исполняемыми edges.

## Базовая архитектура

Система содержит два связанных, но не взаимозаменяемых графа.

### Execution Graph

Определяет:

- какое действие выполняется;
- кто является владельцем;
- при каких условиях разрешён переход;
- какой payload и receipt передаются;
- какие ошибки, повторы и человеческие решения допустимы;
- как остановить и возобновить запуск.

### Artifact and Evidence Lineage Graph

Определяет:

- какие источники и версии использованы;
- каким node создан или изменён artifact;
- какие требования и claims он подтверждает;
- какие downstream artifacts зависят от него;
- что становится stale при изменении upstream artifact;
- какие outputs требуют точечной пересборки.

Execution status не является evidence status. Наличие завершённого node не доказывает качество, factual correctness или publication readiness его результата.

### Control-plane parity for consequential edges

Кожен edge, який може спричинити write, provider cost, external transmission, publication, commercial action або зміну canonical state, повинен зберігати повний ланцюг:

`ACTION_PROPOSAL → POLICY_DECISION → EXACT_AUTHORITY → CONSTRAINED_EXECUTION_BROKER → AUTHORITATIVE_EFFECT_VERIFICATION`.

- `ACTION_PROPOSAL` описує typed action, resolved target, consequential parameters, source context і expected postcondition, але не надає authority.
- `POLICY_DECISION` повертає `ALLOW | DENY | APPROVAL_REQUIRED` для exact proposal і consequence tier.
- `EXACT_AUTHORITY` прив'язує actor, agent, approver/delegation, scope, target, limits, expiry і resource version.
- `CONSTRAINED_EXECUTION_BROKER` виконує лише sealed action через allowlisted adapter/tool без розширення scope.
- `AUTHORITATIVE_EFFECT_VERIFICATION` перевіряє business postcondition за authoritative source. Provider acknowledgement, HTTP 200 або наявність output file самі по собі не є `EFFECT_VERIFIED`.

Наслідковий рівень визначається для кожної action/data flow, а не для агента загалом:

| Tier | Meaning | Default control |
|---|---|---|
| `T0_OBSERVE` | Read-only observation without sensitive disclosure | source and identity receipt |
| `T1_DRAFT` | Draft that cannot change canonical or external state | bounded output and review owner |
| `T2_REVERSIBLE_INTERNAL` | Reversible internal write | policy allow, idempotency and read-back |
| `T3_HIGH_IMPACT_SENSITIVE` | External, cost-bearing, sensitive or high-impact action | exact authority and approval binding |
| `T4_CRITICAL_SYSTEMIC` | Publication, commercial, legal or production-critical systemic effect | named human authority and independent verification |

Inferred target, untrusted-content influence, cross-tenant/bulk/external scope, missing idempotency, missing authoritative verification or irreversible effect can only preserve or raise the tier. Model confidence, schema validity and prior success never lower it.

Approval for `T3`/`T4` is bound to a canonical action digest containing action/schema version, actor and agent identities, resolved target/resource, consequential parameters, policy/tier version, resource version, approver, expiry and one-time nonce. Any material change invalidates the approval and returns the edge to policy evaluation.

## Канонічні сутності

### Node

`Node` — одно ограниченное исполняемое действие или решение с одним владельцем ответственности и формальным input/output contract.

Node может:

- вызвать зарегистрированного агента;
- выполнить deterministic validation;
- запросить решение человека;
- выполнить разрешённое внешнее действие;
- объединить независимые branches по формальным правилам;
- сохранить checkpoint.

Стандарт, инструкция, schema, template, source или artifact сами по себе node не являются. Они регистрируются как зависимости или inputs node.

Один node не может одновременно создавать Product Truth, принимать собственный результат и разрешать публикацию.

### Edge

`Edge` — единственный разрешённый переход между двумя зарегистрированными nodes. Edge выполняется только при истинном guard, валидном payload и разрешённом authority scope.

Отсутствующий edge нельзя заменить импровизированной передачей в чате. Неизвестный маршрут получает `UNROUTABLE_CASE` и передаётся в `HUMAN_ROUTE_DECISION`.

### Run State

`ai_design_run_state` — единственный persisted control-state конкретного запуска. Чат, сообщение, память модели, имя папки или наличие файла не являются run state.

Run State содержит минимум:

- `run_id`, `graph_version`, exact SKU, variant, market, channel и locales;
- pinned Product Truth/Passport path, version и SHA-256;
- current node, completed, active, pending и blocked nodes;
- применённые и доступные edges;
- input/output artifact IDs и hashes;
- evidence gaps, conflicts и blockers;
- approvals с owner, scope, time и expiry;
- retry, round, cost и time budgets;
- side-effect ledger;
- latest checkpoint и resume cursor;
- terminal status и terminal receipt, если запуск завершён.

### Artifact

`Artifact` — неизменяемая версия файла или структурированного объекта, используемая либо созданная node.

Каждая версия artifact получает:

- `artifact_id` и `artifact_version`;
- artifact type и role;
- exact path или durable object reference;
- SHA-256 либо другой утверждённый content identity;
- creator node/run/invocation;
- parent artifact IDs;
- source/evidence bindings;
- status и verification status;
- created time и supersession relation.

Изменение содержимого создаёт новую artifact version. Имя файла без hash не определяет identity.

### Gate

`Gate` — deterministic или evidence-bounded проверка перехода, входа либо результата.

Schema validation, hash comparison, completeness, version freshness, frozen-manifest comparison и closed-enum policy check должны оставаться deterministic, если не требуют смыслового суждения.

Gate не повышает статус соседнего слоя. Например, schema `PASS` не означает output QA `PASS`, а `READY_FOR_QA` не означает publication readiness.

Provider admission є окремим gate для exact runtime fingerprint: adapter, provider/model, operation, media type і reference mode. Новий або змінений fingerprint проходить один `COMMISSIONING_SMOKE`; після фактичного output QA `PASS` він може отримати `PRODUCTION_ADMITTED`. У межах чинного bounded authority автоматичний batch продовжується по одному asset після кожного QA `PASS`. Людина залучається лише на configured checkpoint, exception або release; circuit breaker зупиняє batch при unknown provider outcome, identity drift, integrity failure, повторюваному дефекті, вичерпаному ліміті або зміні fingerprint.

QA defect до rework проходить deterministic `N223_DEFECT_SCOPE_CLASSIFICATION_GATE`. Локальний дефект блокує один asset, shared dependency — лише залежну групу, upstream defect повертається named owner, а identity/integrity/authority failure або повторюваний material defect відкриває batch circuit breaker.

Фактичне visual inspection у `N220` відділено від deterministic decision policy у `N221_CONTENT_OUTPUT_QA_POLICY_GATE`. П'ять QA-груп оцінюються незалежно; critical failure не компенсується середнім балом. Тільки final `PASS` для всіх mandatory assets і complete set дозволяє `CONTENT_PACKAGE_QA_PASS` та release review. Завершений негативний або `QA_INCONCLUSIVE` inspection передається через `E264` у `N221`; він не є технічно незавершеним. Технічна неможливість завершити inspection підпорядкована `AI_DESIGN_CONTENT_OUTPUT_QA_INSPECTION_EXIT_POLICY.md`: transient failure допускає лише bounded `E263` з новим attempt evidence і termination-budget receipt, а input defect або об'єктивно недоступний evidence передається через `E262` у `N224`. Вичерпання retry завершує run як `FAILED_EXHAUSTED` без повторної активації `N220`.

Run closeout у `N235` підпорядкований `AI_DESIGN_RUN_CLOSEOUT_EXIT_POLICY.md`. Successful verdict іде через `E290` до обов'язкового human final content acceptance, без platform transfer. Blocking verdict завжди створює Closeout Exception Package: changed evidence допускає лише bounded `E288` із termination-budget receipt, а unresolved/non-retriable blocker іде через `E287` у `N224`. Post-QA drift інвалідує попередній QA receipt; zero-progress або exhausted re-evaluation завершується `FAILED_EXHAUSTED`.

Усередині `N221` діє package-level `CONTENT_ORIGINALITY_AND_ADDED_VALUE_REVIEW`; нового node або edge не створюється. Перші три повні пакети проходять `SHADOW_VALIDATION_ONLY`: receipt обов'язковий, findings передаються в `E290`, але не блокують чинний QA pass. Після окремого owner decision режим `ENFORCED` вимагатиме `PACKAGE_ORIGINALITY_PASS` або `NOT_APPLICABLE`.

Provider-attempt policy окремо рахує technical retry, regeneration і local edit. Production дозволяє максимум два provider calls на asset: initial call і одну regeneration або підтверджений technical retry у межах окремого бюджету. Commissioning не дозволяє retry/regeneration; unknown outcome завжди потребує reconciliation.

Перед кожним новим provider side effect `N186_PRODUCTION_BATCH_BUDGET_GATE` перевіряє immutable run budget, usage ledger, recovery reserve, untouchable buffer, remaining time і terminal/reconciled status попереднього invocation. `BUDGET_HEALTHY` та `BUDGET_TIGHT` можуть відкрити лише exact next mandatory call; `BUDGET_EXHAUSTED` переводить run у `WAITING_BUDGET_DECISION`. Unknown cost або quota не трактуються як нуль чи unlimited: потрібен bounded call-count cap або versioned authority update без обнулення usage.

Будь-яке міжсесійне або аварійне відновлення проходить через `N250_TRANSITION_REENTRY_CHECKPOINT`. Gate звіряє exact run/SKU, checkpoint, graph, pinned artifacts, provider outcome, human decision та budget state. Clean state дає `RESUME_FROM_CHECKPOINT`; bounded artifact change — `TARGETED_REENTRY`; unknown provider outcome — `RECONCILIATION_REQUIRED`; SKU, Product Truth, incompatible graph або invalid checkpoint — `FULL_RESTART_REQUIRED`. Resume не повторює side effects і не обнуляє usage.

Production observability працює як неблокуючий sidecar до execution graph. Кожний значущий node transition формує compact event, з якого будується current Run Status Snapshot. `SLOW` запускає лише diagnostic warning, `STALLED` — recovery validation без повторення side effect, `WAITING_VALID` зберігає законний wait, а мертвий process із нетермінальним provider invocation дає `ORPHANED` і `RECONCILIATION_REQUIRED`. Успішний asset не блокується observability, якщо наявний мінімальний terminal receipt.

Безпосередньо перед provider execution `N189_EXECUTION_LEASE_AND_IDEMPOTENCY_GATE` отримує exclusive lease для exact `run + asset + operation + fingerprint + sealed record`. Active lease іншого worker блокує duplicate call; валідний terminal result переходить idempotent route до output recording без provider execution. Expired lease після `ACCEPTED | IN_FLIGHT | UNKNOWN` потребує reconciliation. Canonical output version активується атомарно лише після terminal receipt і hash validation; existing versions не перезаписуються.

Усі автоматичні переходи графа підпорядковані `AI_DESIGN_REWORK_BUDGET_AND_TERMINATION_CONTRACT.md`. Кожний non-human-wait edge витрачає щонайменше одну одиницю глобального бюджету й, коли застосовно, scoped budget для asset/package/fingerprint/re-entry/QA/reclassification/resume. Лічильники не обнуляються після checkpoint, migration або human resume. Вичерпання будь-якого applicable budget чи відсутність доказуваного прогресу завершує run як `FAILED_EXHAUSTED`; target node не активується. Human wait не входить до математичного доведення завершення автоматичної частини й не вважається автоматичним циклом.

Після package QA `N235_RUN_CLOSEOUT_GATE` звіряє immutable Final Deliverables Manifest із expected set, файлами/hashes, lineage, QA, leases, provider invocations, budget і checkpoint. Тільки `PRODUCTION_COMPLETE` або `COMPLETE_WITH_APPROVED_EXCLUSIONS` відкривають human final content acceptance. Partial valid assets зберігаються, але весь run не отримує `DONE`. Production closeout не дорівнює прийманню, ручному розміщенню або publication.

Active run залишається pinned до exact graph/contracts/schemas/adapters. Version Migration Gate дозволяє continue pinned, migration або rollback лише з valid checkpoint, без active leases/unresolved invocations і зі збереженням usage. Migration/rollback створюють нову revision; incompatible або unadmitted target блокується, а critical pinned-version defect вимагає emergency stop.

Нова версія отримує production admission лише через staged rollout: static validation, E2E shadow, compatibility, callable adapters, bounded one-run canary, QA/call/cost reconciliation і named-owner activation receipt. Critical incident переводить версію у `SUSPENDED`; local `PASS` не дозволяє global deployment або automatic scale.

Production incident створює immutable quarantine та blast-radius receipt. Quarantined outputs виключаються з reuse, closeout і release; `SEV3` має targeted rework, `SEV2` відкриває affected-scope circuit breaker, `SEV1` призупиняє version admission. Closure потребує containment, reconciliation, verified replacement і independent review.

Retention classification захищає canonical sources, final outputs, execution lineage, checkpoints і open-incident quarantine. Cleanup можливий лише після closeout і reconciliation, починається з dry run та recoverable archive move. Physical deletion потребує окремої authority і не виконується pipeline автоматично.

Capacity admission перед execution lease контролює global/media/provider/host slots, quota, storage, deadline, recovery reserve і bounded run quantum. `DISPATCH_READY` дозволяє лише запит lease; він не є provider authority. Backpressure не створює повторного submit, а cancellation після provider acceptance потребує reconciliation.

Production Readiness Gate агрегує static, E2E shadow, failure-injection, commissioning, canary і named-owner review. Local `PASS` не авторизує provider call; commissioning потребує окремої bounded authority, а publication не входить до readiness verdict.

### Receipt

`Receipt` — неизменяемое доказательство выполненного node, gate, handoff, approval, side effect или terminal outcome. Положительный переход разрешается только receipt, названным в edge contract.

### Checkpoint

`Checkpoint` — согласованный снимок Run State, artifact bindings и side-effect ledger, с которого разрешено безопасное продолжение.

Checkpoint не разрешает повторять уже подтверждённый non-idempotent side effect. Resume сначала выполняет reconciliation, затем выбирает edge.

## Классы nodes

| Класс | Назначение | Пример |
|---|---|---|
| `AGENT_NODE` | Ограниченное смысловое действие по действующей инструкции | Собиратель Паспорта, Content TZ Agent, Prompt Agent |
| `DETERMINISTIC_GATE_NODE` | Проверка schema, hash, completeness, manifest или closed rule | Prompt Package validator |
| `HUMAN_DECISION_NODE` | Решение, требующее named human owner | Разрешение затрат, `CONTINUE_BATCH`, release |
| `EXTERNAL_ACTION_NODE` | Tool/provider/platform action с side effect | Generation call, upload, publication |
| `REDUCER_NODE` | Формальное объединение независимых branch outputs | Fan-in research evidence |
| `CHECKPOINT_NODE` | Persist/reconcile состояния без изменения Product Truth | Transition and Re-entry checkpoint |

Создание нового класса требует новой версии этого контракта.

## Обязательный контракт Node Registry

Каждый node обязан содержать:

```yaml
node_id:
node_version:
node_class:
owner_role:
bounded_responsibility:
prohibited_actions: []
input_schema_refs: []
output_schema_refs: []
canonical_instruction_refs: []
required_artifact_types: []
allowed_tools: []
side_effect_class:
idempotency_policy:
timeout_policy:
retry_policy:
success_verdicts: []
block_verdicts: []
terminal_receipt_schema:
checkpoint_policy:
```

`bounded_responsibility` описывает одно действие. Если node требует двух независимых owners, двух разных approval boundaries или допускает частичное завершение одной из функций, его необходимо разделить.

## Обязательный контракт Edge Registry

Каждый edge обязан содержать:

```yaml
edge_id:
edge_version:
source_node_id:
target_node_id:
trigger:
guard_expression:
required_payload_schema:
required_source_receipts: []
receiver_acceptance_schema:
state_delta:
failure_route_ids: []
retry_route_id:
approval_requirement:
action_proposal_schema:
consequence_tier: T0_OBSERVE | T1_DRAFT | T2_REVERSIBLE_INTERNAL | T3_HIGH_IMPACT_SENSITIVE | T4_CRITICAL_SYSTEMIC
policy_decision_receipt:
authority_binding:
canonical_action_digest_expression:
execution_broker:
effect_verification_contract:
side_effect_precondition:
idempotency_key_expression:
upstream_hash_dependencies: []
invalidation_scope: []
resume_policy:
compensation_action:
```

Edge не создаёт новый business status. Он использует статусы, уже определённые source/target contracts или отдельным status registry.

## Стани Run State

Допустимые control states:

- `RUN_CREATED` — identity и graph version зафиксированы, исполнение не началось;
- `RUN_ACTIVE` — выполняется один или несколько разрешённых nodes;
- `WAITING_RECEIVER_ACCEPTANCE` — output создан, но следующий node ещё не принял handoff;
- `WAITING_HUMAN_DECISION` — отсутствует обязательное scoped решение владельца;
- `RUN_REWORK` — активирован зарегистрированный bounded correction loop;
- `RUN_BLOCKED` — нет разрешённого edge до изменения входных данных или внешнего состояния;
- `RUN_FAILED` — terminal technical/process failure по контракту;
- `RUN_CANCELLED` — запуск остановлен named owner;
- `RUN_COMPLETED` — выполнен определённый terminal node и создан terminal receipt.

`RUN_COMPLETED` не означает `PUBLISHED`, `COMMERCIAL_WIN` или Product Truth approval.

## Классы side effects

| Класс | Смысл | Минимальное управление |
|---|---|---|
| `READ_ONLY` | Чтение без изменения внешнего или локального состояния | Source/version receipt |
| `LOCAL_REVERSIBLE_WRITE` | Создание нового локального artifact без перезаписи канона | Path, hash, parent binding |
| `CANONICAL_WRITE` | Изменение канонического документа или registry | Writeback gate, owner scope, read-back |
| `EXTERNAL_READ` | Запрос внешнего сервиса без внешней записи | Tool/source receipt |
| `EXTERNAL_WRITE` | Изменение внешней системы | Explicit authority, idempotency, reconciliation |
| `COST_BEARING_ACTION` | Provider call или действие с расходом | Cost cap и явное разрешение |
| `PUBLICATION_ACTION` | Публикация или передача во внешний канал | Human release receipt |
| `COMMERCIAL_ACTION` | Spend, price, offer или иное коммерческое действие | Отдельная business authority |

Graph runner не может повысить side-effect authority на основании успешного предыдущего node.

Provider execution використовує окрему `provider_execution_policy`. `PAUSE_BEFORE_PROVIDER` створює одну контрольну зупинку `WAITING_PROVIDER_AUTHORITY`; `PREAUTHORIZED_BOUNDED` дозволяє one-asset invocations без повторного ручного підтвердження лише в межах allowlisted provider/model, call/cost/retry limits, строку дії та визначеного `output_root`. Capability, credentials, cost authority і sealed invocation перевіряються окремо. Вичерпання будь-якого ліміту зупиняє batch. Оновлення authority відновлює run у gate без повторного запуску upstream stages, якщо pinned hashes не змінилися. Жоден такий дозвіл не включає publication authority.

Після authority gate обов'язковий `Provider Adapter Resolution`. Він прив'язує asset до exact adapter ID/version та callable host entrypoint за свіжим capability snapshot. Зареєстрований image adapter не означає доступності video: за відсутності callable video tool runner повертає `VIDEO_ADAPTER_UNAVAILABLE` і не створює animated-still substitute. Лише `ADAPTER_RESOLVED_READY` відкриває один cost-bearing provider call.

## Правила маршрутизации

1. Разрешены только version-pinned nodes и edges активного graph manifest.
2. Router выбирает минимальный достаточный маршрут среди edges с истинными guards.
3. Низкая уверенность, неизвестный случай или конфликт guards не разрешают сокращённый маршрут: применяется broad safe route либо `HUMAN_ROUTE_DECISION`.
4. Receiver acceptance обязательна, если действующий handoff contract требует её. Создание output не равно принятию.
5. Product Truth изменяет только уполномоченный upstream route. Downstream nodes возвращают evidence/delta, а не переписывают Passport самостоятельно.
6. Publication, commercial action, credentials и внешний расход остаются human-controlled.
7. Агент не создаёт node, edge, status или exception во время выполнения.
8. Media reference admission не є окремим legal або production-acceptance node. Для generation route застосовуються `MEDIA_GENERATION_ASSESSMENT` і `TARGET_SOURCE_ROUTE_RECEIPT` v2: технічна якість, `RIGHTS_UNKNOWN`, watermark, сторонній logo/text, людина або фон задають transformation plan, але не блокують edge до Prompt Agent. Edge блокується лише при недостатньому Product Truth/target description, некласифікованому useful signal або неізольованому конфлікті з Product Truth.
9. `GENERATE_WITHOUT_MEDIA_REFERENCE` є валідним route без попереднього доказового відхилення reuse/edit/hybrid levels, якщо exact-SKU Product Truth і generation brief достатні.

### Content TZ Execution Input Routing node

Після `EXPECTED_DELIVERABLES_MANIFEST_FROZEN` і до Prompt Agent обов'язково виконується `N155_CONTENT_TZ_EXECUTION_INPUT_ROUTING`. Owner — `Content TZ Agent`; новий агент або human approval для штатного проходження не створюється.

Node приймає `SEMANTIC_SCOPE_FROZEN`, frozen expected manifest, exact-SKU Product Truth і active media registry. Для кожного `expected_asset_id` він створює `MEDIA_GENERATION_ASSESSMENT` bindings і рівно один `TARGET_SOURCE_ROUTE_RECEIPT` v2, перевіряє відсутність missing/duplicate routes та видає `EXECUTION_INPUTS_READY`. Після цього execution inputs отримують окремий стан `FROZEN`, який не змінює semantic scope.

Edge `E185_COMPILE_PROMPT_PACKAGE` виконується автоматично після schema-valid receiver receipt `PROMPT_INPUT_ACCEPTED` від Image/Video Prompt Agent. Receiver перевіряє лише completeness, hashes, Product Truth binding, route modes і preserve/regenerate boundaries; він не переобирає sources або semantics. `REJECTED` допускається лише з closed rejection class і affected `expected_asset_id`, після чого `E187_REWORK_EXECUTION_INPUTS` повертає bounded delta до `N155`. Human decision потрібне лише якщо для виправлення треба змінити Product Truth, semantic scope або frozen deliverable set.

### Launch mode та review checkpoint

Кожний content run має schema-valid `launch_control`:

```yaml
mode: CONTENT_TZ_ONLY | END_TO_END_GENERATION
human_review_checkpoint: REQUIRED | OPTIONAL | SKIP
terminal_target: CONTENT_TZ_READY | READY_CONTENT_PACKAGE
```

`EXTERNAL_TZ_DELIVERY` після accepted Content TZ переходить до `N147_EXTERNAL_CONTENT_TZ_EXPORT`, створює canonical-bound editable package і лише через E171 входить у terminal `N149_EXTERNAL_CONTENT_TZ_DELIVERY`. `INTERNAL_PIPELINE` після accepted Content TZ переходить до `N150`; `HUMAN_REVIEW_REQUIRED` перед цим маршрутизує через `N145_CONTENT_TZ_HUMAN_REVIEW`, тоді як `AUTO_CONTINUE` не створює human wait.

Завершений external-delivery run не розширюється до production. Майбутня генерація створює новий run і нове Content TZ з актуальних pinned inputs. Legacy-вузол N148 і переходи E172–E174 вилучені з активного execution graph; їхні історичні receipts читаються лише за pinned старою версією графа і не можуть відновити або продовжити новий run.

## Prompt Agent runtime resolution

Після `EXECUTION_INPUTS_READY` перехід до Prompt Agent проходить через `N158_AGENT_RUNTIME_RESOLUTION`. Gate окремо підтверджує node registration, canonical package, installed skill, exact hash parity, active adapter, callable entrypoint і admissible input. Наявність лише файла або запису в реєстрі не є доказом callability.

`AGENT_RESOLVED_READY` дозволяє `E185_COMPILE_PROMPT_PACKAGE`. `AGENT_RELOAD_REQUIRED` дозволяє рівно один `E184_RELOAD_AND_RERESOLVE_PROMPT_AGENT`; повторна невдача дає відновлюваний `AGENT_RUNTIME_BLOCKED` зі збереженням Content TZ, frozen manifest і execution inputs. Загальний статус `AGENT_NOT_FOUND` заборонений: blocker завжди класифікується як version mismatch, adapter unavailable, input inadmissible або runtime blocked.

## Fan-out и fan-in

Параллелизация разрешена только при общем immutable SKU snapshot и доказанной независимости branches.

Каждая branch получает:

- собственный `branch_id`;
- одинаковые pinned upstream hashes;
- отдельные output artifact IDs;
- запрет изменять общий parent artifact;
- terminal branch receipt.

Reducer:

- не применяет `last-writer-wins`;
- не усредняет factual conflicts;
- сохраняет disagreement и provenance;
- принимает только полный обязательный branch set либо explicit partial-completion decision;
- создаёт новый merged artifact, не изменяя branch outputs.

## Циклы и stop contracts

Каждый цикл определяется заранее и содержит:

- `loop_id`;
- entry и exit edges;
- `MAX_ROUNDS`;
- критерий meaningful improvement;
- retry/cost/time budget;
- allowed mutation scope;
- escalation route;
- terminal outcome при исчерпании бюджета.

Разрешённые классы циклов включают targeted TZ rework, prompt correction, production repair и evidence completion. Бесконечная самопроверка или повтор всей цепочки вместо bounded delta запрещены.

## Checkpoint, resume и recovery

Перед внешним side effect, fan-out, handoff и compaction создаётся checkpoint согласно применимому контракту.

Resume выполняет:

1. проверку graph version и checkpoint hash;
2. проверку текущих upstream artifact versions;
3. reconciliation side-effect ledger;
4. выявление stale downstream artifacts;
5. выбор зарегистрированного resume edge.

Если terminal receipt внешнего действия отсутствует, runner не предполагает ни успех, ни неуспех. Он сначала выполняет provider/platform reconciliation. Повторный call без idempotency proof запрещён.

## Версионирование и invalidation

Graph version фиксируется при создании run. Изменение Node Registry, Edge Registry, schema, canonical instruction или authority map не изменяет активный run молча.

Для каждого изменённого upstream artifact применяются `upstream_hash_dependencies` и `invalidation_scope`:

- незатронутые branches сохраняются;
- зависимые outputs получают `STALE_PENDING_REVALIDATION`;
- side effects не повторяются автоматически;
- точечная пересборка предпочтительнее полного rerun;
- переход на новую graph version требует migration/re-entry receipt.

## Ролі та відповідальність

- `Graph Owner` утверждает graph versions, nodes, edges и authority map.
- `Coordinator/Router` выбирает только разрешённые edges и сохраняет Run State.
- `Node Owner` отвечает за bounded action и terminal receipt.
- `Artifact Owner` отвечает за каноническую запись и versioning своего artifact class.
- `Reducer` объединяет branches без изменения factual conflicts.
- `Human Decision Owner` принимает только явно назначенное scoped решение.
- `QA` проверяет фактический output независимо от creator node.
- `Release Owner` отдельно разрешает publication/action; upstream PASS не заменяет это решение.

## Блокери

Execution блокируется при любом из условий:

- `NODE_NOT_REGISTERED`;
- `EDGE_NOT_REGISTERED`;
- `GRAPH_VERSION_MISMATCH`;
- `GUARD_UNRESOLVED`;
- `REQUIRED_PAYLOAD_INVALID`;
- `REQUIRED_RECEIPT_MISSING`;
- `RECEIVER_NOT_ACCEPTED`;
- `UPSTREAM_ARTIFACT_STALE`;
- `SIDE_EFFECT_AUTHORITY_MISSING`;
- `IDEMPOTENCY_UNPROVEN`;
- `CHECKPOINT_INVALID`;
- `UNROUTABLE_CASE`;
- `LOOP_BUDGET_EXHAUSTED`.

Blocker не должен маскироваться общим `NEEDS_REVIEW`. Он содержит owner, evidence, affected node/edge и допустимые recovery routes.

## Acceptance tests

Контракт считается реализованным в runtime только если:

1. каждый active component из `PIPELINE_COMPONENT_MANIFEST` связан хотя бы с одним node либо явно классифицирован как dependency-only;
2. каждый executable R01–R41 mapping имеет typed edge или explicit non-executable governance classification;
3. нет edge с незарегистрированным source/target node;
4. каждый side-effect node имеет authority, idempotency и recovery policy;
5. каждый loop имеет stop contract;
6. fan-in сохраняет conflicts и lineage;
7. Run State проходит schema validation и может быть восстановлен из checkpoint;
8. изменение upstream hash приводит только к заявленному invalidation scope;
9. неизвестный case fail-safe маршрутизируется к человеку;
10. shadow run не пропускает blocker, обязательный в действующем coordinator route.
11. кожен consequential edge має proposal, policy decision, exact authority, execution broker і authoritative effect-verification binding;
12. зміна target, amount/cost cap, recipient, scope, consequential parameter або resource version інвалідує попереднє approval;
13. authenticated, але unauthorized principal отримує deterministic `DENY`;
14. provider acknowledgement без authoritative postcondition не дає `EFFECT_VERIFIED`, а unknown outcome переходить у reconciliation;
15. untrusted-content influence або inferred target не можуть знизити consequence tier чи розширити authority.

## Режимы впровадження

- `GRAPH_SPEC_ONLY` — contracts и registries проверяются без исполнения nodes;
- `GRAPH_SHADOW_RUN` — graph принимает решения параллельно действующему маршруту без side effects;
- `CONTROLLED_RUNTIME` — разрешены только проверенные nodes/edges и scoped side effects;
- `PRODUCTION_RUNTIME` — отдельный release verdict после end-to-end evidence.

Переход между режимами требует отдельного versioned receipt. Наличие этого документа устанавливает только `GRAPH_SPEC_ONLY`.

## Межі доказовості

Контракт формализует модель execution graph. Node Registry, Core Edge Registry, Governance Route Mapping і Run State schema уже створені та структурно перевірені в `GRAPH_SPEC_ONLY`. Graph runner і runtime state-transition writer ще не створені. Наявність registries не підвищує readiness агентів, не запускає generation і не дозволяє external write, spend або publication.

Control-plane parity у версії 2.6 є normative registry contract, але parity чинних edges і runtime enforcement ще не доведені. Тому оновлення не змінює `GRAPH_SPEC_ONLY` на runtime admission і не надає нової authority.

Наступний проєктний крок після Run State — формалізація router decision contract і deterministic state-transition writer перед будь-яким shadow execution.

## Final media controls before human final content acceptance

Для final image/video перехід `Content Output QA → human final content acceptance` має обов'язкові exact-hash artifact controls без створення publication authority. Вони є source evidence для `E290_REQUEST_HUMAN_RELEASE` версії 2.0; edge ID збережено лише для сумісності.

AI Creator і Production Finishing документують actual operation lineage; Content Output QA перевіряє final media; Human Final Content Reviewer особисто приймає комплект, запитує формалізоване виправлення або відхиляє revision. Фактичне розміщення на площадці виконується людиною поза конвеєром. Старі pinned runs не отримують новий mandatory contract без recovery/re-entry decision.
