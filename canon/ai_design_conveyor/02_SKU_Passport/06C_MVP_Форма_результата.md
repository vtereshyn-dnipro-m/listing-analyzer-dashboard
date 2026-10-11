# MVP результат проверки Паспорта SKU

Версия: MVP-11  
Дата обновления: 03.10.2026  
Статус: `PILOT_ONLY`

## 1. Карточка проверки

- Verifier mode: `MVP`
- Run ID:
- Parent run ID: null
- Pilot ID:
- SKU:
- Product / configuration / market:
- Проверяемый Паспорт и версия:
- Passport state / SHA-256:
- Входной handoff ID / `ACCEPTED` receipt ID:
- Контракт 00A version / SHA-256:
- Reconciliation прежних OPEN GAP/REQ: checked IDs, stale IDs, решения:
- Package checker result / finding IDs:
- Response checker intake/outbound result / finding IDs:
- Дата проверки:
- Цель проверки:
- Цикл: первичный / повторный №:

## 2. Что реально проверено

| Источник | Просмотрено | Scope/версия | Полезный локатор | Ограничение |
|---|---|---|---|---|
|  | да / частично / нет |  |  |  |

## 3. Положительная обратная связь

- Что заполнено хорошо:
- Какие утверждения имеют понятное подтверждение:
- Какие сильные стороны/полезные материалы уже выявлены:

## 4. Отрицательная обратная связь

- Что заполнено неясно или неполно:
- Что не подтверждено:
- Какие противоречия или риски найдены:

## 5. Findings

| ID | Приоритет | Категория | Поле/утверждение | Evidence или точный локатор | Вывод | Следующее действие |
|---|---|---|---|---|---|---|
| F-01 | критичный / высокий / обычный | факт / claim / мнение / пробел / конфликт |  |  |  |  |

## 6. Приоритетные вопросы

| ID | Связанный finding | Кому задать | Вопрос | Какой факт/evidence нужен |
|---|---|---|---|---|
| Q-01 |  |  |  |  |

### 6A. Source/evidence conflict decision

Заповнюється лише для `review_scope=source_evidence_conflict`.

| Question ID | Conflict ID | Field/object ID | Current value / unit / scope | Current source locator | New value / unit / scope | New source locator | Evidence/authority difference | Allowed decision | Product Truth effect |
|---|---|---|---|---|---|---|---|---|---|
| Q-01 |  |  |  |  |  |  |  | KEEP_CURRENT / ACCEPT_NEW / KEEP_DISPUTED / NOT_APPLICABLE | verified / proposed / disputed / unchanged |

Owner decision не може автоматично встановити `verified` для technical/safety/compliance claim. Після одного decision/candidate update same-intent question без нового evidence заборонений.

## 7. Задания Собирателю

| ID | Приоритет | Связанный finding | Что сделать | Где искать | Что вернуть | Критерий достаточности |
|---|---|---|---|---|---|---|
| C-01 |  |  |  | official/web/YouTube/comments/media/owner | ссылка, выдержка, документ, таймкод, комментарии или ограничение |  |

Для multimedia evidence за наявності додайте URL, таймкод, буквальний опис сцени, exact-SKU applicability, observed use case/JTBD signal, evidence boundary і довідковий rights information status. Creative placement, монтаж і publication approval не включаються.

## 8. Критичные claims для ручного решения

| Claim | Тип: compliance/safety/identity | Что подтверждает | Чего не хватает | Требуемое ручное решение |
|---|---|---|---|---|
|  |  |  |  |  |

## 9. Изменения после цикла Собирателя

- Новые evidence:
- Закрытые findings:
- Оставшиеся findings:
- Новые конфликты/ограничения:

## 10. Итог

- Run status: `READY` / `READY_WITH_LIMITATIONS` / `NOT_READY` / `BLOCKED`
- Краткое обоснование:
- Следующий участник: Collector / Manual reviewer / Process owner
- Ограничения проверки:

Статус не изменяет Паспорт SKU и не является Product Truth decision или разрешением на публикацию.

## 11. Answer delta
Реестр: [06E](06E_MVP_Реестр_вопросов_и_ответов.md)

| question_id | answer_id | Классификация Собирателя | candidate_update/conflict/no_change | Рекомендация Верификатора | Downstream findings 
|---|---|---|---|---|---
| | | ANSWER_WITH_EVIDENCE/CLAIM_ONLY/PARTIAL/CONFLICT/DECLINED/NO_ANSWER/WRONG_SCOPE | | VERIFIED/PARTIAL/REJECTED | 
Для каждого `question_id` — ровно один статус. Partial создаёт новый `related_question_id`.

- APPROVED candidate_update ID:
- Change event ID:
- Подтверждение записи и object/version IDs:
- Действующий статус после проверки записи:

## 12. Canonical dependency receipt

| Dependency | Canonical path | Version / SHA-256 | Read at | contract_status |
|---|---|---|---|---|
| 00A handoff contract |  |  |  |  |
| 06 role/workflow |  |  |  |  |
| 06E lifecycle/IDs/handoff |  |  |  |  |
| DOCX/XLSX template, якщо застосовано |  |  |  |  |
| tools/checkers |  |  |  |  |

Ця форма не визначає lifecycle, enum, schema або closure policy. Усі значення беруться з зафіксованої версії [06E](06E_MVP_Реестр_вопросов_и_ответов.md).

Для необов'язкової залежності, яка не застосовується, dependency record не створюється або поза `contract_status` фіксується `applicability=NOT_APPLICABLE`. `NA`, `FAIL` та довільні локальні значення заборонені у `contract_status`. Невідоме значення робить result schema-invalid за чинною семантикою 06E, але не створює нового Run status і не підтверджує Product Truth.

### 12A. Незалежні осі стану та rule provenance

| state_axis_record_id | subject_type | subject_id | subject_snapshot_or_version | execution_status | evidence_status | contract_status | product_truth_decision | axis_source_refs | rule_provenance_ids[] | evaluated_by/at | supersedes_state_record_id |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ST-<RUN>-<NNN> |  |  |  |  |  |  |  | exact locator per axis |  |  |  |

| rule_provenance_id | subject_type | subject_id | rule_id | rule_source | rule_version | authority | evidence_ids[] | transformation | result |
|---|---|---|---|---|---|---|---|---|---|
| RP-<RUN>-<NNN> |  |  |  |  |  |  |  |  |  |

Значення й semantics беруться тільки з чинної 06E, version/SHA якої зафіксовано в dependency receipt. Structural `PASS` не є Product Truth proof.

## 13. Source artifact trace

| source_artifact_id | format | storage_path | raw hash або URL capture | normalized record IDs | extraction confidence | manual review required |
|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |

## 14. Active blocks і required actions

| block_id | status | blocking_reason | blocking_object_ids | responsible_party + authority evidence if required | resume_condition | active_at | resolved_at |
|---|---|---|---|---|---|---|---|
|  | active/resolved |  |  |  |  |  |  |

| required_action | blocking_reason | blocking_object_ids | responsible_party | resume_condition | action_status |
|---|---|---|---|---|---|
| REQUEST_INFORMATION |  |  |  |  | planned/in_progress/completed/cancelled |

## 15. Terminal decision і handoff fields

- Candidate final Run status:
- Verifier decision ID / time:
- Run closure/checkpoint package ID / SHA-256, заповнює Собиратель після рішення:
- Handoff receipt ID / result:
- DEC ID / subject snapshot / supersedes decision:
- Manifest ID / revision / SHA-256:
- Package seal-binding / validation result:

## 16. Покриття повернених відповідей

| question_id | source_artifact_id | answer_locator | response_received | stated_answer | evidence_sufficiency_reason | residual_evidence | same_intent_repeat | follow_up_question_id_or_none | Основание различия/повтора |
|---|---|---|---|---|---|---|---|---|---|
|  |  |  | true/false |  |  |  | true/false | none |  |

- `received_response_count`:
- `missing_response_count`:
- `residual_evidence_count`:
- `question_registry_found`: true/false
- `collector_source_intake`: registered/pending із точним дорученням
- `outbound_request_artifact_path`:
- `active_question_registry_snapshot_path`:
- `no_repeat_gate`: PASS/FAIL/PENDING

## 17. Рішення про необхідність зовнішнього запиту

| residual_evidence | blocked_deliverable_or_gate | mandatory_basis | internal_resolution_checked | bounded_draft_possible | external_request_necessary | decision_reason |
|---|---|---|---|---|---|---|
|  |  |  |  | true/false | true/false |  |

- `request_necessity_gate`: PASS/FAIL/PENDING
- `delivery_status`: `DRAFT_NOT_SENT | SENT | CANCELLED`
- Посилання на `question_semantic_coverage`:

## 18. Межі доказовості

- Які sources або поля не перевірені:
- Які conclusions є provisional:
- Які decisions залишаються за людиною:
- Чому structural checks не підтверджують Product Truth:

## 19. Наскрізний claim-chain

| passport_field_id/version | evidence_id | source_artifact_id | approved_claim_ref | content_rule_ref | content_tz_field_ref | asset_element_ref | audit_finding_ref | verification_result_ref |
|---|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |  |

Неіснуючий downstream object не створюється для заповнення таблиці. У Паспорт передаються лише стабільні refs/IDs; runtime details залишаються у цьому result/package або downstream audit.
