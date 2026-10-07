# Mapping результатів Listing Suite для користувача

Версія: 1.1  
Дата: 04.10.2026  
Статус: `READY_FOR_IMPLEMENTATION`

## Призначення

Однозначно зв'язати machine-readable result/reason із `user_message_code`, станом UI та наступною дозволеною дією. Текст локалізації зберігається окремо; code і meaning не перекладаються.

## Правила mapping

- UI не виводить raw exception як основне повідомлення.
- Невідомий result або code дає `CONTRACT_COMPATIBILITY_ERROR`, не success.
- `RECREATE_ACCEPTED` і `RECREATE_IN_PROGRESS` не означають зміну Паспорта.
- Success показується тільки після receipt із підтвердженим read-back.
- Retry не створює новий idempotency key, доки status попереднього request невідомий.

## Evidence delta

| Result | `user_message_code` | UI state | Дозволена дія |
|---|---|---|---|
| `NO_PASSPORT_CHANGE` | `SOURCE_DELTA_NO_CHANGE` | current Passport без змін | переглянути duplicate counts |
| `PASSPORT_UPDATED` | `PASSPORT_UPDATE_CONFIRMED` | показати new version/SHA | відкрити оновлений Паспорт |
| `DECISION_REQUIRED` | `PASSPORT_DECISION_REQUIRED` | показати question/conflict IDs | перейти до рішення |
| `WRONG_SKU_OR_SCOPE` | `SOURCE_WRONG_SKU_OR_SCOPE` | current Passport без змін | виправити SKU/scope |
| `STANDARDS_MATERIAL_ROUTED` | `SOURCE_ROUTED_TO_STANDARDS` | current Passport без змін | відкрити routing receipt |
| `REQUEST_REJECTED` | reason-specific code | current Passport без змін | виправити причину |

## Recreate

| Result | `user_message_code` | UI state | Дозволена дія |
|---|---|---|---|
| `RECREATE_ACCEPTED` | `PASSPORT_RECREATE_ACCEPTED` | operation in progress; old Passport active | read-only status lookup |
| `RECREATE_IN_PROGRESS` | `PASSPORT_RECREATE_ALREADY_RUNNING` | existing operation shown | відкрити existing operation |
| `RECREATE_REJECTED` | reason-specific code | old Passport active | виправити причину й повторити preflight |
| `RECREATE_COMMITTED` | `PASSPORT_RECREATE_COMMITTED` | new Passport active | відкрити new Passport |
| `RECREATE_ROLLED_BACK` | `PASSPORT_RECREATE_ROLLED_BACK` | old Passport active | переглянути recovery receipt |

## Reason-specific codes

| Code | Meaning | Retry rule |
|---|---|---|
| `REQUEST_SCHEMA_INVALID` | payload не відповідає schema | виправити той самий request до запуску |
| `ACTOR_NOT_AUTHORIZED` | authority недостатня | retry лише після зміни authority |
| `STALE_PASSPORT_INPUT` | version/SHA вже не current | отримати current snapshot; confirmations створити заново |
| `NO_ACCEPTED_SOURCE_OBJECTS` | intake не прийняв жодного object | додати придатні матеріали |
| `INTAKE_POLICY_NOT_CONFIGURED` | немає active deployment profile | увімкнення feature flag заборонено |
| `IDEMPOTENCY_KEY_CONFLICT` | key повторено з іншим payload | розслідувати; не генерувати success |
| `RECREATE_CONFIRMATION_MISSING` | немає двох required confirmations | отримати відсутнє підтвердження |
| `RECREATE_CONFIRMATION_EXPIRED` | минув 15-minute TTL | повторити обидва confirmations |
| `RECREATE_CONFIRMATION_MISMATCH` | actor/request/snapshot не збігаються | повторити обидва confirmations |
| `PASSPORT_MUTATION_LOCKED` | SKU mutation lock зайнятий | показати active operation; не дублювати mutation |
| `RECREATE_PREFLIGHT_FAILED` | route-specific preflight не пройдено | виправити named finding |
| `CONTRACT_COMPATIBILITY_ERROR` | невідомий result/code/schema version | зупинити mutation UI і ескалувати integration owner |
| `AUTHORITY_PROFILE_NOT_ACTIVE` | authority profile відсутній або не має active binding | звернутися до identity owner; mutation не повторювати |
| `AUTHORITY_NOT_MAPPED` | identity не прив'язано до canonical role | запросити access mapping |
| `ACTION_NOT_AUTHORIZED` | role не дозволяє requested action | запросити authority review |
| `SKU_SCOPE_DENIED` | role не має exact SKU scope | вибрати дозволений SKU або змінити scope |
| `IDENTITY_NOT_VERIFIED` | identity claims не підтверджені | повторити authentication |

## Локалізація

Локалізований текст отримує stable `user_message_code`, locale і catalog version за `Listing_Suite_Localization_Contract.md`. Активні локалі: `uk-UA`, `ru-RU`; fallback: `uk-UA`; `en-US` має стан `PLANNED`. Відсутній переклад використовує fallback із явним resolution receipt, але не змінює code, severity або allowed action.

## Acceptance tests

- Кожний дозволений result має рівно один default message code.
- Кожний reject fixture має reason-specific code.
- Невідомий code не показується як success.
- Mapping не змінює Passport state самостійно.
- Усі локалі зберігають однакові action semantics.

## Межі доказовості

Документ визначає mapping, але не містить фінальних UX-текстів усіма мовами та не підтверджує реалізацію UI catalog.
