# Політика зберігання архівних Паспортів SKU

Версія: 1.0  
Дата: 04.10.2026  
Статус: `PROFILE_APPROVED_FOR_IMPLEMENTATION`; feature flag `OFF`; physical deletion не дозволено цим контрактом

## Призначення

Визначити lifecycle immutable archive після recreate або restore, правила доступу, legal hold і момент адміністративного review без автоматичного чи користувацького видалення.

## Область застосування

Політика поширюється на archived Passport objects, archive manifests, archive receipts і пов'язані source registries. Вона не поширюється на звичайне версіонування active Passport і не надає publication authority.

## Основні правила

1. Archived object є immutable та має stable locator, manifest SHA-256 і lineage.
2. Звичайний UI не приховує факт існування архівної версії, але не відкриває її без archive-read authority.
3. Archive read дозволено тільки `PRODUCT_OWNER | PASSPORT_ADMIN | AUDITOR` у відповідному SKU scope.
4. Закінчення retention period не видаляє дані: object переходить лише до `ELIGIBLE_FOR_ADMIN_REVIEW`.
5. `LEGAL_HOLD` зупиняє будь-який purge review до explicit release receipt.
6. Open investigation, unresolved recovery, active restore reference або audit dependency також блокують purge eligibility.
7. Listing Suite UI, Координатор і агенти не мають physical deletion authority.
8. Фізичне видалення потребує окремого майбутнього admin purge contract, якого немає у v1.

## Deployment profile

Machine-readable profile відповідає `listing_suite_archive_retention_profile.schema.json` і обов'язково містить:

- retention period у днях;
- archive read roles;
- review owner;
- legal-hold authority;
- effective date та profile SHA-256.

Погоджений production-candidate profile: `Listing_Suite_Archive_Retention_Profile_v1.0.json`.

- `retention_period_days=1095`;
- строк рахується від `archived_at` конкретного archive receipt;
- `review_owner_id=PASSPORT_ADMIN`;
- `legal_hold_authorities=PASSPORT_ADMIN | LEGAL_OWNER | AUDIT_OWNER`;
- archive-read roles: `PRODUCT_OWNER | PASSPORT_ADMIN | AUDITOR`.

`profile_sha256` обчислюється як SHA-256 compact UTF-8 JSON зі стабільним порядком полів без самого поля `profile_sha256`. Відсутній, непідписаний або hash-invalid profile дає `RETENTION_POLICY_NOT_CONFIGURED`; архів зберігається безстроково до виправлення configuration.

## Legal hold lifecycle

Накладення та зняття hold фіксуються окремим immutable receipt за `listing_suite_archive_legal_hold_receipt.schema.json`. Hold може накласти `PASSPORT_ADMIN`, `LEGAL_OWNER` або `AUDIT_OWNER`. Зняти hold може та сама canonical role, що його наклала, або `PASSPORT_ADMIN`; release receipt обов'язково посилається на receipt накладення.

Пріоритет evaluation: несанкціонований purge → `PURGE_NOT_AUTHORIZED`; active legal hold → `LEGAL_HOLD`; active dependency → `BLOCKED_BY_DEPENDENCY`; відсутній валідний profile → `RETAINED`; до deadline → `RETAINED`; на deadline або після нього → `ELIGIBLE_FOR_ADMIN_REVIEW`.

## Стани evaluation

- `RETAINED` — строк не завершився або configuration відсутня;
- `LEGAL_HOLD` — діє hold;
- `BLOCKED_BY_DEPENDENCY` — існує investigation, recovery, restore або audit dependency;
- `ELIGIBLE_FOR_ADMIN_REVIEW` — строк завершився, hold/dependency відсутні;
- `PURGE_NOT_AUTHORIZED` — отримана спроба фізичного видалення без окремого контракту.

Жоден із цих станів не означає physical deletion.

## Acceptance tests

- Відсутній profile → `RETAINED` + `RETENTION_POLICY_NOT_CONFIGURED`.
- До retention deadline → `RETAINED`.
- На `archived_at + 1095 days` і після deadline без hold/dependency → тільки `ELIGIBLE_FOR_ADMIN_REVIEW`.
- Legal hold має пріоритет над deadline.
- Active restore або recovery reference → `BLOCKED_BY_DEPENDENCY`.
- Будь-який purge із цього контуру → `PURGE_NOT_AUTHORIZED`, archive unchanged.
- Read attempt без authority → access denied без розкриття archive content.

## Межі доказовості

Політика та погоджений profile визначають retention evaluation, але не реалізують storage lifecycle, не активують feature flag і не дозволяють physical deletion.
