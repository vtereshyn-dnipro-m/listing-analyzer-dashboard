# Listing Suite contract fixtures

Версія: 2.0  
Дата: 04.10.2026

Fixtures містять вигадані SKU, IDs, paths і SHA-256 та не є продуктовими даними.

- `valid_*` повинні пройти відповідну JSON Schema.
- `invalid_schema_*` повинні бути відхилені schema validation до створення run.
- `contract_reject_*` проходять schema validation, але відхиляються під час preflight за поточним canonical state.
- Очікування для кожного файла задані у `fixture_manifest.json`.
- Transaction fixtures окремо перевіряють archive preparation/commit, atomic switch, rollback, concurrency result, downstream invalidation і заборону двох canonical pointers.
- Intake fixtures перевіряють configured profile, відсутні limits, partial/zero acceptance, path escape і count reconciliation.
- Confirmation/status fixtures перевіряють TTL state, різні required confirmation types, рівно один lookup identifier і read-only replay stored receipt.
- Deployment fixtures перевіряють contract bindings, implementation verification, test receipts і контрольований перехід feature flag `OFF → ON`.
- Restore fixtures перевіряють new-object restore, pre-commit rollback і contract rejection спроби реактивувати archived Passport ID.
- Retention fixtures перевіряють погоджений 1095-day profile, exact deadline, configuration gate, dependency block, legal-hold apply/release, admin-review eligibility та відмову physical deletion.
- Intake boundary matrix перевіряє exact approved limits і `limit + 1`, disallowed archive type, partial confirmation та zero-accepted behavior.
- Authority fixtures перевіряють unbound/BOUND profiles, закритий словник ролей, `PASSPORT_ADMIN` evidence delta, unmapped identity та SKU-scope denial.
- Localization fixtures перевіряють direct resolution, fallback для planned locale та safe mapping невідомого code на `CONTRACT_COMPATIBILITY_ERROR`.

Schema PASS не означає authorization, актуальність snapshot або дозвіл mutation. Contract-negative fixture не можна перетворювати на schema-negative лише для спрощення реалізації.
