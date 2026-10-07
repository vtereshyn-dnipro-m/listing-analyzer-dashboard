# AI Design Execution Lease and Idempotency Contract

## Призначення

Не допустити подвійний provider call, подвійне списання budget або concurrent activation двох output versions для одного exact asset/operation.

## Вхідні дані

- exact run, node, asset, operation і runtime fingerprint;
- sealed execution record та idempotency key;
- current lease, owner process і expiry;
- provider invocation state та terminal receipt;
- output hash validation і current canonical version state.

## Правила виконання

1. Exclusive lease має scope `run_id + asset_id + operation`; незалежні assets не блокують один одного.
2. Lease не замінює execution authority, budget, adapter resolution, admission або sealed invocation acceptance.
3. Active lease іншого worker дає `LEASE_ALREADY_HELD`. Exact terminal result дає `IDEMPOTENT_RESULT_EXISTS` без нового call.
4. Expired lease можна перевидати тільки коли provider invocation має `NOT_STARTED`. `ACCEPTED | IN_FLIGHT | UNKNOWN` потребує reconciliation.
5. Binding mismatch idempotency key, fingerprint або sealed record дає `LEASE_CONFLICT`.
6. Output спочатку має invocation-specific identity. Canonical commit дозволено лише після terminal receipt і hash validation; current version активується атомарно, старі версії не перезаписуються.
7. Lease release не є publication authority і не приховує usage або side-effect ledger.

## Вердикти

- `LEASE_ACQUIRED`;
- `LEASE_ALREADY_HELD`;
- `IDEMPOTENT_RESULT_EXISTS`;
- `LEASE_EXPIRED_RECONCILIATION_REQUIRED`;
- `LEASE_RELEASED`;
- `LEASE_CONFLICT`.

## Acceptance tests

- first acquire;
- duplicate worker;
- idempotent completed result;
- safe expired lease takeover before provider acceptance;
- expired lease after unknown/in-flight invocation;
- binding conflict;
- valid/invalid atomic output commit.

## Межі доказовості

Local lease receipt не доводить external provider outcome. Будь-яка неоднозначність після provider acceptance потребує provider/host reconciliation.
