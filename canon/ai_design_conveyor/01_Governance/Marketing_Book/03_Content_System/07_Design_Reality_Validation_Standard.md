# Design Reality Validation Standard

Status: working standard for Marketing Book and agents  
Marker: MB-DRV-2026-08-29

## 1. Purpose

This standard closes the gap between a clean design file and real buyer perception. For DNIPRO-M content, a visual is not considered effective only because it is well-composed, branded, technically correct, or attractive in Figma. It must also work in the real context where the buyer sees it: marketplace search results, mobile product gallery, product page, A+ block, Store page, banner, video cover, social feed, or advertising placement.

The standard is mandatory for product photos, video frames, marketplace cards, A+ content, Store banners, social/ad creatives, designer briefs, and content audits.

## 2. Basic rule

Every important visual must be checked not only by what the team intended to communicate, but by what a buyer is likely to understand in the first seconds.

The audit or brief must answer three questions:

1. What value should the buyer understand?
2. What will the buyer probably understand without internal context?
3. What can be misunderstood, ignored, cropped, or interpreted as an unsupported promise?

If the answer to question 2 differs materially from question 1, the asset must be corrected.

## 3. Reality Context Check

Design review must include the context where the asset will actually be used. A desktop mockup or Figma frame is not enough.

Required checks:

- marketplace thumbnail and search-result visibility;
- mobile gallery crop and safe zones;
- first product-page screen;
- A+ module visibility on mobile;
- video cover and first 3-5 seconds;
- text readability after compression, scaling, and crop;
- whether the visual still communicates value without explanation from the team.

If real placement cannot be verified, the report must mark the conclusion as limited evidence, not as confirmed compliance.

## 4. Fresh Eyes Review

High-impact visuals require a Fresh Eyes Review: a person who did not create the asset and did not participate in the internal discussion must look at the visual briefly and explain what they understood.

Minimum test questions:

- What product is this?
- What is the main benefit?
- Who is it for?
- What task/problem does it solve?
- What, if anything, looks unclear or questionable?
- What would you click, compare, or ignore?

The goal is not to collect personal preferences. The goal is to find friction, wrong first interpretation, missing value, or misleading emphasis.

## 5. Mental Model Fit

The visual must match the buyer's mental model: how the buyer thinks about the task, not how the internal team thinks about the product.

For tools, power tools, DIY, garden, workshop, and home-repair products, the buyer usually evaluates:

- task fit: what job this tool helps complete;
- proof of capability: what material, load, distance, speed, or result is shown;
- control and safety: how the tool is held, started, adjusted, protected;
- compatibility: battery platform, accessories, consumables, kit content;
- scale and ergonomics: size in hand, weight, reach, maneuverability;
- trust: warranty, service, repair, spare parts, brand presence;
- outcome: the finished cut, cleaned surface, drilled hole, assembled object, prepared garden, or solved household problem.

A visual that shows only a feature without the buyer's task or result is incomplete unless it is intentionally a technical-detail slide.

## 6. Friction over Preference

Reviews and tests must search for friction, not ask whether people like the design.

Useful signals:

- the buyer cannot identify the product quickly;
- the buyer sees the product but not the task value;
- the buyer notices a technical feature but cannot connect it to benefit;
- the buyer reads a claim but does not see proof;
- the buyer sees an attractive scene but not the product role;
- the buyer cannot understand scale, kit content, or compatibility;
- the buyer may form an expectation the product cannot reliably fulfill.

Designer feedback must be converted into tasks: what exactly to change in frame, hierarchy, text, crop, scene, proof, or sequence.

## 7. Real-World Accessibility

Accessibility is treated as real-world usability, not only formal compliance.

The asset must remain understandable when:

- viewed on a small screen;
- seen quickly in a feed or marketplace search;
- viewed with low attention;
- compressed by platform algorithms;
- cropped by mobile layouts;
- read by a non-expert buyer;
- interpreted without internal product knowledge.

Text-on-visual must not carry the only critical meaning. If the message is important, it should be supported by image evidence, captions, alt/product text, or the surrounding content block.

## 8. Testing is for learning, not confirmation

Testing should not be used to prove that the team's design is correct. It must identify what can fail in buyer perception.

The required output of a test or audit is:

- intended message;
- likely buyer interpretation;
- mismatch or friction;
- risk level;
- evidence basis;
- concrete correction task.

If no friction is found, the report must still state what was checked and what evidence supports the conclusion.

## 9. Required fields for briefs and audits

For each high-impact asset, the brief or audit should include:

- Asset role: main image, gallery slide, A+ module, Store banner, video cover, video scene, social/ad creative.
- Intended message: what the asset must communicate.
- Buyer first interpretation: what a non-internal viewer is expected to understand in 3-5 seconds.
- Context: where the asset will be seen.
- Safe-zone/mobile risk: what can be cropped or lost.
- Mental model risk: where internal logic may not match buyer logic.
- False expectation risk: which promise can be perceived too broadly.
- Fresh Eyes requirement: yes/no and who should check.
- Acceptance criteria: how the asset will be judged.
- Required correction if failed: specific task, not a generic recommendation.

## 10. Evidence and status rules for agents

Agents must separate evidence from inference.

Allowed status labels:

- Confirmed: the asset or placement was directly inspected.
- Likely: the conclusion is based on visible evidence, but the exact placement/device was not verified.
- Risk: a plausible perception problem exists and must be checked.
- Not verifiable: the required asset, context, or placement was not available.

Agents must not write that mobile perception, thumbnail visibility, or real placement compliance is confirmed unless the relevant view was actually inspected.

## 11. Related standards

This standard must be applied together with:

- Value Story standards;
- Text-on-Visual and Message Anchoring standards;
- Mobile Crop Rule;
- Marketplace First-Choice Visual standard;
- Product Page and Image Stack standards;
- Content audit report standard;
- Content TZ Agent templates.
## 12. Structured Creative-to-Production Standard

This standard controls the path from approved creative intent to production-ready visual assets. It prevents silent design drift, unsupported claims, product-truth errors, crop failures and unapproved brand improvisation.

### 12.1 Scope

The full gate is mandatory for high-impact assets:

- Amazon main image and product gallery;
- A+ modules and Brand Store;
- marketplace banners and comparison visuals;
- paid social/display creatives;
- video cover, key frames and motion templates;
- localizations and scalable family variants;
- reuse of approved creative templates.

A shortened profile may be used for routine social variants and low-impact exploratory moodboards, but only when product truth, claims, rights, buyer perception and channel restrictions remain protected.

### 12.2 Roles and decision rights

| Role | Responsibility |
|---|---|
| Request owner | Defines business objective, channel, asset role and deadline. |
| Product/Catalog owner | Confirms SKU, kit, compatibility, specifications and product truth version. |
| Brand/Content owner | Approves message, claim IDs, tone, brand rules and CTA. |
| Designer or design agent | Creates bounded variants only inside the approved context. |
| QA reviewer | Checks rendered placement, crops, states and parity. |
| Compliance/Rights owner | Checks claims, disclosures, rights and channel restrictions. |
| Release owner | Makes final `APPROVE / REWORK / HOLD / REJECT` decision. |

One person may hold several roles, but a design agent cannot self-approve product truth gaps, claim gaps, rights gaps, ambiguous buyer-perception risks or external publication.

### 12.3 Mandatory input: `creative_design_context`

For high-impact assets, `creative_design_context` is mandatory before generation, adaptation, localization or reuse of a creative template.

```yaml
asset_id:
asset_role:
business_objective:
channel:
country:
language:
target_placement:
target_dimensions:
SKU_ASIN:
product_truth_version:
approved_claim_ids: []
required_proof_assets: []
brand_system_version:
approved_colors: []
approved_typography: []
approved_spacing_grid:
approved_templates_components: []
logo_rules:
CTA_rules:
reference_assets: []
required_variants_states: []
mobile_thumbnail_crops: []
safe_zones:
text_limits:
allowed_transformations: []
prohibited_transformations: []
allowed_source_files: []
reviewers: []
maximum_correction_passes: 3
deadline:
open_decisions: []
```

If `product_truth_version`, channel/placement, required claim evidence or release owner is missing, the asset receives `NOT_READY`.

Default maximum correction passes = `3`, unless the brief explicitly sets another approved limit. After the limit is reached, the status becomes `STOP_AND_REVIEW`; the agent must not continue by assumption.

### 12.4 Design preflight

Before generating or editing, the designer or design agent must:

1. verify that all reference assets have a version or date;
2. map requested colors, typography and spacing to the approved brand system;
3. map requested layout to approved templates/components;
4. verify rights for photos, video, music, creator assets and fonts;
5. verify SKU, kit, accessories, compatibility and use scene;
6. verify that claims have approved IDs and are not visually expanded;
7. identify all required dimensions, crops, language variants and platform states;
8. produce `preflight_result`.

Preflight statuses:

- `READY` — all critical inputs are confirmed;
- `READY_WITH_CAVEATS` — non-critical open issues have owners;
- `NOT_READY` — a critical input is missing;
- `STOP_AND_REVIEW` — brief, product truth, brand or channel rule conflict.

### 12.5 Executable loop

The controlled loop is:

`approved product truth and claim IDs → creative_design_context → structured creative brief → brand tokens/templates/components → bounded generation or adaptation → render in target placement → compare with approved reference and constraints → correct or escalate → creative_parity_report → human release decision`.

#### Step 1. Pull

Pull current design context, tokens, templates, component variants, product assets and channel requirements. A screenshot or moodboard is a visual reference, not a full production specification.

#### Step 2. Map

Create a mapping:

`brief requirement → approved token/component/claim/product asset → source reference`.

Any unmapped material element is a `MISMATCH`, not creative permission.

#### Step 3. Generate or adapt

The designer or design agent may:

- create only requested variants;
- adapt dimensions, crop and localization only within approved limits;
- preserve editability, layers and stable asset/version IDs;
- mark synthetic elements according to current AI Creative Governance.

The designer or design agent must not:

- invent badges, CTA, claims, icons or product configuration;
- create a new brand convention without approval;
- change unrelated layouts, components or assets;
- use hardcoded substitute brand values when an approved token is missing;
- treat similarity to a screenshot as complete QA.

#### Step 4. Render in context

Render not only the master asset, but every required placement variant:

- required pixel dimensions;
- mobile crop and marketplace thumbnail;
- compression/downscale;
- light/dark background, when relevant;
- long localized phrase;
- video cover and first 3-5 seconds;
- hover/focus/disabled/loading/error states for interactive assets, when relevant.

#### Step 5. Compare

Compare rendered output against:

1. approved brief;
2. structured brand tokens/templates;
3. approved reference;
4. product truth and claims;
5. target placement constraints.

Mismatch categories:

`TOKEN | COMPONENT | LAYOUT | CROP | TYPOGRAPHY | PRODUCT_TRUTH | CLAIM | RIGHTS | ACCESSIBILITY | LOCALIZATION | CHANNEL | UNRELATED_CHANGE`.

#### Step 6. Correct or escalate

- `P0/P1` mismatch blocks release;
- `P2` returns to correction;
- `P3` may be accepted as risk only by the release owner;
- after maximum correction passes, status becomes `STOP_AND_REVIEW`;
- ambiguity is not closed by agent assumption.

### 12.6 Mandatory output: `creative_parity_report`

For high-impact assets, `creative_parity_report` is mandatory.

```yaml
asset_id:
asset_version:
source_context_version:
checked_placements: []
checked_variants_states: []
expected_references: []
actual_renders: []
mismatches:
  - id:
    category:
    severity:
    expected:
    actual:
    evidence:
    owner:
    disposition:
    retest_evidence:
visual_parity_status:
product_truth_status:
claim_policy_status:
brand_status:
accessibility_readability_status:
rights_status:
buyer_comprehension_status:
release_decision:
release_owner:
date:
```

The report must separate visual parity from product truth, claim policy, brand, accessibility/readability, rights and buyer comprehension. A clean visual diff does not create approval by itself.

### 12.7 Release gate

`APPROVE` is allowed only when:

- critical mismatches = `0`;
- product truth = `PASS`;
- claims/policy = `PASS`;
- brand/template parity = `PASS`;
- required crops/placements = `PASS`;
- accessibility/readability = `PASS`;
- rights = `PASS`;
- Fresh Eyes or buyer-comprehension check is completed for high-impact assets;
- final files match verified checksum/version;
- external publication is confirmed by a human release owner.

Allowed release decisions:

- `APPROVE` — asset may be released or handed to publishing;
- `REWORK` — asset returns to bounded correction;
- `HOLD` — asset waits for missing decision/evidence;
- `REJECT` — asset cannot be used in the requested context.

### 12.8 Shortened profile for routine social variants

Routine social variants may use a shortened profile only when the asset does not create a new product claim, new brand convention, new product representation, new safety implication or new channel promise.

Minimum shortened profile:

- asset role and channel;
- source product truth version;
- approved claim IDs or `no_claims`;
- approved template/component reference;
- required dimensions/crops;
- rights status;
- quick buyer-comprehension check;
- human release decision before external publication.

If any of these are missing or disputed, the asset moves to the full gate.

### 12.9 Stop conditions

Immediate `STOP_AND_REVIEW` is required when:

- critical source/context is missing or has two active versions;
- design token has no approved mapping;
- component instance is detached/unapproved;
- brief conflicts with brand system;
- product visual conflicts with SKU/kit truth;
- claim has no approved evidence;
- rights or disclosure are unknown;
- required state/placement cannot be verified;
- correction requires unrelated refactor/redesign;
- maximum correction passes are exhausted;
- QA tool is unavailable and no equivalent evidence path exists.

Stop output:

```text
status: STOP_AND_REVIEW
blocking_issue:
evidence:
decision_required:
allowed_options:
owner:
affected_assets:
safe_next_action:
```

### 12.10 Preservation of other gates

This standard does not replace existing DNIPRO-M gates. It adds the creative-to-production control layer while preserving:

- product truth and SKU/kit/compatibility validation;
- claims and policy validation;
- rights and disclosure validation;
- buyer perception, Fresh Eyes and comprehension checks;
- mobile crop, text-on-visual and AI readability checks;
- channel-specific Amazon, marketplace, Store, A+, paid creative and video requirements.

<!-- MB_MESSAGE_MEDIA_2026_09_27_START -->
## Контроль збереження товару та способу виконання

### Призначення та область застосування

Для генерації, редагування й компонування товарних зображень до виконання визначити, що дозволено змінити і яким доказом буде підтверджений результат. Блок уточнює чинні Visual Invariants та Reference-led Delta Edit, не замінюючи їх і не дозволяючи нових дій без погодженого ТЗ.

### Вхідні дані

У чинний запис референсів додати `asset_id`, версію/хеш, exact SKU/variant, права, видимі області, повноваження джерела та рішення щодо використання. Ролі: `BASE` визначає композицію; `SUBJECT_DONOR` — лише видиму підтверджену ідентичність товару; графіка продавця, упаковка, логотип і дані мають власну область повноважень. Одне фото не підтверджує автоматично характеристики, комплект або права на повторну публікацію. Суперечливі референси повертаються власнику Product Truth, а не усереднюються.

### Правила виконання

До завдання додати `fidelity_mode`, `change_exactly`, `preserve_exactly`, `may_change`, `source_refs`, `mask_or_region`, `tolerance`, `qa_method`, `reviewer`.

| Режим | Що зберігається та як перевіряється |
| --- | --- |
| `IDENTITY_MATCH` | Геометрія, деталі, пропорції, колір exact SKU, матеріал, логотип і написи. Камера та фон можуть змінюватися в дозволених межах; нові видимі поверхні потребують доказу. |
| `COMPOSITION_LOCK` | Додатково зберігаються ракурс, crop, розташування, масштаб та структура фону. Перевірити весь кадр, не лише виправлене місце. |
| `MASKED_REGION_LOCK` | Зміна обмежена заданою маскою; обов'язкові порівняння поза маскою, визначений допуск і перевірка всього результату. |
| `PIXEL_EXACT` | Пікселі поза дозволеною операцією зберігаються без змін; потрібні детерміноване компонування та виміряна різниця. Сам промпт цього не гарантує. |
| `REDESIGN` | Дозволена лише названа зміна конструкції. Результат не є зображенням вихідного SKU для продажу; потрібне окреме рішення щодо нової продуктової версії. |

Для нової видимої області зафіксувати `OBSERVED_VIEW`, `SUPPORTED_NOVEL_VIEW`, `NOVEL_VIEW_UNVERIFIED` або `NOVEL_VIEW_CONFLICT`. Перші два потребують exact-SKU джерела. Непідтверджений ракурс повертається на інший crop/ракурс або збір референсів; правдоподібність не дозволяє вигадувати приховані кріплення, порти чи написи. Upscale не перетворює нечітку деталь на перевірений факт.

Спосіб виконання обирається за потрібною зміною:

- `NATIVE_CONTENT_PRESERVING` — resize, compression, conversion, дозволені crop/pad без домальовування;
- `MASK_BASED_EDIT` — локальна зміна з маскою й перевіркою захищених областей;
- `GENERATIVE_RECONSTRUCTION` — домальовування, нова сцена або інша змістова генерація;
- `TEXT_LAYOUT_COMPOSITION` — контрольоване компонування точного тексту, таблиці, стрілок або наданого логотипа.

Не запускати повторну генерацію для суто технічної зміни. Якщо критичний текст не проходить перевірку в генерації, використовувати прийняте базове зображення та окреме точне компонування. Перевіряти текст проти approved exact copy, локаль, орфографію, OCR і читабельність; OCR не є єдиним доказом. Семантичні шари промпту не вважати окремими редагованими шарами файла.

Для вирізання фону використовувати маску предмета, а не глобальне видалення світлих пікселів. Перевірити білі й прозорі деталі, краї та потрібні тіні на білому, темному й кольоровому фоні. Pure-white JPEG і transparent PNG — різні результати.

Числа й фізичні терміни камери, освітлення та руху класифікувати як `DETERMINISTIC_PARAMETER`, `PROMPT_HINT`, `POSTPROCESS_PARAMETER` або `UNSUPPORTED_PARAMETER`. Параметр у тексті промпту не доводить фізичного розрахунку. Перевіряти опору предмета, масштаб, перспективу, контакт, напрямок тіні й відбиття за фактичним результатом.

### Ролі та вердикти

Content TZ Agent фіксує дозволені зміни; виконавець обирає доступний спосіб у цих межах; аудитор перевіряє результат. `FIDELITY_MODE_CONFLICT`, `NOVEL_VIEW_UNVERIFIED`, `NOVEL_VIEW_CONFLICT`, `OUTSIDE_MASK_PIXEL_DRIFT` та `SOURCE_DETAIL_INSUFFICIENT` блокують відповідне твердження про точність і передачу відповідного матеріалу на публікацію. Планування може тривати з явно відкритим питанням. Жоден режим не знімає human release gate.

### Acceptance tests

- Зміна фону не змінює захищений товар; для pixel/mask-вимоги збережений результат вимірювання.
- Невидимий у джерелах роз'єм не отримує статус підтвердженого після генерації.
- Нечитабельна етикетка після upscale лишається прогалиною доказів, а не новим Product Truth.
- Зміна розміру без нового змісту не створює новий generative attempt.
- Точний напис збігається з погодженим текстом; тінь, контакт і пропорції перевірені на всьому зображенні.

### Метрики та межі доказовості

Відстежувати identity drift, непідтверджені ракурси, помилки тексту, відхилення поза маскою, повторні генерації та час на прийнятий матеріал. Режими є контрактом перевірки, не обіцянкою можливостей конкретної моделі. Новий інструмент або версія потребує окремого випробування; фізична й товарна достовірність не випливають із професійної лексики промпту.
<!-- MB_MESSAGE_MEDIA_2026_09_27_END -->
