# AI Design Recovery and Resume Contract

## Призначення

Відновлювати exact run після session boundary, технічного збою, human pause, budget stop або provider ambiguity без повторення вже виконаних side effects і без повного перезапуску незмінених етапів.

## Вхідні дані

- immutable checkpoint і current Run State;
- exact `run_id`, SKU та pinned graph version;
- hashes Product Truth, Content TZ, Prompt Package й affected artifacts;
- side-effect ledger та terminal/reconciliation state останнього provider invocation;
- current human-decision, authority і production-budget state.

## Правила виконання

1. Resume завжди починається з `N250_TRANSITION_REENTRY_CHECKPOINT`; прямий перехід до downstream node заборонений.
2. Exact checkpoint, run, SKU, graph і artifact bindings перевіряються до вибору маршруту.
3. `UNKNOWN` або `IN_FLIGHT` provider outcome дає тільки `RECONCILIATION_REQUIRED`; повторний provider call заборонений.
4. Pending human decision та exhausted budget зберігають відповідний waiting state. Budget update не обнуляє usage.
5. Зміна bounded downstream artifact створює `TARGETED_REENTRY` до його named owner/node. Незмінені upstream artifacts не перегенеровуються.
6. Зміна SKU або Product Truth, несумісний graph чи invalid checkpoint дають `FULL_RESTART_REQUIRED`.
7. Відновлення не надає provider execution, spend, publication або release authority.

## Стани та вердикти

- `RESUME_FROM_CHECKPOINT` → `RESUME_READY`;
- `RESUME_AFTER_HUMAN_DECISION` → `RESUME_READY`;
- `RESUME_AFTER_BUDGET_UPDATE` → `RESUME_READY`;
- `RECONCILIATION_REQUIRED` → `WAITING_RECONCILIATION`;
- `TARGETED_REENTRY` → `RESUME_READY`;
- `FULL_RESTART_REQUIRED` → `RESTART_REQUIRED`.

## Acceptance tests

- clean checkpoint resume;
- human decision received/pending;
- valid budget update/exhausted budget;
- unknown provider outcome;
- targeted artifact change;
- SKU, Product Truth, graph або checkpoint mismatch;
- no provider call, usage reset чи publication authority.

## Межі доказовості

Локальний receipt доводить лише придатність маршруту відновлення за наданими bindings. External provider state має підтверджуватися provider/host reconciliation evidence.
