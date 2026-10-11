# Handoff для реалізації інтеграції Listing Suite → Паспорт SKU

Версія: 1.2  
Дата: 04.10.2026  
Статус: `READY_FOR_IMPLEMENTATION`  
Тип: ненормативний implementation guide; правила визначають канонічні контракти.

## Призначення

Дати команді реалізації однозначну карту точок входу, виходу, перевірок і меж відповідальності. Документ не задає HTTP URL, технологію черги, мову програмування або структуру бази даних: transport і deployment належать окремому програмному проєкту.

## Канонічні залежності

Перед реалізацією зафіксувати version і SHA-256:

1. `00A_Контракт_передач_Паспорта_SKU.md` v2.13 — маршрути, стани й дозволені результати.
2. `Listing_Suite_Integration_Contract.md` v1.1 — межа UI та конвеєра.
3. `listing_suite_passport_action_request.schema.json` — запит дії.
4. `listing_suite_passport_action_receipt.schema.json` — єдина відповідь Listing Suite.
5. `passport_recreate_archive_receipt.schema.json` — архівний receipt.
6. `passport_recreate_transaction_receipt.schema.json` — транзакція recreate.
7. `00_Агент_координатор_конвейера_Паспорта_SKU.md` v2.7 — orchestration rules.
8. `Listing_Suite_Source_Intake_Policy.md` v1.0 — file/folder intake і deployment profile.
9. `Listing_Suite_UI_Message_Mapping.md` v1.0 — result/reason → UI state/action.
10. `fixtures/listing_suite/fixture_manifest.json` v2.0 — executable positive, schema-negative і contract-negative examples.
11. `listing_suite_source_intake_profile.schema.json` і `listing_suite_source_intake_receipt.schema.json` — machine-readable folder intake boundary.
12. `listing_suite_recreate_confirmation_receipt.schema.json` — TTL та lifecycle окремого confirmation.
13. `listing_suite_passport_status_query.schema.json` і `listing_suite_passport_status_response.schema.json` — read-only lookup без mutation authority.
14. `listing_suite_deployment_manifest.schema.json` і `listing_suite_feature_activation_receipt.schema.json` — deployment binding та контрольований feature activation.
15. `listing_suite_passport_restore_request.schema.json` і `listing_suite_passport_restore_receipt.schema.json` — admin-only post-commit restore.
16. `Listing_Suite_Archive_Retention_Policy.md`, `Listing_Suite_Archive_Retention_Profile_v1.0.json`, legal-hold та retention evaluation/boundary schemas — погоджений 1095-day immutable archive lifecycle без deletion authority.
17. `Listing_Suite_Authority_Mapping_Contract.md`, authority profile/evaluation schemas і production-candidate profile — canonical RBAC; реальні IdP bindings ще обов'язково додати.
18. `Listing_Suite_Localization_Contract.md`, locale profile, message catalog і resolution receipt schema — `uk-UA`/`ru-RU` із fallback `uk-UA`; `en-US` planned.
17. `Listing_Suite_Configuration_Decision_Register.md` — owner-controlled values, без яких відповідні flags залишаються `OFF`.

Зміна version або SHA залежності вимагає повторного contract test. Відкритий run завершується за власним збереженим snapshot.

## Межа систем

```text
Listing Suite UI
  → source intake adapter
  → schema / authority / idempotency checks
  → Координатор Паспорта SKU
  → профільний route
  → control receipt
  → receipt mapper
  → Listing Suite UI
```

UI не звертається безпосередньо до Собирателя, Аудитора або Верифікатора. Adapter не змінює Product Truth, не перемикає canonical pointer і не тлумачить результати агентів.

## Точки входу

### 1. Реєстрація окремих файлів

Вхід: файли, явно вибрані користувачем для exact SKU. Вихід: frozen `source_inventory` з `source_artifact_id`, type, original locator, archived locator, SHA-256 і access result для кожного об'єкта.

Коментар реалізатору: спочатку скопіювати прийнятий файл до `product_root/артефакти/YYYY-MM-DD/`, виконати read-back і лише потім включати його до request. Опис користувача є context, а не продуктовим фактом.

### 2. `SELECT_FOLDER_SNAPSHOT`

Це intake entry point, а не `requested_action` агента. Він створює одноразовий рекурсивний inventory за versioned intake policy. Заборонено обходити symlink, shortcut або junction, підписуватися на майбутні зміни папки чи розширювати права користувача.

Коментар реалізатору: transport name може відрізнятися, але `SELECT_FOLDER_SNAPSHOT` залишається audit token. Якщо прийнято нуль об'єктів, action request не створюється.

### 3. `SUBMIT_SOURCE_EVIDENCE_DELTA`

Вхід: schema-valid JSON, exact current Passport snapshot і щонайменше один accepted або exact-duplicate source object. Координатор перетворює action тільки на `source_evidence_delta`. Terminal UI output — один receipt за `listing_suite_passport_action_receipt.schema.json`.

Коментар реалізатору: прийняття запиту не означає зміну Паспорта. Не показувати `PASSPORT_UPDATED`, доки new version/SHA не пройшли read-back.

### 4. Підтвердження recreate

Перший вхід фіксує `RECREATE_INTENT_CONFIRMED`, другий — `RECREATE_SNAPSHOT_CONFIRMED`. Обидва належать одному actor і `recreate_request_id`, містять однакові Passport version/SHA та діють 15 хвилин.

Коментар реалізатору: confirmation не створює run і не захоплює mutation lock. Після зміни current version/SHA обидва підтвердження непридатні.

### 5. `RECREATE_PASSPORT`

Вхід: schema-valid request, два чинні confirmations, frozen inventory, recreate reason і authority `PASSPORT_ADMIN` або `PRODUCT_OWNER_WITH_RECREATE_AUTHORITY`. Route — тільки `passport_recreate`. Виходи: control receipt, archive receipt і transaction receipt.

Коментар реалізатору: UI не виконує архівування. Координатор керує preflight, lock, staging, read-back та atomic switch. До switch старий Паспорт залишається єдиним active canonical object.

### 6. Read-only status lookup

Допускається read-only query за `request_id`, `operation_id` або `idempotency_key` для повторного показу вже створеного receipt. Це не mutation action і не може відновлювати, повторювати або продовжувати route.

Query відповідає `listing_suite_passport_status_query.schema.json` і містить рівно один lookup identifier. Response відповідає `listing_suite_passport_status_response.schema.json`, має `mutation_authority=NONE` та `replayed_from_storage=true`.

Коментар реалізатору: конкретний endpoint визначає програмний проєкт. Query повертає збережений receipt без переобчислення.

## Точки виходу

Evidence delta повертає лише `NO_PASSPORT_CHANGE`, `PASSPORT_UPDATED`, `DECISION_REQUIRED`, `WRONG_SKU_OR_SCOPE`, `STANDARDS_MATERIAL_ROUTED` або `REQUEST_REJECTED`.

Recreate повертає лише:

- `RECREATE_ACCEPTED` — запит прийнятий, switch ще не виконаний;
- `RECREATE_IN_PROGRESS` — для SKU вже є активна recreate operation;
- `RECREATE_REJECTED` — preflight або authority відхилили запит без зміни Паспорта;
- `RECREATE_COMMITTED` — atomic switch і обов'язкові receipts завершені;
- `RECREATE_ROLLED_BACK` — pre-commit failure завершено без зміни canonical pointer.

Невідомий result не маппити на успіх. Зберегти raw receipt, повернути compatibility error і не змінювати UI state Паспорта.

## Обов'язковий порядок перевірок

1. Schema validation і `additionalProperties=false`.
2. Actor authentication та authority.
3. Exact SKU/product version.
4. Current Passport ID/version/SHA.
5. Source inventory, archived locator, SHA-256 і access result.
6. Idempotency key та hash canonical payload.
7. Per-SKU mutation lock.
8. Route-specific preflight.

Відмова до створення run не створює Passport version, archive receipt або agent launch.

## Idempotency і повторна доставка

- Той самий key і canonical payload повертають збережений receipt.
- Той самий key з іншим payload дає `IDEMPOTENCY_KEY_CONFLICT`.
- Network timeout не доводить невиконання; клієнт спочатку запитує receipt, а не генерує новий key.
- Receipt зберігається до відправлення відповіді клієнту.

Коментар реалізатору: hash рахувати після стабільної canonical serialization, а не з довільного порядку JSON properties.

## Atomicity, recovery і downstream

Recreate виконується тільки як `RECREATE_PREFLIGHT → ARCHIVE_PREPARED → NEW_PASSPORT_BUILDING → SWITCH_COMMITTED`. Canonical pointer змінюється однією atomic operation. Після commit незавершені bindings до old Passport SHA отримують `STALE_PASSPORT_BINDING`.

До commit дозволений автоматичний rollback. Після commit автоматичний rollback заборонено; за потреби використовується затверджений admin-only `RESTORE_ARCHIVED_PASSPORT` з окремими request/receipt schemas і feature flag.

Коментар реалізатору: reconciliation може quarantine orphan staging, але не має права приховати чинний Паспорт або створити другий active pointer.

## Admin-only restore

`RESTORE_ARCHIVED_PASSPORT` не є UI rollback. Archived object залишається immutable, а новий Passport object отримує historical lineage і `NOT_READY`. До atomic switch current Passport залишається canonical. Route використовує окремий request/receipt contract і feature flag; звичайний користувач його не бачить.

## Спостережуваність та аудит

Для кожної спроби зберігати `request_id`, payload SHA-256, actor, authority, SKU, current Passport snapshot, idempotency key, operation/lock ID, contract versions/SHA, timestamps, result і receipt IDs. Secrets, access tokens і вміст приватних файлів у log не записувати.

Технічний log не замінює control receipt. UI показує user message code, версію Паспорта та question/conflict IDs, але не внутрішні agent handoffs.

## Feature flags і порядок ввімкнення

1. `listing_suite.source_evidence_delta` — після schema, duplicate, conflict, wrong-SKU та idempotency integration tests.
2. `listing_suite.folder_snapshot_v1` — після access, recursion, limits, partial/zero intake та path-containment tests.
3. `listing_suite.passport_recreate` — після authority, confirmation TTL, concurrency, archive/build failure, atomic switch, recovery та downstream invalidation tests.

Flags вмикаються окремо. PASS одного route не активує інші.

Кожний deployment створює manifest за `listing_suite_deployment_manifest.schema.json`. Перехід flag `OFF → ON` дозволений лише окремим receipt за `listing_suite_feature_activation_receipt.schema.json`, прив'язаним до manifest SHA та test receipt IDs.

## Acceptance tests

- Позитивні fixtures проходять schema validation, негативні відхиляються до mutation.
- Повторна доставка не створює повторної операції.
- При кожному failure зберігається рівно один active canonical Passport.
- `PASSPORT_UPDATED` і `RECREATE_COMMITTED` підтверджені read-back.
- Немає provider calls, publication або physical deletion.
- Feature flag change має actor, timestamp і test receipt.
- Contract versions/SHA записані в deployment manifest.

## Рішення програмного проєкту

Команда реалізації обирає HTTP/RPC/queue transport, URL і method names, authentication provider, lock/storage technology, retry intervals, observability stack та UI polling/push model. Ці рішення не можуть змінювати action tokens, schemas, authority, state meanings, atomicity або дозволені results.

## Межі доказовості

Цей handoff описує логічну межу інтеграції та коментарі для реалізації. Він не доводить наявність adapter, endpoint, database transaction, lock service, recovery worker або UI mapping до проходження integration tests у програмному проєкті.
