# Контракт мапінгу повноважень Listing Suite

Версія: 1.0  
Дата: 04.10.2026  
Статус: `CONTRACT_READY_BINDING_REQUIRED`; feature flags `OFF`

## Призначення

Однозначно перетворювати перевірені identity claims користувача на канонічні ролі та дозволені дії Listing Suite без довіри до ролі, переданої UI.

## Область застосування

Контракт діє для `SUBMIT_SOURCE_EVIDENCE_DELTA`, `RECREATE_PASSPORT`, `RESTORE_ARCHIVED_PASSPORT`, archive read, archive review, legal-hold apply/release і read-only status lookup. Він не надає publication або physical deletion authority.

## Вхідний контракт

Authorization adapter отримує authenticated subject, verified IdP issuer, immutable subject ID, group/claim set, requested action і exact SKU scope. UI-поле `actor_authority` є лише заявленим контекстом запиту та не є доказом повноваження.

Adapter використовує лише versioned profile за `listing_suite_authority_mapping_profile.schema.json`. Реальні IdP group IDs додаються deployment owner у `idp_bindings`; secrets і access tokens у profile не зберігаються.

## Канонічні ролі

- `DATA_CONTRIBUTOR`: передача нових source artifacts і перегляд результату власного запиту у дозволеному SKU scope.
- `PRODUCT_OWNER`: права evidence delta, read active Passport та archive read у дозволеному SKU scope.
- `PRODUCT_OWNER_WITH_RECREATE_AUTHORITY`: права `PRODUCT_OWNER` плюс `RECREATE_PASSPORT` із двома чинними confirmations.
- `PASSPORT_ADMIN`: evidence delta, recreate, restore, archive read/review, legal hold, release та recovery.
- `AUDITOR`: read-only active Passport, history, receipts та archive read.
- `LEGAL_OWNER`: legal-hold apply і release власного hold; без Passport mutation.
- `AUDIT_OWNER`: legal-hold apply для audit scope і release власного hold; без Passport mutation.

## Правила виконання

1. Authentication, role mapping і SKU scope — три окремі перевірки; успіх однієї не замінює інші.
2. Користувач може мати кілька ролей; дозволені дії об'єднуються, але scope не розширюється.
3. `PASSPORT_ADMIN` дозволено `SUBMIT_SOURCE_EVIDENCE_DELTA`; це є канонічним вирівнюванням Integration Contract зі schema.
4. Невідомий issuer, group або subject без binding дає `AUTHORITY_NOT_MAPPED`.
5. Відсутній, hash-invalid або `BINDING_REQUIRED` profile дає `AUTHORITY_PROFILE_NOT_ACTIVE`.
6. Дія поза дозволеним набором дає `ACTION_NOT_AUTHORIZED`.
7. Роль без exact SKU scope дає `SKU_SCOPE_DENIED`; роль не означає глобальний доступ.
8. `PRODUCT_OWNER_WITH_RECREATE_AUTHORITY` є окремим explicit binding, а не автоматичним наслідком `PRODUCT_OWNER`.
9. Legal hold може зняти actor із тією самою canonical role, яка його наклала, або `PASSPORT_ADMIN`; потрібен попередній apply receipt.
10. Зміна profile застосовується тільки до нової authorization evaluation і не переписує історичні receipts.
11. Кожна evaluation випускає receipt за `listing_suite_authority_evaluation_receipt.schema.json`.

## Стани та вердикти

- `AUTHORIZED`: identity, binding, action і SKU scope пройдені.
- `DENIED`: mutation/read не виконуються; reason code обов'язковий.
- `BINDING_REQUIRED`: canonical matrix затверджена, але реальні IdP identifiers ще не прив'язані.
- `BOUND`: profile містить перевірені IdP bindings і може проходити integration tests.

## Acceptance tests

- UI самостійно передав адміністративну роль → `DENIED` без verified IdP mapping.
- Unmapped user/group → `AUTHORITY_NOT_MAPPED`.
- Valid role, wrong SKU scope → `SKU_SCOPE_DENIED`.
- `DATA_CONTRIBUTOR` на recreate → `ACTION_NOT_AUTHORIZED`.
- `PASSPORT_ADMIN` на evidence delta → `AUTHORIZED`.
- `PRODUCT_OWNER` не отримує recreate без окремого `PRODUCT_OWNER_WITH_RECREATE_AUTHORITY` binding.
- Кілька ролей об'єднують actions, але не SKU scopes.
- Profile `BINDING_REQUIRED` або hash mismatch → fail-closed.
- Жодна роль не отримує publication чи physical deletion authority.

## Межі доказовості

Контракт і production-candidate profile визначають canonical RBAC semantics. Реальний IdP, group IDs, claim names і directory membership ще не підключені; тому `LS-CFG-005` залишається `BINDING_REQUIRED`, а всі mutation flags — `OFF`.
