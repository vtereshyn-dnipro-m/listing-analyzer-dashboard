# AI Design Passport Audit Receipt Contract

Статус: `active_v1.0`

## Призначення

Контракт формалізує payload переходу `E050_ACCEPT_AUDITED_PASSPORT`: результат одного незалежного risk-oriented аудиту повертається Координатору для вибору наступного дозволеного маршруту.

Receipt не є Product Truth decision, не редагує Паспорт, не закриває gaps і не надає publication authority.

## Вхідні дані

- прийнятий input package та його receipt;
- exact SKU/product version;
- current Passport path/version/state/SHA-256;
- Collector package ID/manifest/SHA-256;
- audit report path/SHA-256;
- фактично перевірений handoff scope;
- findings, diagnostics, open gaps/conflicts і evidence refs.

Machine schema: `ai_design_passport_audit_receipt.schema.json`.

## Правила виконання

1. Для E050 дозволені лише `AUDIT_ACCEPTED` і `AUDIT_ACCEPTED_WITH_GAPS`.
2. `AUDIT_ACCEPTED` потребує відсутності open gap/conflict IDs у перевіреному scope.
3. `AUDIT_ACCEPTED_WITH_GAPS` потребує хоча б одного `VERIFIER_INFORMATION_GAP` або open gap/conflict ID та маршруту `READY_FOR_VERIFIER`.
4. `DIAGNOSTIC_METADATA_MISMATCH` та інші технічні diagnostics з читабельними джерелами не стають blocking findings і не створюють rework loop.
5. `CRITICAL_PRODUCT_RISK` або `PACKAGE_OR_COLLECTOR_REWORK` робить E050 непридатним; такий результат маршрутизується окремим edge за 00A.
6. Кожний finding має object refs, evidence refs, cause, next action, owner і closure criterion.
7. `no_material_conflict=true` означає лише відсутність конфлікту, що забороняє E050. Відомі open conflicts можуть бути передані Верифікатору як явні IDs.
8. Receipt immutable та bound до Passport, Collector package, audit report і Run State hashes.

## Стани та вердикти

- `AUDIT_ACCEPTED` — аудит не виявив open knowledge gaps/conflicts у заявленому scope;
- `AUDIT_ACCEPTED_WITH_GAPS` — пакет прийнятий, gaps/conflicts видимі й передані Верифікатору;
- schema-invalid, stale або відсутній receipt — `UNRESOLVED`, а не автоматичний reject.

## Acceptance tests

- exact E050/N050/N020 binding;
- `input_receipt=ACCEPTED` і `handoff_verdict=READY_FOR_VERIFIER`;
- exact Passport/package/report hashes;
- audited scope та audited object refs не порожні;
- verdict узгоджений із gaps/conflicts/findings;
- diagnostics не перетворені на blocking/rework;
- критичні/rework findings не проходять E050;
- authority boundary забороняє Product Truth, canonical write і publication claims.

## Межі доказовості

Receipt доводить лише виконання та результат аудиту в exact scope. Координатор окремо застосовує graph guard і receiver acceptance; Верифікатор окремо працює з gaps/conflicts.
