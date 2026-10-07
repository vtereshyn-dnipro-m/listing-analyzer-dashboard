# Контракт UI-станів і дій користувача Image Collection

Версія: 1.0  
Дата: 04.10.2026  
Статус: `IC_07_08_APPROVED_FOR_IMPLEMENTATION`; feature flag `OFF`

## Призначення

Закрити `IC-07–IC-08`: дати Listing Suite однозначну UI state machine, прив'язану до фактичних receipts, і типізувати адресні рішення користувача без передачі йому внутрішньої координації агентів.

## Принцип

`ui_state` є read-only projection і не створює нового Run status. Source of truth — collection request, source registry, access queue, Reviewer/Skeptic receipts, human decision receipt і Passport delta receipt. UI не встановлює agent verdict самостійно.

## UI states

| `ui_state` | Умова | Доступна дія |
|---|---|---|
| `NOT_STARTED` | немає collection request/ID | створити дозволений start request |
| `MATERIALS_REGISTERED` | source records створені, execution ще не почалось | запустити підтверджений scope |
| `SEARCH_RUNNING` | active discovery/intake execution | переглядати прогрес або скасувати дозволеним control route |
| `ACCESS_REQUIRED` | є open access action | надати lawful file/export/access або виключити source |
| `REVIEW_RUNNING` | assets передані Reviewer/Skeptic, gate не завершено | чекати receipts |
| `USER_DECISION_REQUIRED` | є адресний SKU/revision або asset decision | виконати named action |
| `READY_FOR_CONFIRMATION` | media gate `READY_FOR_HUMAN_REVIEW`, human acceptance відсутній | підтвердити/частково прийняти/відхилити collection |
| `COLLECTION_CONFIRMED` | є human decision `COLLECTION_READY` | переглянути підтверджений pool |
| `PASSPORT_TRANSFER_PENDING` | delta передано, `PASSPORT_DELTA_APPLIED` відсутній | read-only status lookup |
| `PASSPORT_TRANSFERRED` | є `PASSPORT_DELTA_APPLIED` з new Passport version/SHA | відкрити оновлений Паспорт |
| `COMPLETED_WITH_LIMITATIONS` | terminal human/technical result має residual limitations | переглянути limitations і дозволений recovery action |

Проєкція відповідає `image_collection_ui_state_receipt.schema.json` і завжди містить evidence refs та рівно одну next action.

## Пріоритет станів

Для одночасних сигналів застосовується порядок: `ACCESS_REQUIRED` → `USER_DECISION_REQUIRED` → `REVIEW_RUNNING` → `READY_FOR_CONFIRMATION` → `PASSPORT_TRANSFER_PENDING` → `PASSPORT_TRANSFERRED`. `COMPLETED_WITH_LIMITATIONS` використовується лише для terminal outcome, а не для приховування активної адресної дії.

`COLLECTION_CONFIRMED` не означає, що delta вже внесено в Паспорт. `PASSPORT_TRANSFERRED` не означає publication clearance.

## Дії користувача

Закритий `requested_action`:

- `CONFIRM_ASSET_SKU_REVISION`;
- `PROVIDE_LAWFUL_ACCESS_ARTIFACT`;
- `EXCLUDE_SOURCE_FROM_SCOPE`;
- `ACCEPT_PROPOSED_ASSET`;
- `REJECT_PROPOSED_ASSET`;
- `CONFIRM_COLLECTION_COMPLETE`.

Запит відповідає `image_collection_user_action_request.schema.json` і містить actor, exact collection/SKU, expected manifest version/SHA, target type/IDs, decision, evidence refs, timestamp та idempotency key.

## Правила виконання

1. Дія застосовується тільки до названих source/asset/collection IDs.
2. Stale manifest binding дає `STALE_COLLECTION_INPUT`; дія не застосовується.
3. Повтор exact payload/idempotency key повертає попередній receipt; інший payload із тим самим key дає `IDEMPOTENCY_KEY_CONFLICT`.
4. `PROVIDE_LAWFUL_ACCESS_ARTIFACT` потребує registered evidence artifact ID; token/password у payload заборонені.
5. `EXCLUDE_SOURCE_FROM_SCOPE` не видаляє source record і provenance.
6. Asset accept/reject не змінює Reviewer/Skeptic verdict; це окреме human disposition.
7. `CONFIRM_COLLECTION_COMPLETE` допустимий лише для target type `COLLECTION`, media gate `READY_FOR_HUMAN_REVIEW` і не в `PILOT_REVIEW_ONLY`.
8. Лише receipt людини може встановити `COLLECTION_READY`.
9. Human action не надає publication authority й не запускає Passport delta повторно.
10. Result receipt відповідає `image_collection_user_action_receipt.schema.json`.

## Acceptance tests

- UI state без evidence refs відхиляється.
- Кожний UI state має рівно одну next action.
- Open access action має пріоритет над review progress.
- `COLLECTION_READY` без `CONFIRM_COLLECTION_COMPLETE` receipt відхиляється.
- Complete action у `PILOT_REVIEW_ONLY` відхиляється.
- Stale manifest action не змінює collection.
- Access action без registered artifact відхиляється.
- Exclusion зберігає source record.
- `PASSPORT_TRANSFERRED` потребує `PASSPORT_DELTA_APPLIED` reference.

## Межі доказовості

Контракт визначає projection і user actions, але не доводить реалізацію екрана, notification delivery або live agent execution. Feature flags і provider authority залишаються `OFF`.
