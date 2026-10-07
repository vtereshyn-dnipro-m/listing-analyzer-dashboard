# Контракт budget і гарантованої завершуваності v1.0

## Призначення

Контракт гарантує, що кожна автоматична гілка AI Design за скінченну кількість переходів досягає успішного terminal state або контрольованого `FAILED_EXHAUSTED`. Очікування людини обліковується окремо й не вважається автоматичним циклом.

## Область застосування

Budget check є обов'язковим precondition для кожного автоматичного edge, включно з forward, rework, retry, resume, recovery та повторним QA. Зміна route, artifact version, defect class, checkpoint або agent не скидає counters.

## Вхідні дані та контракт

Canonical ledger прив'язаний до run, package та immutable revision. Він містить global automatic-transition budget, per-asset і per-package rework, upstream re-entry, QA evidence refresh, reclassification, checkpoint resume, owner-approved resume та defect identity registry.

## Правила виконання

1. До transition writer кожен automatic edge отримує `TERMINATION_BUDGET_ALLOW` або terminal disposition.
2. Кожний дозволений автоматичний edge атомарно збільшує `automatic_transitions_used`; zero-cost automatic transition заборонений.
3. Rework-подія додатково списує відповідний scoped counter.
4. Fingerprint нормалізується з asset, criterion, defect class, locator, expected/observed state і dependency binding. Rename не створює новий budget.
5. Checkpoint, resume та migration переносять counters без reset.
6. Вичерпання будь-якого ліміту встановлює `terminal.is_terminal=true`, `terminal.status=FAILED_EXHAUSTED` і один із exhaustion codes.
7. Human wait не споживає automatic-transition budget; кожний owner-approved resume споживає окремий finite counter.

## Стани та вердикти

- `TERMINATION_BUDGET_ALLOW`;
- `TERMINATION_BUDGET_EXHAUSTED`;
- `ZERO_PROGRESS_TRANSITION_REJECTED`;
- `COUNTER_RESET_REJECTED`;
- `DUPLICATE_DEFECT_IDENTITY_REUSED`.

## Acceptance tests

- кожний automatic transition зменшує global remaining budget;
- вичерпання дає `FAILED_EXHAUSTED`;
- checkpoint не скидає counters;
- різна назва з тим самим normalized fingerprint використовує той самий defect budget;
- reclassification, QA refresh, upstream re-entry та resume не перевищують configured maxima;
- human wait не витрачає automatic budget, але resume витрачає owner-resume budget.

## Метрики

- automatic transitions used/remaining;
- rework transitions per asset/package;
- distinct normalized defects per asset;
- upstream re-entries;
- QA evidence refreshes;
- checkpoint та owner resumes;
- terminal exhaustion reason.

## Блокери

Відсутній або stale ledger, counter reset, zero-progress transition чи невідомий event class блокують edge до запису стану.

## Межі доказовості

Контракт доводить скінченність автоматичних переходів за умови, що transition writer не може обійти resolver. Він не гарантує успішний контент-результат і не обмежує тривалість очікування людини.
