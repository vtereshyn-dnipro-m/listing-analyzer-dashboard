# Agent Session Contract

Статус: `active_v1.0`

## Призначення

Контракт визначає керовану багатокрокову сесію для одного SKU, marketplace і бізнес-питання. Сесія об'єднує роботу спеціалізованих агентів, але не замінює Product Truth, Marketing Book, Content TZ, approval або незалежну верифікацію.

## Область застосування

Контракт застосовується до ланцюга `SKU/source intake -> Product Truth/SKU Passport -> market and competitor analysis -> value story -> Content TZ -> production -> audit -> verification -> human release -> experiment/learning`.

Один чат без структурованого паспорта сесії не є керованою сесією. Сесія не надає агентам нових прав на зовнішні зміни, spend, публікацію або зміну канонічних документів.

## Вхідні дані

```yaml
session_passport:
  contract_version: "1.0"
  session_id:
  created_at:
  owner:
  sku_id:
  exact_model_revision:
  marketplace:
  country:
  business_question:
  requested_outcome:
  current_stage:
  product_truth_ref:
    path_or_id:
    revision:
    sha256:
    verification_status:
  marketing_book_ref:
    revision_or_date:
    applicable_sections: []
  context_contract_version:
  evidence_snapshot:
    source_ids: []
    captured_at:
    freshness_status:
  active_hypothesis_ids: []
  open_gap_ids: []
  current_agent_role:
  allowed_actions: []
  prohibited_actions: []
  decisions: []
  approved_action_ids: []
  handoff_receipt_ids: []
  verification_receipt_ids: []
  session_status:
```

## Правила виконання

1. Сесія прив'язується до exact SKU/model/revision, marketplace, country і одного сформульованого decision question.
2. Кожний агент читає поточний `session_passport`, перевіряє pinned revisions і працює лише в межах своєї ролі.
3. Висновок попереднього агента є контекстом, а не доказом. Доказом є лише доступне джерело з provenance та locator.
4. Product Truth факти, маркетингові інтерпретації, гіпотези, рішення і зовнішні дії зберігаються як різні типи об'єктів.
5. Зміна Product Truth revision, marketplace, country, business question, evidence freshness або дозволів створює новий checkpoint; матеріальна зміна scope створює нову сесію.
6. Session memory не є канонічною пам'яттю. Повторне використання між сесіями дозволене лише після `SESSION_TO_CANONICAL_WRITEBACK_GATE=PASS`.
7. Відсутні дані мають статус `UNKNOWN`, `EVIDENCE_GAP` або `CONFLICT`; їх не можна підмінювати нулем чи припущенням.
8. Будь-яка дія, що змінює spend, bid, budget, campaign, Product Truth, Content TZ, канонічний стандарт або опублікований asset, потребує окремого чинного approval за відповідним доменним контрактом.

## Ролі та маршрутизація

| Роль | Дозволений результат | Заборонена підміна |
| --- | --- | --- |
| Product Truth / Passport Agent | verified facts, provenance, gaps, conflicts | positioning або рекламна рекомендація як факт |
| Market / Competitor Agent | market signals, SOV/keyword/offer comparison | точний competitor spend без доказу |
| Positioning Agent | evidence-bounded differentiation hypotheses | запис гіпотези в SKU Passport |
| Content TZ Agent | production-ready brief із traceability | самостійне схвалення claim |
| Creator | draft assets | зміна Product Truth або публікація |
| Auditor | незалежні findings щодо заданого audit object | редагування власного об'єкта аудиту |
| Verifier | evidence reconciliation і verdict | успадкування verdict автора без перевірки |
| Experiment Analyst | result, uncertainty і learning candidate | автоматичний запис у Marketing Book |

## Стани

`CREATED -> CONTEXT_READY -> IN_PROGRESS -> HANDOFF_PENDING -> VERIFICATION_PENDING -> HUMAN_DECISION_PENDING -> COMPLETED`

Блокувальні стани: `CONTEXT_NOT_READY`, `CONTEXT_STALE`, `SCOPE_CONFLICT`, `EVIDENCE_GAP_BLOCKING`, `APPROVAL_REQUIRED`, `VERIFICATION_FAILED`, `CANONICAL_WRITEBACK_BLOCKED`.

`COMPLETED` означає, що запитаний результат перевірено в межах сесії. Це не означає publication readiness або зміну канону.

## Acceptance tests

- exact SKU/model/marketplace/country зафіксовані;
- Product Truth, Marketing Book і context versions pinned;
- кожен висновок має тип `FACT | SIGNAL | HYPOTHESIS | DECISION | ACTION`;
- кожний handoff має чинний `SESSION_HANDOFF_RECEIPT`;
- Creator і незалежний Auditor/Verifier не об'єднані в одну роль;
- зовнішні або канонічні зміни мають approval і read-back;
- session learning не потрапляє в канон без writeback gate.

## Межі доказовості

Сесія може пов'язувати PPC, retail, competitor, content і experiment signals, але не доводить причинність лише часовим збігом. Competitor spend вважається `ESTIMATE` або замінюється на observable signals: SOV, placement frequency, keyword overlap, price, Buy Box, reviews і search-funnel metrics.
