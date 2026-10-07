# Дорожня карта застосування матеріалів хвилі 2026-09-26

- **Статус:** `PROPOSAL_ONLY`
- **Мета:** перетворити прийняті сьогодні знання на конкретні зміни, пілоти й decision gates у чинних проєктах.
- **Межа повноважень:** цей документ не змінює downstream-проєкти, не активує skills/plugins, не запускає генерацію, публікацію, PPC-зміни або зовнішні дії.
- **Принцип:** непідтверджені твердження не відкидаються автоматично; вони переходять у контрольований експеримент, але не стають production truth до проходження acceptance gate.

## 1. Контекст і база рішень

До roadmap включено дев'ять канонічних контрактів, сформованих із сьогоднішньої хвилі:

1. `Agent capability resolution and runtime readiness`;
2. `Skill execution gates for external send and image editing`;
3. `AI product-image fidelity modes and evidence limits`;
4. `Buyer-reason-to-slot brief traceability for PDP and product creative`;
5. `Canvas transform and generative-media execution contracts`;
6. `Creative skill package completeness and runtime activation`;
7. `E-commerce image slot and platform-spec governance`;
8. `Generative product media: visual-physics and temporal contracts`;
9. `Amazon PPC Pulse: alert restraint and coverage contract`.

Окремі camera, lighting, negative-space та pipeline guides залишені як corroborating references. Їхні числові значення й tool claims не дублюються як універсальні правила.

## 2. Єдина модель роботи з підтвердженими й непідтвердженими даними

### 2.1 Evidence lanes

- `ADOPT_NOW`: правило достатньо обґрунтоване для включення у workflow, schema, gate або acceptance test. Це не означає, що конкретний runtime уже реалізований.
- `PILOT_HYPOTHESIS`: правдоподібна, але непідтверджена ідея. Дозволена лише у bounded test із comparator, метрикою, stop rule й expiry.
- `HOLD_FOR_EVIDENCE`: твердження може бути важливим, але потребує official platform source, current tool schema, engineering/sourcing evidence, права або exact-SKU reference.
- `REJECT_AS_POLICY`: внутрішньо суперечливе або небезпечне узагальнення, яке не повинно потрапляти навіть у default workflow. Його можна досліджувати лише як окрему негативну гіпотезу.

### 2.2 Картка тестової гіпотези

Кожне непідтверджене правило, яке беремо в роботу, отримує:

`hypothesis_id | source_claim | target project | bounded scope | control/comparator | changed variable | protected constants | primary metric | guardrails | stop rule | expiry | evidence owner | result | decision`.

Заборонено одночасно змінювати багато факторів і потім приписувати результат одному з них. Позитивний output не підвищує гіпотезу до policy без повторюваності й потрібного рівня evidence.

## 3. Спільний фундамент для всіх агентних проєктів

### Беремо в роботу

1. `Agent Capability Receipt`: documented, installed, bound, injected, callable, authorized і execution-verified — різні стани.
2. `Capability Dependency Matrix`: intent → package/resources → tool/schema → permission → fallback → blocker → fixture.
3. `Authority Matrix`: кожний модуль змінює лише свій decision object; presentation/media layer не змінює Product Truth, engineering truth або commercial approval.
4. `Execution Plane Map`: decision/compilation → probabilistic execution → deterministic post-processing/QA.
5. `Source/Input Preflight`: identity, hash/version, rights, completeness, freshness, dimensions/schema та intended output фіксуються до execution.
6. `Prompt/Input Gate` і `Result Acceptance Gate` є різними перевірками.
7. Кожний retry має reason, limit, cost/side-effect boundary і повторний full-output check.
8. `READY`, `PASS` або `CHANNEL_READY` можливі лише після визначеного acceptance check.

### Беремо лише на тестування

- фіксована кількість prompt-блоків;
- один AI-call на output;
- один автоматичний retry;
- конкретні model/provider routes;
- camera, lighting, negative-space й duration numbers із guides.

### Не переносимо

- `enabled = true` як доказ готовності;
- назву tool/skill у документі як доказ callable capability;
- красивий результат як доказ Product Truth, engineering truth або platform compliance;
- самозміну thresholds, permissions або authority агентом.

## 4. Пріоритет портфеля

### Хвиля P0 — безпосередній операційний ефект

1. AI Design / Marketing Book.
2. Image & Video Prompt Agent / AI Creator.
3. ACOS Management: PPC Pulse як read-only diagnostic lane.
4. Спільний capability/runtime registry та KB wave closure.

### Хвиля P1 — підсилення вхідних даних і каналів

1. SKU Passport / Listing Suite.
2. Market Research / Assortment / AI Product Designer.
3. TikTok Shop / Creator Commerce / Social Reels.
4. Marketplace Market Intelligence Agent.

### Хвиля P2 — методичне перевикористання

1. AI Procces building як демонстраційний process case.
2. AI in Supply Chain як reusable decision/monitoring method.
3. Articles and training products.

Послідовність є пріоритетом, а не календарним commitment. Перехід до наступної хвилі не потребує завершення всіх попередніх робіт, але потребує визначених owners і capacity gate.

## 5. Проєкт: DM AMAZON — AI Design / Marketing Book

### Цільовий артефакт

`C:\Users\ystep\Documents\DM AMAZON\Маркетинг Бук\DNIPRO-M Marketing Book\06_Production_and_Learning\03_AI_Design_Content_Creation_Pipeline.md`

### Беремо в роботу

- `Buyer Reason Card` як decision contract перед побудовою image/video set.
- `Buyer Reason-to-Slot Trace Matrix`: кожний slot має buyer question, message, evidence, exact copy, visual proof mechanism і acceptance test.
- `Asset Inventory and Authority Matrix`: BASE, subject donor, packaging, merchant graphic, logo, certificate та data-only asset отримують окремі права й disposition.
- `Fidelity Mode Contract`: `IDENTITY_MATCH`, `COMPOSITION_LOCK`, `MASKED_REGION_LOCK`, `PIXEL_EXACT`, `REDESIGN`.
- `Novel View Evidence Gate` для ракурсів, які відкривають раніше невидимі surfaces.
- `Platform Spec Binding` і `copy_locale_binding` як versioned inputs.
- адаптивний `Slot Contract`; L0–L5 використовуються як semantic plan, а не як доказ фізично відокремлених layers.
- розділення accepted base visual і deterministic typography/composition для critical text.
- `Parameter Reality Ledger` для canvas, camera, light, motion і provider parameters.
- visual-physics, OCR, product-identity, mobile/thumbnail і full-asset QA.

### Гіпотези для тестування

1. Adaptive prompt schema проти фіксованих 13 блоків.
2. One-call composite проти `base visual → native text/graphics composition`.
3. `8–28%` negative-space starting range проти copy/locale-driven sizing.
4. Lens/aperture vocabulary проти observable camera-intent description без чисел.
5. Optional AO/rim-light wording проти scene-specific lighting contract.
6. Один bounded retry проти immediate human rework після першого defect.

### Дорожня карта

1. **Contract design.** Додати proposal для `creative_media_execution_contract` і зв'язати його з чинним Content TZ та Creative Production Run.
2. **Schema package.** Підготувати Buyer Reason Card, Slot Trace Matrix, Asset Authority Matrix, Fidelity Contract, Platform Binding і Result Receipt schemas.
3. **Fixture.** Один non-live exact SKU: hero, supporting proof slot, exact-text infographic й короткий video shot. Зберегти current-pipeline control.
4. **Blind review.** Reviewer не знає, який asset створений current чи contract-driven route; оцінює identity, claim trace, buyer-message clarity, text і channel readiness окремо.
5. **Pilot.** Три SKU різної складності: simple product, text-heavy packaging, reflective/transparent або multi-part product.
6. **Release decision.** `ADOPT | MODIFY | RETEST | REJECT`; жодної автоматичної publication authority.

### Acceptance tests

- 100% decision-bearing claims і exact copy мають evidence ID.
- Кожний slot має унікальну функцію; duplicate/low-purpose slots блокуються.
- Усі newly visible product regions мають evidence state.
- Critical copy проходить OCR, spelling, locale й mobile checks.
- Pixel/mask claims підтверджуються measured comparison.
- Product fidelity pass не підміняє platform/publication pass.

### Метрики

- `RETURN_TO_TZ_AGENT` rate;
- unsupported-claim rejection;
- identity/novel-view defect rate;
- exact-text first-pass rate;
- AI calls і reviewer minutes per accepted asset;
- accepted-slot uniqueness;
- controlled-test conversion/CTR lift тільки після channel release.

## 6. Проєкт: Image & Video Prompt Agent / AI Creator

### Цільовий артефакт

`C:\Users\ystep\Documents\DM AMAZON\Маркетинг Бук\WORKSTREAM_Content_TZ_Agent\99_Backlog\Image_Video_Prompt_Agent_Specification_v0.1.md`

### Беремо в роботу

- перехід від keyword dispatcher до route contract: intent → authority → capability → execution plane → QA;
- `Capability Manifest` та `Capability Dependency Matrix` на кожний image/video route;
- task-adaptive prompt package замість обов'язкового заповнення всіх блоків;
- explicit `fidelity_mode`, `novel_view_state`, `parameter_reality_modes`, `platform_spec_binding_ref`, `copy_locale_binding_ref`;
- native-versus-generative routing і окремі working/delivery dimensions;
- retry budget, failure taxonomy, checkpoint/branch/rollback;
- observed-output manifest, Multi-turn Drift Ledger і result acceptance receipt;
- fail-closed status, якщо package, tool, schema, permission або evidence не підтверджено.

### Гіпотези для тестування

- заявлені provider/model names і parameters;
- one-call multi-layer generation;
- two-axis video motion budget;
- 4–6 second shots як drift reducer;
- concise preservation clause проти розширеного invariant manifest;
- model-specific routing за fidelity/cost/latency.

### Дорожня карта

1. **v0.2 specification:** розширити current Prompt Package й route states без активації агента.
2. **Package closure:** перевірити required references, scripts, schemas, adapters і tool bindings.
3. **Negative fixtures:** missing tool, stale platform spec, conflicting references, unreadable text, unavailable video provider, pixel-exact request через generative-only route.
4. **Representative eval:** generation, local edit, exact text, marketplace slot, novel view і video continuity.
5. **Shadow mode:** агент компілює package, але production виконує чинний human workflow.
6. **One-SKU pilot:** non-live SKU, named reviewer, no publication.
7. **Readiness verdict:** максимум `ACTIVE_UNVALIDATED` до representative fixtures; `ACTIVE_VALIDATED` лише для exact runtime/version.

### Acceptance tests і метрики

- mandatory Content TZ constraints traced 100%;
- capability mismatch і nonexistent-tool routing rate;
- native/generative misrouting rate;
- first-pass acceptance, retry success і human override;
- identity/text/video-continuity defects;
- cost/latency per accepted output;
- zero autonomous claim, Product Truth або publication changes.

## 7. Проєкт: SKU Passport / Listing Suite

### Цільовий артефакт

`C:\Users\ystep\Documents\DM AMAZON\Закладка Синтез\01_Паспорт SKU\Конвейер заполнения Паспорта SKU\Listing_Suite_ТЗ_Синтез_Паспорт_SKU_v01.md`

### Беремо в роботу

Лише neutral Product Truth та evidence projections:

- visual reference inventory із asset hash/version, exact SKU і rights;
- visible-surface coverage map;
- verified logo, labels, on-product/on-package text;
- material/color/texture identity fields із evidence;
- exact-SKU accessory/in-box inventory;
- reference conflict і insufficient-view states;
- engineering-source status для dimensions, BOM, exploded view і process visuals;
- invalidation event, коли змінився SKU, packaging, artwork або reference authority.

### Не переносимо до Passport

- camera, lighting, scene, style, prompt, provider або composition fields;
- buyer reason, marketing claim priority або publication status;
- synthesized novel-view details;
- provisional BOM/MOQ або supplier recommendation як facts.

### Дорожня карта

1. Спроєктувати `visual_identity_projection` як зовнішню проєкцію, а не розширення neutral fact core.
2. Додати view coverage й evidence states: `OBSERVED_VIEW`, `SUPPORTED_NOVEL_VIEW`, `NOVEL_VIEW_UNVERIFIED`, `NOVEL_VIEW_CONFLICT`.
3. Перевірити три SKU з різною повнотою reference pack.
4. Передати projection у Content TZ й виміряти, які повернення були викликані відсутніми facts/references.
5. Приймати schema лише якщо вона зменшує downstream ambiguity без змішування Product Truth і creative intent.

### Acceptance tests і метрики

- жодний creative choice не записаний як product fact;
- кожний protected invariant має source;
- conflict/insufficient evidence не замінюється plausible guess;
- `RETURN_TO_PASSPORT` і invented-view rate до/після;
- visual-source completeness і stale-reference rate.

## 8. Проєкт: Market Research / Assortment / AI Product Designer

### Цільові артефакти

- `C:\Users\ystep\Documents\DM AMAZON\RESEARCH_TO_OPERATOR_ASSET_INSTRUCTION.md`;
- `C:\Users\ystep\Documents\DM AMAZON\07_Agents\marketplace-market-intelligence\SKILL.md`.

### Беремо в роботу

- product design як exploratory branch після market/customer evidence, а не як джерело market truth;
- `Product Concept Evidence Card`: problem/job, evidence, hypothesis, differentiation mechanism, exact assumptions, unknowns, feasibility owner;
- мінімум source classes, а не просто «≥3 sources»: customer/review, marketplace/category, competitor/product, economics/operations;
- окремі statuses: `EXPLORATORY_CONCEPT`, `FEASIBILITY_PENDING`, `ENGINEERING_REVIEW_REQUIRED`, `SOURCING_REVIEW_REQUIRED`, `CONCEPT_REJECTED`;
- concept comparison за decision criteria, а не за aesthetic preference;
- supplier discovery відділяється від supplier approval.

### Гіпотези для тестування

- portfolio `Entry / Premium / Innovative` проти concepts, сформованих навколо трьох різних customer problems;
- три обов'язкові concepts проти adaptive count за evidence diversity;
- generative concept images як спосіб швидшого customer/internal feedback;
- provisional BOM/MOQ ranges як elicitation aid, але не як sourcing fact.

### Дорожня карта

1. Додати experimental concept lane до Research-to-Operator flow.
2. Побудувати одну Concept Evidence Card для реального opportunity candidate.
3. Згенерувати дві portfolio structures й провести blinded decision review.
4. Для обраного concept створити engineering/sourcing question pack, не manufacturing package.
5. Supplier search запускати лише після feasibility gate й approved requirement baseline.
6. Після supplier evidence оновлювати concept, а не «підганяти» факти під зображення.

### Acceptance tests і метрики

- усі market/problem claims мають evidence status;
- concept image не створює dimensions, material, certification або hidden construction fact;
- BOM/MOQ мають `PROVISIONAL` status до named evidence;
- concept diversity, decision clarity, engineering-return rate, supplier-evidence closure time;
- customer/internal test result не видається за market demand без відповідного design.

## 9. Проєкт: ACOS Management

### Цільові артефакти

- `C:\Users\ystep\Documents\DM AMAZON\Маркетинг Бук\WORKSTREAM_ACOS_Management\ACOS_Management_Working_KB_2026-08-23.md`;
- `C:\Users\ystep\Documents\DM AMAZON\Маркетинг Бук\WORKSTREAM_ACOS_Management\PPC_Backlog.md`;
- `C:\Users\ystep\Documents\DM AMAZON\Маркетинг Бук\WORKSTREAM_ACOS_Management\Agentic_Campaign_Control.md`.

### Беремо в роботу

Amazon PPC Pulse як read-only diagnostic layer, пов'язаний із чинними backlog items:

- `PPC-002`: schema/date/identity validation;
- `PPC-003`: versioned threshold registry;
- `PPC-004`: human review queue;
- `PPC-007`: false-positive, missed-incident і threshold review;
- `PPC-011`: freshness/failure-aware scheduled pull;
- `PPC-038/039`: authority registry й append-only trace;
- `PPC-060/061`: persistence/regime logic для signal escalation.

Обов'язкові нові outputs: `PPC Pulse Shadow Report`, `coverage_receipt`, `spec_code_parity_report`, `preliminary_recheck_queue`.

### Гіпотези для тестування

- усі source thresholds, floors, spend minimums і window multipliers;
- same-weekday baseline;
- D-4 attribution settlement rule;
- maximum 8 findings / 5 campaign findings;
- 75% або інші significance thresholds із суміжних матеріалів — лише у відповідному experiment context, не у Pulse за замовчуванням.

### Дорожня карта

1. **Spec reconciliation:** узгодити `SKILL.md`, tables, `pulse.py`, worked example, X1 windows, floors і ratio contribution semantics.
2. **Configuration layer:** threshold/window/floor/attribution settings як versioned config за marketplace/account/campaign role.
3. **Deterministic fixtures:** healthy account, low-volume spike, unsettled attribution, missing target, average-of-ratios trap, duplicate findings, event mode, partial coverage.
4. **Shadow run:** 10 business days на одному marketplace без campaign changes; human reviewer labels useful/noise/missed issue.
5. **Daily read-only pilot:** findings plus coverage receipt і ranked direction-only next steps.
6. **Integration:** передавати confirmed finding у чинну ACOS decision queue; Pulse не встановлює bid/budget.
7. **Scale gate:** інший marketplace отримує власну configuration/eval, без копіювання thresholds.

### Acceptance tests і метрики

- aggregate-first ratio calculations;
- zero actionable finding on healthy fixture;
- 100% skipped triggers мають reason;
- preliminary sales-side signal не стає high severity без settlement rule;
- suppression не втрачає reconstructable numbers;
- false-positive, missed-actionable, findings/run, review minutes/run;
- `PULSE_PARTIAL_COVERAGE` і `PULSE_INVALID_INPUT` не описуються як «все добре»;
- zero autonomous PPC mutation.

## 10. Проєкт: TikTok Shop / Creator Commerce / Social Reels

### Цільові артефакти

- `C:\Users\ystep\Documents\DM AMAZON\TIKTOK_SHOP_CREATOR_COMMERCE_PILOT_PLAYBOOK_2026-09-10.md`;
- `C:\Users\ystep\Documents\DM AMAZON\AI_TZ\TZ_AI_04_Social_Reels_Country_Experiment_Agent_v0.1.md`.

### Беремо в роботу

- `Slot Contract` адаптується до carousel slide, shoppable image і short-video shot;
- `Temporal Shot Contract` із start/end state, camera path, product motion, continuity anchors і failure conditions;
- exact SKU/claim/rights lock перед creator handoff;
- creator отримує raw material pack: approved product facts, reference visuals, allowed claims, prohibited claims, shot/demo options і disclosure/usage-rights requirements;
- text-safe-zone, locale, UI overlay і mobile readability перевіряються на TikTok surface, не за Amazon rules;
- comment/creator signals залишаються hypothesis inputs до Shop funnel й contribution evidence.

### Гіпотези для тестування

- 3-second hook;
- lo-fi/native visual проти polished creative;
- human presence та hands-on demonstration;
- same-week trend adaptation;
- median recent views і recency як creator-selection signals;
- one-call text+product composite проти native overlay;
- 4–6 second stable shots і two-axis motion budget.

Кожна гіпотеза тестується через чинний Carousel/Experiment Card. Не змінювати одночасно hook, creator, offer, format і paid support.

### Дорожня карта

1. Розширити proposal для `Slide Contract` і Experiment Card полями fidelity/evidence/execution mode.
2. Створити один SKU-Angle Wedge із трьома test cells: opening, proof mechanism або visual execution — тільки одна variable per comparison.
3. Зробити brand-made prototype перед creator handoff.
4. Перевірити creator package на Product Truth, disclosure, rights і exact CTA.
5. Публікувати через existing Native Publish Handoff.
6. Scale лише після Shop funnel, contribution, fulfilment, returns і repeatability gates.

### Acceptance tests і метрики

- product/claim/CTA traceability;
- hook hold/completion, product-page view, ATC, checkout, order і contribution;
- creator output reuse/approval rate;
- comment signal → hypothesis → test closure;
- identity/text defects і channel-compliance blocks;
- жодного перенесення Amazon image threshold як TikTok policy.

## 11. Проєкт: Marketplace Market Intelligence Agent

### Цільовий артефакт

`C:\Users\ystep\Documents\DM AMAZON\07_Agents\marketplace-market-intelligence\SKILL.md`

### Беремо в роботу

- `Platform Spec Binding` як output marketplace-mechanism adapter;
- окремі states `OFFICIAL_CURRENT`, `OFFICIAL_STALE`, `SECONDARY_HYPOTHESIS`, `ACCOUNT_OBSERVATION`, `UNVERIFIED`;
- market/category/country/account/date scope для image, listing, fulfilment і creator rules;
- versioned capability/source receipt;
- research rule може відкрити bounded test, але не публікацію або account change.

### Гіпотези для тестування

Усі source-specific numeric claims щодо image count, product coverage, default language, human presence, resolution, provider limit і trend behavior. Вони входять у backlog verification або experiment design, а не в hard rules.

### Дорожня карта

1. Додати proposed `platform_spec_binding` schema до output contract.
2. На одному marketplace провести official-source refresh для конкретного country/category/surface.
3. Зіставити guide claims із official evidence: confirm, narrow, reject, expire.
4. Передати verified binding у AI Design/Content TZ; unresolved rules передати як `EXPERIMENT_ONLY`.
5. Налаштувати recheck trigger за date, policy change або publication defect.

### Acceptance tests і метрики

- 100% hard platform rules мають source/version/checked_at/scope;
- unverified rule не дає `CHANNEL_READY`;
- cross-market leakage rate;
- stale binding rate й time-to-refresh;
- кількість source claims, переведених у verified/narrowed/rejected status.

## 12. Проєкт: AI Procces building

### Цільовий артефакт

`C:\Users\ystep\Documents\AI Procces building\KNOWLEDGE_TO_AGENT_ASSET_OPERATING_INSTRUCTION.md`

### Що забираємо

Не camera/prompt details, а сам пакет як demonstrative process case для вже наявних `Reusable Creative Skill Package Contract` і `Agent graph adoption`.

### Дорожня карта демонстраційного кейсу

1. **AS-IS:** зафіксувати заявлений router, package inventory, tools і route count.
2. **Gap register:** 4/5/6-route inconsistency, documented-versus-callable gaps, missing dependencies, authority conflicts, unverified provider parameters.
3. **TO-BE:** capability-aware router із fail-closed blocker, fallback і evidence receipt.
4. **SOP:** onboarding/update skill package — inventory → reference closure → binding → fixtures → activation → monitoring → rollback.
5. **RACI:** package owner, runtime owner, domain authority, verifier, release owner.
6. **Acceptance test pack:** missing tool, stale spec, unauthorized action, conflicting references, negative route, recovery after interruption.
7. **Handoff:** process case передається як навчальний/демонстраційний, не як активний Creative Designer runtime.

### Гіпотези для тестування

- чи зменшує Capability Receipt час діагностики routing failures;
- чи знаходять negative fixtures більше критичних дефектів, ніж structural review;
- чи потрібен один router або кілька domain-specific adapters.

### Метрики й межі

- time-to-diagnose, unresolved dependency rate, false-ready verdicts, handoff completeness, rollback success;
- не переносити fixed prompt schemas або marketplace numbers у загальний process conveyor.

## 13. Проєкт: AI in Supply Chain

### Цільові артефакти

- `C:\Users\ystep\Documents\AI in Supply Chain\AI_in_Supply_Chain_Practical_Implementation_Program.md`;
- `C:\Users\ystep\Documents\AI in Supply Chain\knowledge_base\articles\ARTICLE_TO_ASSET_OPERATING_INSTRUCTION.md`.

### Беремо в роботу

1. `Agent Capability Receipt` як практичний asset для Modules 15–17 і 19: documented tool ≠ runtime-ready capability.
2. PPC Pulse узагальнюється у `Operational Signal Pulse Method Card`:
   - relative change;
   - absolute materiality;
   - baseline volume;
   - data maturity/latency;
   - suppression/root-cause compression;
   - coverage receipt;
   - human action gate.
3. `Evidence ceiling` для generated technical diagrams: візуалізація не створює BOM, dimension, process або safety fact.
4. `Execution Plane Map` для agent/workflow design: decision, probabilistic analysis, deterministic validation й human release.

### Гіпотези для тестування

- context-specific thresholds для forecast exception, supplier delay, inventory risk або transport deviation;
- same-weekday/seasonal baselines;
- alert caps і suppression order;
- dynamic-versus-static baselines;
- visual prompt guides як спосіб швидше створювати навчальні assets, але не як proof.

### Дорожня карта

1. Створити `Operational Signal Pulse Method Card` із supply-chain прикладом.
2. Побудувати fixture set: healthy noise, low-volume spike, delayed data, duplicate symptoms, partial coverage.
3. Провести workshop/use test на одному decision process, наприклад inventory exception review.
4. Додати Capability Receipt до agent/vendor evaluation exercise.
5. Публікувати як method/tool asset після independent reviewer й use test.

### Acceptance tests і метрики

- threshold без business-cost context не стає policy;
- quiet result містить coverage;
- alert веде до named decision/owner, а не просто anomaly;
- false/missed alerts, review minutes, decision lead time, action reversals;
- generated diagram має evidence boundary.

## 14. Проєкт: Articles and training products

### Цільовий артефакт

`C:\Users\ystep\Documents\Статті\Інструкція Article-to-Asset.md`

### Забираємо чотири готові editorial/product directions

1. **Installed is not callable.** Primary asset: `Agent Capability Receipt`.
2. **A professional prompt is not a camera or physics engine.** Primary asset: `Parameter Reality Ledger`.
3. **Quiet dashboard does not mean healthy system.** Primary asset: `Coverage Receipt`.
4. **“Keep the product unchanged” has five different meanings.** Primary asset: `Fidelity Mode Card`.

Для кожного напряму потрібні: managerial decision, case, failure mode, reusable checklist/card, evidence boundary, independent reviewer і silent-read/use test.

### Гіпотези для тестування

- article → carousel → short presentation derivative;
- diagram-first explanation проти narrative-first;
- unverified numeric examples як clearly labelled exercises;
- capability/coverage cards як downloadable assets.

### Acceptance tests і метрики

- source claim, inference, hypothesis і recommendation розділені;
- жодна provider/platform claim не подається current без verification;
- artifact можна використати без автора;
- completion, reuse/download, workshop decision quality, reviewer corrections;
- presentation formatting не підмінює evidence quality.

## 15. Проєкт: Central KB та skill-governance layer

### Беремо в роботу

- завершити тематичну хвилю єдиним source/case inventory;
- оновити релевантні case/function indexes лише один раз;
- rebuild lexical index і semantic index після recoverable backup;
- перевірити SHA linkage, case count і golden queries;
- додати capability/package state до майбутніх skill/plugin intakes;
- не створювати новий canonical case для кожного corroborating guide.

### Поточний блокер

Semantic search у хвилі повертав NumPy `PermissionError`. До відновлення runtime semantic results не використовуються як доказ; lexical fallback і direct canonical read-back залишаються допустимими.

### Acceptance tests

- немає source register зі статусом `in_progress` у завершеній хвилі;
- один canonical case на net-new method, без дублювання compact guides;
- lexical/semantic case counts і index SHA узгоджені після rebuild;
- golden queries знаходять дев'ять канонічних контрактів;
- batch maintenance не змінює downstream project artifacts.

## 16. Загальний порядок реалізації

### Крок 1 — погодити portfolio decisions

Підтвердити `P0`, `P1`, `P2`, owners і capacity. Окремо вирішити, чи ACOS Pulse та Image/Video Prompt Agent розробляються паралельно чи послідовно.

### Крок 2 — підготувати insertion packages

Для кожного `PROPOSE` створити точний change set: target section, fields/statuses, acceptance tests, migration impact і що навмисно не змінюється.

### Крок 3 — спочатку fixtures, потім runtime

Жодна implementation task не стартує без positive, negative, conflict і stale-evidence fixtures. Structural validation не замінює behavioral test.

### Крок 4 — shadow/pilot before authority

Нові agents, creative routes й PPC Pulse спочатку працюють у planning/shadow/read-only режимі. Authority розширюється окремим рішенням після read-back.

### Крок 5 — learning receipts

Кожний pilot завершується: `expected | observed | evidence gaps | guardrail breaches | reviewer decision | rule/config change | next state`.

## 17. Рішення, які потрібні від власника портфеля

1. Затвердити або змінити пріоритет `P0 → P1 → P2`.
2. Назвати перший non-live SKU для AI Design/Prompt Agent pilot.
3. Назвати marketplace/account для PPC Pulse shadow run.
4. Визначити перший supply-chain use case для generic Pulse Method Card.
5. Після цього окремо дозволити внесення в downstream artifacts; до такого дозволу roadmap залишається `PROPOSAL_ONLY`.

## 18. Межі доказовості

- Документ синтезує локальні матеріали й чинні project artifacts; він не перевіряє live marketplace policies, provider APIs, model quality або account data.
- Непідтверджені правила дозволені лише як experiments із чітким статусом.
- Позитивний pilot на одному SKU, account або marketplace не доводить універсальність.
- Runtime readiness, engineering correctness, supplier feasibility, channel compliance й business lift мають окремі evidence gates.
