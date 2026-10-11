# Пакет передачі Image Collection UI у програмну реалізацію

Версія: 1.0  
Дата: 04.10.2026  
Статус: `CONTRACT_PACKAGE_COMPLETE`; feature flags `OFF`

## Мета

Передати команді Listing Suite повний набір контрактів для реалізації вкладки «Медіа» без перенесення агентської логіки в інтерфейс. Пакет закриває `IC-01–IC-10` на рівні вимог, JSON Schema, fixtures і локальних contract tests.

## Контекст і межа систем

Listing Suite збирає параметри, показує проєкцію стану та передає типізовані запити. Координатор перевіряє route і binding. Image Collector виконує збір. Reviewer і Skeptic формують незалежні receipts. Собиратель Паспорта застосовує media delta. Інтерфейс не вибирає агентів, не присвоює verdict і не редагує Product Truth.

Рекомендовані transport endpoints нижче є іменами integration handlers, а не новими доменними маршрутами:

- `POST /media-collections:start` → `START_MEDIA_COLLECTION`;
- `GET /media-collections/{collection_id}/state` → UI state receipt;
- `GET /media-collections/{collection_id}/result` → UI result receipt;
- `POST /media-collections/{collection_id}/actions` → typed human action;
- `GET /skus/{sku_id}/media-snapshot` → existing-media snapshot.

Backend може використати інший transport, але payloads, enums, idempotency та authority boundaries змінювати не можна без нової версії контракту.

## Матриця IC-01–IC-10

| Gap | Реалізований контроль | Канонічне джерело | Test evidence |
|---|---|---|---|
| `IC-01` | snapshot усіх попередніх collections/assets | Collection Model Contract | `IC_01_EXISTING_MEDIA_SNAPSHOT=PASS` |
| `IC-02` | чотири окремі collection purposes | Collection Model Contract | `IC_02_COLLECTION_PURPOSE=PASS` |
| `IC-03` | закритий typed media intake | Collection Model Contract | `IC_03_TYPED_MEDIA_INPUT=PASS` |
| `IC-04` | `LOCAL_ONLY` відокремлено від discovery | Collection Model Contract | `IC_04_DISCOVERY_BOUNDARY=PASS` |
| `IC-05` | media/document/mixed router | Passport Boundary Contract | `IC_05_INTAKE_ROUTER=PASS` |
| `IC-06` | initial collection тільки після мінімального Паспорта | Passport Boundary Contract | `IC_06_INITIAL_AFTER_MINIMUM_PASSPORT=PASS` |
| `IC-07` | evidence-backed UI state machine | UI State and Human Action Contract | `IC_07_UI_STATE_MACHINE=PASS` |
| `IC-08` | typed human actions і human-only completion | UI State and Human Action Contract | `IC_08_HUMAN_ACTIONS=PASS` |
| `IC-09` | `START_MEDIA_COLLECTION`, confirmation та idempotency | Listing Suite Binding and Result Contract | `IC_09_START_BINDING=PASS` |
| `IC-10` | агрегований user-facing result receipt | Listing Suite Binding and Result Contract | `IC_10_UI_RESULT_RECEIPT=PASS` |

## Точки входу

### Existing-media snapshot

Перед відображенням форми запуску backend повертає schema-valid snapshot із current Passport/media-registry binding, попередніми collections, sources і assets. UI не будує snapshot із випадкових локальних файлів.

### Start request

Після підтвердження користувача UI відправляє `listing_suite_start_media_collection_request`. Backend повторно перевіряє current Passport version/SHA, snapshot SHA, scope confirmation, purpose/mode, source classification, root containment та idempotency.

Позитивний binding створює канонічні runtime artifacts `MEDIA_COLLECTION_REQUEST` і `MEDIA_COLLECTION_AUTHORIZATION_RECEIPT` для E090/E100. UI payload не передається Image Collector напряму.

### Human action

UI відправляє тільки action з чинного enum. Backend звіряє expected manifest version/SHA та target IDs. Stale action не застосовується. Access credentials не зберігаються в action payload; приймається лише locator зареєстрованого lawful artifact.

## Точки виходу

### Start receipt

UI обробляє `START_ACCEPTED`, `START_REPLAYED`, `USER_INTENT_REQUIRED`, `ROUTED_TO_PASSPORT_INTAKE` або `START_REJECTED`. `START_REPLAYED` відкриває наявний collection; створення другого run заборонено.

### State receipt

State endpoint повертає рівно один `ui_state`, evidence refs і одну next action. UI не реконструює пріоритети локально. Open access і user-decision states мають пріоритет над фоновим review progress.

### Result receipt

Result endpoint повертає source/asset counts, open actions, media gate, Passport delta status та одну next action. `COMPLETED` можливий тільки за наявності `PASSPORT_DELTA_APPLIED` і base/new Passport snapshots. До цього показується `PASSPORT_TRANSFER_PENDING`.

## Дані та зберігання

- Product artifacts зберігаються тільки всередині exact-SKU `product_root`.
- Collection root: `<product_root>/артефакти/<YYYY-MM-DD>/image_collector/<collection_id>/`.
- Оригінали immutable; exclusion не видаляє source record.
- Request, receipt, manifest і result мають version/SHA та lineage.
- Idempotency ledger зберігає key, request SHA, collection ID, run ID і terminal binding receipt.
- Технічні handoffs доступні для diagnostics/audit, але основний екран використовує UI receipts.

## Обробка помилок

UI показує user-facing message, але зберігає machine reason code. Обов'язкові mappings:

| Reason code | Поведінка UI |
|---|---|
| `STALE_PASSPORT_INPUT` | оновити Паспорт і вимагати повторне підтвердження |
| `STALE_MEDIA_SNAPSHOT` | перечитати snapshot, не запускати collection |
| `CONFIRMATION_SCOPE_MISMATCH` | показати змінений scope і запросити нове підтвердження |
| `COLLECTION_ROOT_OUTSIDE_PRODUCT_ROOT` | заблокувати запуск як configuration error |
| `PURPOSE_MODE_MISMATCH` | повернути до вибору purpose/mode |
| `IDEMPOTENCY_KEY_CONFLICT` | не повторювати submit; відкрити diagnostic reference |
| `USER_INTENT_REQUIRED` | попросити вибрати media intake або Passport source intake |
| `ROUTED_TO_PASSPORT_INTAKE` | відкрити дозволений Passport intake route |

## Порядок реалізації

1. Реалізувати persistence для snapshot, binding/action/state/result receipts та idempotency ledger.
2. Реалізувати read-only snapshot/state/result handlers.
3. Реалізувати start binding до наявних E090/E100, не до Image Collector напряму.
4. Реалізувати typed human actions зі stale-write protection.
5. Додати UI controls і user-facing reason mapping.
6. Виконати contract tests і integration tests із mock Coordinator.
7. Виконати non-live exact-SKU pilot із реальним файловим зберіганням.
8. Увімкнути feature flag тільки після окремого admission рішення.

## Acceptance tests для програмної реалізації

1. Після вибору SKU UI читає всі попередні collections із snapshot.
2. Initial start до мінімального Паспорта повертає block без run.
3. Exact double-click створює один collection/run.
4. Зміна scope після confirmation не використовує старе підтвердження.
5. Document input не потрапляє до Image Collector.
6. Mixed input не створює два runs.
7. `USER_MEDIA_INTAKE` не виконує internet discovery.
8. Stale human action не змінює manifest.
9. Quarantine видимий і не входить до accepted count.
10. Pilot не може встановити `COLLECTION_READY`.
11. Pending Passport delta не відображається як completed.
12. Applied Passport delta показує base/new version/SHA.
13. Жодна UI-операція не надає publication authority.
14. Усі створені product artifacts проходять path containment і SHA read-back.

## Ризики та обмеження

- Local contract `PASS` не підтверджує реалізацію transport, persistence, locking або UI.
- Реальний folder picker потребує окремо реалізованого provider/authorization adapter за чинним intake contract.
- Live internet collection і DaVinci export не перевірялися цим пакетом.
- Feature flags, provider calls, spend і publication authority не активовані.

## Наступні дії

Власник програмної реалізації має заповнити implementation mapping: endpoint/handler, storage table або document store, lock/idempotency mechanism, notification channel, feature flag name та посилання на integration-test evidence. Після цього виконується окремий contract-conformance review і non-live pilot.

## Межі доказовості

Пакет готовий для програмної реалізації, але не є підтвердженням production readiness. Production admission потребує реалізованих handlers, persistence, integration tests, pilot evidence та окремого owner decision.
