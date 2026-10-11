# MVP negative acceptance fixtures Паспорта SKU

Fixture set: `SKU-PASSPORT-NEGATIVE-01`  
Версія набору: `1.0`  
Статус: `PILOT_ONLY`  
Дата: 2026-09-27

## Призначення

Цей файл матеріалізує десять negative acceptance scenarios 06D як точні input/expected fixtures. Він не визначає lifecycle, enum, authority або schema: усі нормативні значення беруться з dependency snapshot нижче. PASS потребує exact comparison усіх наведених expected fields і відсутності prohibited mutations.

## Canonical dependency snapshot

| Dependency | Version | SHA-256 |
|---|---|---|
| `00A_Контракт_передач_Паспорта_SKU.md` | 2.6 | `3C6F7F9C158FD2785B4FB397C39E7C4369FB77DC5071AB57A3EC85D35A3D112E` |
| `06E_MVP_Реестр_вопросов_и_ответов.md` | MVP-10 | `0FE36BD67EB54A16ABE32823467AC4F01A3E8F5274C66531926AF6F60BC4430F` |

Якщо version або SHA не збігається, цей fixture set не виконується й отримує `FIXTURE_DEPENDENCY_MISMATCH`; новий Run status не створюється. Для нового canonical snapshot створюється нова версія fixture set, а цей файл не переписується по суті.

## Fixture contract

Кожен fixture містить:

```yaml
fixture_id:
input_subject:
input_payload:
rule_provenance_input:
state_axis_input:
expected_rule_provenance:
expected_state_axis_record:
expected_package_admissibility:
expected_run_status_effect:
prohibited_mutations: []
```

Відсутнє поле не домислюється. `UNCHANGED` означає відсутність mutation на відповідному об'єкті; це не новий status enum.

## PROV-01 — missing normative rule

```yaml
fixture_id: PROV-01
input_subject: {subject_type: derived_fact, subject_id: FACT-T01, snapshot: v1}
input_payload: {candidate_value: "42", proposed_operation: update}
rule_provenance_input: {rule_id: null, rule_source: null, rule_version: null}
state_axis_input: {state_axis_record_id: ST-RUN-T01-001}
expected_rule_provenance: {authority: UNKNOWN, result: PROPOSAL_ONLY}
expected_state_axis_record: {subject_id: FACT-T01, product_truth_decision: NONE}
expected_package_admissibility: false
expected_run_status_effect: UNCHANGED
prohibited_mutations: [passport_write, gap_close, blocking_decision, product_truth_upgrade]
```

## PROV-02 — optional example promoted to default

```yaml
fixture_id: PROV-02
input_subject: {subject_type: classification, subject_id: CLS-T02, snapshot: v1}
input_payload: {classification: DEFAULT_X, only_basis: optional_example}
rule_provenance_input: {authority: CORE_DEFINED, rule_source: optional_example}
state_axis_input: {state_axis_record_id: ST-RUN-T02-001}
expected_rule_provenance: {authority: PROPOSED, result: PROPOSAL_ONLY}
expected_state_axis_record: {subject_id: CLS-T02, product_truth_decision: NONE}
expected_package_admissibility: false
expected_run_status_effect: UNCHANGED
prohibited_mutations: [default_assignment, passport_write, gap_close, blocking_decision]
```

## PROV-03 — missing or mismatched RP reference

```yaml
fixture_id: PROV-03
input_subject: {subject_type: conflict_resolution, subject_id: CON-T03, snapshot: v2}
input_payload: {rule_provenance_ids: [RP-RUN-T03-001]}
rule_provenance_input: {rule_provenance_id: RP-RUN-T03-001, subject_type: derived_fact, subject_id: FACT-OTHER}
state_axis_input: {state_axis_record_id: ST-RUN-T03-001}
expected_rule_provenance: {binding_valid: false}
expected_state_axis_record: {subject_id: CON-T03, product_truth_decision: NONE}
expected_package_admissibility: false
expected_run_status_effect: UNCHANGED
prohibited_mutations: [conflict_close, passport_write, product_truth_upgrade]
```

## STATE-01 — empty evidence result

```yaml
fixture_id: STATE-01
input_subject: {subject_type: evidence_evaluation, subject_id: E-T04, snapshot: v1}
input_payload: {raw_result: "", normalized_measurement: null}
rule_provenance_input: {rule_provenance_ids: [RP-RUN-T04-001]}
state_axis_input: {execution_status: completed, evidence_status: null, contract_status: PASS}
expected_rule_provenance: {result: NO_VALUE_OBTAINED}
expected_state_axis_record: {evidence_status: EVIDENCE_UNAVAILABLE, product_truth_decision: NONE}
expected_package_admissibility: true
expected_run_status_effect: UNCHANGED
prohibited_mutations: [normalize_empty_to_zero, create_verified_evidence, product_truth_upgrade]
```

## STATE-02 — success envelope without measurements

```yaml
fixture_id: STATE-02
input_subject: {subject_type: tool_result_evaluation, subject_id: TOOL-T05, snapshot: v1}
input_payload: {success: true, measurements: null}
rule_provenance_input: {rule_provenance_ids: [RP-RUN-T05-001]}
state_axis_input: {execution_status: success, evidence_status: null, contract_status: PASS}
expected_rule_provenance: {result: EXECUTION_ONLY_NO_MEASUREMENT}
expected_state_axis_record: {execution_status: success, evidence_status: EVIDENCE_UNAVAILABLE, product_truth_decision: NONE}
expected_package_admissibility: true
expected_run_status_effect: UNCHANGED
prohibited_mutations: [create_measurement, create_verified_evidence, passport_write, product_truth_upgrade]
```

## HANDOFF-01 — Passport changed after handoff

```yaml
fixture_id: HANDOFF-01
input_subject: {subject_type: run_preflight, subject_id: RUN-T06, snapshot: handoff-1}
input_payload: {handoff_passport_version: 7, current_passport_version: 8, handoff_sha: AAA, current_sha: BBB}
rule_provenance_input: {rule_provenance_ids: [RP-RUN-T06-001]}
state_axis_input: {state_axis_record_id: ST-RUN-T06-001}
expected_rule_provenance: {result: STALE_PASSPORT_INPUT}
expected_state_axis_record: {contract_status: PASS, product_truth_decision: NONE}
expected_package_admissibility: false
expected_run_status_effect: BLOCKED
prohibited_mutations: [start_processing, passport_write, parent_package_mutation]
```

## IDENTITY-01 — wrong SKU or variation

```yaml
fixture_id: IDENTITY-01
input_subject: {subject_type: evidence_applicability, subject_id: E-T07, snapshot: v1}
input_payload: {target_sku: SKU-A, evidence_sku: SKU-B, variation_match: false}
rule_provenance_input: {rule_provenance_ids: [RP-RUN-T07-001]}
state_axis_input: {state_axis_record_id: ST-RUN-T07-001}
expected_rule_provenance: {result: IDENTITY_SCOPE_CONFLICT}
expected_state_axis_record: {evidence_status: EVIDENCE_UNAVAILABLE, product_truth_decision: NONE}
expected_package_admissibility: true
expected_run_status_effect: UNCHANGED
prohibited_mutations: [bind_evidence_to_target_fact, verify_target_fact, passport_write]
```

## STATE-03 — structural PASS without Product Truth proof

```yaml
fixture_id: STATE-03
input_subject: {subject_type: candidate_update, subject_id: CHG-T08, snapshot: v1}
input_payload: {schema_valid: true, evidence_ids: []}
rule_provenance_input: {rule_provenance_ids: [RP-RUN-T08-001]}
state_axis_input: {execution_status: success, contract_status: PASS, evidence_status: EVIDENCE_UNAVAILABLE}
expected_rule_provenance: {result: STRUCTURAL_PASS_ONLY}
expected_state_axis_record: {contract_status: PASS, evidence_status: EVIDENCE_UNAVAILABLE, product_truth_decision: NONE}
expected_package_admissibility: false
expected_run_status_effect: UNCHANGED
prohibited_mutations: [approve_change, passport_write, product_truth_upgrade]
```

## STATE-04 — missing, stale or global state record

```yaml
fixture_id: STATE-04
input_subject: {subject_type: blocking_decision, subject_id: BLK-T09, snapshot: v3}
input_payload: {state_axis_record_id: ST-RUN-T09-001}
rule_provenance_input: {rule_provenance_ids: [RP-RUN-T09-001]}
state_axis_input: {state_axis_record_id: ST-RUN-T09-001, subject_id: GLOBAL-RUN, subject_snapshot_or_version: v1}
expected_rule_provenance: {binding_valid: true}
expected_state_axis_record: {binding_valid: false}
expected_package_admissibility: false
expected_run_status_effect: UNCHANGED
prohibited_mutations: [activate_block, change_run_status, passport_write]
```

## CONTRACT-01 — unrecognized contract status

```yaml
fixture_id: CONTRACT-01
input_subject: {subject_type: dependency_check, subject_id: DEP-T10, snapshot: v1}
input_payload: {dependency_id: 06E, supplied_contract_status: FAIL}
rule_provenance_input: {rule_provenance_ids: [RP-RUN-T10-001]}
state_axis_input: {state_axis_record_id: ST-RUN-T10-001, contract_status: FAIL}
expected_rule_provenance: {result: UNRECOGNIZED_RESPONSE_SHAPE}
expected_state_axis_record: {contract_status: UNRECOGNIZED_RESPONSE_SHAPE, product_truth_decision: NONE}
expected_package_admissibility: false
expected_run_status_effect: UNCHANGED
prohibited_mutations: [accept_local_status, change_run_status, passport_write, product_truth_upgrade]
```

## Acceptance

- Усі десять fixtures виконуються проти одного dependency snapshot.
- Exact comparison охоплює кожне expected field і всі `prohibited_mutations`.
- Відсутність prohibited mutation перевіряється read-back відповідного Passport/package object.
- Вільне формулювання, близький за змістом статус або reviewer interpretation не замінює exact expected value.
- Structural fixture PASS не є доказом runtime production readiness або правильності Product Truth поза цим bounded набором.
