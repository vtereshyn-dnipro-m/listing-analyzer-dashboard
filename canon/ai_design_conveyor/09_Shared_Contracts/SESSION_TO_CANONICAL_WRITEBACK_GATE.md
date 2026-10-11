# Session-to-Canonical Writeback Gate

Статус: `active_v1.0`

## Призначення

Gate не дозволяє автоматично перетворювати діалог, агентний висновок, конкурентний сигнал або результат одного тесту на Product Truth, правило Marketing Book чи чинну інструкцію агента.

## Цільові канони

| Target | Що може бути записано | Що не може бути записано |
| --- | --- | --- |
| SKU Passport | verified product fact, provenance, conflict, evidence gap, approved extension field | positioning, PPC result, competitor weakness, unverified review hypothesis |
| Marketing Book | повторно застосовне evidence-backed правило, approved positioning principle, verified learning | одиничний результат без меж застосування |
| Content TZ / agent instruction | approved operational rule з acceptance test | vendor feature claim або рекомендація без локальної перевірки |
| Experiment / learning log | bounded test result, uncertainty, context and decision | загальна істина про товар або ринок |

## Writeback request

```yaml
canonical_writeback_request:
  request_id:
  session_id:
  target_artifact:
  target_section_or_object:
  proposed_change:
  object_type: VERIFIED_FACT | CONFLICT | GAP | APPROVED_RULE | LEARNING | RETIREMENT
  evidence_refs: []
  source_session_hypothesis_ids: []
  applicable_scope:
  non_applicable_scope:
  uncertainty:
  contradiction_check:
  target_owner:
  approval_ref:
  pre_write_sha256:
  required_regression_checks: []
  disposition: PROPOSED | APPROVED | REJECTED | SUPERSEDED
```

## Gate

`PASS` можливий лише якщо:

1. target artifact і owner визначені;
2. evidence доступне, має provenance і підтримує саме запропонований зміст;
3. hypothesis не видається за факт;
4. перевірено суперечності з чинним каноном;
5. scope і межі повторного використання явні;
6. є approval власника target artifact;
7. pre-write SHA-256 збігається перед записом;
8. після запису виконано read-back, link/navigation check, targeted regression і новий SHA-256;
9. попередню версію збережено за чинним source-folder workflow, а не створено паралельний канон.

Інакше status: `CANONICAL_WRITEBACK_BLOCKED` із конкретною причиною.

## Спеціальне правило SKU Passport

Сесія посилається на `passport_revision` та `passport_sha256`, але не записує в Паспорт повний conversation transcript. Дозволені лише нормалізовані verified objects, gaps, conflicts, source links і change events. Маркетингова інтерпретація залишається downstream.

## Спеціальне правило навчання

Experiment result спочатку стає `LEARNING_CANDIDATE`. Статус `REUSABLE_LEARNING` дозволений лише після перевірки test design, confounders, economics, marketplace/country/SKU scope і повторюваності або явного обмеження застосування.
