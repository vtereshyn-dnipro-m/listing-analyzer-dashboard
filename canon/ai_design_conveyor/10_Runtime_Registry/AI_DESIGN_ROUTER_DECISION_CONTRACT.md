# AI Design Router Decision Contract

## Призначення

Router визначає єдиний дозволений наступний edge для конкретного immutable Run State snapshot. Він не виконує node, не змінює Run State і не створює новий маршрут під час виконання.

## Область застосування

Contract застосовується після schema-valid Run State і до state-transition writer. Кожне рішення прив'язане до `run_state_sha256`, graph version та точного набору active nodes.

## Вхідні дані

- immutable Run State snapshot;
- active Node Registry;
- active Edge Registry;
- immutable Typed Gate Evaluation records для кожного candidate з path і SHA-256;
- terminal state, якщо запуск уже завершено.

Текстовий `guard_expression` у Edge Registry є нормативним описом, а не кодом для `eval`. Його результат передається Router лише як `PASS`, `FAIL` або `UNRESOLVED` із evidence refs.

## Правила виконання

1. Candidate set дорівнює всім зареєстрованим outgoing edges усіх active nodes.
2. Router не може приховати candidate, щоб штучно отримати однозначний вибір.
3. Candidate дослівно відтворює immutable Typed Gate Evaluation; Router validator звіряє path, SHA-256 та всі copied results.
4. Edge є eligible лише коли він registered, state-available, а trigger, guard, payload, receipts, authority та receiver precheck пройдені.
5. Один eligible edge дає `EDGE_SELECTED`.
6. Два або більше eligible edges дають `HUMAN_ROUTE_DECISION`; Router не використовує `first match`, `last writer wins`, cost або власну перевагу.
7. Нуль eligible edges дає `RUN_BLOCKED`; відсутність registered outgoing edge фіксується як `UNROUTABLE_CASE`.
8. Terminal run дає `NO_OP_TERMINAL` і не створює нового переходу.
9. Cost-bearing provider edge потребує явного `authority_result = PASS`; `NOT_REQUIRED` для нього заборонено.
10. Router output не є transition receipt і не дозволяє side effect. Його може застосувати лише окремий state-transition writer після повторної перевірки hash та edge identity.

## Ролі та відповідальність

- deterministic gate owners створюють typed check results;
- Router порівнює candidate set і застосовує closed decision rules;
- Human Route Decision Owner вирішує лише справжню неоднозначність або unknown case;
- state-transition writer окремо перевіряє та застосовує selected edge.

## Вердикти

- `EDGE_SELECTED` — рівно один eligible edge;
- `RUN_BLOCKED` — немає дозволеного переходу;
- `HUMAN_ROUTE_DECISION` — одночасно допустимі кілька маршрутів;
- `NO_OP_TERMINAL` — run уже terminal.

## Acceptance tests

```powershell
& "C:\Users\ystep\Documents\DM AMAZON\AI Design Conveyor\10_Runtime_Registry\Test-AIDesignRouterDecision.ps1" `
  -DecisionPath "<router decision.json>" `
  -RunStatePath "<immutable run state.json>"
```

Validator перевіряє schema, Run State hash, graph version, active nodes, повноту candidates, exact required receipts, eligibility formula, provider authority та outcome cardinality.

## Блокери

Router fail-closed зупиняється при state hash drift, graph mismatch, пропущеному candidate, unknown edge, unresolved guard, invalid payload, missing receipt, authority gap або receiver rejection.

## Межі доказовості

Router Decision доводить лише коректність вибору edge для конкретного state snapshot. Він не доводить успішне виконання target node і не змінює persisted state.

