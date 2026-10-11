# Structural Template Registry

Статус: `active_v0.1_shadow`

## Призначення

Реєстр задає повторювані композиційні структури між `APPROVED_SEMANTIC_INTERPRETATION` і конкретним `CHANNEL_COMPONENT`. Він не створює Product Truth, claims, channel rules або publication authority.

## Контракт використання

`STRUCTURAL_TEMPLATE` є optional. Для простого чи унікального asset використовується `NOT_APPLICABLE` із причиною. Для повторюваної композиції Prompt Package має immutable binding до `template_id`, version, registry path/SHA-256, slots, allowed variations і deviations.

Стани: `TEMPLATE_SELECTED | TEMPLATE_ADAPTED | NEW_TEMPLATE_REQUIRED | STRUCTURAL_REVIEW_REQUIRED | NOT_APPLICABLE`.

- `TEMPLATE_SELECTED`: чинний шаблон використано без structural deviation.
- `TEMPLATE_ADAPTED`: змінено лише дозволену variation; delta задокументована.
- `NEW_TEMPLATE_REQUIRED`: жоден шаблон не покриває повторювану композицію; provider execution не стартує до review.
- `STRUCTURAL_REVIEW_REQUIRED`: порушено slot, hierarchy, safe zone, continuity або channel constraint.
- `NOT_APPLICABLE`: композиція одноразова/проста або channel не потребує reusable structure.

## Обов'язкові поля binding

```yaml
structural_template_binding:
  applicability: APPLICABLE | NOT_APPLICABLE
  applicability_reason:
  template_id:
  template_version:
  registry_path:
  registry_sha256:
  selection_status: TEMPLATE_SELECTED | TEMPLATE_ADAPTED | NEW_TEMPLATE_REQUIRED | STRUCTURAL_REVIEW_REQUIRED | NOT_APPLICABLE
  target_asset_ids: []
  required_slots: []
  optional_slots: []
  slot_bindings: []
  allowed_variations: []
  applied_variations: []
  deviations: []
  channel_constraints: []
  localization_constraints: []
  reviewer:
```

## ST-PRODUCT-HERO-01 — Product Hero

- Version: `1.0`
- Purpose: один точний SKU як головний об'єкт без вигаданих аксесуарів або доказових claims.
- Required slots: `PRODUCT`, `BACKGROUND`, `SAFE_TEXT_ZONE`.
- Optional slots: `SUPPORTING_PROP`, `DETERMINISTIC_BADGE`.
- Allowed variations: centered або rule-of-thirds product placement; horizontal/vertical safe zone; clean studio або approved usage background.
- Channels: main/supporting image, A+ hero, carousel cover, opening video frame.
- Boundary: exact product fidelity і channel rules мають вищий пріоритет; generated typography заборонена.

## ST-PROBLEM-ACTION-RESULT-01 — Problem → Product Action → Result

- Version: `1.0`
- Purpose: показати buyer problem, видиму дію продукту та дозволений result без причинного перебільшення.
- Required slots: `PROBLEM`, `PRODUCT_ACTION`, `RESULT`, `EVIDENCE_BOUNDARY`.
- Optional slots: `CTA`, `DISCLAIMER`.
- Allowed variations: three-panel, carousel sequence або video sequence; result може мати `ILLUSTRATIVE_VALUE_VISUAL` замість observed result.
- Channels: A+, carousel, image series, short video.
- Boundary: generative result не позначається як actual/verified performance.

## ST-FEATURE-PROOF-01 — Feature → Visible Proof

- Version: `1.0`
- Purpose: зв'язати одну feature/claim із видимим exact-SKU proof region.
- Required slots: `FEATURE_LABEL`, `PRODUCT_REGION`, `PROOF`, `SOURCE_OR_LIMITATION`.
- Optional slots: `CALLOUT`, `COMPARISON_CONTROL`.
- Allowed variations: close-up, exploded deterministic graphic, annotated full product; overlay виконує Finishing/Localization.
- Channels: supporting image, A+ module, carousel card, video insert.
- Boundary: label не розширює approved semantic interpretation; proof region має reference/evidence binding.

## ST-SEQUENTIAL-USE-01 — Sequential Use

- Version: `1.0`
- Purpose: показати послідовність використання без змішування несумісних станів в одному кадрі.
- Required slots: `START_STATE`, `ACTION_STATE`, `END_STATE`, `CONTINUITY_ANCHOR`.
- Optional slots: `SAFETY_STEP`, `PPE`, `WARNING`, `CTA`.
- Allowed variations: 3–5 carousel cards, 3–5 video beats, deterministic montage.
- Channels: carousel, A+ sequence, instructional image series, video.
- Boundary: кожний state має окремий sub-asset/beat; continuity та safety перевіряються до release.

## Acceptance tests

- Binding посилається на цей registry через path і SHA-256.
- Усі required slots мають однозначні target bindings.
- Applied variation входить до allowed variations; інше дає `STRUCTURAL_REVIEW_REQUIRED`.
- Structural template не змінює Product Truth, approved claims, Visual Invariants або channel requirements.
- Generated asset не стає новим canonical template без окремого review, fixture і version bump.

## Межі доказовості

Це `active_v0.1_shadow`: registry придатний для non-live compilation і QA, але ще не має cross-SKU performance evidence. Він не дозволяє provider execution або publication і не доводить conversion lift.
