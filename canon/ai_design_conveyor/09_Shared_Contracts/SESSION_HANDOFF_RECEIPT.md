# Session Handoff Receipt

Статус: `active_v1.0`

## Призначення

Receipt фіксує передачу між двома агентними ролями в межах однієї сесії. Він не є доказом якості результату і не замінює незалежний аудит.

## Контракт

```yaml
session_handoff_receipt:
  receipt_id:
  session_id:
  from_role:
  to_role:
  handed_off_at:
  stage_from:
  stage_to:
  scope:
  input_refs: []
  output_refs: []
  product_truth_revision:
  context_contract_version:
  evidence_snapshot_id:
  fact_ids: []
  signal_ids: []
  hypothesis_ids: []
  decision_ids: []
  open_gap_ids: []
  prohibited_inferences: []
  required_checks_by_receiver: []
  permissions_transferred: []
  permissions_not_transferred: []
  sender_status: READY_FOR_HANDOFF | PARTIAL_WITH_GAPS | BLOCKED
  receiver_status: ACCEPTED | ACCEPTED_WITH_LIMITS | REJECTED_STALE | REJECTED_SCOPE | REJECTED_INTEGRITY
  receiver_read_back_at:
```

## Правила виконання

1. Передаються посилання на об'єкти й pinned revisions, а не переказ без provenance.
2. `FACT`, `SIGNAL`, `HYPOTHESIS`, `DECISION` і `ACTION` не змішуються.
3. Receiver перевіряє exact SKU/scope, current revision, доступність input refs та freshness.
4. Передача не переносить права автора. `permissions_transferred` може містити лише права, надані чинним approval.
5. Auditor і Verifier отримують артефакт, критерії, джерела та gaps, але не зобов'язані приймати reasoning або verdict автора.
6. Застарілий або неповний handoff не виправляється мовчки; він повертається з адресним status і finding.

## Acceptance tests

- `session_id`, sender, receiver і stage transition однозначні;
- усі output refs існують і читаються;
- Product Truth revision збігається з Session Passport;
- gaps і prohibited inferences явно передані;
- receiver зробив read-back;
- немає прихованого перенесення approval або publication authority.
