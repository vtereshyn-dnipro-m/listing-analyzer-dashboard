# Rights Clearance Queue

`collection_id`: `<COLLECTION_ID>`  
`task_sku`: `<SKU>`  
`updated_at`: `<ISO-8601>`

Для кожного source з `unknown` або `restricted` rights заповнити окремий запис:

```yaml
source_id: SRC-000
source_url: https://example.invalid/source
rights_owner: null
requested_use:
  - analysis
requested_human_action: Встановити правовласника та отримати письмовий дозвіл
deadline_or_priority: NORMAL
status: OPEN
resolution_outcome: PENDING
resolution_receipt: null
```

Допустимі outcomes після рішення: `RIGHTS_CLEARED`, `RIGHTS_DENIED`, `ANALYSIS_ONLY_APPROVED`, `EXCLUDED_BY_OWNER`. Кожне закрите рішення потребує receipt із path і SHA-256. Повторний запуск обмежується `RIGHTS_CLEARANCE_DELTA` для source IDs із manifest `delta_retry_source_ids`.
