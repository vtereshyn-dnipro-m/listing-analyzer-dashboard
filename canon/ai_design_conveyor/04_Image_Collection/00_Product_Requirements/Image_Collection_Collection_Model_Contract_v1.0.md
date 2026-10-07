# Контракт моделі collection для Image Collection

Версія: 1.0  
Дата: 04.10.2026  
Статус: `IC_01_04_APPROVED_FOR_IMPLEMENTATION`; feature flag `OFF`

## Призначення

Закрити `IC-01–IC-04`: дати Listing Suite стабільний snapshot наявної медиабази, відрізнити первинний, додатковий, локальний і recovery-збір, типізувати media inputs та виключити несанкціонований internet discovery.

## Вхідні дані

Перед показом дій для exact SKU система формує `existing_media_snapshot` за `existing_media_snapshot.schema.json`. Snapshot прив'язаний до current Passport ID/version/SHA та canonical media registry version/SHA і містить:

- попередні `collection_id`;
- усі відомі source IDs;
- counts `accepted/review/quarantine/unavailable`;
- `last_checked_at` кожного source;
- lineage `source → asset → Passport row`;
- незакриті access, review і human actions;
- immutable snapshot SHA-256.

Порожня медиабаза не означає відсутність snapshot: створюється schema-valid empty snapshot із нульовими counts і порожніми collections/sources.

## `collection_purpose`

- `INITIAL_COLLECTION`: перший discovery-збір після створення мінімального Паспорта `NOT_READY`; попередніх collections немає.
- `ADDITIONAL_DISCOVERY`: новий internet discovery відносно всієї попередньої медиабази; потребує previous search cutoff, prior surface/query coverage і глобальної SKU-дедуплікації.
- `USER_MEDIA_INTAKE`: обробка тільки явно переданих файлів/URL; загальний internet discovery заборонено.
- `RECOVERY_DELTA`: повтор лише для названих failed/blocked source IDs; завершені джерела не повторюються.

Режим виконання `STANDARD | PILOT_REVIEW_ONLY` залишається окремою віссю і не замінює `collection_purpose`.

## Типи media input

Закритий `source_input_type`:

- `IMAGE_FILE`;
- `VIDEO_FILE`;
- `DIRECT_IMAGE_URL`;
- `DIRECT_VIDEO_URL`;
- `MEDIA_PAGE_URL`;
- `MEDIA_FOLDER` — тільки з чинним `folder_contract_ref`.

Для `MEDIA_PAGE_URL` сторінка отримує окремий source ID. Кожне знайдене зображення/відео отримує власний source/asset ID та lineage до сторінки. Extraction receipt показує found/retrieved/unavailable objects і reason code кожної невдачі.

## Правила виконання

1. Snapshot читається до створення нового `collection_id`.
2. `INITIAL_COLLECTION` допустимий лише за нульової кількості попередніх collections.
3. `ADDITIONAL_DISCOVERY` допустимий лише за наявності попередньої collection, cutoff і prior coverage.
4. `USER_MEDIA_INTAKE` має `discovery_mode=LOCAL_ONLY`; додавання файла не дозволяє internet discovery.
5. `RECOVERY_DELTA` має `discovery_mode=TARGETED_RECOVERY` і непорожній перелік target source IDs.
6. `INITIAL_COLLECTION` та `ADDITIONAL_DISCOVERY` мають `discovery_mode=INTERNET_DISCOVERY` і human-confirmed search scope.
7. Дедуплікація виконується проти всіх sources/assets snapshot, а не лише поточної collection.
8. Повтор exact request з тим самим idempotency key повертає попередній receipt; інший payload із тим самим key відхиляється.
9. Зміна purpose, discovery mode або search scope після старту потребує нового human confirmation і нового request.

## UI actions

- `Обробити додані матеріали` формує `USER_MEDIA_INTAKE` і ніколи не запускає загальний пошук.
- `Знайти нові матеріали` формує `INITIAL_COLLECTION` для порожнього snapshot або `ADDITIONAL_DISCOVERY` для непорожнього snapshot.
- Recovery запускається лише з адресного failed/blocked source action, а не загальною кнопкою нового пошуку.

## Acceptance tests

- Порожній snapshot допускає `INITIAL_COLLECTION`, але не `ADDITIONAL_DISCOVERY`.
- Snapshot із попередньою collection допускає `ADDITIONAL_DISCOVERY`, але не `INITIAL_COLLECTION`.
- `USER_MEDIA_INTAKE + INTERNET_DISCOVERY` відхиляється schema validation.
- `ADDITIONAL_DISCOVERY` без cutoff/coverage відхиляється.
- `RECOVERY_DELTA` без target source IDs відхиляється.
- `MEDIA_FOLDER` без folder contract відхиляється.
- Page source та extracted media не мають одного source ID.
- Existing source не реєструється як новий під час additional discovery.

## Межі доказовості

Контракт визначає модель і preflight, але не реалізує UI, search adapter або media registry reader. До integration-test PASS нові UI actions і feature flag залишаються `OFF`.
