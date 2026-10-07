# Контракт запуску Image Collection із Listing Suite та UI result receipt

Версія: 1.0  
Дата: 04.10.2026  
Статус: `IC_09_10_APPROVED_FOR_IMPLEMENTATION`; feature flag `OFF`

## Призначення

Закрити `IC-09–IC-10`: перетворити команду вкладки «Медіа» на типізований `START_MEDIA_COLLECTION` без паралельного маршруту та повернути користувачу стислий результат, сформований із канонічних receipts.

## Вхідний контракт

Listing Suite формує `listing_suite_start_media_collection_request` із:

- `requested_action=START_MEDIA_COLLECTION`;
- actor, exact SKU і product version;
- current Passport ID/version/state/path/SHA;
- `collection_purpose` та execution/discovery mode;
- повним `existing_media_snapshot` reference;
- user-provided source inventory;
- visual targets;
- search scope або `LOCAL_ONLY`;
- product root і детермінованим collection root;
- human confirmation, прив'язаним до SHA всього scope;
- idempotency key.

UI не створює `collection_id` і не вибирає агента. Binding service перевіряє request, обчислює request SHA, виконує eligibility та intake classification, а потім створює або повертає існуючі `MEDIA_COLLECTION_REQUEST` і `MEDIA_COLLECTION_AUTHORIZATION_RECEIPT` для `E090/E100`.

## Правила виконання

1. Passport і media snapshot мають відповідати exact SKU та current version/SHA.
2. Confirmation дійсний лише для exact `scope_sha256`; зміна purpose, sources, targets, search scope або roots потребує нового confirmation.
3. `USER_MEDIA_INTAKE` дозволяє лише `LOCAL_ONLY`; `INITIAL_COLLECTION` і `ADDITIONAL_DISCOVERY` — лише затверджений `INTERNET_DISCOVERY`; `RECOVERY_DELTA` — лише named source IDs.
4. `collection_root` має бути всередині `product_root/артефакти/<date>/image_collector/`.
5. Однаковий idempotency key та payload повертають той самий `collection_id` і receipt; інший payload із тим самим key дає `IDEMPOTENCY_KEY_CONFLICT`.
6. Повторне натискання не створює другу collection.
7. Document або mixed input не запускають Image Collector: повертаються відповідні router results.
8. Binding не передає cookies, credentials, spend, publication або Product Truth authority.
9. Відсутній чи stale confirmation, Passport або snapshot дає `START_REJECTED`; жоден run не створюється.
10. `START_ACCEPTED` означає лише прийнятий bounded запуск, не успішний збір.

## Binding receipt

`listing_suite_start_media_collection_receipt` повертає `START_ACCEPTED | START_REPLAYED | USER_INTENT_REQUIRED | ROUTED_TO_PASSPORT_INTAKE | START_REJECTED`, exact request SHA, collection/run IDs або `null`, downstream request/authorization refs, reason code і `automatic_duplicate_runs_created=0`.

## UI result receipt

Основний екран отримує `image_collection_ui_result_receipt`, а не технічний handoff. Він містить:

- collection ID і purpose;
- sources existing/new/duplicate/inaccessible;
- assets accepted/review/quarantine/rejected;
- open user action IDs;
- media gate;
- Passport delta status;
- base/new Passport version/SHA лише після `PASSPORT_DELTA_APPLIED`;
- рівно одну наступну дію.

Дозволені result states: `STARTED`, `IN_PROGRESS`, `DECISION_REQUIRED`, `READY_FOR_CONFIRMATION`, `PASSPORT_TRANSFER_PENDING`, `COMPLETED`, `COMPLETED_WITH_LIMITATIONS`, `REQUEST_REJECTED`.

`COMPLETED` потребує `PASSPORT_DELTA_APPLIED` і new Passport version/SHA. За відсутності receipt результат залишається `PASSPORT_TRANSFER_PENDING`. UI result не встановлює agent verdict і не надає publication authority.

## Acceptance tests

1. Schema-valid start створює один binding receipt.
2. Exact replay повертає той самий collection ID без нового run.
3. Idempotency key із зміненим payload відхиляється.
4. Scope SHA, що не збігається з confirmation, відхиляється.
5. Collection root поза product root відхиляється.
6. `USER_MEDIA_INTAKE` з internet discovery відхиляється.
7. UI result містить усі чотири source та asset counts.
8. `COMPLETED` без `PASSPORT_DELTA_APPLIED` відхиляється.
9. `PASSPORT_TRANSFER_PENDING` не містить new Passport snapshot.
10. Кожний result має рівно одну next action.

## Межі доказовості

Контракт і fixtures підтверджують форму binding та decision semantics. Вони не доводять реалізацію UI/backend, live agent execution, notification delivery або provider access. Feature flag і зовнішні side effects залишаються `OFF`.
