# PRODUCT MEDIA SEMANTIC REGISTRY

Версия: 1.1  
Статус: нормативный  
Дата: 30.09.2026

## Призначення

`PRODUCT_MEDIA_SEMANTIC_REGISTRY` — єдиний versioned semantic index усіх фото, відео, frames/clips і external media records точного товару. Він створюється при первинному Паспорту, delta-оновлюється при кожному новому intake/context і використовується Content TZ, Prompt Agent, AI Creator та QA.

Реєстр не є другим Паспортом і не встановлює Product Truth. Він описує, що фактично видно/чути, де саме, з якою confidence і для яких downstream tasks матеріал потенційно корисний.

## Розміщення й версії

`<product_root>/службові/product_media_semantic_registry/product_media_semantic_registry.json`

Кожна revision immutable; active pointer містить path/version/SHA-256. Старі revisions зберігаються.

## Обов'язковий зміст

- immutable `asset_id`, media type, original/current filename, canonical path, SHA-256, source/provenance, exact product/version applicability;
- observed objects/components/configuration/action/result/person/PPE/environment/logos/text/angle/quality/defects;
- Creator roles, value/JBTD IDs, checklist IDs і allowed routes;
- для video — timecoded segments зі start state, action, end state/result, visible product/components/connections, continuity, frame/clip usefulness і quality;
- task-scoped dispositions та append-only semantic events.

Фізично різати video на intake не потрібно: timecode є locator; frame/clip створюється як derived asset тільки при використанні та має parent binding.

## Інваріанти

1. Перейменування не змінює `asset_id`; original/current names і path-change event зберігаються.
2. Duplicate SHA-256 отримує `duplicate_of`; новий content hash — окремий asset/revision relation.
3. Новий context виконує delta enrichment; correction не переписує старе observation без event/reason/actor/time.
4. `NOT_RELEVANT_FOR_TARGET` не є global reject: інший target повторно оцінює asset.
5. Route priority: `DIRECT_REUSE → CROP/RETOUCH → EDIT/COMPOSITE → HYBRID → GENERATE_NEW`.
6. Downstream agent фіксує registry version/hash, target query, evaluated/selected IDs і reasons; execution-bound candidate завжди оглядається безпосередньо.

## Checklist bindings

Stable `checklist_item_ids` охоплюють щонайменше: product identity, full kit, component/configuration, connection, operation, before/process/after, visible result, scale/reach, storage, transport, safety/PPE, advertised branding, third-party marks, packaging, mobile readability і source quality. Категорійні пункти додаються extension IDs зі збереженням original wording.

## Ролі

- Собиратель Паспорта створює initial registry для всіх media intake.
- Image Collector додає internet media, observations, video segments, comments/customer signals і Creator utility tags.
- Content TZ робить target-scoped query для кожного shot/scene/value.
- Prompt Agent повторно оглядає execution candidates і фіксує exact bindings.
- AI Creator до generation перевіряє reuse/edit candidates; після execution записує derivative lineage та usefulness.
- Auditor перевіряє coverage, locators, hashes, event history і пропущений придатний candidate.

## Стани

Registry: `DRAFT | ACTIVE | SUPERSEDED`. Observation: `OBSERVED | INFERRED | UNKNOWN | CONFLICT`. Task disposition: `SELECTED | ALTERNATE | NOT_RELEVANT_FOR_TARGET | QUALITY_INSUFFICIENT | IDENTITY_UNCERTAIN | BLOCKED_BY_CLAIM | NOT_REVIEWED`.

## Emergent JBTD/value candidates

Якщо під час огляду media виявлено точну дію, configuration, use case або видимий результат, якого немає в confirmed JBTD/value Паспорта, агент не відкидає сигнал. Він створює `EMERGENT_JBTD_VALUE_CANDIDATE` і пов’язує його з exact `asset_id`/`segment_id`, source, observed action/result та confidence.

Перед створенням кандидата виконай semantic comparison з чинними JBTD/value: `MATCH_EXISTING | EXTENDS_EXISTING | NET_NEW | CONFLICT | UNRESOLVED`. `MATCH_EXISTING` створює evidence binding до існуючої записі, а не duplicate candidate.

Lifecycle: `REQUIRES_CONFIRMATION → CONFIRMED | REJECTED | MERGED_WITH_EXISTING | SUPERSEDED`. До рішення кандидат передається в Паспорт в окремий блок кандидатів і не стає Product Truth.

Content eligibility до підтвердження: `EVIDENCE_BOUND_VISUAL_USE`. Можна показувати лише точно спостережувану дію/результат у тій самій configuration/context з traceable evidence. Заборонені generalized performance claims, числові обіцянки, порівняння, причинні висновки та поширення на інші умови. `CLAIM_COPY` дозволяється лише після `CONFIRMED`/`MERGED_WITH_EXISTING` і звичайної claim-перевірки.

## Форма рішення власника

Для кожного `REQUIRES_CONFIRMATION` Паспорт обов’язково показує чотири варіанти: `CONFIRM_AS_JBTD | CONFIRM_AS_VALUE | RECLASSIFY_AS_SCENARIO | REJECT`. Рішення фіксує `decided_by`, `decided_at`, rationale, final classification і application scope.

`RECLASSIFY_AS_SCENARIO` зберігає evidence та content utility, але не додає запис до JBTD/value. `CONFIRM_AS_JBTD` і `CONFIRM_AS_VALUE` завжди мають explicit application scope; це не розширює evidence за межі observed context.

## Acceptance tests

- усі media мають ID/path/hash/provenance;
- video segments мають valid range і parent;
- checklist/value/JBTD bindings використовують stable IDs;
- кожне observed action/result або пов’язане з existing JBTD/value, або має `EMERGENT_JBTD_VALUE_CANDIDATE` з evidence locator;
- original filename збережено, current name відповідає видимому content;
- немає silent overwrite;
- execution candidate оглянуто;
- `GENERATE_NEW` має documented insufficiency reuse/edit routes;
- active pointer/hash збігається з registry file у `product_root`.

## Межі доказовості

Semantic tag означає potential usefulness, а не Product Truth, claim approval, QA acceptance чи publication authority.
