# AI Design Graph Shadow Run Contract

## Призначення

`GRAPH_SHADOW_RUN` перевіряє, яке рішення прийняв би execution graph для зафіксованого `Run State`, і порівнює його з очікуваним рішенням чинного маршруту. Режим не запускає агентів, provider calls, завантаження, публікацію або інші зовнішні side effects.

## Область застосування

Shadow run дозволений після schema-valid `Run State` і наявності typed Gate Input для кожного вихідного edge активного node. Для terminal state Gate Input не потрібні.

Послідовність виконання:

`Run State validation → Gate Evaluation → Router Decision assembly → optional simulated state transition → legacy comparison → Shadow Run Report`.

## Вхідні дані

- незмінний `Run State` із pinned graph version та hashes;
- повний набір `ai_design_gate_input` для доступних вихідних edges або Evidence Bundle для автоматичного виклику Gate Input Builder;
- опціональні `expected_outcome` і повний canonical `expected_edge_id` чинного маршруту;
- чинні Edge Registry, schemas та validators.

Скорочені edge labels на кшталт `E010` не є ідентичністю edge. Порівняння виконується лише за повним `edge_id`.

## Правила виконання

1. Runner створює нову output-папку і не перезаписує наявний результат.
2. Кожний Gate Input перевіряється та перетворюється на evidence-bound Gate Evaluation.
3. Набір Gate Evaluations повинен точно дорівнювати набору вихідних edges активних nodes.
4. Один eligible edge дає `EDGE_SELECTED`; більше одного — `HUMAN_ROUTE_DECISION`; відсутність eligible edge — `RUN_BLOCKED`; terminal state — `NO_OP_TERMINAL`.
5. State transition виконується лише як локальна симуляція після `EDGE_SELECTED`. Вхідний state не змінюється.
6. `external_side_effects_executed` завжди дорівнює `0`. Інше значення робить результат недопустимим.
7. Відсутні або stale факти не домислюються й дають `UNRESOLVED`.
8. Evidence Bundle та готові Gate Inputs є взаємовиключними режимами входу.

## Вердикти

- `MATCH` — outcome і selected edge точно збігаються з reference route;
- `DIVERGENCE` — є відмінність у рішеннях;
- `NO_REFERENCE` — graph decision сформовано, але reference route не надано.

`MATCH` підтверджує лише еквівалентність рішення для конкретного snapshot. Він не переводить graph у runtime.

## Acceptance tests

- один eligible edge вибирається та симулюється рівно один перехід;
- кілька eligible edges не обираються автоматично;
- неповний guard evidence дає fail-safe `RUN_BLOCKED`;
- terminal state дає `NO_OP_TERMINAL` без Gate Inputs;
- у всіх сценаріях немає зовнішніх side effects;
- тимчасові regression artifacts видаляються після перевірки.

## Блокери

- неповний candidate set;
- невалідний або не прив'язаний до state Gate Input;
- невідомий чи скорочений `edge_id`;
- спроба перезапису output;
- будь-який зовнішній side effect.

## Межі доказовості

Shadow run перевіряє control-plane рішення та локальну state delta. Він не доводить якість роботи агента, доступність provider, коректність зовнішніх фактів або право на publication.
