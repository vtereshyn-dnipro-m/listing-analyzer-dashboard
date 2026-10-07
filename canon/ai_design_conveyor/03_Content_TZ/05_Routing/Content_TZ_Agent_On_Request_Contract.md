# Content TZ Agent — On-Request Routing Contract

Версія: `1.6`  
Статус: `active_v1.6`  
Дата: 03.10.2026

## Призначення

Контракт визначає єдиний дозволений маршрут запуску Content TZ Agent через Агента-координатора AI Design. Агент працює лише за явним запитом користувача або уповноваженого власника задачі.

Canonical module routing читається лише з `content_tz_module_manifest.json`, а цілісність активних файлів — з `ACTIVE_PACKAGE.json`. Unknown signal або package integrity mismatch дає fail-closed verdict і не переходить у `CORE_ONLY`.

## Область застосування

Контракт діє для створення, оновлення або повторної перевірки Content TZ та для запуску повного content-generation cycle для точного SKU/версії, ринку, мови, каналу та deliverable. Він не змінює маршрут Паспорта SKU за 00A. `END_TO_END_GENERATION` дозволяє внутрішні downstream transitions, але не дає publication authority, не скасовує provider/cost preflight і не дозволяє canonical Product Truth writeback.

## Trigger

Дозволений trigger:

```yaml
content_tz_request:
  requested_action: CREATE_CONTENT_TZ | UPDATE_CONTENT_TZ | RECHECK_CONTENT_TZ | CREATE_CONTENT_PIPELINE | EXPAND_RUN_SCOPE
  launch_control:
    mode: CONTENT_TZ_ONLY | END_TO_END_GENERATION
    human_review_checkpoint: REQUIRED | OPTIONAL | SKIP
    terminal_target: CONTENT_TZ_READY | READY_CONTENT_PACKAGE
    authority_ref:
  request_source: USER | AUTHORIZED_TASK_OWNER
  request_text_ref:
  requested_at:
  sku_id:
  exact_model_revision:
  marketplace:
  country:
  language:
  channel:
  requested_deliverable:
  requested_content_types: []
  existing_tz_ref:
  product_root:
  output_path:
  coordinator_identity: AI_DESIGN_COORDINATOR
  product_registry_ref:
  product_registry_sha256:
  marketplace_profile_id:
  marketplace_registry_ref:
  marketplace_registry_sha256:
  marketplace_requirement_receipt_ref:
  amazon_content_method_registry_ref:
  amazon_content_method_registry_sha256:
  amazon_content_method_receipt_ref:
  passport:
    path_or_id:
    revision:
    sha256:
    verification_status: READY | READY_WITH_LIMITATIONS
    sufficient_for_deliverable: true | false
    fact_evidence_locators: []
  context:
    profile: CONTENT_TZ
    contract_version: active_v1.6
    receipt_status: PASS | FAIL
  session:
    required: true | false
    session_passport_ref:
    inbound_handoff_status: ACCEPTED | REJECTED | PENDING
  rights_status: PASS | BLOCKED
  safety_status: PASS | BLOCKED
```

Запит має бути явним за сенсом. `Створи Content TZ` за замовчуванням означає `CONTENT_TZ_ONLY`. Команда `Запусти конвеєр створення контенту` означає `END_TO_END_GENERATION`, `terminal_target: READY_CONTENT_PACKAGE` і `human_review_checkpoint: OPTIONAL`, якщо користувач не вимагає обов'язкової зупинки або прямо не наказує її пропустити. `EXPAND_RUN_SCOPE` дозволений лише за новою явною командою продовжити вже завершений `CONTENT_TZ_ONLY` run.

### Заборонені автоматичні triggers

Content TZ Agent не запускається автоматично після:

- `PASSPORT_READY`, `READY_WITH_LIMITATIONS` або іншого стану Паспорта;
- завершення Image Collector;
- появи нового джерела, audit finding, experiment result або learning candidate;
- завершення попереднього етапу конвеєра;
- внутрішньої рекомендації іншого агента.

У цих випадках Координатор фіксує `CONTENT_TZ_NOT_REQUESTED/NO_RUN`.

## Вхідний контракт

До запуску Координатор перевіряє:

1. Заповнений `content_tz_request` з дозволеним `requested_action`.
2. Exact SKU/model revision, marketplace/country, language, channel і deliverable.
3. Єдиний канонічний Паспорт SKU з version, SHA-256, verification state і fact/evidence locators, достатніми для requested deliverable.
4. `CONTEXT_ASSEMBLY_CONTRACT.md` зі статусом `active_v1.1`, profile `CONTENT_TZ` і `context_contract_receipt=PASS`.
5. Застосовні версії Marketing Book, channel requirements, claims, rights і safety constraints.
6. `session_passport` та accepted inbound `session_handoff_receipt`, якщо запуск є частиною керованої багатоагентної сесії.
7. `coordinator_identity=AI_DESIGN_COORDINATOR`, output path усередині exact `product_root`, Passport SHA-256 та чинний canonical module manifest.
8. Owner-controlled product registry із pinned SHA-256 зв’язує exact SKU/revision із canonical product root, Passport path/revision/SHA та дозволеними fact/evidence locators. Registry і Passport bytes перевіряються фактично; довільний існуючий каталог не є product root.
9. Для marketplace deliverable агент резолвить active `marketplace_requirements_registry.json` для exact marketplace/country/language/content types. Якщо exact locale profile відсутній або неповний, receipt повертає `LOCALE_REQUIREMENTS_PENDING/BASE_TZ_ONLY`: базове Content TZ за verified Passport продовжується, але locale compliance appendix і publication-ready package блокуються до верифікації правил.
10. Amazon method registry та SKU-scoped method evidence обов'язкові лише для явно запитаного search/competitive/SEO/listing-optimization scope або підтвердженого trigger. Відсутність live main image, SERP, reviews/Q&A чи competitor evidence не блокує базове Content TZ; блокується лише відповідний optional method output.
11. Semantic review receipt не є статичним файлом пакета агента. Після формування output незалежний Reviewer створює новий registry за `semantic_review_receipt_registry_schema.json` усередині exact `product_root`. Кожен receipt прив'язується до exact SKU/revision, `request_id`, `run_id`, output ID/content SHA-256 та SHA-256 канонічно resolved evidence bundle.
12. Координатор формує окремий trusted binding за `coordinator_semantic_review_binding_schema.json` у своєму control plane, а не всередині producer payload. Binding містить expected context, bytes/hash accepted route receipt, owner product registry, канонічний media registry, byte-resolved Passport, `requested_asset_types`, зовнішній Passport value-signal inventory, незалежний value-synthesis stage receipt та value-delivery review receipt exact SKU/revision/request/run. Validator парсить accepted route і вимагає точного збігу requested formats; парсить Passport і вимагає exact `product_truth`; читає bytes та перераховує SHA-256 усіх control files. Delivery receipt фіксує coverage matrix і value-bearing shot/scene content, тому збереження ID із підміною змісту не проходить. Final validator отримує binding окремим аргументом `--coordinator-review-binding`, а його очікуваний canonical SHA-256 — другим незалежним аргументом `--coordinator-binding-sha256` з trusted Coordinator channel.

Відсутній явний запит дає `CONTENT_TZ_NOT_REQUESTED/NO_RUN`. Відсутній або недостатній Product Truth дає `CONTENT_TZ_INPUT_BLOCKED/BLOCKED` і повернення в контур SKU. Missing/stale profile, schema або required triggered module дає `BLOCKED_CONTEXT`.

## Правила виконання

1. Координатор створює лише route record і запускає Content TZ Agent за канонічною інструкцією. Він не створює ТЗ самостійно.
2. Content TZ Agent читає pinned inputs і без проміжного user approval формує Product Value Synthesis candidate package: core value proposition, повний inventory, value candidates з disposition та P0/P1/P2 pillars. Незалежний value Reviewer випускає `PRODUCT_VALUE_SYNTHESIS_ACCEPTED` receipt. Лише після його перевірки агент створює primary-angle rationale, value coverage matrix, сценарій, shot list/scene list, вимоги та acceptance criteria.
3. Агент завершує всі author edits, перераховує хеші з фінальних bytes і запускає `07_QA_Tools/validate_author_preflight.py` для exact `agent-output`: спочатку `--phase SYNTHESIS`, а перед Value Delivery Review — `--phase VALUE_DELIVERY`. Лише `AUTHOR_PREFLIGHT_PASS` дозволяє handoff відповідному Reviewer. Receipt зберігається в exact `product_root`; `REWORK` повертає роботу тому самому Content TZ Agent без запуску independent review.
4. Агент виконує інші applicable QA самого ТЗ і готує outbound receipt. Незалежне погодження виконує downstream Reviewer після створення ТЗ; `AUTHOR_PREFLIGHT_PASS` не є self-approval і не замінює semantic acceptance. Після freeze expected deliverables Content TZ Agent як owner `N155_CONTENT_TZ_EXECUTION_INPUT_ROUTING` оцінює useful media signals і створює execution routes; Prompt Agent лише приймає та компілює їх.
5. Запит на оновлення не змінює чинну версію ТЗ до успішного QA та read-back; попередня версія зберігається.
6. Для `CONTENT_TZ_ONLY` завершення Content TZ створює `STOP_CONTENT_TZ_READY` і не запускає Prompt Agent або Creator. Для `END_TO_END_GENERATION` після applicable human-review checkpoint внутрішній маршрут автоматично продовжується через expected deliverables, execution-input routing, Prompt Agent, Creator preflight, дозволений provider execution і QA до `READY_CONTENT_PACKAGE`. Publication завжди залишається окремим approval.
7. `human_review_checkpoint` незалежний від `mode`: `REQUIRED` зупиняє run до named owner decision; `OPTIONAL` показує ТЗ без блокувальної паузи; `SKIP` одразу продовжує після внутрішнього acceptance.
8. `EXPAND_RUN_SCOPE` завжди запускає `RUN_SCOPE_RECONCILIATION`: перевіряються Passport/Product Truth, Content TZ, expected manifest, downstream modules, checkpoint і side effects. Current artifacts повторно не створюються; stale dependencies отримують bounded rework.

## Ролі та відповідальність

- Координатор: trigger validation, pinned versions, route record, launch, handoff visibility.
- Content TZ Agent: режисерсько-сценарний аналіз, Product Value Synthesis Gate, traceable brief, product-value narrative, shot/storyboard specification, requirements, acceptance criteria та outbound package.
- Content TZ Semantic Reviewer: незалежна змістовна перевірка output проти resolved evidence та випуск SKU/run-bound receipt.
- SKU/Product Truth roles: verification і update фактів.
- Downstream Reviewer/authorized owner: перевірка та погодження вже створеного ТЗ.
- Downstream receiver: незалежний read-back і handoff receipt.

## Стани та вердикти

- `CONTENT_TZ_NOT_REQUESTED/NO_RUN`: explicit request відсутній; агент не запускається.
- `CONTENT_TZ_INPUT_BLOCKED/BLOCKED`: requested run не має достатнього verified input.
- `BLOCKED_CONTEXT`: required contract/schema/module missing or stale.
- `CONTENT_TZ_IN_PROGRESS`: профільний агент виконує requested action.
- `CONTENT_TZ_REVIEW_REQUIRED`: ТЗ створено й передано на незалежну downstream перевірку.
- `CONTENT_TZ_READY_FOR_HANDOFF`: requested outputs пройшли applicable QA і готові до receiver read-back.
- `CONTENT_TZ_REJECTED`: receiver повернув package за дозволеним `SESSION_HANDOFF_RECEIPT` verdict.
- `STOP_CONTENT_TZ_READY`: terminal target `CONTENT_TZ_READY` досягнуто; downstream не запущено, checkpoint дозволяє лише explicit scope expansion.
- `RUN_SCOPE_RECONCILIATION`: явне розширення з `CONTENT_TZ_ONLY` до `END_TO_END_GENERATION` проходить freshness/readiness reconciliation.
- `READY_CONTENT_PACKAGE`: усі очікувані outputs створені, збережені та пройшли applicable production QA; publication authority не надано.

## Вихідний контракт

```yaml
content_tz_run_receipt:
  contract_version: "1.6"
  request_ref:
  requested_action:
  launch_control:
    mode:
    human_review_checkpoint:
    terminal_target:
    authority_ref:
  session_id:
  sku_id:
  exact_model_revision:
  marketplace:
  country:
  language:
  channel:
  product_root:
  agent_package_version:
  instruction_path:
  instruction_sha256:
  product_truth_ref:
    path_or_id:
    revision:
    sha256:
    verification_status:
  context_contract_receipt_ref:
  marketing_book_refs: []
  loaded_module_refs: []
  marketplace_requirement_receipt_ref:
  amazon_content_method_receipt_ref:
  semantic_review_context:
    receipt_registry_ref:
    receipt_registry_sha256:
    request_id:
    run_id:
    coordinator_binding_ref:
    coordinator_binding_sha256:
  output_refs: []
  qa_receipts: []
  open_gap_ids: []
  prohibited_inferences: []
  status: CONTENT_TZ_INPUT_BLOCKED | BLOCKED_CONTEXT | CONTENT_TZ_IN_PROGRESS | CONTENT_TZ_REVIEW_REQUIRED | CONTENT_TZ_READY_FOR_HANDOFF | CONTENT_TZ_REJECTED | STOP_CONTENT_TZ_READY | RUN_SCOPE_RECONCILIATION | READY_CONTENT_PACKAGE
  next_route: STOP | RETURN_TO_SKU | HANDOFF_TO_REVIEWER | HANDOFF_TO_REQUESTED_RECEIVER | EXECUTION_INPUT_ROUTING | RUN_SCOPE_RECONCILIATION
  publication_authority: NOT_GRANTED
```

## Acceptance tests

1. Без explicit request маршрут дає `CONTENT_TZ_NOT_REQUESTED/NO_RUN` і не запускає агента.
2. `PASSPORT_READY` без explicit request не запускає Content TZ Agent.
3. Explicit request за відсутнього/недостатнього Product Truth дає `CONTENT_TZ_INPUT_BLOCKED/BLOCKED`.
4. Valid explicit request з pinned inputs запускає лише Content TZ Agent із `requested_action` із контракту.
5. Агент не створює новий Product Truth, claim approval, prompt, asset або publication decision.
6. Результат має exact SKU/version, input/output hashes, QA receipts, gaps і `publication_authority: NOT_GRANTED`.
7. `CONTENT_TZ_ONLY` завершується `STOP_CONTENT_TZ_READY`; Prompt Agent і Creator не запускаються.
8. `END_TO_END_GENERATION` після applicable review автоматично переходить до expected deliverables та execution-input routing без повторного user confirmation.
9. `REQUIRED` review зупиняє run, `OPTIONAL` не блокує, `SKIP` не створює human-decision node.
10. `EXPAND_RUN_SCOPE` без reconciliation заборонений; current Content TZ не створюється повторно.
11. Provider cost authority і publication approval не виводяться з `END_TO_END_GENERATION` автоматично.
8. Marketplace receipt керує лише channel-specific appendix: чужий locale/content type забороняє compliance claim, але не видаляє базовий сценарій і shot/storyboard за Product Truth.
9. Amazon method receipt вимагається лише для activated search/competitive/SEO/listing-optimization method blocks; його відсутність не блокує базове Content TZ.
10. Після створення ТЗ downstream Reviewer випускає semantic receipt. Відсутність цього receipt означає `CONTENT_TZ_REVIEW_REQUIRED`, а не заборону агенту створити ТЗ.
11. Handoff Product Value Reviewer без `AUTHOR_PREFLIGHT_PASS` для `SYNTHESIS` повертає `AUTHOR_PREFLIGHT_REQUIRED`; handoff Value Delivery Reviewer без `AUTHOR_PREFLIGHT_PASS` для `VALUE_DELIVERY` повертає той самий verdict.
12. Author preflight відхиляє stale inventory hash, односторонні signal/candidate bindings, noncanonical enums, stale stage text, hash mismatch reviewed subjects і locale blocker, який помилково блокує `BASE_TZ_ONLY`.

## Блокери

Глобально блокують тільки: missing explicit request/ref; unknown SKU/version; insufficient or stale Product Truth; invalid Passport SHA-256; unresolved source conflict, що заважає описати товар; blocked safety; missing/stale context profile; unaccepted required session handoff; wrong Coordinator identity; unknown routing signal; невідповідність `ACTIVE_PACKAGE.json`; missing required base schema; output path outside exact `product_root`. Marketplace registry/locale/category gaps дають `LOCALE_REQUIREMENTS_PENDING/BASE_TZ_ONLY` і блокують лише locale compliance appendix та publication-ready package. Amazon method registry/input/evidence gaps блокують лише явно activated optional method block. Downstream semantic receipt відсутній до створення ТЗ за визначенням і не є precondition.

## Межі доказовості

Валідний route receipt доводить, що запуск був дозволений і прив'язаний до pinned inputs. Він не доводить семантичну якість ТЗ, роботу зовнішніх інструментів, publication readiness або business lift.
