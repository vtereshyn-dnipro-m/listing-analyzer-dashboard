# AI Design Gate Fact Resolver and Gate Input Builder Contract

## Призначення

Компонент перетворює поточний `Run State` та нормалізований Evidence Bundle на повний набір Gate Inputs для всіх вихідних edges активних nodes. Він не виконує LLM-інтерпретацію документів і не створює відсутні факти.

## Вхідні дані

- schema-valid, hash-pinned `Run State`;
- Core Edge Registry;
- Gate Fact Provider Registry;
- опціональний Evidence Bundle, прив'язаний до exact `run_id` і `run_state_sha256`.

Evidence Bundle містить лише нормалізовані fact evidence та edge controls. Для зовнішнього факту обов'язкові provider class, artifact type, source path/SHA-256, exact state binding, freshness та evidence references.

## Правила виконання

1. Builder визначає вихідні edges лише з активних nodes.
2. Необхідні facts виводяться з guard expressions; довільні facts не запитуються.
3. `RUN_STATE_DERIVATION` обчислюється тільки закритими функціями для явно підтриманих facts.
4. Інший факт приймається лише при точній відповідності Provider Registry, source hash, run binding і `CURRENT` freshness.
5. Відсутній, stale або неперевірений факт не включається у facts і фіксується як unresolved у Build Manifest. Gate Evaluator трактує його як `UNRESOLVED`.
6. Відсутній edge control формує `UNRESOLVED` trigger/payload/receiver та `MISSING` required receipts. Authority має `NOT_REQUIRED`, крім provider-execution edge, де вона залишається `UNRESOLVED`.
7. Builder створює нову output-папку, не змінює Run State й не виконує зовнішніх side effects.
8. Shadow Run може прийняти `EvidenceBundlePath` і викликати Builder самостійно; одночасна передача Evidence Bundle та готових Gate Inputs заборонена.

## Acceptance tests

- для initial state два identity facts виводяться детерміновано й E010 стає eligible;
- без Evidence Bundle створюються inputs для всіх outgoing edges, але невідомі дані залишаються unresolved;
- неправильний state hash у Evidence Bundle відхиляється;
- повторний запис у наявну output-папку відхиляється;
- `external_side_effects_executed = 0`.

## Межі доказовості

Builder перевіряє нормалізовані evidence records, але не перетворює довільні DOCX, відео або повідомлення на факти. Таке перетворення залишається відповідальністю відповідного validator, agent або human reviewer, який видає допустимий receipt.
