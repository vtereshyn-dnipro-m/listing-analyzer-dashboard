# Listing Suite — ТЗ интерфейса паспорта SKU

## Закладка «Синтез»

Версия: 01  
Статус: компактная рабочая версия  
Дата: 30.08.2026  
Связанный документ: Listing_Suite_ТЗ_Синтез_Паспорт_SKU_v01.md, версия 01

---

## 1. Назначение

Интерфейс предназначен для поддержания Product Truth, источников, evidence и истории SKU.

Он также показывает связанные JBTD и Buyer Episodes из внешней buyer-knowledge области в режиме read-only.

Интерфейс не является:

- редактором marketplace-листинга;
- Marketing Book;
- редактором JBTD и Buyer Episodes;
- системой Episode–SKU Fit;
- системой генерации или публикации контента.

## 2. Стартовый экран

Главный экран состоит из четырёх блоков первого уровня:

1. **Идентификация SKU** — SKU, внутреннее название, страна производства или сообщение о нескольких актуальных значениях по scope, marketplace-контекст и дата изменения.
2. **Evidence status** — пользовательские состояния verified (только для current_verified), partial, unverified и stale; unavailable и access_denied показываются как диагностические состояния доступа source/evidence, без readiness score.
3. **Конфликты** — открытые конфликты фактов, источников и вариаций; каждый показатель ведёт к конкретному объекту.
4. **Решение** — одно доступное следующее действие verifier: проверить proposal, разрешить conflict, запросить уточнение или оставить запись без изменения.

Остальные атрибуты, источники, evidence, история, технические ID, scope и версии раскрываются по запросу. Они не конкурируют с четырьмя блоками первого уровня. Это обязательная логика progressive disclosure.

Несогласованность вариаций показывается отдельным критическим alert, а не строкой среди характеристик. Alert содержит marketplace, parent/child или variation theme, конфликтующие значения и требуемое решение verifier.

Основные действия:

1. Добавить источник.
2. Проверить предложения.
3. Разрешить конфликты.

Показатели открывают соответствующие рабочие очереди и не являются generation gate.

Минимальные роли и ограничения действий сохраняются: contributor создаёт proposals, verifier принимает решения, administrator управляет правами и восстановлением; административная роль сама по себе не даёт права подтверждения.
## 3. Навигация

Доступны четыре области:

1. Product Truth.
2. Источники и evidence.
3. Связанные JBTD / Buyer Episodes — read-only.
4. История изменений.

Marketplace Listing открывается отдельно.

## 4. Product Truth

### 4.1. Список фактов

По умолчанию показываются:

- название и значение;
- единица и группа;
- effective_truth_status как основной итоговый статус;
- workflow, verification, freshness и applicability как диагностические компоненты;
- количество evidence;
- конфликт, если есть;
- дата изменения.

Raw `verified` не показывается как текущий подтверждённый факт, если effective_truth_status не равен `current_verified`.

Доступны поиск, сортировка, пагинация и фильтры по группе, статусам, evidence, конфликту и дате.

### 4.2. Карточка факта

Карточка показывает:

- исходное и нормализованное значение;
- тип значения и единицу измерения;
- отдельно context и scope;
- fact identity: fact_code или нормализованное имя вместе со scope;
- независимые статусы;
- связанные evidence и источники;
- конфликт;
- историю и сравнение версий.

Технические ID раскрываются только в служебных деталях.

### 4.3. Действия

В зависимости от роли пользователь может:

- предложить новый факт;
- добавить context или evidence;
- принять или отклонить proposal;
- принять новую версию;
- запросить уточнение;
- открыть conflict;
- просмотреть историю.

Система не заменяет подтверждённое значение молча.

Contributor может создавать и дополнять proposals. Только verifier может принять или отклонить proposal, принять новую версию, создать решение по conflict и установить или снять `verified`.

## 5. Источники и evidence

Пользователь добавляет ссылку или локальный файл. Локальный файл передаётся в Asset Registry; паспорт получает asset_id, версию, hash и locator.

Для источника показываются:

- source_id;
- тип и класс source policy;
- asset_id / asset_version_id или внешний locator;
- состояние доступа;
- lifecycle status источника;
- дата фиксации;
- количество evidence и связанных фактов.

Карточка evidence показывает evidence_id, source_id и версию источника, конкретный фрагмент, страницу, координаты или таймкод, relation `supports / contradicts / insufficient / unclear`, способ создания, дату извлечения и связанные facts или relations.

Доступны действия:

- открыть источник;
- запустить извлечение;
- просмотреть proposals;
- создать manual evidence;
- проверить доступность locator;
- отметить источник устаревшим или заменённым.

Без immutable-версии источника установка `verification_status = verified` недоступна. Если immutable-версия становится недоступна, effective_truth_status меняется на `stale_verified_history`, а запись попадает в очередь пересмотра.

## 6. Связанные JBTD и Buyer Episodes

Раздел является read-only проекцией внешней buyer-knowledge области.

Показываются:

- связанная JBTD;
- краткий контекст Buyer Episode;
- рынок, язык и период, если указаны;
- evidence status;
- дата проверки;
- подпись `Observed together in context`;
- статус relation как техническое состояние связи;
- постоянное пояснение: «Не является оценкой соответствия SKU задаче покупателя»;
- ссылка на каноническую запись.

Из паспорта можно предложить новую запись, исправление или нейтральную relation с SKU. Прямое редактирование и Episode–SKU Fit недоступны.

## 7. История

История показывает:

- дату и объект изменения;
- старое и новое значение;
- тип операции;
- user, agent, import или system;
- причину;
- связанную версию и evidence.

Доступно сравнение текущей и предыдущей версии.

## 8. Состояния интерфейса

Отдельно показываются:

- нет данных;
- proposal ожидает проверки;
- conflict;
- stale;
- unavailable или access denied;
- extraction in progress / failed;
- duplicate detected;
- partial save.

Ошибка не должна выглядеть как отсутствие данных.

Если действие недоступно, интерфейс кратко объясняет причину и указывает допустимый следующий шаг. Например: добавить подходящий источник, передать предложение verifier или открыть каноническую запись во внешней области.

## 9. Проверка MVP

Интерфейс соответствует MVP, если пользователь может end-to-end:

1. добавить источник и получить proposals;
2. проверить и принять или отклонить proposal;
3. сравнить evidence и разрешить conflict;
4. открыть связанную JBTD или Buyer Episode read-only;
5. корректно обработать unavailable источник.
6. увидеть предупреждение о различающихся характеристиках и понятное объяснение недоступного действия.

Интерфейс не содержит authoring buyer knowledge, Marketplace Listing editor, Analytics, content generation, bulk approval или merge/split UI.

## 10. Changelog v0.6 → v0.7

- интерфейс синхронизирован с независимыми статусами основного ТЗ;
- ролевые ограничения отделены от назначения ответственности;
- карточка факта дополнена value type и fact identity;
- source и evidence синхронизированы с минимальной моделью основного ТЗ;
- в read-only buyer knowledge добавлен статус нейтральной relation с SKU;
- уточнено отображение проверенной страны производства.

## 11. Следующий документ

Технический контракт уточняет API, состояния, права, интеграции, безопасность, производительность, accessibility и тестовые сценарии.

## 12. Нормативное дополнение после adversarial review

Дата: 30.08.2026. При расхождении с более общими формулировками выше этот раздел имеет приоритет.

### 12.1. Четырёхблочный стартовый экран

На summary отображается только effective_truth_status. Raw статусы раскрываются как диагностические детали; одиночный badge `verified` запрещён вне значения `current_verified`. unavailable и access_denied не являются effective_truth_status и отображаются как состояния доступа source/evidence.

На первом уровне одновременно видны только четыре блока:

1. **Идентификация SKU** — SKU, внутреннее название, актуальный scope и marketplace-контекст.
2. **Evidence status** — verified, partial, unverified, stale и unavailable состояния; verified отображается в сводке только при выполнении passport eligibility-check.
3. **Конфликты** — открытые конфликты фактов, источников и вариаций.
4. **Решение** — одно следующее безопасное действие verifier с переходом к конкретному work item.

Если действует несколько scope или значений, шапка не выбирает одно значение молча, а показывает «несколько значений по scope» и раскрывает список.

Открытый conflict исключает объект из однозначной verified-сводки до разрешения. Это предупреждение о качестве знания, а не generation readiness.
### 12.2. Progressive disclosure

Информация раскрывается в три уровня: summary четырёх блоков без технических ID; work item с context, scope, статусами и действиями; audit details с evidence fragments, evidence links, ID, версиями и Change Events. Сигнал всегда ведёт к объекту и evidence, на которых основан.

### 12.3. Variation critical alerts

Несогласованность вариаций — отдельный variation alert и отдельная очередь, а alert с severity = critical — отдельный критический случай; alert не является характеристикой факта. Alert обязан содержать:

- marketplace;
- parent/child или variation theme;
- affected SKU или ASIN;
- конфликтующие fact versions и значения;
- scope каждого значения;
- severity и status;
- требуемое решение verifier;
- дату и ссылку на evidence/history.

Verifier может acknowledge alert, открыть conflict, создать proposal для нужного SKU или resolve с обязательной причиной. Факт одного SKU не показывается как подтверждённый факт другого без отдельного proposal и evidence. Сравнение выполняется по нормализованным единицам, совпадающим scope и периоду. Missing critical fact создаёт alert типа missing_critical_fact. `acknowledged` не убирает alert из активной очереди; `resolved` требует resolution_code, затронутые версии и evidence либо `not_a_conflict`. Alert ничего не разрешает и не блокирует в генерации или публикации.
### 12.4. Нейтральные JBTD и Buyer Episodes

JBTD и Buyer Episodes показываются отдельными коллекциями и могут иметь независимые relations с SKU. Связь JBTD ↔ Buyer Episode отображается только при наличии канонической внешней связи. Relation `observed_in_context` и её статус не означают fit, силу соответствия, приоритет или рекомендацию.

### 12.5. Evidence links

Карточка evidence отдельно показывает source fragment и список evidence links: target, relation и конкретную fact version, buyer-knowledge relation или conflict. Evidence-массивы являются проекциями; создавать и изменять можно только отдельные evidence_link.

### 12.6. Отказные состояния

Для заблокированного действия интерфейс показывает информативную карточку отказа, а не общий текст validation failed. В карточке обязательны:

- заблокированное действие;
- конкретное поле или объект;
- стабильный reason code;
- нарушенное правило или причина;
- сохранённые, подготовленные и несохранённые изменения;
- контекст: marketplace, язык, листинг, версия и источник правила, если доступны;
- один следующий безопасный шаг;
- владелец решения только при необходимости внешнего решения.

`Partial save` показывает operation_id, результат по каждому объекту (`saved`, `prepared`, `failed`, `not_attempted`) и безопасный retry только для failed/not_attempted. `duplicate detected` показывает совпавшие identity и scope. `replaced source` требует существующий replacement source. `clarification request` имеет состояния open/answered/cancelled и оставляет proposal в proposed до ответа или отмены. API может вернуть несколько next_allowed_actions, но UI выделяет одно детерминированное primary action, остальные раскрываются отдельно.

Общий текст validation failed без этих элементов запрещён. Отказ не удаляет сохранённые изменения и не создаёт generation readiness или publication gate.

## 13. Changelog v0.7 → v0.8

- главный экран закреплён вокруг четырёх блоков: идентификация SKU, evidence status, конфликты и решение;
- progressive disclosure определён как обязательный порядок раскрытия данных;
- variation alert дополнен marketplace, parent/child, variation theme, конфликтующими значениями и решением verifier;
- добавлен полный refusal contract с saved changes и context;
- уточнено исключение конфликтующих и устаревших данных из verified-сводки;
- generation readiness и общий readiness score не добавлялись.

## 14. Changelog v0.8 → версия 01

- effective_truth_status закреплён как основной пользовательский статус;
- raw verified отделён от current_verified;
- добавлены правила отображения unavailable и stale_verified_history;
- evidence_link закреплён как единственная каноническая модель связей;
- variation alert дополнен правилами detection и resolution;
- добавлен запрет fallback между SKU на уровне пользовательского контракта;
- partial save дополнен operation_id, idempotency и результатом по объектам;
- next_allowed_actions разделены на primary action и раскрываемые alternatives;
- уточнены clarification и replacement source states.







---

## 15. Changelog после проверки согласованности

Дата: 30.08.2026.

- unavailable/access_denied определены как диагностические статусы доступа source/evidence;
- variation alert разделён на warning и critical по критичности факта;
- сохранена связка UI с country-by-scope и context-scoped Listing/variation model.

<!-- QPO_REQUIREMENT_COVERAGE_UI_2026_09_10_START -->
## 16. Read-only проєкція «Покриття вимог»

Дата: 10.09.2026.

У розділі пов'язаних JBTD / Buyer Episodes додається read-only вкладка `Покриття вимог`. Вкладка відображає зовнішні `requirement_evaluation` і не перетворює Паспорт SKU на Episode–SKU Fit editor.

### 16.1. Таблиця

Для кожного рядка показуються:

- shopping mission / hypothesis і `context_version`;
- атомарна вимога;
- `evaluation_result`: qualifies, disqualifies, conditional або unresolved;
- використані факти та їх версії;
- missing facts;
- required clarification;
- marketplace/country/language;
- дата оцінювання і review status;
- посилання на канонічну QPO-картку.

### 16.2. Картка оцінювання

Картка показує requirement, comparison rule, rationale, fact values, scope, evidence status, missing facts, context version та history. Перехід до факту відкриває його канонічну картку; редагування fit-рішення виконується тільки у зовнішній QPO/buyer-knowledge області.

Постійне пояснення:

> Результат залежить від контексту shopping mission і не є універсальною характеристикою SKU, підтвердженим Product Truth або дозволеним маркетинговим claim.

### 16.3. Стан повторної перевірки

Якщо використана fact version стала stale, superseded, disputed або змінився context version, інтерфейс показує `re-evaluation required`, причину і посилання на об'єкт. Старий результат залишається в історії та не показується як поточний без повторного review.

### 16.4. Перевірка інтерфейсу

- Користувач бачить, який факт призвів до включення, виключення або невизначеності.
- Missing fact не відображається як негативна властивість SKU.
- Read-only вкладка не дозволяє підтверджувати Product Truth або fit.
- Зміна критичного факту дає видимий re-evaluation signal.
- Технічні ID доступні лише на audit-рівні progressive disclosure.
<!-- QPO_REQUIREMENT_COVERAGE_UI_2026_09_10_END -->

<!-- MULTIMEDIA_EVIDENCE_UI_2026_09_10_START -->
## 17. Интерфейс мультимедийных источников и Visual/UGC

Раздел реализует мультимедийный контракт функционального ТЗ и агента-собирателя версии 03.

Доступны отдельные представления: `Видео`, `Комментарии`, `Claims и evidence`, `Сравнения`, `Visual/UGC opportunities`, `Покрытие и gaps`. Claim, evidence, комментарий, интерпретация и asset approval не смешиваются. Claim открывает все evidence, а evidence — все claims и targets many-to-many.

Карточка видео показывает URL, канал/автора, дату, язык, длительность, описание, класс видео, транскрипт/субтитры, попытки аудиотранскрипции, комментарии и ограничения. Каждый вывод показывает `source_id`, locator, timestamp/frame ID/comment locator, source type, evidence class, confidence, relation, conflict/gap и usage-rights status.

Классы evidence: brand claim, author statement, observed on screen, measured/tested by author, subjective author assessment, user comment. Постоянное предупреждение: наличие функции в кадре не доказывает эффективность; слова автора, субъективная оценка и комментарий не подтверждают технический параметр.

Комментарии фильтруются по plus/minus, claim confirmation/refutation, JBTD/контексту, языку и периоду. Агрегат показывает направление, n_comments, независимых авторов, период, доступную выборку, долю и ограничения; он не маркируется как technical evidence.

Сравнение показывает exact competitor SKU, одинаковый сценарий, метрику, условия, методы и evidence обеих сторон. При несопоставимости показывается `comparison_basis_gap`, без победителя.

Visual/UGC opportunity и approved asset — разные сущности. Opportunity показывает scene locator, JTBD, место использования, claim, качество, монтаж, rights/consent, brand/privacy risks. Approval возможен только отдельным действием уполномоченного владельца.

Coverage показывает numerator, denominator, единицу, правило расчёта и unresolved gaps. `inaccessible_expected_scope` остаётся видимым; изменение denominator раскрывает основание и Change Event.

### 17.1. Критерии приёмки интерфейса

- мультимедийный вывод прослеживается до source и точного locator;
- claim/evidence навигируются many-to-many;
- visual opportunity нельзя принять за approved asset;
- комментарии показывают n, период, выборку и направление;
- access gap остаётся видимым в denominator;
- source type, evidence class, confidence, conflict/gap и usage-rights status видны без технического JSON.
<!-- MULTIMEDIA_EVIDENCE_UI_2026_09_10_END -->

## 18. Контроль воспроизводимости и прав мультимедиа

Audit-уровень показывает для каждой производной source, тип, путь или locator, acquired_at, size, SHA-256 и reproducibility status. Для locator показываются результат обратной проверки и точная причина FAIL.

Coverage раздельно отображает planned frames, inspected/usable/rejected/unavailable frames, просмотренные целевые интервалы в секундах и continuous visual coverage либо not measured. Интерфейс не показывает 100% визуального покрытия только на основании выполненного плана дискретных кадров.

Visual/UGC opportunity имеет отдельные поля usage_rights_status, consent_status, privacy_risk_status, brand_risk_status, claim_review_status, owner и next action. Пустое разрешение исключает approved asset.

<!-- AI_SHOPPING_SURFACE_OBSERVATION_UI_2026_09_10_START -->
## UI: узгодженість факту між поверхнями

У картці decision-critical факту додати розкривний блок «Представлення на поверхнях», не змінюючи чотири блоки першого рівня і не показуючи aggregate readiness score.

Таблиця: surface type, marketplace/account, ASIN/variant, observed value, source timestamp, access status, evidence link, state `CONSISTENT | STALE | CONFLICT | MISSING | NOT_APPLICABLE`.

CONFLICT і STALE ведуть до конкретної conflict/evidence card; MISSING не показується як false. Фільтри: surface, marketplace, variant, state, observed date. Primary action: відкрити conflict, оновити evidence, запросити перевірку або нічого не змінювати. Recommendation/transaction decision тут не створюється.

Acceptance: verifier за два переходи бачить surface, value, timestamp і evidence, що спричинили conflict або stale state.
<!-- AI_SHOPPING_SURFACE_OBSERVATION_UI_2026_09_10_END -->

<!-- COGNITIVE_FRICTION_AND_MOMENTUM_UI_LAI101_START -->
## 19. Cognitive Friction Audit і чесний first-value progress

Контроль застосовується до flow: add source, review proposal, open evidence, resolve conflict і request missing evidence. Він не змінює Product Truth schema/statuses і не автоматизує verifier judgment.

### 19.1. Класифікація кроків

- `AUTOMATIC` — знайома повторювана навігаційна або механічна дія;
- `DELIBERATE_REQUIRED` — evidence, applicability, conflict або approval decision, де свідоме рішення обов'язкове;
- `AVOIDABLE_DELIBERATION` — повторне введення, зайвий пошук, втрата контексту, неоднозначний state/icon або непрогнозований interaction.

Primary flow не проходить release з unresolved `AVOIDABLE_DELIBERATION` без documented waiver, task evidence, owner і review date. Автоматизація не може прибрати `DELIBERATE_REQUIRED`.

### 19.2. First-value view

Після першої обробки source інтерфейс показує `first_value_projection`: identity status, processed inputs, candidate facts, evidence links, blocking gaps, conflicts і одну `next_safe_action`. `INITIAL_DIAGNOSTIC_READY` відображається як первинний навігований результат, а не готовий Паспорт або downstream readiness.

Prefill відображається тільки як proposal з source/locator, scope, confidence і review state. Example/dummy data візуально відокремлюється і не впливає на Product Truth, coverage або readiness.

### 19.3. Review queue та expert automaticity

Review queue читає `review_queue_summary`, підтримує стабільне сортування і веде прямо до referenced object/evidence/gap. Для expert user зберігаються стабільні назви та розташування identity/evidence/conflict/decision, keyboard navigation, next item, open evidence, request evidence і повернення до попереднього filter/scroll context. Batch navigation дозволена; batch approval заборонений.

Якщо редизайн змінює spatial layout, shortcuts або learned path, потрібен transition mode або порівняльний task test із decision-error guardrail.

### 19.4. Evidence-based progress

Замість одного percentage окремо показуються processed inputs, required-fact coverage, verified-fact coverage, open Blocking gaps, open conflicts і package/downstream admissibility. Для кожного ratio показуються numerator, denominator і calculation basis. Unknown/inaccessible scope не зникає без scope decision.

### 19.5. Acceptance metrics

- `time_to_first_value`;
- `blank_state_abandonment_rate`;
- hesitation і backtracking events;
- `prefill_accept_without_correction_rate` і `prefill_correction_rate`;
- expert shortcut/path retention;
- decision-error та unsupported-approval rate;
- recovery to prior filter/record/context.

Release acceptance: немає unresolved avoidable deliberation без waiver; prefill не обходить verification; progress не перевищує usable state; expert path не зламаний без transition/evidence; прискорення не збільшує decision errors або unsupported approvals.
<!-- COGNITIVE_FRICTION_AND_MOMENTUM_UI_LAI101_END -->

<!-- CONTENT_PRODUCTION_TRUTH_PROJECTION_UI_2026_09_17_START -->
## Read-only Content Production Truth Projection

Інтерфейс Паспорта може показувати read-only consumer view для Content TZ/AI Design: snapshot ID/version, exact SKU/variant/scope, linked current fact versions, evidence status, conflicts/gaps/stale dependencies, approved assets/rights і downstream bindings/invalidation status.

У цій проєкції немає authoring title, cover, script, emotional angle, creative winner або publication action. Дозволені дії: відкрити canonical fact/evidence, створити clarification/evidence proposal, переглянути affected downstream bindings та export/versioned snapshot. Content performance не підвищує verification status.

При critical change інтерфейс показує affected snapshot/binding count і `REVALIDATION_REQUIRED`; alert веде до точного fact/evidence/change event. Паспорт не переписує downstream content автоматично.
<!-- CONTENT_PRODUCTION_TRUTH_PROJECTION_UI_2026_09_17_END -->

<!-- AMAZON_QUANTITY_FACT_UI_2026_09_21_START -->
## UI: кількість одиниць і окремих паків у variation

У картці exact child SKU показати поруч, але не зливати в одне поле: `total_unit_count`, `unit_type`, `number_of_packs`, `units_per_pack`/component manifest, packaging evidence, fact versions, verification state та scoped marketplace/product-type eligibility. Відображення `Number of Packs = 1` у внутрішній моделі не означає обов'язковість цього поля в Amazon single-pack submission.

Для однакових паків UI показує `total = packs × units_per_pack` і read-only reconciliation state `CONSISTENT | CONFLICT | UNKNOWN | NOT_APPLICABLE`. Для змішаних наборів показує component manifest замість хибного множення. Видимий `Size` та інші listing surfaces залишаються observations, а не джерелом verified quantity.

Variation alert показує exact child/parent, marketplace, product type, eligibility source/date, conflicting values, packaging locator, affected fact versions, severity та required verifier decision. `QUANTITY_FACT_CONFLICT`, `PACK_RECONCILIATION_FAILED` і `CHILD_QUANTITY_MISSING` ведуть до існуючої review queue; UI не self-resolve alert і не пропонує автоматичну міграцію theme.

Acceptance: verifier за два переходи бачить фізичний evidence, structured fields і PDP/feed/packaging mismatch; одиниці товару не переплутані з окремими паками; відсутній child fact не заповнюється значенням sibling; `UNKNOWN` eligibility не маскується зеленим станом.
<!-- AMAZON_QUANTITY_FACT_UI_2026_09_21_END -->

<!-- DOWNSTREAM_SEMANTIC_CHANNEL_BINDING_UI_2026_09_27_START -->
## UI: Product Truth → semantic interpretation → channel component

У read-only Content Production Truth Projection показати lineage від exact `fact_version_ids`/`evidence_ids` до `semantic_interpretation_id_version` і `channel_asset_id_version`. Для image/video дати drill-down до asset, shot/frame, demonstrated claim, exact variant, kit/accessory status, rights, allowed surface і verifier status.

Додати filters `REVALIDATION_REQUIRED`, `INVALIDATED`, broken/missing binding і blocking eval failure. Перехід веде до canonical fact/evidence або downstream object, але не дає редагувати semantic interpretation, content, verifier status чи release decision з інтерфейсу Паспорта.

Acceptance: wrong variant, stale fact, missing rights або absent kit accessory видимі без aggregate-score masking; verifier за два переходи відкриває source locator і affected frame/component. Зелений state не відображається для unknown або unreviewed binding.
<!-- DOWNSTREAM_SEMANTIC_CHANNEL_BINDING_UI_2026_09_27_END -->

