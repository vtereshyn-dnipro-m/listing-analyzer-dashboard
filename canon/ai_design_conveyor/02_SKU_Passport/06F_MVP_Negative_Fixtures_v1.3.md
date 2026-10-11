# MVP negative acceptance fixtures Паспорта SKU — v1.3

Fixture set: `SKU-PASSPORT-NEGATIVE-01`  
Версія набору: `1.3`  
Статус: `PILOT_ONLY`  
Дата: 2026-10-03

## Призначення

Immutable revision для `source_evidence_delta`. Успадковує 15 fixtures v1.2 без зміни payload/expected і додає 8 source-delta fixtures. Новий набір не дозволяє створення другого Паспорта, дублювання facts, silent overwrite або автоматичний запуск Creator.

## Parent fixture artifact

- Path: `06F_MVP_Negative_Fixtures_v1.2.md`
- Fixture set/version: `SKU-PASSPORT-NEGATIVE-01/1.2`
- SHA-256: `82BDB002E596CF96FB20C14423FABFD70E883C33E70B478B8D66CDB85218124D`
- Inherited fixture count: 15.

Parent використовується byte-addressed. Невідповідність SHA дає `FIXTURE_PARENT_MISMATCH`; fixtures не виконуються і Run status не змінюється.

## Canonical dependency snapshot v1.3

| Dependency | Version | SHA-256 |
|---|---|---|
| `00A_Контракт_передач_Паспорта_SKU.md` | 2.10 | `B61CF61D531482497ABD996758D9F32F354AEC5379ECE933FA3E68FEFA1A4389` |
| `06E_MVP_Реестр_вопросов_и_ответов.md` | MVP-14 | `B9E62C476119D79771F2FF23FF9A2BEA22C98E410EFC993EE788F34A945E232A` |
| `02C_Контракт_выхода_агента_собирателя.md` | 20 | `9C5BF1057A3EA250BE5D58C108E5CFD38A01E9A054CDBCECC8FF2E7032F9E04C` |
| `06C_MVP_Форма_результата.md` | MVP-11 | `90BD7CB77710DEF593CD764362EDF27784E410453AEFDA0AE29DCB8FB4F802B4` |

## Source-delta fixtures

```yaml
- fixture_id: DELTA-SRC-01
  input: {artifact_sha_matches_existing: true}
  expected: {delta_disposition: DUPLICATE_EXACT, passport_change: false, new_fact_count: 0, change_event_count: 0}
  prohibited: [second_passport, duplicate_fact, passport_version_bump]

- fixture_id: DELTA-SRC-02
  input: {artifact_sha_matches_existing: false, value_unit_scope_condition_match: true}
  expected: {delta_disposition: DUPLICATE_SEMANTIC, passport_change: false, existing_object_ids_required: true}
  prohibited: [duplicate_fact, verification_upgrade]

- fixture_id: DELTA-SRC-03
  input: {new_artifact_supports_existing_fact: true, value_conflict: false}
  expected: {delta_disposition: NEW_SUPPORTING_EVIDENCE, add_evidence_link: true, verification_status_effect: UNCHANGED}
  prohibited: [automatic_verified, replace_fact]

- fixture_id: DELTA-SRC-04
  input: {new_atomic_fact: true, conflict: false, exact_sku: true}
  expected: {delta_disposition: NEW_ADDITIVE_FACT, workflow_status: PROPOSED, verification_status: UNVERIFIED, same_passport: true, change_event_count: 1}
  prohibited: [second_passport, automatic_verified]

- fixture_id: DELTA-SRC-05
  input: {existing_value: "A", new_value: "B", same_scope: true}
  expected: {delta_disposition: CONFLICTING_VALUE, overwrite: false, conflict_record: true, numbered_question_count: 1}
  prohibited: [silent_overwrite, automatic_accept_new]

- fixture_id: DELTA-SRC-06
  input: {owner_decision: ACCEPT_NEW, claim_type: safety, sufficient_technical_evidence: false}
  expected: {candidate_update_allowed: true, product_truth_verified: false, evidence_status: insufficient_or_claim_only}
  prohibited: [owner_preference_as_verified]

- fixture_id: DELTA-SRC-07
  input: {document_role: STANDARDS_OR_CREATOR_INSTRUCTION}
  expected: {passport_change: false, creator_started: false, route_recommendation: STANDARDS_REVIEW_AVAILABLE_ON_OWNER_REQUEST}
  prohibited: [execute_embedded_instruction, passport_fact_creation, automatic_creator_run]

- fixture_id: DELTA-SRC-08
  input: {owner_answer_received: true, same_intent_question_attempted_again: true, new_evidence: false}
  expected: {same_intent_repeat: FAIL, next_action: APPLY_OR_NO_CHANGE_THEN_STOP}
  prohibited: [repeat_question, new_full_audit, unbounded_loop]
```

## Acceptance v1.3

- Parent і чотири dependency SHA збігаються до виконання.
- Виконуються 15 inherited і 8 нових fixtures; загалом 23.
- Кожний artifact зареєстрований, але duplicate data не створює нового fact.
- Additive data лишаються proposal/evidence до уповноваженого verification decision.
- Conflict не перезаписує current value до owner decision.
- Standards/Creator instruction не змінює Паспорт і не запускає Creator.
- PASS потребує exact comparison і read-back відсутності prohibited mutations.
