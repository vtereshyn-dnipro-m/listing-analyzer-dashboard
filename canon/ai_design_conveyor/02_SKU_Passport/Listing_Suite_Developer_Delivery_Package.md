# Пакет передачі Listing Suite → Паспорт SKU команді розробки

Версія: 1.2  
Дата: 04.10.2026  
Статус: `READY_FOR_IMPLEMENTATION`  
Production activation: `NOT_AUTHORIZED`

## Призначення

Єдина точка входу для команди, яка реалізовуватиме інтеграцію в окремому програмному проєкті. Пакет розділяє нормативні контракти, implementation guidance, executable fixtures, конфігурацію та майбутній scope.

## Область реалізації v1

До v1 входять:

1. реєстрація окремих source objects;
2. `SELECT_FOLDER_SNAPSHOT` як intake operation;
3. `SUBMIT_SOURCE_EVIDENCE_DELTA`;
4. два confirmations і `RECREATE_PASSPORT`;
5. read-only status lookup;
6. deployment manifest і контрольована активація feature flags.

Не входять: фізичне видалення архівів, автоматична публікація, provider execution, background folder watch, cloud subscription і автоматичний web research. `RESTORE_ARCHIVED_PASSPORT` входить лише як admin-only route з окремим feature flag.

## Нормативні контракти

| Артефакт | Роль | Обов'язковість |
|---|---|---|
| `00A_Контракт_передач_Паспорта_SKU.md` v2.13 | route, states, receipts, atomicity | обов'язково |
| `Listing_Suite_Integration_Contract.md` v1.0 | межа UI та Координатора | обов'язково |
| `Listing_Suite_Source_Intake_Policy.md` v1.0 | intake invariants і configuration gate | обов'язково для intake |
| `Listing_Suite_UI_Message_Mapping.md` v1.0 | result/reason → UI state/action | обов'язково для UI |
| `listing_suite_passport_action_request.schema.json` | delta/recreate request | обов'язково |
| `listing_suite_passport_action_receipt.schema.json` | UI control receipt | обов'язково |
| `listing_suite_source_intake_profile.schema.json` | deployment intake limits/types | обов'язково для intake |
| `listing_suite_source_intake_receipt.schema.json` | frozen folder/file inventory | обов'язково для intake |
| `listing_suite_recreate_confirmation_receipt.schema.json` | confirmation lifecycle/TTL | обов'язково для recreate |
| `passport_recreate_archive_receipt.schema.json` | archive preparation/commit | обов'язково для recreate |
| `passport_recreate_transaction_receipt.schema.json` | atomic switch/rollback/downstream | обов'язково для recreate |
| `listing_suite_passport_status_query.schema.json` | read-only lookup request | обов'язково для lookup |
| `listing_suite_passport_status_response.schema.json` | stored status replay | обов'язково для lookup |
| `listing_suite_deployment_manifest.schema.json` | implementation/contract binding | обов'язково для deployment |
| `listing_suite_feature_activation_receipt.schema.json` | feature flag transition | обов'язково для activation |
| `listing_suite_passport_restore_request.schema.json` | admin restore request | обов'язково для restore |
| `listing_suite_passport_restore_receipt.schema.json` | restore atomic transaction | обов'язково для restore |
| `Listing_Suite_Archive_Retention_Policy.md` v1.0 | archive lifecycle, access, legal hold | обов'язково для archive operations |
| `listing_suite_archive_retention_profile.schema.json` | retention configuration | обов'язково для retention evaluation |
| `listing_suite_archive_retention_evaluation_receipt.schema.json` | retained/hold/review verdict | обов'язково для retention evaluation |
| `Listing_Suite_Archive_Retention_Profile_v1.0.json` | погоджені 1095 днів, roles та authorities | production-candidate; flag лишається `OFF` |
| `listing_suite_archive_legal_hold_receipt.schema.json` | apply/release legal hold | обов'язково для зміни hold state |
| `listing_suite_archive_retention_boundary_cases.schema.json` | exact deadline та precedence matrix | обов'язково для contract tests |
| `Listing_Suite_Authority_Mapping_Contract.md` | canonical roles, actions і SKU scope | обов'язково для authentication/authorization adapter |
| `Listing_Suite_Authority_Profile_v1.0.json` | approved matrix без реальних IdP bindings | `BINDING_REQUIRED`; не активувати |
| `listing_suite_authority_mapping_profile.schema.json` | versioned IdP binding profile | обов'язково для deployment |
| `listing_suite_authority_evaluation_receipt.schema.json` | per-request authorization verdict | обов'язково для mutation та archive access |
| `Listing_Suite_Localization_Contract.md` | locale resolution і fallback semantics | обов'язково для UI messages |
| `Listing_Suite_Locale_Profile_v1.0.json` | enabled/planned locales | production-candidate; UI flag `OFF` |
| `Listing_Suite_Message_Catalog_v1.0.json` | повні `uk-UA`/`ru-RU` UX-тексти | обов'язково для UI acceptance |
| `listing_suite_message_resolution_receipt.schema.json` | direct/fallback/unknown-code result | обов'язково для fallback audit |

Під час deployment фіксуються exact file version і SHA-256. Назва файла без hash не є достатнім binding.

## Implementation guidance

- `Listing_Suite_Implementation_Handoff.md` пояснює logical entry/exit points, sequencing, retry, logging і ownership.
- `Listing_Suite_ТЗ_Контент_Паспорт_SKU.md` визначає UX-модель вкладки `Створення`.
- `00_Агент_координатор_конвейера_Паспорта_SKU.md` визначає orchestration rules після прийняття request.
- `02`, `02B`, `02C` визначають staging build і output Собирателя; UI їх безпосередньо не викликає.

Guidance не може перевизначити JSON Schema або 00A. При суперечності реалізація зупиняється як `CONTRACT_COMPATIBILITY_ERROR`.

## Executable fixtures

Canonical fixture set: `fixtures/listing_suite/fixture_manifest.json` v2.0.

Fixtures поділені на:

- positive schema cases;
- schema-negative cases, які не створюють run;
- contract-negative cases, які проходять schema і блокуються preflight;
- output receipts, які перевіряють дозволені state combinations.

Команда не повинна переписувати contract-negative cases у schema-negative лише для спрощення adapter logic.

## Порядок реалізації

### Етап 1. Read-only foundation

Реалізувати contract loader, SHA binding, schema validation, canonical JSON serialization, receipt store і status lookup. Feature flags залишаються `OFF`.

### Етап 2. Source intake

Реалізувати exact-file intake, deployment profile, archive copy/hash/read-back, folder snapshot, path containment і partial/zero behavior.

### Етап 3. Evidence delta

Реалізувати authority, current Passport preflight, idempotency, per-SKU mutation lock, Coordinator binding і UI receipt mapping.

### Етап 4. Recreate

Реалізувати confirmation lifecycle, archive preparation, staging, atomic pointer switch, rollback до commit, recovery і downstream invalidation.

### Етап 5. Activation

Створити deployment manifest, виконати integration fixtures у цільовому environment і випустити окремий activation receipt для кожного flag.

## Entry/exit responsibility matrix

| Boundary | Producer | Consumer | Success evidence |
|---|---|---|---|
| file/folder selection | Listing Suite intake adapter | source registry | intake receipt + frozen inventory |
| delta/recreate request | Listing Suite action adapter | Координатор | accepted/rejected control receipt |
| confirmation | authorized UI/admin flow | recreate preflight | active confirmation receipt |
| archive/staging transaction | Координатор/storage layer | canonical pointer store | archive + transaction receipts |
| status query | Listing Suite UI | receipt store | read-only stored response |
| feature activation | deployment owner | runtime configuration | deployment manifest + activation receipt |

## Gates перед передачею між етапами

- Schema PASS не замінює authority, state, path, count або snapshot preflight.
- `ACCEPTED` не дорівнює `COMMITTED`.
- `RECREATE_ACCEPTED` не змінює canonical Passport.
- UI success допускається тільки після read-back і terminal receipt.
- Network timeout вимагає status lookup, а не нового idempotency key.
- Невідомий code/schema version fail-closed.

## Configuration required

До intake tests власник продукту та infrastructure owner мають затвердити deployment profile: дозволені types, file count, sizes, video duration і recursion depth. До цього `listing_suite.folder_snapshot_v1=OFF`.

Фінальні локалізовані повідомлення визначені у `Listing_Suite_Message_Catalog_v1.0.json`. Реалізація повинна зберігати stable `user_message_code`, catalog binding і однакову action semantics; UI rendering ще не перевірено.

Усі залишкові owner-controlled parameters ведуться тільки у `Listing_Suite_Configuration_Decision_Register.md`. Команда реалізації не створює production defaults із fixture values.

## Навмисно невизначені implementation choices

Команда може самостійно обрати HTTP/RPC/queue transport, endpoint names, database, lock technology, retry intervals, polling/push model та observability stack. Вона не може змінювати action tokens, schemas, authority, result meanings, atomicity або publication boundary.

## Admin-only restore boundary

`RESTORE_ARCHIVED_PASSPORT` створює новий Passport object з archived snapshot; archived object не реактивується. Current active Passport архівується лише під час atomic switch. Restored values зберігають provenance, але readiness і current verification скидаються. Route доступний тільки `PASSPORT_ADMIN`, має два confirmations, окремі schemas і flag `listing_suite.passport_restore=OFF` до integration-test PASS. Після recreate `SWITCH_COMMITTED` він ніколи не запускається автоматично.

## Acceptance tests

1. Усі cases з fixture manifest дають exact expected schema/contract result.
2. Негативний case не створює несанкціонованої mutation.
3. Для кожного success існує persisted receipt і read-back.
4. При failure зберігається рівно один active canonical Passport.
5. Кожний enabled flag має verified implementation, test receipts і activation receipt.
6. Secrets відсутні у manifests, receipts і logs.
7. Publication authority залишається `NOT_GRANTED`.

## Формат передачі

Команді передається вся папка `02_SKU_Passport` або immutable snapshot з manifest. Мінімальний handoff містить цей документ, усі нормативні файли з таблиці, fixture folder, test script і frozen runtime baseline. Окреме копіювання лише JSON schemas без 00A та integration contract заборонено.

## Межі доказовості

Пакет готовий до реалізації та contract-driven integration testing. Він не підтверджує наявність програмного adapter, storage transactions, lock service, recovery worker, UI mapping або production deployment.
