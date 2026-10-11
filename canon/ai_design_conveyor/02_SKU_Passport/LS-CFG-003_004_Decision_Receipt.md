# Decision receipt LS-CFG-003/004

Версія: 1.0  
Дата: 04.10.2026  
Статус: `APPROVED`

## Призначення

Зафіксувати owner-рішення щодо строку зберігання архівних Паспортів SKU, адміністративного review та legal hold для Listing Suite.

## Рішення

- `retention_period_days=1095`.
- Відлік починається від `archived_at` конкретного archive receipt.
- На момент `archived_at + 1095 days` об'єкт отримує лише `ELIGIBLE_FOR_ADMIN_REVIEW`; автоматичне чи фізичне видалення не дозволяється.
- `review_owner_id=PASSPORT_ADMIN`.
- Legal hold можуть накладати `PASSPORT_ADMIN`, `LEGAL_OWNER`, `AUDIT_OWNER`.
- Legal hold може зняти роль, яка його наклала, або `PASSPORT_ADMIN`; потрібен окремий immutable receipt.
- Активні restore/recovery, investigation або audit dependency мають пріоритет над строком і дають `BLOCKED_BY_DEPENDENCY`.
- За відсутності валідного profile архів зберігається безстроково з `RETENTION_POLICY_NOT_CONFIGURED`.

## Сфера дії

Рішення затверджує production-candidate configuration. Воно не активує feature flag, не створює storage lifecycle job і не надає physical deletion authority.

## Підтвердження

- Власник рішення: `PROJECT_OWNER`.
- Погодження: пряма команда користувача в робочому чаті від 04.10.2026 — «согласен».
- Канонічний profile: `Listing_Suite_Archive_Retention_Profile_v1.0.json`.
- Environment: `TEST/STAGING/PRODUCTION_CANDIDATE`; production activation — лише окремим activation receipt.

## Межі доказовості

Receipt підтверджує policy decision, але не реалізацію, не deployment і не видалення архівних об'єктів.
