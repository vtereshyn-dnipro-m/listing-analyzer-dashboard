# Decision receipt LS-CFG-006

Версія: 1.0  
Дата: 04.10.2026  
Статус: `APPROVED`

## Рішення

- Enabled locales: `uk-UA`, `ru-RU`.
- Default і fallback locale: `uk-UA`.
- `en-US`: `PLANNED`, не активується до 100% catalog coverage.
- Resolution order: user preference → organization preference → default locale.
- Machine-readable codes, severity й allowed actions не перекладаються.
- Missing translation або unsupported locale використовує `uk-UA` із явним fallback status.

## Підтвердження

- Власник рішення: `PROJECT_OWNER`.
- Погодження: пряма команда користувача від 04.10.2026 — «подтверждаю».
- Канонічний контракт: `Listing_Suite_Localization_Contract.md`.
- Locale profile: `Listing_Suite_Locale_Profile_v1.0.json`.
- Message catalog: `Listing_Suite_Message_Catalog_v1.0.json`.

## Межі доказовості

Рішення затверджує локалі й каталог, але не підтверджує UI rendering. Production UI flag залишається `OFF` до acceptance tests реалізації.
