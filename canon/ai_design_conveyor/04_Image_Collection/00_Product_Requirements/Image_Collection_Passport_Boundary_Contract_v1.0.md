# Контракт межі Image Collection ↔ Паспорт SKU

Версія: 1.0  
Дата: 04.10.2026  
Статус: `IC_05_06_APPROVED_FOR_IMPLEMENTATION`; feature flag `OFF`

## Призначення

Закрити `IC-05–IC-06`: маршрутизувати media й документні inputs до правильного контуру та дозволяти первинний Image Collection тільки після створення мінімального канонічного Паспорта exact SKU.

## Intake classification

До створення collection кожний input отримує receipt за `media_intake_classification_receipt.schema.json`.

- media file, direct media URL або media page → `ACCEPTED_AS_MEDIA_SOURCE`;
- документ, сертифікат, інструкція, каталог, опис або продуктова document page → `ROUTE_TO_PASSPORT_SOURCE_INTAKE`;
- сторінка, що одночасно містить значущий документний і media content → `USER_INTENT_REQUIRED`;
- непідтримуваний або нерозпізнаний object → `UNSUPPORTED_INPUT`.

Router визначає contour, але не аналізує Product Truth і не встановлює media verdict.

## Mixed input

`USER_INTENT_REQUIRED` не створює collection і не запускає Passport source delta. Користувач обирає одну або обидві цілі окремо:

- `MEDIA_COLLECTION_ONLY`;
- `PASSPORT_SOURCE_INTAKE_ONLY`;
- `BOTH_AS_SEPARATE_REQUESTS`.

Останній варіант створює два незалежні request IDs, idempotency keys і receipts. Один input зберігає lineage до обох registered artifacts, але жоден contour не успадковує verdict іншого.

## Первинний збір

Image Collector не запускається лише за назвою товару, SKU text або ще не записаним candidate Passport. Перед `INITIAL_COLLECTION` потрібен eligibility receipt за `image_collection_initial_eligibility_receipt.schema.json`:

- існує один canonical Passport exact SKU;
- стан Паспорта належить `NOT_READY | BLOCKED | READY_WITH_LIMITATIONS | READY`;
- Passport ID/version/path/SHA пройшли read-back;
- identity exact SKU підтверджена;
- сформовано `existing_media_snapshot`, навіть якщо він порожній;
- немає другого active canonical Passport.

Для нового товару порядок такий:

`source intake → Собиратель створює мінімальний єдиний Passport NOT_READY → read-back receipt → existing_media_snapshot → INITIAL_COLLECTION action available → окреме human confirmation → Image Collector`.

Створення мінімального Паспорта не запускає Image Collection автоматично. Воно лише робить дію доступною.

## Правила виконання

1. `ROUTE_TO_PASSPORT_SOURCE_INTAKE` формує рекомендацію `SUBMIT_SOURCE_EVIDENCE_DELTA` або initial Passport intake; Image Collector не отримує документ як media source.
2. `ACCEPTED_AS_MEDIA_SOURCE` не змінює Passport і не запускає collection без start request.
3. Mixed input не породжує два запуски без explicit user choice.
4. До eligibility `AVAILABLE` UI показує причину блокування й не створює `collection_id`.
5. Passport `NOT_READY` достатній для первинного media-збору, якщо identity/read-back пройдені; він не означає Product Truth readiness.
6. Passport `BLOCKED` допускає collection лише якщо active block не забороняє identity/media use; інакше eligibility `BLOCKED`.
7. Зміна Passport version/SHA після eligibility робить receipt stale; потрібна повторна перевірка.
8. Router та eligibility receipts не є agent run і не дозволяють provider calls.

## Acceptance tests

- PDF certificate → `ROUTE_TO_PASSPORT_SOURCE_INTAKE`, collection не створено.
- Direct image URL → `ACCEPTED_AS_MEDIA_SOURCE`, але run ще не створено.
- Mixed page → `USER_INTENT_REQUIRED`, автоматичних запусків `0`.
- `BOTH_AS_SEPARATE_REQUESTS` → два різні request IDs та idempotency keys.
- Відсутній Passport → eligibility `BLOCKED / SKU_PASSPORT_REQUIRED`.
- Candidate без read-back → `BLOCKED / PASSPORT_READBACK_REQUIRED`.
- Exact minimal `NOT_READY` Passport + empty snapshot → `AVAILABLE` для `INITIAL_COLLECTION`.
- Stale Passport SHA → `BLOCKED / STALE_PASSPORT_BINDING`.

## Межі доказовості

Контракт визначає routing та availability, але не реалізує UI router або автоматичне створення Паспорта. Provider execution і production activation залишаються забороненими до окремих integration tests.
