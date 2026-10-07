# End-to-End Agent Evaluation Contract

Версія: 1.0  
Статус: `DOCUMENTED_CONTROL_CONTRACT`

## Призначення

Визначити окремі критерії приймання для агентів, що збирають, інтерпретують, готують, створюють, перевіряють і оцінюють content assets. Контракт не замінює чинні JSON schemas, human approval або live validation.

## Область застосування

Контракт діє для ланцюга `SKU Passport Collector → Product Truth Verifier → Content TZ Agent → Prompt Agent → AI Creator → Auditor/Verifier → Experiment Analyst`. Кожен етап оцінюється за власним об'єктом рішення. Середній бал по всьому конвеєру заборонений.

## Контракт обов'язкових шарів та optional structural template

1. `PRODUCT_TRUTH_PRIMITIVE` — атомарний факт exact SKU/variant із versioned evidence, scope, validity, rights і verifier status.
2. `APPROVED_SEMANTIC_INTERPRETATION` — дозволений для конкретної buyer/channel контексту сенс, value story або claim wording, який не розширює факт.
3. `STRUCTURAL_TEMPLATE` — optional versioned composition contract для повторюваних A+/carousel/image/video assets: roles, slots, variations, safe zones і channel constraints. Він не створює fact або claim.
4. `CHANNEL_COMPONENT` — title, bullet, A+, image element, shot, frame, caption, video beat або інший executable content component.

Нейтральне точне відображення verified специфікації може посилатися безпосередньо на Product Truth, якщо формулювання не додає обіцянку, comparison, buyer outcome або implied capability. Переконливий content повинен мати semantic interpretation. Для повторюваної композиції ланцюг має вигляд `PRODUCT_TRUTH_PRIMITIVE → APPROVED_SEMANTIC_INTERPRETATION → STRUCTURAL_TEMPLATE → CHANNEL_COMPONENT`; для унікальної/простої — template отримує `NOT_APPLICABLE` із причиною. Заборонено переносити raw/unverified fact у channel component, а також записувати template, channel wording, creative hypothesis або performance result назад у Product Truth.

## Рольова eval-матриця

| Етап | Об'єкт перевірки | Blocking dimensions |
| --- | --- | --- |
| Collector | source-to-field capture | source coverage, exact identity, extraction correctness, provenance completeness |
| Product Truth Verifier | fact/evidence decision | faithfulness, correctness, conflict detection, SKU/variant/scope applicability |
| Content TZ Agent | approved brief/TZ | Product Value Synthesis completeness, buyer/channel relevance, feature-to-benefit traceability, P0/P1 asset coverage, claim-to-evidence coverage, no silent Passport-value omission, no claim expansion |
| Prompt Agent | compiled Prompt Package | approved-TZ fidelity, schema/capability consistency, structural-template binding, invariant coverage, no silent rewrite |
| AI Creator | execution receipt і asset | prompt/hash fidelity, exact SKU, protected invariants, requested-versus-observed delta |
| Auditor/Verifier | independent acceptance | defect-detection recall, false-pass control, evidence trace, independent source read-back |
| Experiment Analyst | decision record | outcome/denominator identity, contamination, guardrails, causal and transfer boundary |

Провал blocking dimension завжди дає `REWORK` або `BLOCKED`; його не можна компенсувати relevance, fluency, aesthetics, CTR чи середнім балом.

## Обов'язковий frame evidence binding

```yaml
frame_evidence_binding:
  asset_id:
  shot_or_frame_id:
  demonstrated_claim:
  semantic_interpretation_id_version:
  fact_version_ids: []
  evidence_ids: []
  exact_sku_variant:
  accessory_and_kit_status:
  rights_status:
  allowed_surface:
  verifier_status:
```

Для image/video кожна візуально передана capability, kit/accessory state, quantity, label або safety condition має binding до кадру чи shot. Посилання лише на asset загалом недостатнє.

## Стани і вердикти

- `PASS` — усі застосовні blocking dimensions пройдені з відтворюваним evidence.
- `REWORK` — дефект виправний у поточному етапі.
- `BLOCKED` — бракує authority, evidence, exact identity, rights, valid approval або current provider capability.
- `NOT_APPLICABLE` — dimension не застосовний із записаною причиною.

Для runtime/media використовуються fail-closed reasons `APPROVAL_INVALIDATED`, `PIPELINE_CONTRACT_CONFLICT`, `PROVIDER_CAPABILITY_UNVERIFIED`. `OUTPUT_VERIFIED` може виставити лише незалежний QA/Verifier після перевірки файлу, а не Creator.

## Acceptance tests

Мінімальний regression set містить десять cases із `e2e_agent_eval_cases.json`: wrong variant; fluent unsupported claim; conflicting sources; accessory absent from kit; stale fact after TZ approval; missing media rights; brief changed after approval; provider schema mismatch; visually good wrong quantity; CTR growth with worse returns/not-as-described. Кожен case має зупинитися на очікуваному етапі, не створюючи downstream asset або release decision.

## Метрики

Для кожної ролі окремо вести blocking-pass rate, false-pass rate, missed-conflict rate, traceability completeness і regression escape rate. Бізнес-метрики не підміняють quality gate.

## Межі доказовості

Цей файл і JSON fixtures є документованим контрактом. Вони не доводять, що tests автоматизовані, agents deployed, provider callable, rights valid або production behavior verified.

