# Расхождения в каноне AI Design Conveyor

Производный отчёт `canon/check_references.py` по снимку `canon/MANIFEST.json`.
Канон не правится; код берёт ФАЙЛ из снимка, а не версию из ссылки.

## 1. Ссылки на версию или SHA соседа

Всего: 20.

| Где ссылка | На что | Указано | В файле | SHA |
|---|---|---|---|---|
| `02_SKU_Passport/00A_Контракт_передач_Паспорта_SKU.md` | `Listing_Suite_Integration_Contract.md` | 1.1 | 1.2 | — |
| `02_SKU_Passport/02B_Шаблон_запуска_агента_собирателя.md` | `00A_Контракт_передач_Паспорта_SKU.md` | 2.10 | 2.13 | — |
| `02_SKU_Passport/02_Агент_собиратель_Паспорта_SKU.md` | `00A_Контракт_передач_Паспорта_SKU.md` | 2.10 | 2.13 | — |
| `02_SKU_Passport/03_Агент_аудитор_качества_Паспорта_SKU.md` | `00A_Контракт_передач_Паспорта_SKU.md` | 2.10 | 2.13 | — |
| `02_SKU_Passport/06D_MVP_Сценарии_приёмки.md` | `06F_MVP_Negative_Fixtures_v1.3.md` | 1.2 | 1.3 | — |
| `02_SKU_Passport/06E_MVP_Реестр_вопросов_и_ответов.md` | `00A_Контракт_передач_Паспорта_SKU.md` | 2.10 | 2.13 | — |
| `02_SKU_Passport/06F_MVP_Negative_Fixtures.md` | `00A_Контракт_передач_Паспорта_SKU.md` | 2.6 | 2.13 | не совпадает |
| `02_SKU_Passport/06F_MVP_Negative_Fixtures_v1.1.md` | `00A_Контракт_передач_Паспорта_SKU.md` | 2.6 | 2.13 | не совпадает |
| `02_SKU_Passport/06F_MVP_Negative_Fixtures_v1.1.md` | `02C_Контракт_выхода_агента_собирателя.md` | 18 | 23 | не совпадает |
| `02_SKU_Passport/06F_MVP_Negative_Fixtures_v1.2.md` | `00A_Контракт_передач_Паспорта_SKU.md` | 2.7 | 2.13 | не совпадает |
| `02_SKU_Passport/06F_MVP_Negative_Fixtures_v1.2.md` | `02C_Контракт_выхода_агента_собирателя.md` | 19 | 23 | не совпадает |
| `02_SKU_Passport/06F_MVP_Negative_Fixtures_v1.3.md` | `00A_Контракт_передач_Паспорта_SKU.md` | 2.10 | 2.13 | не совпадает |
| `02_SKU_Passport/06F_MVP_Negative_Fixtures_v1.3.md` | `02C_Контракт_выхода_агента_собирателя.md` | 20 | 23 | не совпадает |
| `02_SKU_Passport/06_MVP_Агент_верификатор_интервьюер.md` | `00A_Контракт_передач_Паспорта_SKU.md` | 2.10 | 2.13 | — |
| `02_SKU_Passport/Listing_Suite_Developer_Delivery_Package.md` | `Listing_Suite_Integration_Contract.md` | 1.0 | 1.2 | — |
| `02_SKU_Passport/Listing_Suite_Developer_Delivery_Package.md` | `Listing_Suite_UI_Message_Mapping.md` | 1.0 | 1.1 | — |
| `02_SKU_Passport/Listing_Suite_Implementation_Handoff.md` | `Listing_Suite_Integration_Contract.md` | 1.1 | 1.2 | — |
| `02_SKU_Passport/Listing_Suite_Implementation_Handoff.md` | `00_Агент_координатор_конвейера_Паспорта_SKU.md` | 2.7 | 2.9 | — |
| `02_SKU_Passport/Listing_Suite_Implementation_Handoff.md` | `Listing_Suite_UI_Message_Mapping.md` | 1.0 | 1.1 | — |
| `02_SKU_Passport/Listing_Suite_ТЗ_Контент_Паспорт_SKU.md` | `Listing_Suite_Integration_Contract.md` | 1.1 | 1.2 | — |

## 2. Реестры графа против `AI_DESIGN_EXECUTION_GRAPH_CONTRACT.md`

Поле объявлено в контракте обязательным, в реестре его нет.

| Реестр | Поле | Нет у | Всего |
|---|---|---|---|
| `AI_DESIGN_CORE_EDGE_REGISTRY.json` | `action_proposal_schema` | 87 | 87 |
| `AI_DESIGN_CORE_EDGE_REGISTRY.json` | `consequence_tier` | 87 | 87 |
| `AI_DESIGN_CORE_EDGE_REGISTRY.json` | `policy_decision_receipt` | 87 | 87 |
| `AI_DESIGN_CORE_EDGE_REGISTRY.json` | `authority_binding` | 87 | 87 |
| `AI_DESIGN_CORE_EDGE_REGISTRY.json` | `canonical_action_digest_expression` | 87 | 87 |
| `AI_DESIGN_CORE_EDGE_REGISTRY.json` | `execution_broker` | 87 | 87 |
| `AI_DESIGN_CORE_EDGE_REGISTRY.json` | `effect_verification_contract` | 87 | 87 |

## 3. Схема состояния запуска

- `ai_design_run_state.schema.json` → `lifecycle_state` не допускает состояний, которые контракт графа («Стани Run State») объявляет: `RUN_CREATED`, `RUN_FAILED`, `RUN_CANCELLED`.
- `ai_design_run_state.schema.json` → `product_root` требует путь с буквой диска Windows (`^[A-Za-z]:\\.+`); путь тома Unity Catalog (`/Volumes/…`) под него не подходит.

## 4. Эталонные скрипты движка против контрактов

Движок Listing Suite (`services/graph_*.py`) следует контракту там, где скрипт с ним расходится.

- Контракт графа — версия `2.6`, а версия графа `AI-DESIGN-GRAPH-2.6` не совпадает в: `AI_DESIGN_GATE_FACT_PROVIDER_REGISTRY.json` (`AI-DESIGN-GRAPH-2.5`), `AI_DESIGN_E2E_SHADOW_SCENARIOS.json` (`AI-DESIGN-GRAPH-2.5`), `New-AIDesignControlledRunState.ps1` (`AI-DESIGN-GRAPH-2.5`). Факт `graph_version_compatible` сравнивает с реестром поставщиков и поэтому ложен для запуска, закреплённого по контракту, — ребро E310 закрыто.
- Условия вне грамматики `Invoke-AIDesignGateEvaluation.ps1` (эталон бросает исключение, ребро не вычисляется): `E183_RESOLVE_PROMPT_AGENT_RUNTIME`: `route_receipt_count == expected_asset_count`.
- Фактов вида `RUN_STATE_DERIVATION` в реестре поставщиков 83, закрытых функций в `New-AIDesignGateInputs.ps1` — 9. Без функции и потому всегда UNRESOLVED (74): `adapter_resolution`, `admission_verdict`, `agent_resolution_verdict`, `allowed_execution_verdicts`, `amendment_verdict`, `approved_remaining_asset_ids`, `attempt_verdict`, `authority_verdict`, `auto_batch_receipt_valid`, `budget_verdict`, `circuit_breaker_open`, `closeout_evidence_changed`, `closeout_exception_route`, `closeout_recheck_budget_remaining`, `closeout_verdict`, `content_package_qa_verdict`, `content_tz_package_validation`, `content_tz_scenario_control`, `content_tz_self_check`, `correction_request_valid`, `cross_artifact_parity`, `defect_scope_verdict`, `delivery_authority_valid`, `delivery_route`, `evidence_changed`, `execution_inputs_frozen`, `expected_deliverables_draft_exists`, `expected_draft_validation`, `export_validation`, `final_content_decision`, `finishing_acceptance_verdict`, `finishing_required`, `full_collection_rerun_authorized`, `input_check`, `inspection_outcome`, `lease_verdict`, `manual_batch_decision_required`, `new_attempt_evidence`, `next_asset_id`, `next_call_authorized`, `owner_route_decision`, `passport_delta_route`, `policy_changed`, `prior_verdict`, `product_truth_change_required`, `production_admission`, `qa_evidence_complete`, `qa_evidence_refresh_budget_remaining`, `qa_verdict`, `recipient_bound`, `reclassification_attempt`, `recovery_run_state`, `rejection_class`, `reload_attempt_count`, `remaining_expected_asset_ids_count`, `remediation_attempt`, `requested_changes_complete`, `result_revision_new`, `review_decision`, `review_mode`, `reviewed_draft_hash_current`, `rework_attempt`, `rework_route_decision`, `route_class`, `route_receipt_count`, `same_defect_occurrence`, `scope_change_authorized`, `scope_change_required`, `scope_expansion_authorized`, `sealed_execution_record_exists`, `sealed_execution_record_valid`, `semantic_scope_frozen`, `upstream_owner`, `validation_required`.
- `Invoke-AIDesignStateTransition.ps1` не вызывает `Resolve-AIDesignTerminationBudget.ps1`, хотя `AI_DESIGN_STATE_TRANSITION_WRITER_CONTRACT.md` (правила 13–16) требует квитанцию бюджета до записи. Обратные рёбра в эталоне ничем не ограничены.
- `Invoke-AIDesignStateTransition.ps1` исключает применённые рёбра из доступных, а правило 8 контракта записи делает доступными все исходящие рёбра активных узлов. По эталону ребро переделки срабатывает один раз за запуск, и бюджет «3 переделки на ассет» недостижим.
- Сопоставление класса ребра (`CHECKPOINT`, `CONDITIONAL`, `FORWARD`, `RESUME`, `RETRY`, `REWORK`) классу события бюджета (`FORWARD`, `REWORK`, `UPSTREAM_REENTRY`, `QA_EVIDENCE_REFRESH`, `RECLASSIFICATION`, `CHECKPOINT_RESUME`, `OWNER_APPROVED_RESUME`, `HUMAN_WAIT`) в каноне не задано.
- `ai_design_run_state.schema.json` требует `pinned_product_truth` с путём, версией и SHA существующего Паспорта — запуск первичного создания (Паспорта ещё нет) схемой не представим.
