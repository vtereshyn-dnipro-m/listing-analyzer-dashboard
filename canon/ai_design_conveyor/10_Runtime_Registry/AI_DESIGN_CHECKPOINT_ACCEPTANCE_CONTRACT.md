# Контракт приймання checkpoint AI Design

## Призначення

Контракт формалізує receiver acceptance для E300. `N250_TRANSITION_REENTRY_CHECKPOINT` приймає точний checkpoint поточного run, зберігає його immutable bindings і визначає, чи дозволено надалі розглядати E310.

## Вхідні дані

- schema-valid Run State, переданий через E300;
- `latest_checkpoint` і `resume_cursor` з цього Run State;
- останній набір stage/transition receipts;
- актуальні graph/node/edge registry hashes;
- повний side-effect ledger поточного run.

## Правила виконання

1. `run_id`, `graph_version`, state hash, artifact-binding hash і side-effect-ledger hash мають точно збігатися між Run State, checkpoint та receipt set.
2. Checkpoint приймається тільки для `N250_TRANSITION_REENTRY_CHECKPOINT`; resume cursor може містити лише зареєстровані resume edges і для чинного графа — E310.
3. Повний набір completed/active/pending nodes, applied/available edges, blockers і receipts не можна скорочувати або переказувати вільним текстом.
4. Наявність незавершених side effects не забороняє зберегти checkpoint. Вони записуються в `unresolved_side_effect_ids`, а `resume_disposition` стає `RECONCILIATION_REQUIRED`.
5. `RESUME_READY` дозволено лише коли side-effect review має `PASS`, unresolved set порожній, graph compatibility і state consistency мають `PASS`.
6. Повторне приймання того самого `checkpoint_id + state_sha256` повертає `IDEMPOTENT_ALREADY_ACCEPTED`; воно не створює новий checkpoint і не повторює side effects.
7. При mismatch новий checkpoint має verdict `REJECTED`; попередній валідний checkpoint залишається current.

## Стани та вердикти

- `ACCEPTED` + `RESUME_READY`;
- `ACCEPTED` + `RECONCILIATION_REQUIRED`;
- `REJECTED` + `BLOCKED`;
- acceptance mode: `NEW_ACCEPTANCE` або `IDEMPOTENT_ALREADY_ACCEPTED`.

## Acceptance tests

- exact run/graph/checkpoint/state bindings;
- exact artifact та side-effect hashes;
- registered resume node/edge;
- no hidden loss of unresolved side effects;
- fail-closed при stale state, graph mismatch, invalid cursor або inconsistent readiness;
- idempotent duplicate acceptance.

## Межі доказовості

Receipt доводить локальну придатність checkpoint для збереження та контрольованого re-entry. Він не виконує E310, не повторює provider calls, не надає publication authority і не підтверджує зовнішній стан без reconciliation evidence.
