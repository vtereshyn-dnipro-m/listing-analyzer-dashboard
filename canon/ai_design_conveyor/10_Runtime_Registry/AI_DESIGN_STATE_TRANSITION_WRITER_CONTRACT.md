# AI Design State-Transition Writer Contract

## Призначення

State-transition writer атомарно застосовує один валідний `EDGE_SELECTED` до immutable Run State snapshot. Writer не обирає маршрут, не виконує target node і не перезаписує попередню версію state.

## Область застосування

Writer працює між Router Decision і виконанням target node. Він змінює лише control-state, названий у `state_delta` вибраного edge, та створює transition receipt/checkpoint.

## Вхідні дані

- schema-valid immutable input Run State;
- schema-valid Router Decision із `EDGE_SELECTED`;
- active Edge Registry;
- current immutable Rework Budget Ledger;
- schema-valid Termination Budget Request і receipt `TERMINATION_BUDGET_ALLOW` для кожного переходу, що не є human wait;
- нові, ще не зайняті paths для output state і transition receipt.

## Правила виконання

1. Input State і Router Decision повторно перевіряються незалежними validators.
2. `run_state_sha256` у decision повинен збігатися з фактичним input state.
3. Selected edge має залишатися registered, state-available і виходити з active source node.
4. Writer приймає лише `EDGE_SELECTED`; blocked, ambiguous або terminal decisions не застосовуються.
5. Input State не перезаписується. Існуючі output/receipt paths викликають fail-closed stop.
6. Source node завершується лише коли `complete_source_node = true`.
7. Target node видаляється з попереднього bucket і активується лише коли `activate_target_node = true`.
8. Selected edge переходить до `applied_edge_ids`; outgoing edges активних nodes стають structurally available для наступної typed evaluation.
9. Open blocker може бути закритий лише edge, названим у його `allowed_recovery_edge_ids`.
10. Transition event і receipt ref додаються до Run State; створюються checkpoint і resume cursor.
11. External side effects writer не виконує і ledger самостійно не доповнює.
12. Спочатку валідуюються temporary output/receipt; лише після `PASS` вони переміщуються на final paths.
13. Кожний non-human-wait transition до зміни Run State проходить `Resolve-AIDesignTerminationBudget.ps1`. Нульова вартість автоматичного переходу заборонена.
14. Writer застосовує edge лише з receipt `TERMINATION_BUDGET_ALLOW`, прив'язаним до current ledger revision, request hash, `run_id`, edge і defect fingerprint, якщо він потрібний.
15. Incremented ledger, transition receipt і нова Run State revision фіксуються як одна атомарна операція. Частковий запис заборонений.
16. `TERMINATION_BUDGET_EXHAUSTED` або `ZERO_PROGRESS_TRANSITION_REJECTED` не активує target node: run отримує terminal status `FAILED_EXHAUSTED` і blocker `LOOP_BUDGET_EXHAUSTED`.
17. Resume, re-entry, checkpoint recovery, graph migration та owner-approved continuation не обнуляють і не зменшують жодного лічильника.
18. Human wait не витрачає automatic-transition budget, але вихід із wait через автоматичний edge знову потребує budget receipt.

## Checkpoint semantics

`checkpoint_payload_sha256` є hash нового state payload після control-state delta та transition history, але до embedding `latest_checkpoint` і `resume_cursor`. Це усуває circular self-hash. Final output SHA-256 окремо зберігається у transition receipt.

## Вердикти

- `TRANSITION_APPLIED` — новий state і receipt створені та перевірені;
- `FAILED_EXHAUSTED` — подальший автоматичний перехід заборонений через вичерпання глобального або scoped budget чи через zero-progress transition;
- будь-яка невідповідність — exception без створення final output;
- наявний final path — immutable overwrite rejection.

## Acceptance tests

```powershell
& "C:\Users\ystep\Documents\DM AMAZON\AI Design Conveyor\10_Runtime_Registry\Invoke-AIDesignStateTransition.ps1" `
  -InputStatePath "<input state.json>" `
  -DecisionPath "<router decision.json>" `
  -OutputStatePath "<new state path.json>" `
  -ReceiptPath "<new receipt path.json>"
```

Незалежна перевірка:

```powershell
& "C:\Users\ystep\Documents\DM AMAZON\AI Design Conveyor\10_Runtime_Registry\Test-AIDesignTransitionReceipt.ps1" `
  -ReceiptPath "<receipt path.json>"
```

## Блокери

Writer зупиняється при invalid input/decision, hash drift, неактивному source, недоступному edge, забороненому blocker recovery, missing/invalid termination-budget receipt, budget exhaustion, zero-progress transition, existing output path, invalid output state або invalid receipt.

## Межі доказовості

Writer доводить control-state transition. Він не доводить виконання target node, не створює його terminal receipt і не надає side-effect authority.
