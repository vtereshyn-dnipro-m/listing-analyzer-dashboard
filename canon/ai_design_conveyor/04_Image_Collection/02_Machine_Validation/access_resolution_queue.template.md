# Access Resolution Queue

`collection_id`: `<COLLECTION_ID>`  
`task_sku`: `<SKU>`  
`updated_at`: `<ISO-8601>`

Для кожного недоступного social-оригіналу або comments corpus заповнити окремий запис:

```yaml
source_id: SRC-000
source_url: https://example.invalid/source
blocker: SESSION_REQUIRED
requested_human_action: Надати штатний export або виключити source
requested_use:
  - analysis
deadline_or_priority: NORMAL
status: OPEN
resolution_outcome: PENDING
resolution_receipt: null
```

Допустимі `blocker`: `LOGIN_REQUIRED`, `SESSION_REQUIRED`, `COMMENTS_SESSION_REQUIRED`, `PLATFORM_BLOCKED`, `ORIGINAL_UNAVAILABLE`.

`RESOLVED` або `EXCLUDED` потребує receipt із path і SHA-256. Повторний запуск обмежується `ACCESS_RESOLUTION_DELTA` для source IDs із manifest `delta_retry_source_ids`.
