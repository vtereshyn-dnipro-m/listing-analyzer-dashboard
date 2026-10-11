# Інтеграційний контракт Listing Suite → Конвеєр Паспорта SKU

Версія: 1.2  
Дата: 04.10.2026  
Статус: `READY_FOR_IMPLEMENTATION`; feature flags за замовчуванням `OFF`

## Призначення

Перетворити дії вкладки `Створення` на типізовані запити Координатору без прямого вибору агентів, зміни Product Truth або роботи UI з canonical pointer.

## Область застосування

Звичайний UI підтримує лише:

- `SUBMIT_SOURCE_EVIDENCE_DELTA` — безпечне додавання зареєстрованих матеріалів до чинного Паспорта;
- `RECREATE_PASSPORT` — контрольована повна заміна active Passport object у тій самій lineage.

Адміністративний контур окремо підтримує `RESTORE_ARCHIVED_PASSPORT`; він не є дією звичайного UI.

UI не архівує папки, не створює Паспорт, не перемикає canonical pointer і не виконує web research.

`RESTORE_ARCHIVED_PASSPORT` є окремим admin-only route, не входить до звичайної вкладки `Створення` і використовує власні request/receipt schemas. Archived object не реактивується; створюється новий Passport object у тій самій lineage.

## Вхідні дані та binding

Запит відповідає `listing_suite_passport_action_request.schema.json`. `requested_action`, exact SKU/product version, current Passport snapshot, actor, idempotency key та frozen source inventory є обов'язковими.

Кожен source object спочатку копіюється в `product_root/артефакти/YYYY-MM-DD/`, отримує `source_artifact_id`, immutable SHA-256, origin locator, archived locator та пооб'єктний access result. User description є context, а не Product Truth.

## `SUBMIT_SOURCE_EVIDENCE_DELTA`

UI передає Координатору тільки зареєстровані artifacts. Partial intake дозволено, якщо прийнято хоча б один об'єкт. Недоступні об'єкти не входять до agent scope і повертаються в receipt. Нуль прийнятих об'єктів дає `REQUEST_REJECTED` без запуску.

Результати: `NO_PASSPORT_CHANGE | PASSPORT_UPDATED | DECISION_REQUIRED | WRONG_SKU_OR_SCOPE | STANDARDS_MATERIAL_ROUTED | REQUEST_REJECTED`.

## Folder snapshot v1

`SELECT_FOLDER_SNAPSHOT` є intake-механізмом, а не окремою agent action:

- лише явно вибрана локальна папка поточного користувача;
- одноразовий рекурсивний snapshot;
- symlink, shortcut і junction не обходяться;
- права не розширюються;
- підтримані типи й limits задаються [versioned intake policy](Listing_Suite_Source_Intake_Policy.md); без active deployment profile intake fail-closed;
- inventory заморожується до відправлення;
- майбутні зміни папки не відстежуються;
- дублікати отримують `duplicate_of`;
- якщо жоден object не прийнято, action не запускається.

## `RECREATE_PASSPORT`

Recreate створює новий `passport_id` у тій самій `passport_lineage_id`. У кожний момент існує рівно один `ACTIVE` canonical Passport. Старий object після commit стає immutable `ARCHIVED` і отримує `replaced_by_passport_id`; новий містить `replaces_passport_id/version`.

Потрібні два confirmations одного уповноваженого `actor_id` і одного `recreate_request_id`: `RECREATE_INTENT_CONFIRMED` та `RECREATE_SNAPSHOT_CONFIRMED`. Вони мають однаковий current Passport version/SHA, діють 15 хвилин і самі не створюють run. Зміна snapshot дає `STALE_PASSPORT_INPUT`.

Старі fact values, `VERIFIED`, conflicts і decisions автоматично не переносяться. Старі artifacts можуть увійти лише до frozen inventory з explicit lineage; старий Паспорт є історичним evidence, а не Product Truth нового object.

## Authority

- evidence delta: `PRODUCT_OWNER | DATA_CONTRIBUTOR | PASSPORT_ADMIN`;
- recreate: `PASSPORT_ADMIN | PRODUCT_OWNER_WITH_RECREATE_AUTHORITY`;
- archive read: `PRODUCT_OWNER | PASSPORT_ADMIN | AUDITOR`;
- physical deletion не входить до цього контракту.

Роль визначається backend тільки з verified identity claims за `Listing_Suite_Authority_Mapping_Contract.md` і versioned authority profile. Значення `actor_authority`, отримане від UI, не є authorization evidence. Окремо перевіряється exact SKU scope. Відсутній active `BOUND` profile, unmapped identity або scope mismatch дають fail-closed без mutation чи archive disclosure.

## Concurrency та idempotency

Усі mutation routes використовують per-SKU exclusive lock. Під час recreate commit window інші зміни canonical Passport заборонені. Нові files можна зареєструвати як `REGISTERED_PENDING_RECONCILIATION`, але не застосовувати.

Повтор exact payload з тим самим idempotency key повертає попередній receipt. Той самий key з іншим payload дає `IDEMPOTENCY_KEY_CONFLICT`. Паралельний recreate отримує `RECREATE_IN_PROGRESS` або `RECREATE_REJECTED`.

## Atomic switch, rollback і recovery

Послідовність: `RECREATE_PREFLIGHT → ARCHIVE_PREPARED → NEW_PASSPORT_BUILDING → SWITCH_COMMITTED`. До commit старий Паспорт залишається єдиним canonical. Помилка переводить staging у quarantine і завершується `RECREATE_FAILED` або `RECREATE_ROLLED_BACK`; старий pointer не змінюється.

Після `SWITCH_COMMITTED` автоматичний rollback заборонено. Повернення archived Passport є окремою адміністративною дією `RESTORE_ARCHIVED_PASSPORT` з новою authority, receipt та atomic switch.

Lease recovery і reconciliation виявляють orphan staging, але не створюють другий canonical pointer і не приховують чинний Паспорт.

## Downstream invalidation

Після recreate commit Content TZ, Prompt Packages, незавершені content runs, generation leases і QA receipts, прив'язані до old Passport SHA, отримують `STALE_PASSPORT_BINDING`. Новий provider execution за старим binding заборонений. Завершені історичні runs залишаються read-only і відтворюваними за old hash.

## UI receipt

UI відображає тільки result, user message, affected Passport version та question/conflict IDs. Internal handoffs, manifests і agent routing не показуються. Receipt відповідає `listing_suite_passport_action_receipt.schema.json`.

Machine-readable result і reason перетворюються на UI state та наступну дозволену дію тільки за [UI Message Mapping](Listing_Suite_UI_Message_Mapping.md). Невідомий result/code не маппиться на success.

## Feature flags

- `listing_suite.source_evidence_delta = OFF` до integration-test PASS;
- `listing_suite.folder_snapshot_v1 = OFF` до intake-test PASS;
- `listing_suite.passport_recreate = OFF` до всіх recreate/concurrency/recovery/downstream tests PASS.
- `listing_suite.passport_restore = OFF` до restore lineage/revalidation/atomic-switch/downstream tests PASS.

`READY_FOR_IMPLEMENTATION` не означає production activation.

## Acceptance tests

Обов'язкові сценарії визначені в 00A та `Test-ListingSuitePassportCreationContracts.ps1`. Жодний PASS не надає publication authority або право фізичного видалення архіву.

## Межі доказовості

Цей контракт робить route і payload однозначними. Він не доводить реалізацію UI, storage adapter, lock service або canonical pointer store до їхніх окремих integration tests.
