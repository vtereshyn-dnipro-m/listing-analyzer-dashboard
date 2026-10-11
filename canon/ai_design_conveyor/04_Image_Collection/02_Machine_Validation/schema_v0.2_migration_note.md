# Image Collector manifest migration: v0.1 → v0.2

Дата: 24.09.2026  
Тип зміни: breaking pre-production contract update

## Причина

Schema v0.1 не фіксувала вимогу зберігати всі product-specific artifacts у canonical product root. Додавання required storage contract не сумісне з уже materialized v0.1 manifests, тому machine version підвищено до `v0.2`.

## Зміни

- `schema_version` тепер має значення `v0.2`.
- Додано required object `storage`:
  - `product_root`;
  - `artifact_date`;
  - `collection_root`;
  - `placement_status=PASS`.
- `collection_root` повинен мати форму `<product_root>/артефакти/<artifact_date>/image_collector/<collection_id>`.
- Validator повертає `PRODUCT_ARTIFACT_ROOT_REQUIRED` або `PRODUCT_ARTIFACT_PLACEMENT_INVALID` при порушенні.

## Migration rule

Historical v0.1 manifest не редагується і не оголошується v0.2 автоматично. Для повторного використання створюється новий manifest v0.2 із перевіреним storage block, актуальними file paths/hashes і новим validation result.

## Межі доказовості

Migration підтверджує schema/placement integrity, але не перевіряє зміст media, права, SKU match або readiness до production.
