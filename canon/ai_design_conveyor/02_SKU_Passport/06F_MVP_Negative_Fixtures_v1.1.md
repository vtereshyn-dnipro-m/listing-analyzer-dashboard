# MVP negative acceptance fixtures Паспорта SKU — v1.1

Fixture set: `SKU-PASSPORT-NEGATIVE-01`  
Версія набору: `1.1`  
Статус: `PILOT_ONLY`  
Дата: 2026-09-27

## Призначення

Це нова immutable revision набору 1.0 для 06E MVP-11. Вона успадковує exact payloads десяти fixtures із parent artifact і додає перевірку canonical locator осей. Parent не переписується.

## Parent fixture artifact

- Path: `06F_MVP_Negative_Fixtures.md`
- Fixture set/version: `SKU-PASSPORT-NEGATIVE-01/1.0`
- SHA-256: `84866588CE3C5920568123432240332265BB645C858295643ABC1A468963CDF0`
- Inherited fixture IDs: `PROV-01`, `PROV-02`, `PROV-03`, `STATE-01`, `STATE-02`, `HANDOFF-01`, `IDENTITY-01`, `STATE-03`, `STATE-04`, `CONTRACT-01`.

Успадкування означає byte-addressed reuse payloads parent artifact; локальна перефраза або інше expected value заборонені. Для виконання v1.1 runner/read-back поєднує inherited payload із новим dependency snapshot нижче. Якщо parent SHA не збігається, набір не виконується.

## Canonical dependency snapshot v1.1

| Dependency | Version | SHA-256 |
|---|---|---|
| `00A_Контракт_передач_Паспорта_SKU.md` | 2.6 | `4CF49E85D715E2C6CCFD449199258F0BD68A32494830F5111B08DB92DD6E138C` |
| `06E_MVP_Реестр_вопросов_и_ответов.md` | MVP-11 | `AD69840A692C3122E90EA99A9A7718DC2AD80E99E5F1811158B9F73AC81530B8` |
| `02C_Контракт_выхода_агента_собирателя.md` | 18 | `D929160128B144F4F9A1AF21630887B680EEB2515110E7EF82C696BDCF35709D` |
| `06C_MVP_Форма_результата.md` | MVP-10 | `9F2D42081087AC8BCD8052DB865309F62B4686D8F8798E7D6D587CEB4FF56BCA` |

Inherited fixtures зберігають свої input/expected payloads. Нормативні locators і schemas беруться з snapshot v1.1. Якщо зміна dependency робить inherited expected value невалідним, fixture отримує `FIXTURE_REBASE_CONFLICT`, а не тихе виправлення.

## Axis source overlay для inherited fixtures

Перед виконанням до inherited `state_axis_input` додається наведений exact overlay. Він не змінює інші input/expected fields parent fixture.

| Fixture | execution_status_source | evidence_status_source | contract_status_source | product_truth_decision_source |
|---|---|---|---|---|
| PROV-01 | `06E MVP-11#normative-status-model` | `Passport v02#3.1.verification_status` | `06E MVP-11#four-independent-axes` | `Passport v02#3-product-truth` |
| PROV-02 | `06E MVP-11#normative-status-model` | `Passport v02#3.1.verification_status` | `06E MVP-11#four-independent-axes` | `06E MVP-11#decision-events` |
| PROV-03 | `06E MVP-11#normative-status-model` | `Passport v02#3.1.verification_status` | `06E MVP-11#four-independent-axes` | `06E MVP-11#decision-events` |
| STATE-01 | `fixture://SKU-PASSPORT-NEGATIVE-01/1.1#mock-operation-contract` | `06E MVP-11#EVIDENCE_UNAVAILABLE` | `06E MVP-11#four-independent-axes` | `Passport v02#3-product-truth` |
| STATE-02 | `fixture://SKU-PASSPORT-NEGATIVE-01/1.1#mock-operation-contract` | `06E MVP-11#EVIDENCE_UNAVAILABLE` | `06E MVP-11#four-independent-axes` | `Passport v02#3-product-truth` |
| HANDOFF-01 | `06E MVP-11#gate-next-run` | `06E MVP-11#normative-status-model` | `06E MVP-11#four-independent-axes` | `06E MVP-11#terminal-closure-handoff` |
| IDENTITY-01 | `06E MVP-11#normative-status-model` | `Passport v02#3.1.applicability` | `06E MVP-11#four-independent-axes` | `Passport v02#3-product-truth` |
| STATE-03 | `06E MVP-11#change-lifecycle` | `Passport v02#3.1.verification_status` | `06E MVP-11#four-independent-axes` | `Passport v02#3-product-truth` |
| STATE-04 | `06E MVP-11#state-axis-record` | `06E MVP-11#state-axis-record` | `06E MVP-11#four-independent-axes` | `06E MVP-11#state-axis-record` |
| CONTRACT-01 | `06E MVP-11#dependency-check` | `06E MVP-11#EVIDENCE_UNAVAILABLE` | `06E MVP-11#four-independent-axes` | `06E MVP-11#decision-events` |

`fixture://SKU-PASSPORT-NEGATIVE-01/1.1#mock-operation-contract` є test-only dependency цього набору: `execution_status` допускає лише literal `success | completed` згідно з конкретним fixture input. Він не є production enum, не експортується до агентських контрактів і не створює Run status.

## STATE-05 — missing axis source locator

```yaml
fixture_id: STATE-05
input_subject: {subject_type: candidate_update, subject_id: CHG-T11, snapshot: v2}
input_payload: {candidate_value: "100", proposed_operation: update}
rule_provenance_input: {rule_provenance_ids: [RP-RUN-T11-001]}
state_axis_input:
  state_axis_record_id: ST-RUN-T11-001
  subject_type: candidate_update
  subject_id: CHG-T11
  subject_snapshot_or_version: v2
  execution_status: completed
  evidence_status: verified
  contract_status: PASS
  product_truth_decision: APPROVED
  axis_source_refs:
    execution_status_source: null
    evidence_status_source: null
    contract_status_source: 06E#four-state-axes
    product_truth_decision_source: null
expected_rule_provenance: {binding_valid: true}
expected_state_axis_record:
  execution_status: null
  evidence_status: null
  contract_status: SCHEMA_UNVERIFIED
  product_truth_decision: NONE
expected_package_admissibility: false
expected_run_status_effect: UNCHANGED
prohibited_mutations: [accept_local_status, approve_change, passport_write, product_truth_upgrade, create_block_without_separate_rule]
```

## Acceptance v1.1

- Parent SHA та SHA всіх чотирьох canonical dependencies збігаються до виконання.
- Виконуються десять inherited fixtures і `STATE-05`; incomplete execution не є PASS набору.
- `axis_source_refs` містять exact file/section/field або dependency ID/version/SHA.
- Missing locator дає `SCHEMA_UNVERIFIED`, але не створює `BLOCKED` без окремого чинного block rule.
- PASS потребує exact field comparison і read-back відсутності prohibited mutations.
