# 06. Production and Learning — briefs, тесты и обучение

**Статус:** working

## Производственный цикл

```text
Customer insight + product truth
        ↓
Creative brief
        ↓
Design / copy / photo / video
        ↓
Claim and Visual QA
        ↓
Publish or structured test
        ↓
Winner Library + Marketing Book update
```

## Creative Brief

Каждый brief содержит:

```text
Asset ID / version:
Канал, страна, язык, формат:
Аудитория и рабочая ситуация:
Задача пользователя:
Одна central idea:
Hook:
Product truth / demonstrable proof:
Комплектность, compatibility, ограничения:
Allowed claims / prohibited claims:
CTA:
Primary KPI and guardrails:
Owner / approval status:
```

### Minimum Viable Brief Gate

Неполный вход можно принять, но до детальной production-разработки необходимо зафиксировать:

| Поле | Требование |
|---|---|
| Audience | Для кого создается материал и в какой ситуации выбора/использования |
| Desired outcome | Какое изменение поведения или бизнес-результат ожидается |
| Hypothesis | Почему сообщение, proof или формат должны привести к outcome |
| Evidence status | Что подтверждено, что является hypothesis, assumption или unknown |
| Metric / decision | По какой метрике и правилу принимается следующее решение |
| Available source materials | Доступные документы, assets, product facts, исследования и прошлые результаты |
| Assumptions | Рабочие допущения, используемые временно |
| Blocking questions | Только вопросы, без которых нельзя принять ближайшее решение |
| Early direction checkpoint | Outline и один representative brief для дешевой проверки направления |

Статусы: `rough_input_received -> minimum_brief_ready -> direction_validation_required -> direction_confirmed -> ready_for_production`. Пропуск обязательного поля фиксируется как blocker.

До массовой разработки согласовать outline и один representative brief. Decision record: `direction selected | reason | audience/outcome fit | rejected alternative | unresolved issue | confirmer | timestamp | next commitment`.

До confirmation действует `exploration_mode`. После `direction_confirmed` действует `committed_direction`: material change требует `reason | affected artifacts | cost/calendar impact | metric/acceptance impact | reapproval owner/status`. Без explicit reapproval зависимые материалы не изменяются.

## Creator brief

Формула для short-form content:

`hook -> реальная демонстрация -> граница обещания -> CTA`.

Creator не получает задание «сделать вирусно». Он получает точную задачу, продуктовую правду, допустимые claims, запрет на ложную демонстрацию и условия использования контента.

## Experiment Card

За один тест меняем одну основную переменную: hook, hero image, демонстрацию, proof block, CTA или порядок image slots.

| Поле | Что фиксируем |
|---|---|
| Hypothesis | H0/H1 и почему вариант должен помочь конкретному решению |
| Baseline | текущий asset и результат |
| Primary KPI | CTR, qualified visit, CVR, ATC, purchase — по задаче |
| Test surface / outcome type | Для Amazon MAIN: `SIMULATED_SHELF_CHOICE`, `LIVE_SEARCH_CTR` або `PDP_CONVERSION/SALES`; не підміняти один результат іншим |
| Evidence route / denominator | Метод тесту, marketplace/ASIN/query або PDP cohort, observation window, baseline і challenger version; респонденти та вибір у pretest, impressions/clicks для CTR, unique visitors/orders/sales для PDP |
| Decision-worthy effect / MDE | минимальный lift, который оправдывает изменение |
| Sample / power | требуемый n, power target и единица анализа |
| Test family | primary metric/segment, one- или two-sided, число сравнений и correction rule |
| Unit-economics definition | finance owner, currency, revenue, COGS, variable fulfillment/payment costs, attributable variable acquisition costs, returns/refunds horizon і formula version |
| Economic decision metric | contribution per exposed unit та incremental contribution net of implementation/operating cost; для non-commercial surface — `ECONOMICS_NOT_OBSERVED` із причиною |
| Guardrails | compliance, AOV, gross margin, CAC, returns/refunds, cancellations, complaints/trust, repeat purchase і operational capacity |
| Decision rule | scale / continue / stop до запуска |
| Replication plan | новое окно, holdout или независимая когорта до статуса winner |

Для Amazon MAIN simulated-SERP test або швидка перевірка зрозумілості відбирають гіпотези, але не встановлюють фактичний CTR чи продажі. Manage Your Experiments рандомізує відвідувачів PDP і дає conversion/sales evidence; його результат не є доказом зміни search-result CTR. Якщо тип outcome, denominator, контекст або sufficiency відсутні, фіксувати `inconclusive` чи `experiment_error`, а не `winner`. Пороги на кшталт 50 респондентів або 75% significance не застосовувати без заздалегідь визначених MDE, sample/power і decision rule. Channel compliance перевіряється окремо до live-тесту; прийняття зображення на іншому ASIN не є дозволом для цільового listing.

### CRO Economics Receipt

Для тесту, який змінює conversion, sales, offer або претендує на commercial impact, до Experiment Result Card додається окремий receipt:

| Поле | Що фіксуємо |
|---|---|
| Experiment linkage | experiment/result ID, control/variant hashes, surface, ASIN/marketplace/locale, window і data cutoff |
| Comparable exposure | eligible population, control/treatment exposure, denominator, exclusions і attribution boundary |
| Experiment result | primary metric, effect size, uncertainty, MDE, sample/power і `positive_result / negative_result / inconclusive / experiment_error` |
| Unit economics by arm | conversion, AOV, revenue, COGS, variable costs, contribution per order і contribution per exposed unit |
| Incremental economics | treatment-control contribution на спільній exposure basis мінус incremental implementation/operating cost |
| Guardrail deltas | margin, CAC, returns/refunds, cancellations, complaints/trust, repeat purchase, compliance і operational capacity |
| Economics decision | finance formula/version, owner, verdict, rationale, next action і reuse boundary |

Economics verdict не замінює experiment-result status:

- `ECONOMIC_WIN` — incremental contribution позитивний у межах decision rule, guardrails прийнятні;
- `CONVERSION_UP_PROFIT_DOWN` — conversion зріс, але contribution або обов'язковий guardrail погіршився;
- `ECONOMICS_INCONCLUSIVE` — даних або точності недостатньо для decision-worthy economic effect;
- `ECONOMICS_NOT_OBSERVED` — surface/evidence route не вимірює economic outcome; дозволене лише bounded creative learning без profit claim;
- `DO_NOT_SCALE` — економічний результат негативний, неприйнятний або непереносимий.

Experiment Analyst не підставляє невідомі COGS, acquisition allocation, return horizon або lifetime value. Без затвердженої finance owner формули economic winner не присвоюється. Вищий CTR/CVR не компенсує lower contribution або post-purchase harm.

Views не делают ролик победителем сами по себе. Важен downstream результат при сопоставимом spend и аудитории.

## Winner Library

| Asset ID | Аудитория / ситуация | Hook | Proof | Канал | KPI | Ограничения | Версия |
|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |

В библиотеку заносим причину результата, а не только итоговый файл.

### Evidence status для Winner Library

- `exploratory lead` — post-hoc или secondary finding; требует отдельного подтверждающего теста;
- `initial win` — прошёл заранее заданное decision rule, но ещё не повторён;
- `replicated win` — эффект подтверждён на новом окне, holdout или независимой когорте;
- `scaled standard` — replicated win внедрён и guardrails не ухудшились.

Решение принимается по матрице `statistical support × decision relevance`: значимый, но слишком малый lift не становится winner; большой, но пока неточный эффект отправляется на дополнительный сбор данных. Для commercial claim статус `scaled standard` потребує `ECONOMIC_WIN`; `CONVERSION_UP_PROFIT_DOWN`, `ECONOMICS_INCONCLUSIVE`, `ECONOMICS_NOT_OBSERVED` і `DO_NOT_SCALE` зберігаються в learning library, але не стають profit-backed winner.

**Owner:** Marketing Analytics / PPC Lead. **Следующее действие:** применить расширенную Experiment Card к ближайшему тесту Store, PDP или PPC и не присваивать статус winner без поля `Replication status`.



## AI GTM validation extensions — 2026

### Customer Twin Pretest

Перед запуском важливого PDP, Store, A+, video або campaign concept можна використовувати AI customer twin тільки як hypothesis screen.

| Шар | Вимога |
|---|---|
| Real VoC | Reviews, Q&A, returns reasons, support cases, search terms and customer objections |
| Behavioral map | Job, trigger, fear, switching barrier, proof expected |
| Anchor statements | 4–6 реальних buyer-language реакцій від rejection до strong fit |
| Output | Natural reaction, closest anchor, evidence used, uncertainty, recommended real test |

Не використовувати середній score 1–5 як рішення. Synthetic output не отримує статус customer evidence.

**Owner:** Customer Insights / Content Strategy Lead. **Наступна дія:** створити anchor set для одного priority ASIN і застосувати його до наступних двох creative concepts; переможець визначається реальним Experiment Card, а не twin score.

### Deal-Context Competitive Copilot

Для B2B, distributor або marketplace-partner discussions відокремлювати:

1. регулярний intelligence pipeline — competitor offers, pricing, reviews, proof, objections, win/loss і freshness;
2. deal-time interface — конкретний контекст account/opportunity, релевантні landmines, proof і recommended response.

Copilot не має права вигадувати competitor fact або використовувати stale battlecard без позначення. Кожна відповідь містить `verified facts / inference / recommended tactic / sources / freshness`.

**Owner:** Product Marketing / Commercial Lead. **Наступна дія:** підготувати один approved competitor evidence pack для ключового Amazon.es competitor і перевірити copilot на трьох реальних decision scenarios.

### Evidence boundary

Методи походять із practitioner case collection Growth Unhinged. Наведені в джерелі pipeline, CTR і productivity результати не є нашими benchmark і мають підтверджуватися власними контрольованими вимірюваннями.

## Creator Brief Extension — AI Visibility

AI visibility стає додатковим deliverable creator campaign, але не замінює product truth, audience fit, compliance чи business outcome.

### Creator citation baseline

Перед shortlist перевіряємо:

| Поле | Що фіксуємо |
|---|---|
| Prompt cluster | Category, problem, use case, comparison, recommendation |
| Model / surface | ChatGPT, Gemini, Perplexity, Google AI surfaces та інші релевантні |
| Citation footprint | Чи згадується creator; які URL/платформи цитуються |
| Topical authority | У якому контексті creator вважається релевантним |
| Narrative accuracy | Чи коректно AI передає позицію creator-а та brand context |
| Freshness | Дата аудиту й останнього релевантного матеріалу |

Citation footprint — один із selection signals, а не гарантія результату.

### Поля AI Visibility Deliverable у creator brief

- target prompts/topics;
- explicit brand і product name;
- buyer/job/use context;
- demonstrable proof і differentiator;
- honest limits та comparison boundary;
- machine-readable caption або transcript;
- durable public URL і disclosure;
- заборона keyword stuffing, duplicated scripts і неперевірених claims.

### Measurement and stop rule

Вести pre/post citation panel поруч із reach, engagement, qualified traffic, sales, ROAS і cost efficiency. Окремо показувати unique cited sources, source diversity, narrative accuracy та citation plateau. Кореляцію між campaign і AI visibility не називати причинним ROI.

Зупинити або переробити хвилю при duplicated wording, concentration in one source/platform, narrative distortion, community backlash або відсутності citation movement після погодженого observation window.

**Owner:** Creator Marketing Lead разом із SEO/GEO Lead. **Наступна дія:** провести baseline для п’яти потенційних creators у двох priority prompt clusters і використати нові поля в наступному creator brief; Sales/ROAS залишаються обов’язковими outcome metrics.

<!-- PARTNER_BRIDGE_PORTABILITY_EXPERIMENT_2026_08_29_START -->
## Partner Audience Bridge and Portability Test

### Creator / affiliate brief extension

For every partner, complete:

`existing audience desire -> unresolved next job -> relevant product/asset -> credible proof -> natural promotion angle -> trust-preserving CTA`

The brief must also contain the approved repeatable line, prohibited overclaims, evidence links and the buyer condition under which the product is not a fit.

### Experiment card extension

Test one bridge angle at a time. Record:

- unaided recall and accurate repeatability of the core idea;
- share/referral rate;
- percentage of reviews/UGC that repeat the mechanism or approved line;
- creator message consistency;
- qualified traffic, conversion and new-to-brand by bridge angle;
- complaint/negative-sentiment rate for sensitive framing or humor.

### Winner rule

An asset is not a positioning winner from reach or CTR alone. Promote it to the Winner Library only when the idea travels accurately across at least two independent creators/audiences and retains proof, fit conditions and acceptable sentiment.
<!-- PARTNER_BRIDGE_PORTABILITY_EXPERIMENT_2026_08_29_END -->

## Agentic Media Brief — executable contract

Agentic Media Brief is not a descriptive campaign note. It is an executable contract for AI-assisted media, campaign, marketplace, retail media, PPC, DSP, creator amplification or automated optimization workflows.

The brief must define what the system is allowed to do, what it must not do, what result it optimizes for, which proxies are acceptable, when automation must stop, and when a human owner must decide.

An incomplete Agentic Media Brief must not launch. The system must return `missing_decisions` with the exact missing fields and owner required to resolve them.

### Required Agentic Media Brief fields

```text
Brief ID:
Campaign / media objective:
Business outcome:
Proxy metrics:
Decision metric and threshold:
Budget:
Period:
Geo:
Format:
Frequency:
Pacing:
Allowed audiences:
Blocked audiences:
Allowed inventory:
Blocked inventory:
Allowed contexts:
Blocked contexts:
Allowed adjacency:
Blocked adjacency:
Brand-safety constraints:
Legal constraints:
Age constraints:
Privacy constraints:
Creative-to-context rules:
Automatic targeting change boundaries:
Automatic bid change boundaries:
Automatic pacing change boundaries:
Automatic supply-path change boundaries:
Stop-loss thresholds:
Anomaly thresholds:
Escalation conditions:
Vendor-reported campaign results evidence status:
Missing decisions:
Owner:
```

### Vendor-reported campaign results evidence status

Vendor-reported results can be useful, but they are not automatically decision-grade evidence. They must be marked separately from platform export, controlled experiment, internal analytics or verified business outcome.

Allowed evidence statuses:

- `vendor_reported_unverified` — vendor or agency reported result without independent verification;
- `platform_export_verified` — result checked against platform export or raw report;
- `internal_analytics_matched` — result matched to internal analytics/CRM/order data within known limits;
- `controlled_experiment_supported` — result supported by holdout, geo split, incrementality test or other controlled method;
- `business_outcome_confirmed` — linked to verified business outcome with documented attribution limits;
- `not_verifiable` — source is unavailable or cannot support the claim.

Vendor-reported results must include date, source, metric definition, attribution window, included/excluded channels, known limitations and owner.

### Automation boundaries

Automatic changes are allowed only inside written boundaries. The system must not autonomously expand into blocked audiences, blocked inventory, blocked contexts, blocked adjacency, sensitive age groups, legally restricted contexts, privacy-sensitive segments or unapproved supply paths.

Any proposed change outside boundaries must be returned as `escalation_required`, not executed.

### Stop-loss and anomaly control

Stop-loss and anomaly thresholds must be set before launch. Examples of threshold types:

- spend without minimum proxy signal;
- CPA/ACOS/ROAS outside accepted range;
- sudden conversion drop;
- abnormal CTR/CVR spike that may indicate tracking or traffic-quality issue;
- frequency above allowed ceiling;
- traffic from blocked or unknown inventory;
- geo/audience drift;
- brand-safety or legal flag;
- vendor-reported result that conflicts with platform/internal data.

### Requirements

| ID | Requirement | Level |
|---|---|---|
| MB-AMB-R001 | Agentic Media Brief must state business outcome and proxy metrics separately. | MUST |
| MB-AMB-R002 | Budget, period, geo, format, frequency and pacing must be explicit before launch. | MUST |
| MB-AMB-R003 | Allowed and blocked audiences, inventory, contexts and adjacency must be defined before launch. | MUST |
| MB-AMB-R004 | Brand-safety, legal, age and privacy constraints must be explicit and machine-readable enough for agent execution. | MUST |
| MB-AMB-R005 | Creative-to-context rules must define which claims, visuals, offers, proof and tone are allowed in each context. | MUST |
| MB-AMB-R006 | Boundaries for automatic targeting, bid, pacing and supply-path changes must be explicit; changes outside boundaries require escalation. | MUST |
| MB-AMB-R007 | Stop-loss thresholds, anomaly thresholds and escalation conditions must be defined before launch. | MUST |
| MB-AMB-R008 | Incomplete brief must not launch; system returns missing_decisions with missing field, risk and owner. | MUST |
| MB-AMB-R009 | Vendor-reported campaign results require evidence status and cannot be treated as verified business outcome without supporting evidence. | MUST |
| MB-AMB-R010 | Agent must separate platform reach, proxy metric movement, human response and business outcome when reporting campaign result. | MUST |
| MB-AMB-R011 | Agent must not optimize proxy metrics in a way that violates brand-safety, legal, privacy, age, adjacency or creative-to-context constraints. | MUST NOT |
| MB-AMB-R012 | Every automated recommendation must produce action status: execute_within_boundaries, escalation_required, missing_decisions, monitor_only or reject. | MUST |

### Acceptance criteria

An Agentic Media Brief is launch-ready only if:

- business outcome and proxy metrics are both present and not conflated;
- budget, period, geo, format, frequency and pacing are filled;
- allowed/blocked audiences, inventory, contexts and adjacency are filled;
- brand-safety/legal/age/privacy constraints are explicit;
- creative-to-context rules are actionable;
- automation boundaries for targeting/bid/pacing/supply path are explicit;
- stop-loss/anomaly/escalation thresholds are set;
- vendor-reported results have evidence status if used;
- missing decisions list is empty.

If any required decision is missing, output status is `missing_decisions`, not `ready_to_launch`.

### Metrics

- complete Agentic Media Brief rate;
- missing decisions by field;
- launches blocked by missing decisions;
- escalations caused by boundary violations;
- stop-loss triggers by type;
- anomaly detections by type;
- vendor-reported result verification rate;
- proxy-to-business-outcome match rate;
- privacy/legal/brand-safety incidents avoided before launch.

<!-- MB-AI-DESIGN-EXPERIMENT-LEARNING-2026-09-09 -->
## AI Design visual hypothesis and experiment contract

Перед production AI/product-image brief повинен містити Primary Visual Hypothesis Card: buyer question, evidence IDs, Product Truth IDs, current observable problem, one dominant change, causal mechanism, held-constant elements, primary metric, guardrails, risks і human decision.

Пакет із 3–5 варіантів має містити 3–5 різних causal hypotheses. Стилістичні варіанти одного mechanism зберігаються як variants однієї гіпотези.

Experiment Result Card обов'язково фіксує control/variant hashes, sample/traffic, primary metric, conversion/return/complaint/compliance guardrails, confounders, uncertainty та один із результатів: `positive_result`, `negative_result`, `inconclusive`, `experiment_error`. Якщо заявлено commercial impact, картка також посилається на `CRO Economics Receipt` з contribution per exposed unit, incremental contribution, guardrail deltas, finance formula/version і окремим economics verdict.

Winner Library зберігає `context -> hypothesis -> evidence -> controlled change -> result -> confidence -> limitation -> reuse boundary`. Asset без цього ланцюга не є reusable winner. Один positive result не стає універсальним standard без Amara Gate.
<!-- MB-ASSET-PORTFOLIO-NECESSITY-2026-09-09 -->
## Asset Portfolio Necessity and subtraction decisions

Before an AI Design production brief, link an approved Asset Portfolio Necessity Card and distinguish `optimization_potential` from `investment_priority`. The brief must state the buyer job, existing assets reviewed, verified gap, case for and against investment, expected incremental value, opportunity cost, approved action and disposition of any superseded asset.

A long list of possible improvements does not raise priority by itself. Portfolio guardrails include role overlap, claim inconsistency, scarce channel slots, production/QA/localization/maintenance cost and fragmented experiment traffic.

Winner and Failure learning must also retain subtraction decisions: `not_created`, `maintained_as_is`, `reused`, `consolidated`, `replaced`, `retired`. Record evidence, owner, date, affected asset IDs, reason and conditions for reconsideration so rejected or consolidated ideas are not repeatedly regenerated.

## Brand entity and query-cluster learning

Every relevant experiment/result record links `entity_definition_id`, `buyer_job_id`, `query_cluster_id` and `portfolio_decision_id`. AI-visibility learning separates:

- accuracy of the brand definition;
- selected category and brand/product distinction;
- cited sources and source freshness;
- sentiment and material misrepresentation;
- cross-system consistency and repeat-run stability;
- observed demand signals from AI-generated hypotheses and tool estimates.

A visibility increase is not a winner when sentiment is negative, the entity/category is wrong, or source support is weak. Record external outdated descriptions and entity conflicts as correction/investigation inputs, not automatic content-production tasks.

## CI-AI learning record separation

Store observation, interpretation, decision, experiment and outcome as separate linked records with immutable provenance, source family/origin, market/time scope, causal strength, expiry/retest date and supersession links. A false alarm, rejected hypothesis, failed test or AI recommendation cannot become positive evidence. Record recommendation run variance, approval invalidation, stop-loss, recovery limitations and downstream blast-radius incidents without storing raw model reasoning as reusable truth.

<!-- MB_MESSAGE_MEDIA_2026_09_27_START -->
## Зв'язок причини покупки з виробничим завданням

### Вхідні дані та правила виконання

Доповнити чинний Creative Brief, не створюючи паралельний паспорт. Buyer Reason Card — логічний блок цього ж брифу: `buyer_job`, `use_scenario`, `purchase_trigger`, `primary_selling_reason`, `belief_shift`, `proof_refs`, `offer_or_review_refs`, `evidence_status`, `owner`. Не вигадувати мотив, знижку чи відгук; непідтверджене лишається гіпотезою або питанням. Один основний аргумент визначається для конкретного завдання, а не назавжди для всього бренду. Brand Message Fit застосовується до зміни наявного контенту за умовами стандарту повідомлень.

Кожний запланований кадр/slot отримує рядок у чинному плані: `slot_id`, `role`, `buyer_question`, `buyer_reason_ref`, `message`, `evidence_ids`, `exact_copy`, `visual_proof_mechanism`, `source_asset_ids`, `execution_mode`, `acceptance_test`. Порожні необов'язкові поля мають обґрунтоване `NOT_APPLICABLE`; непідтверджений факт не замінюється таким статусом. Кадр без функції повертається на уточнення; канально обов'язковий ракурс може бути потрібним без окремої рекламної тези. Канонічні сім слотів галереї не перенумеровуються.

Для наявного upload зафіксувати використання: `PASS_THROUGH`, `REBUILD`, `VISUAL_SOURCE`, `DATA_ONLY` або `NOT_USED`, причину та права. Стиль узгоджує палітру, світло й характер зображень, але не примушує всі кадри повторювати один ракурс. Не додавати текст, стрілки або декорації лише для заповнення шаблону.

### Прив'язка вимог каналу

До чинного поля «Требования канала» додати `platform`, `market`, `category`, `surface`, `official_source`, `version_or_checked_at`, `checker`, `hard_requirements`, `recommendations`, `conflicts`, `recheck_trigger`. Для тексту також потрібні `locale`, версія затвердженого перекладу та reviewer. Кількість кадрів, розміри, допустимі написи й заборони беруться з цієї перевіреної прив'язки, а не з пам'яті агента. Зміна ринку, placement, правила або прострочена релевантна перевірка запускає повторну перевірку.

`PLATFORM_SPEC_UNVERIFIED` блокує висновок про готовність до каналу; концептуальний draft із відкритим питанням допустимий без публікації. Невідома локаль блокує вбудований текст, але не обов'язково безтекстовий ескіз. Непідтверджена можливість генератора не дозволяє обіцяти execution.

### Acceptance tests і метрики

Кожний decision-bearing claim та exact copy мають джерело й applicable scope; кожний slot — роль і критерій перевірки; кожний використаний asset — походження та рішення щодо використання. Відстежувати trace coverage, зайві/повторні кадри, повернення на уточнення й first-pass acceptance. Це якість брифу, не доказ комерційного ефекту.
<!-- MB_MESSAGE_MEDIA_2026_09_27_END -->
