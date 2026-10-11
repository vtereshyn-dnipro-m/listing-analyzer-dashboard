# Listing Suite — ТЗ для закладки «Синтез»

## Паспорт SKU как нейтральная база продуктовых утверждений и фактов

Версия: 02  
Статус: консолідована робоча версія  
Дата редакції: 27.09.2026

---

## 1. Назначение и границы

Паспорт SKU хранит атомарные утверждения о продукте с явно указанным статусом проверки, связанные источники, evidence и историю изменений. Подтверждённые утверждения образуют проверенный слой Product Truth; proposals, частично проверенные данные и конфликты остаются видимыми, но не выдаются за подтверждённые факты.

Он нужен, чтобы:

- поддерживать Product Truth;
- показывать происхождение и качество данных;
- сохранять старые значения и конфликты;
- показывать связанные JBTD и Buyer Episodes;
- передавать нейтральные данные внешним модулям Listing Suite.

Паспорт не определяет:

- маркетинговое позиционирование и claims;
- содержание Title, Bullet, A+, FAQ или PPC;
- правила и лимиты marketplace;
- готовность к генерации или публикации;
- правила вибору креативних референсів, novel-view, continuity або preservation mode;
- сцени, камеру, освітлення, композицію, style, prompt або provider/model settings;
- creative treatment, технічний спосіб генерації та рішення про зовнішнє використання матеріалу;
- Episode–SKU Fit;
- ответственность за использование данных внешними модулями.

Границы внешних областей:

- buyer-knowledge library хранит и проверяет JBTD и Buyer Episodes;
- Marketing Book хранит утверждённые правила позиционирования, интерпретации фактов, claims, tone of voice и выбора контентных поверхностей;
- Marketplace Listing хранит конкретную реализацию контента для marketplace, страны или региона, seller account, языка и категории;
- Analytics хранит метрики эффективности и результаты измерений.

Паспорт передаёт этим областям нейтральные данные и ссылки на канонические записи, но не копирует их решения внутрь Product Truth.

## 2. Разделение данных

### 2.1. Паспорт SKU

Хранит:

- внутренний SKU и связь с номенклатурой;
- внутреннее название;
- Product Truth;
- источники и evidence;
- историю изменений;
- нейтральные связи с внешними JBTD и Buyer Episodes.

Кожний запис знання має один тип: `PRODUCT_FACT`, `OBSERVED_USE_CASE`, `CUSTOMER_SIGNAL`, `JTBD_HYPOTHESIS`, `CLAIM_CANDIDATE` або `VERIFIED_CLAIM`. `CUSTOMER_SIGNAL`, `JTBD_HYPOTHESIS` і `CLAIM_CANDIDATE` не переходять автоматично в `PRODUCT_FACT` або `VERIFIED_CLAIM`.

Страна производства хранится как версионируемый факт. При необходимости она уточняется по партии, комплектации или периоду.

Производитель может храниться как закрытый служебный или регуляторный факт, но не выводится публичным полем шапки.

### 2.2. JBTD и Buyer Episodes

JBTD и Buyer Episodes принадлежат внешней библиотеке buyer knowledge.

JBTD — каноническое внутреннее обозначение модели задачи, ценности и желаемого прогресса покупателя. Buyer Episode — каноническая запись конкретной ситуации возникновения, поиска и выбора решения. Их внутренняя структура и правила доказательности определяются buyer-knowledge library, а не паспортом SKU.

В паспорте они:

- показываются read-only;
- не копируются и не редактируются;
- связываются с SKU через many-to-many relation;
- не интерпретируются как fit или маркетинговая рекомендация.

Из паспорта можно только предложить новую запись, исправление или relation. Предложение проверяется во внешней buyer-knowledge области.

Нейтральная relation содержит как минимум:

- relation_id;
- sku;
- buyer_knowledge_type: jbtd или buyer_episode;
- buyer_knowledge_id;
- relation_type: observed_in_context;
- relation_status: proposed, accepted или rejected;
- evidence links via evidence_link, если связь опирается на evidence;
- created_by и created_at / updated_at.

Relation означает только документированное совместное наблюдение SKU и buyer-knowledge записи в заданном исследовательском контексте. Она не содержит fit, приоритета, разрешения на claim или рекомендации по использованию.

### 2.3. Marketplace Listing

Marketplace Listing хранится отдельно от Product Truth.

Он содержит marketplace, страну или регион, seller account, язык, listing_id, ASIN, вариации и контент листинга. Связь Listing ↔ SKU является many-to-many и поддерживает bundle и multipack.

Метрики эффективности принадлежат отдельному Analytics-слою.

### 2.4. Файлы и assets

Паспорт не хранит бинарные файлы.

Локальный файл сначала передаётся во внешний Asset Registry. Паспорт получает стабильные asset_id, asset_version_id, content_hash, locator и метаданные. URL является адресом доступа, а не идентичностью материала.

## 3. Product Truth

Область Product Truth управляет атомарными утверждениями о продукте и их проверкой. Проверенный слой Product Truth образуют только записи, прошедшие полный eligibility-check: `accepted + verified`, `freshness_status = current`, `applicability = applicable`, допустимое `evidence_link` с immutable evidence и отсутствие затрагивающего open conflict. Остальные записи остаются рядом как proposals, частично проверенные данные или история решений.

Один факт содержит одно независимо проверяемое утверждение и не включает рекламную интерпретацию или правила использования.

### 3.1. Минимальные поля факта

| Поле | Назначение |
|---|---|
| fact_id | Уникальный идентификатор |
| sku | Связь с продуктом |
| fact_group | Навигационная группа |
| fact_name | Человеческое название утверждения |
| fact_code | Стабильный код характеристики, если есть |
| value_type | text, number, range, boolean, enum, list, measurement или compound |
| value_raw | Значение из источника |
| value_normalized | Нормализованное значение |
| unit | Единица измерения, если применима |
| context | Пояснение, необходимое для понимания значения |
| scope | Деталь, комплектация, партия, условия или период применимости |
| evidence_links | Вычисляемая проекция evidence_link; не источник истины |
| workflow_status | proposed, accepted или rejected |
| verification_status | unverified, partial или verified |
| freshness_status | current, stale или unknown |
| effective_truth_status | Вычисляемый итоговый статус для пользовательских и внешних проекций |
| applicability | applicable, not_applicable или unknown |
| rule_provenance_ref | Стабільне посилання на нормативний provenance змістовного рішення у run/package |
| approved_claim_ref | Read-only ID затвердженого claim, якщо він існує |
| downstream_trace_refs | Стабільні IDs content rule, Content TZ field, asset element, audit finding і verification result, якщо ці об'єкти існують |
| created_at / updated_at | Даты создания и изменения |

Статусы независимы. Конфликт хранится отдельной записью и не заменяет статусы факта.

`rule_provenance_ref` веде до запису з `rule_id`, `rule_source`, `rule_version`, `authority`, `evidence_ids[]`, `transformation`, `result`. У Паспорті не дублюються runtime logs, tool envelopes або повний manifest. Downstream refs не створюють Product Truth, claim approval чи publication approval; відсутній downstream object не вигадується для повноти ланцюга.

`workflow_status` описывает решение по записи: находится ли она на проверке, принята в паспорт или отклонена. `verification_status` описывает силу подтверждения evidence и не заменяет workflow-решение. Поэтому запись может быть `accepted + unverified`, но только `effective_truth_status = current_verified` входит в текущий проверенный слой Product Truth.

### 3.2. Основные правила

1. Один факт — одно утверждение.
2. Отсутствие данных не считается отрицательным фактом.
3. Изменение не удаляет старое значение.
4. Идентичность факта определяется `sku + fact_code` или нормализованным `fact_name`, а также scope.
5. Разные одновременно действующие scope хранятся как отдельные факты.
6. Scope является частью идентичности факта: изменение scope создаёт новую fact identity, а изменение значения в том же scope создаёт новую версию.
7. Пересчёт единиц или дополнительное совпадающее evidence фиксируется через Change Event без лишней версии факта.
8. Change Event фиксирует тип операции, actor — user, agent, import или system, причину, время и связанные версии или evidence; actor не является ответственным за дальнейшее использование данных.
9. Неоднозначность передаётся verifier и не объединяется автоматически.
10. Merge и split не выполняются автоматически и не входят в MVP-интерфейс.

### 3.3. `semantic_consistency_check`

Кожна зміна факту проходить автоматичну перевірку відповідності назви й значення, одиниці типу характеристики, canonical name/code, scope, exact SKU/variant/market/version, відсутності об’єднання різних сутностей і збереження змісту під час нормалізації.

```yaml
semantic_consistency_check:
  status: PASS | REVIEW_REQUIRED | CONFLICT
  checks: []
  affected_fact_ids: []
  issue_codes: []
  performed_by:
  performed_at:
```

`REVIEW_REQUIRED` передається verifier. `CONFLICT` створює або оновлює canonical conflict; агент не виправляє неоднозначність здогадкою.

### 3.4. Автоматично вилучені зовнішні ознаки

Агент автоматично створює proposals для спостережених форми й основних частин товару, кольорів і кольорових зон, органів керування, портів, конструктивних елементів, логотипів, написів, маркувань і відмінностей між зображеннями exact SKU.

Статус спостереження: `OBSERVED | PARTIALLY_OBSERVED | NOT_OBSERVED | CONFLICT | NOT_APPLICABLE`. Він описує стан знання, не є дозволом або забороною генерації та не присвоює `verified`.

Кожний extraction result містить `confidence_score`, `extraction_config_version` і `route_reason`. Versioned threshold керує лише маршрутом: low-confidence, unreadable, conflict і невизначений exact-SKU/variant match передаються verifier; решта залишається proposals у штатному маршруті. Жодний threshold не надає `verified` без чинного verifier-рішення.

### 3.5. OCR, логотипи, написи й маркування

Агент знаходить текстові зони, виконує OCR, зберігає literal result окремо від normalized text, мову, location on product/package, evidence locator і confidence. Нерозбірливий текст не відновлюється здогадкою.

Статуси: `VERIFIED | PARTIAL | UNREADABLE | CONFLICT | NOT_OBSERVED`. `VERIFIED` для marking встановлює verifier за чинним evidence contract; confidence керує лише exception routing.

### 3.6. Поштучна комплектація

Кожний елемент комплекту зберігається окремо: `item_id`, `item_name`, `quantity`, `included_status`, `applicable_variant`, `evidence_links`, `verification_status`, `conflict_id`. `included_status`: `INCLUDED | NOT_INCLUDED | PARTIAL | UNKNOWN | CONFLICT`.

Неповна комплектація не блокує весь Паспорт автоматично; вона впливає лише на застосування, для якого точний склад комплекту є критичним.

## 4. Источники и evidence

Источник — целый объект: инструкция, упаковка, сертификат, фото, видео, ссылка, отзыв, Q&A или внутренние данные.

Evidence — конкретный релевантный фрагмент источника: текст, значение, страница, область изображения или таймкод. Его relation к утверждению хранится отдельно как `supports`, `contradicts`, `insufficient` или `unclear`.

Минимальная запись source содержит `source_id`, класс source policy, `asset_id / asset_version_id` или внешний locator, язык, дату фиксации, `access_status`: available, unavailable, access_denied или unknown — и отдельный `lifecycle_status`: current, stale или replaced.

Минимальная запись evidence содержит `evidence_id`, `source_id`, точный фрагмент и локализацию, relation к связанному объекту, дату извлечения, способ создания — agent, manual или import — и ссылки на связанные facts или relations.

### 4.1. Source policy

Используются четыре класса источников:

- authoritative_primary — утверждённые спецификации, инструкции, упаковка, сертификаты и master data;
- direct_observation — документированное измерение или проверка продукта;
- buyer_observation — интервью, отзывы, Q&A, обращения и поисковые сигналы;
- secondary — сторонние статьи, конкурентные листинги и пересказы.

Правила:

- только verifier устанавливает или снимает verified;
- Product Truth подтверждается authoritative_primary либо документированным direct_observation;
- buyer_observation и secondary не подтверждают Product Truth самостоятельно;
- правила подтверждения JBTD и Buyer Episodes определяет внешняя buyer-knowledge library;
- недоступный источник не используется для нового подтверждения;
- сохранённое immutable evidence остаётся частью аудита; при устаревании источника связанные знания пересматриваются и при необходимости получают `freshness_status = stale`.

### 4.2. Работа с внешними материалами

Для материала сохраняются asset_id, asset_version_id, content_hash, locator, тип, дата фиксации и точная локализация evidence.

Если источник доступен пользователю, но недоступен агенту, verifier может создать manual evidence с фрагментом и точной локализацией. Без сохраняемой immutable-версии источник может создать proposal, но не новый verified Product Truth.

Asset/version нельзя удалить, пока на него ссылается evidence.

### 4.3. Повнота джерела

Джерело має `source_completeness_status`: `COMPLETE | PARTIAL | UNKNOWN | CONFLICT`. Зберігаються лише доступні відомості: тип, URL/asset, автор/виробник/продавець/користувач, exact SKU/version match, дата отримання та supported fact IDs.

`PARTIAL` і `UNKNOWN` не блокують Паспорт. Якщо через неповноту не можна підтвердити exact-SKU applicability, лише відповідний факт залишається `partial` або `unverified`.

Канонічне походження факту залишається many-to-many: `fact_version → evidence_link[] → evidence → source`. `source_id` є властивістю evidence, а не єдиним зв’язком факту. Для `current_verified` потрібне щонайменше одне admissible evidence link, але факт може мати кілька evidence з різних джерел.

### 4.4. Довідкова інформація про права та ліцензії

```yaml
rights_information:
  status: KNOWN | PARTIAL | UNKNOWN | NOT_APPLICABLE
  note:
  source:
```

`PARTIAL` і `UNKNOWN` не блокують Паспорт, не означають заборону використання та не змінюють verification/effective truth status продуктового факту. Permission, consent, asset approval, publication і content usage constraints належать зовнішньому asset/content workflow.

## 5. Основные рабочие сценарии

### 5.1. Добавить источник

Добавить файл или ссылку → Asset Registry → извлечение evidence → proposals.

Агент может предложить новый факт, новую версию, evidence или conflict, но ничего не подтверждает автоматически.

### 5.2. Проверить предложение

Verifier просматривает fact identity, scope, source policy и evidence и выбирает:

- новый факт;
- новую версию;
- только новое evidence;
- отклонить;
- запросить уточнение;
- создать conflict.

### 5.3. Разрешить конфликт

Verifier сравнивает значения, scope, версии и evidence и может оставить текущее значение, принять новую версию, разделить scope или оставить конфликт открытым.

Дополнительные сценарии — связь buyer knowledge и поддержание stale/unavailable данных — доступны из отдельных очередей.

Ни один сценарий не создаёт generation или publication gate.

## 6. MVP

В MVP входят:

- Product Truth;
- Sources, Asset Registry и evidence;
- агентское извлечение в proposals;
- автоматичне вилучення зовнішніх ознак, OCR і первинної поштучної комплектації з exception routing;
- `semantic_consistency_check` для нових і змінених fact proposals;
- review и conflict queues;
- история и сравнение версий;
- роли contributor, verifier и administrator;
- read-only JBTD и Buyer Episodes;
- предложение нейтральной Buyer Episode ↔ SKU relation;
- базовые поиск, фильтры и пагинация;
- обработка loading, extraction failed, access denied и partial save;
- предупреждение, если у вариантов, партий или комплектаций различаются характеристики;
- понятное сообщение о причине недоступного действия и допустимом следующем шаге.

В MVP не входят:

- авторинг buyer knowledge;
- Episode–SKU Fit;
- Marketplace Listing editor и Analytics;
- генерация и публикация контента;
- bulk approval;
- интерфейсы merge, split и reversal;
- saved views, сложные role presets и мобильная версия.

## 7. Критерии приёмки

Паспорт реализован корректно, если:

- Product Truth отделён от Marketplace Listing;
- канонические JBTD и Buyer Episodes доступны только read-only, а предложения передаются во внешнюю buyer-knowledge область;
- утверждения атомарны и имеют независимые статусы;
- accepted-запись может оставаться unverified, но не входит в проверенный слой Product Truth;
- verified нельзя установить без допустимого evidence и verifier;
- агент создаёт только proposals;
- подтверждённое значение не заменяется молча;
- конфликты и старые версии видны;
- файлы хранятся в Asset Registry, а не в паспорте;
- недоступные источники обрабатываются по source policy;
- три основных сценария проходят end-to-end;
- паспорт не управляет маркетингом, генерацией или публикацией.
- категоріальний профіль додає поля, не змінюючи universal core;
- `semantic_consistency_check` виявляє mismatch назви, значення, одиниці, scope і exact SKU/variant;
- `PARTIAL/UNKNOWN` rights або source metadata не блокують Паспорт;
- visual/OCR extraction створює proposals, а не verified facts; exceptions маршрутизуються verifier;
- комплектація зберігається поштучно й версіонується;
- customer signal або JTBD hypothesis не стає продуктовим фактом чи verified claim без окремої перевірки;
- invalidation event вказує affected fact IDs і запускає повторну перевірку без редагування контенту;
- lifecycle state пояснюється через конкретний вплив прогалини на заявлене застосування.

## 8. Changelog v0.12 → v0.13

- уточнено, что паспорт хранит утверждения разных статусов, а не только подтверждённые факты;
- явно разделены Passport, buyer-knowledge library, Marketing Book, Marketplace Listing и Analytics;
- добавлен минимальный контракт нейтральной Buyer Knowledge ↔ SKU relation;
- разделены `fact_name`, `fact_code`, `value_type`, `context` и `scope`;
- уточнена семантика workflow и verification;
- добавлены минимальные записи source и evidence;
- Change Event отделён от назначения ответственности;
- правила доказательности JBTD и Buyer Episodes возвращены во внешнюю buyer-knowledge library.

## 9. Следующий документ

Технический контракт отдельно описывает:

- сущности, ID и связи;
- API и события;
- переходы статусов;
- детальную матрицу прав;
- интеграции Asset Registry и buyer knowledge;
- безопасность, производительность и восстановление;
- accessibility;
- тесты и миграцию данных.

## 10. Нормативное дополнение после adversarial review

Розділ деталізує контракт станів і не змінює межі, визначені розділами 1–4.

### 10.1. Контракт состояний

| Событие | Предусловие | Результат | Обязательный side effect |
|---|---|---|---|
| Создать proposal | contributor, agent или import создал запись | `proposed + unverified/partial` | Change Event |
| Запросить уточнение | proposal недостаточно определён | workflow остаётся `proposed`; создаётся clarification request | причина и ожидаемое уточнение видимы в очереди |
| Принять без полной проверки | решение verifier | `accepted + unverified/partial` | запись не входит в проверенный Product Truth |
| Подтвердить | допустимое immutable evidence и решение verifier | `accepted + verified` | фиксируются evidence links и Change Event |
| Отклонить | решение verifier | `rejected + unverified/partial` | verified снимается; причина обязательна; запись остаётся в истории |
| Source стал stale | policy event или verifier | source `stale` | связанные факты ставятся в очередь пересмотра; freshness меняется на stale, если актуальность evidence больше не подтверждена |
| Source replaced | указан replacement source | старый source `replaced` | immutable evidence сохраняется; verified не переносится на replacement автоматически |
| Открыть conflict | несовместимые значения или scope | отдельная conflict-запись `open` | значения не заменяются автоматически |
| Разрешить conflict | решение verifier | conflict `resolved` | обязательны resolution, причина, версии и evidence |

Запрещены `proposed + verified` и `rejected + verified`. `verified + stale` допускается только как историческое состояние до обязательного пересмотра и не входит в текущий проверенный слой. Conflict — отдельная сущность, а не статус факта. `not_applicable` требует scope и причины.
Проверенный слой Product Truth формируется только при одновременном выполнении всех условий: workflow_status = accepted, verification_status = verified, freshness_status = current, applicability = applicable, есть evidence_link с relation = supports к конкретной fact_version, source policy допускает класс источника, immutable evidence доступно и решение принял verifier. Внешняя доступность locator проверяется отдельно и сама по себе не отменяет текущий статус при сохранённой immutable-версии.

Открытый conflict исключает факт из однозначной verified-проекции до разрешения конфликта. Сам факт и его версии не удаляются; интерфейс показывает состояние disputed и ведёт к сравнению значений, scope и evidence. `verified + stale` допускается только как историческое состояние и не входит в текущую verified-проекцию. `source replaced` не переносит подтверждение автоматически: требуется новый evidence и повторное решение verifier.

Запрос уточнения не является подтверждением и оставляет запись proposed. Снятие verified, перевод в stale, отклонение и разрешение conflict всегда создают Change Event с причиной и затронутыми версиями.
`effective_truth_status` вычисляется, а не вводится пользователем и не заменяет исходные статусы:

- `current_verified` — accepted + verified + current + applicable, допустимое evidence_link supports к конкретной fact_version, доступная immutable-версия и отсутствие затрагивающего open conflict;
- `disputed` — fact_version затронута open conflict;
- `stale_verified_history` — ранее verified, но freshness или доступность доказательства больше не позволяют считать запись текущей;
- `partial` — подтверждение неполное;
- `unverified` — подтверждение отсутствует;
- `rejected` — workflow_status = rejected.

Raw `verification_status = verified` не может отображаться как текущий подтверждённый факт, если effective_truth_status не равен current_verified.

Временная недоступность внешнего locator не уничтожает и не обнуляет факт, если immutable-версия evidence сохранена и доступна. В этом случае источник получает access_status = unavailable или access_denied, но eligibility сохраняется до policy recheck. unavailable и access_denied являются статусами доступа source, а не отдельными значениями effective_truth_status. Если immutable-версия недоступна или утрачена, effective_truth_status переводится в stale_verified_history, создаётся Change Event и запись попадает в очередь пересмотра. Автоматическое удаление факта запрещено.

Открытый conflict хранит `affected_fact_version_ids`, `affected_scope` и `affected_sku_ids`. Из verified-проекции исключается только пересечение этих объектов и scope; конфликт одной партии не скрывает подтверждённую версию другой партии.

Загальний lifecycle state Паспорта визначається впливом прогалин на заявлене застосування:

- `READY` — критичних для заявленого застосування прогалин немає;
- `READY_WITH_LIMITATIONS` — Паспорт придатний у явно визначених межах;
- `NOT_READY` — критичних доказів для заявленого застосування бракує;
- `BLOCKED` — продовження неможливе через конкретний зовнішній або контрактний блокер.

Неповнота окремого поля, джерела, візуальної ознаки, інформації про права, customer signal або комплектації не блокує Паспорт автоматично. Кожне зниження lifecycle state містить `affected_use`, `critical_gap_or_conflict_id`, rationale та умову зняття. `PARTIAL`, `UNKNOWN`, `NOT_OBSERVED` або невідомі права без такого наслідку не можуть самостійно знизити стан.

### 10.2. Evidence link

Каноническая связь evidence с объектом хранится только как отдельная сущность `evidence_link`: `evidence_link_id`, `evidence_id`, `target_type` (`fact_version`, `buyer_knowledge_relation`, `conflict`), `target_id`, `relation` (`supports`, `contradicts`, `insufficient`, `unclear`), `created_by`, `created_at`. Одно evidence может иметь разные relations к разным объектам; relation всегда относится к конкретной версии. Поля `evidence_links` и любые evidence-массивы в проекциях вычисляются из evidence_link и не являются источником истины.

### 10.3. Buyer knowledge без скрытого Fit

Buyer-knowledge relation означает только документированное совместное наблюдение SKU и записи в заданном исследовательском контексте и имеет тип `observed_in_context`. `accepted` подтверждает корректность этой связи, но не означает fit, силу соответствия, приоритет, suitability, разрешение на claim или рекомендацию. JBTD и Buyer Episode связываются со SKU независимо.

### 10.4. Variation critical alerts

Нейтральный `variation_family_id` обозначает принадлежность SKU к продуктовой семье, но не даёт права наследовать факты. Alert создаётся при несовместимых или неодинаково применимых critical facts связанных SKU: размеры, напряжение, мощность, совместимость, комплектность, bundle/multipack, страна производства, регуляторные признаки.

Минимальные поля: `alert_id`, `variation_family_id`, `marketplace`, `listing_id`, `parent_id` или `parent_asin`, `child_id` или `child_asin`, `variation_theme`, affected SKU, fact versions, `alert_type`, конфликтующие значения, scope каждого значения, нейтральное описание, severity (`warning`, `critical`), status (`open`, `acknowledged`, `resolved`), required verifier decision, timestamps, actor и resolution note. Alert не является generation/publication gate. Перенос факта на другой SKU требует отдельного proposal, scope и evidence.
Системный инвариант запроса Product Truth: возвращаются только факты, для которых `fact.sku = requested_sku`. Parent-, family-, listing- и sibling-fallback запрещены, включая bundle и multipack. Отсутствующее значение child SKU остаётся unknown и не заменяется значением parent. Копирование факта на другой SKU создаёт новый proposal и новую fact_version; evidence_link не копируется, а verified не наследуется.

Variation alert создаётся только после сравнения значений с учётом нормализованных единиц, совпадающих scope и периода применимости. Missing значение не считается равным другому значению: оно создаёт отдельный alert типа missing_critical_fact, если факт критичен для данной variation theme или категории. `warning` допускает наблюдение без немедленного решения, `critical` требует решения verifier. `acknowledged` не убирает alert из активной очереди. `resolved` допустим только при resolution_code, затронутых версиях и evidence либо явном обосновании `not_a_conflict`.

### 10.5. Нейтральный refusal contract

Заблокированное действие возвращает `blocked_action`, стабильный `reason_code`, нейтральное объяснение, конкретное поле или объект, нарушенное правило или причину, `context`, `saved_state`, `next_allowed_actions` и, при необходимости, `decision_owner`. `saved_state` отдельно показывает сохранённые, подготовленные и несохранённые изменения. Запрещены агрегированный readiness score и трактовка отсутствия ошибок, conflicts или proposals как разрешения на генерацию либо публикацию. Внешним модулям передаются факты и статусы, но не readiness verdict.
Для каждой операции partial save возвращаются `operation_id`, `idempotency_key` и результат по каждому объекту: `saved`, `prepared`, `failed` или `not_attempted`. Change Event создаётся для сохранённой части. Повтор разрешён только для failed и not_attempted объектов с тем же idempotency_key; повтор не создаёт новую fact_version для уже saved объекта.

`next_allowed_actions` содержит варианты восстановления конкретной операции, а не шаги к readiness. Внешний модуль возвращает полный список; интерфейс выбирает одно детерминированное primary action и показывает остальные после раскрытия.

Clarification имеет состояние `open`, `answered` или `cancelled`, requested_fields и response; proposal нельзя принять до ответа или отмены запроса. Для replaced source обязателен существующий `replacement_source_id`, запрещены self-reference и циклы; старый источник получает replaced только после успешной фиксации связи.

## 11. Changelog v0.13 → v0.14

- добавлены инварианты verified-проекции и eligibility-check для evidence;
- определено поведение accepted/verified факта при открытом conflict, stale и replaced source;
- variation alert дополнен marketplace, parent/child, variation theme, конфликтующими значениями и обязательным решением verifier;
- refusal contract дополнен конкретным полем, причиной, контекстом, saved state и optional decision owner;
- сохранена нейтральная роль паспорта без generation readiness и маркетинговых разрешений.

## 12. Changelog v0.14 → версия 01

- добавлен вычисляемый effective_truth_status;
- raw verified запрещён как единственный пользовательский признак текущей подтверждённости;
- уточнено влияние unavailable/access_denied и утраты immutable evidence;
- определена область воздействия conflict по fact version, scope и SKU;
- evidence_link закреплён как единственная каноническая модель evidence-связей;
- добавлен системный запрет parent/family/listing/sibling fallback;
- определены detection и resolution rules variation alert;
- добавлена транзакционная модель partial save и idempotent retry;
- уточнены clarification и replacement source transitions.










---

## 13. Changelog после проверки согласованности

Дата: 30.08.2026.

- уточнена полная eligibility-формула Product Truth;
- scope закреплён как часть fact identity;
- unavailable/access_denied отделены от effective_truth_status.

<!-- QPO_REQUIREMENT_COVERAGE_2026_09_10_START -->
## 14. Requirement Coverage Projection для QPO та агентних рішень

Розділ деталізує інтеграцію з shopping-mission/QPO процесом і не змінює universal core Паспорта.

### 14.1. Архітектурна межа

Паспорт SKU не розраховує Episode–SKU Fit і не зберігає результат відповідності як Product Truth. Зовнішня buyer-knowledge/QPO область може створювати `requirement_evaluation`, яка пов'язує атомарну вимогу shopping mission із конкретними версіями фактів SKU.

Результат оцінювання має одне зі значень: `qualifies`, `disqualifies`, `conditional` або `unresolved`. Він є контекстним рішенням, а не властивістю продукту, маркетинговим claim, дозволом на публікацію чи універсальною рекомендацією.

Buyer observation, search query, query co-occurrence або mission hypothesis не можуть створювати чи підтверджувати Product Truth. Вони можуть лише вказати, які факти потрібно знайти, перевірити або повторно оцінити.

### 14.2. Зовнішня сутність `requirement_evaluation`

| Поле | Призначення |
|---|---|
| `evaluation_id` | Стабільний унікальний ID оцінювання |
| `mission_id` | Shopping mission або bounded mission hypothesis |
| `requirement_id` | Атомарна вимога місії |
| `sku` | SKU, що оцінюється |
| `marketplace`, `country`, `language` | Контекст застосування |
| `fact_version_ids` | Конкретні версії фактів Product Truth |
| `comparison_rule` | `equals`, `contains`, `lte`, `gte`, `compatible_with` або інше контрольоване правило |
| `evaluation_result` | `qualifies`, `disqualifies`, `conditional`, `unresolved` |
| `rationale` | Пояснення зв'язку між вимогою і фактами |
| `missing_fact_codes` | Критичні факти, яких бракує |
| `required_clarification` | Питання покупцеві або оператору, потрібне для рішення |
| `context_version` | Версія місії та набору обмежень |
| `evaluated_by`, `evaluated_at` | Автор і час оцінювання |
| `review_status` | `draft`, `reviewed`, `rejected` |

### 14.3. Правила станів

1. Відсутність факту дає `unresolved`, а не `disqualifies`.
2. `disqualifies` дозволено лише за наявності перевіреного факту, правила порівняння і конкретної вимоги.
3. `conditional` вимагає явної умови та `required_clarification` або наступної перевірки.
4. Зміна `context_version`, критичної `fact_version` або scope переводить пов'язану оцінку в чергу повторної перевірки.
5. Одна вимога може мати кілька фактів; один факт може використовуватися в кількох контекстних оцінюваннях.
6. Підтвердження `requirement_evaluation` не змінює статусів Product Truth.

### 14.4. Критерії приймання інтеграції

- Fit-рішення фізично й логічно відділені від Product Truth.
- Кожна оцінка посилається на конкретні `fact_version_ids`.
- Search language не може бути evidence для product fact.
- Застарілий або superseded факт запускає re-evaluation, але не переписує історію.
- Паспорт надає read-only проєкцію і стабільне посилання на канонічну зовнішню оцінку.
- Проєкція не створює generation, publication або marketplace eligibility gate.
<!-- QPO_REQUIREMENT_COVERAGE_2026_09_10_END -->

<!-- NPO_PHRASE_CANDIDATE_RELATIONS_2026_09_10_START -->
## 15. NPO phrase candidates і зв'язок із Product Truth

Паспорт SKU не зберігає search phrase, query demand або AI-generated wording як Product Truth. Зовнішня NPO/query область може створити `phrase_candidate_relation`, що пов'язує фразу з конкретними версіями фактів SKU та дозволеними listing surfaces.

Мінімальні поля: `phrase_candidate_id`, `sku`, `marketplace`, `language`, `head_noun`, `parent_phrase_id`, `phrase_text`, `phrase_class`, `relation_type`, `relation_value`, `query_evidence_id`, `fact_version_ids`, `applicability`, `proof_requirement`, `allowed_surfaces`, `prohibited_inference`, `owner`, `status`, timestamps.

`phrase_class`: `identity | category | product_type | material | style | room | placement | constraint | trust | audience | use_case | gift | format | comparison | seasonal | complement | problem`.

Статуси: `candidate | verified | approved | published | rejected | stale`. `verified` означає, що phrase коректно посилається на чинні факти й evidence; воно не підтверджує demand або performance. `approved` є рішенням listing/content owner, не verifier Product Truth.

Інваріанти:
- search query, autocomplete, review language або AI suggestion не створюють product fact;
- relation посилається на конкретні `fact_version_ids`; verified не успадковується після зміни факту;
- `conditional`, `false` або `unresolved` applicability блокує безумовне використання phrase;
- audience, comparison, complement, problem і use-case phrases не стають властивостями SKU без явної relation та boundary;
- head noun не можна змінювати так, щоб фраза непомітно описувала інший product type;
- видалення phrase relation не змінює Product Truth.

Read API повертає phrase candidates окремою проекцією з linked fact versions, evidence state і allowed surfaces. Product Truth API їх не повертає.

Acceptance: жодна phrase не може отримати `approved`, якщо linked critical fact не має `current_verified`, applicability не `true`, proof requirement не закритий або phrase суперечить Product Truth.
<!-- NPO_PHRASE_CANDIDATE_RELATIONS_2026_09_10_END -->


<!-- MULTIMEDIA_EVIDENCE_2026_09_10_START -->
## 16. Мультимедійні джерела, коментарі та evidence signals

Розділ деталізує обробку відео, фото, коментарів і порівняльних матеріалів та не додає до Паспорта creative/content-authoring сутності.

### 16.1. Полноценная обработка сторонних источников

Сторонний источник, включённый в разрешённый scope, должен исследоваться, а не только регистрироваться. Для видео отдельно обрабатываются страница, описание, субтитры или транскрипт, аудиодорожка, доступные кадры и комментарии. Тип видео хранится как один или несколько контролируемых классов с основанием: `official_promo`, `independent_review`, `test_or_comparison`, `repair_or_teardown`, `user_experience`.

Минимальная запись видео содержит `source_id`, URL/locator, название, автора или канал, дату публикации, язык, длительность, описание, способ получения транскрипта и статус доступа к комментариям. Для каждого мультимедийного вывода обязательны `source_id`, воспроизводимый locator и точный `timestamp`, `frame_id` либо `comment_locator`. Вывод без такой тройки не допускается в evidence, comparison signal или visual opportunity.

Порядок отримання мовлення: опубліковані субтитри, автоматично створені субтитри, аудіотранскрипція. Якщо вилучення неможливе, зберігаються спроби, метод, час і результат; створюється `source_access_gap`. Відсутність доступу не видаляє джерело, але не блокує Паспорт автоматично; coverage denominator використовується лише тоді, коли метрика фактично обчислюється.

### 16.2. Claim и evidence

`claim` и `evidence` являются разными сущностями и связываются many-to-many через отдельный `evidence_link`. Один claim может поддерживаться или опровергаться несколькими evidence; одно evidence может относиться к нескольким claims, фактам, conflicts или relations. Claim не становится Product Truth и не наследует verification evidence автоматически.

Для мультимедийного evidence обязательно хранится один класс происхождения: `brand_claim`, `author_statement`, `observed_on_screen`, `measured_by_author`, `subjective_author_assessment` или `user_comment`.

Наличие функции или действия в кадре доказывает только факт наблюдения, но не эффективность, производительность, безопасность или устойчивость результата. `author_statement`, субъективная оценка и пользовательский комментарий не подтверждают технический параметр без допустимого самостоятельного evidence.

### 16.3. Коментарі та insight signals

Коментарі обробляються як `buyer_observation`: JTBD, claim signal, плюс, мінус, objection або use case. Коментар не є технічним доказом незалежно від кількості повторень.

Мінімальна запис: `insight_id`, `insight_type`, `source_refs`, `supporting_mentions`, `contradicting_mentions`, `evidence_status`, `applicability`. Кількість згадувань допомагає оцінити повторюваність, але не є самостійним доказом. `n_comments`, independent authors, period, sample size, share і denominator можуть зберігатися як необов’язкова діагностика методу; їх відсутність не блокує реєстрацію сигналу й не визначає силу продуктового факту.

### 16.4. Сильные, слабые и сравнительные сигналы

Сильная или слабая сторона сохраняется как evidence-linked signal, а не как подтверждённый claim. Конкурентное сравнение допустимо только при указанном `exact_competitor_sku`, одинаковом сценарии использования, одинаковой метрике и сопоставимых условиях измерения. Если хотя бы один элемент отсутствует, результат маркируется как несопоставимый или создаётся `comparison_basis_gap`; победитель не объявляется.

### 16.5. Візуальне evidence та observed use cases

Паспорт зберігає source/video ID, timestamp або frame ID, буквальний опис спостережуваної сцени, exact-SKU applicability, пов’язаний fact/observed use case/customer signal і межу доказовості. Наявність функції або дії в кадрі не підтверджує ефективність чи performance claim.

`Visual/UGC opportunity`, місце використання в listing, creative quality, необхідність монтажу, approved asset, consent, brand/privacy approval та publication action не є сутностями Паспорта й належать зовнішньому content/asset workflow. У Паспорті залишається лише `rights_information` за розділом 4.4.

### 16.6. Діагностика покриття

Для джерела або run можуть зберігатися planned/actual video metadata, transcript і visual review coverage, число evidence за класами походження та unresolved gaps. Coverage є діагностикою методу збору, а не продуктовим фактом, claim strength або самостійним readiness gate.

Якщо coverage обчислюється, зберігаються numerator, denominator, одиниця, правило розрахунку й gap IDs. Невідомий denominator позначається unknown; його відсутність не блокує JTBD/claim/plus/minus signal.

### 16.7. Критерии приёмки мультимедийного контура

1. Каждый мультимедийный вывод имеет `source_id + locator + timestamp/frame_id/comment_locator`.
2. Claim и evidence реализованы как разные many-to-many сущности.
3. Візуальний фрагмент зберігається лише як evidence/observation; creative opportunity й asset approval залишаються поза Паспортом.
4. Конкурентное сравнение содержит exact competitor SKU, одинаковый сценарий, метрику и сопоставимые условия.
5. Insight signal має source refs, supporting/contradicting mentions, evidence status і applicability; marketing denominator не є обов’язковим.
6. Coverage, якщо обчислюється, відтворюється; відсутня статистика не маскується як повна.
7. Дані дозволяють показати source type, evidence class, confidence, conflict/gap і довідковий rights information status.
<!-- MULTIMEDIA_EVIDENCE_2026_09_10_END -->

## 18. Нормативное уточнение воспроизводимости мультимедийного evidence

Для мультимедийного evidence Asset Registry или внешний evidence package обязан хранить immutable identity производной: source_id, тип, stable locator или exact path, acquired_at, size и SHA-256. Если производную нельзя сохранить, evidence остаётся non_reproducible, получает видимый gap и не участвует в eligibility verified.

Визуальное покрытие описывается раздельно: выполнение плана опорных кадров в frames, просмотр целевых интервалов в seconds и непрерывный просмотр в seconds против duration. Один кадр не считается одной секундой просмотра. Все сводные показатели вычисляются из атомарных записей; несовпадение блокирует приёмку пакета.

Gap и request имеют двустороннюю проверяемую связь. Change Event отделяет recorded_at от occurred_at и sequence_no. Эти поля относятся к доказательности и аудиту, а не добавляют продуктовые факты.

<!-- AI_SHOPPING_SURFACE_OBSERVATION_2026_09_10_START -->
## Cross-Surface Observation для узгодженості Product Truth

Паспорт не зберігає AI-ranking або commercial readiness score. Він надає нейтральний шар спостережень, щоб зовнішній consumer бачив, чи однаково представлений decision-critical факт.

Сутність `surface_observation` містить: `observation_id`; `sku`, `fact_id`, `fact_version_id`; `surface_type` (`feed`, `pdp`, `schema`, `marketplace_attribute`, `cart`, `checkout`, `manual`, `packaging`, `external_review`); marketplace/country/account; listing/ASIN/variant; locator; observed value; observed/source timestamps; access status; evidence ID.

Проєкція порівнює тільки однакові fact identity, scope, variant і period та повертає `CONSISTENT | STALE | CONFLICT | MISSING | NOT_APPLICABLE`. CONFLICT прив'язується до canonical conflict_id. STALE не переписує історичний факт. External review може виявити contradiction, але не підтверджує Product Truth самостійно. MISSING не є негативним product fact.

Consumer contract віддає observations, consistency state, affected versions, conflicts і timestamps. First-failure, readiness, recommendation, publication і transaction decisions залишаються зовнішнім workflows.

Acceptance: critical identity, variant, specification, price/offer, availability і policy facts звіряються за surface та timestamp; mismatch не замінює Product Truth; немає fallback між SKU/variants; aggregate readiness score не створюється.
<!-- AI_SHOPPING_SURFACE_OBSERVATION_2026_09_10_END -->

## Зовнішні read-only consumers і feedback

Зовнішні модулі можуть читати версіоновані факти, evidence links, scope, conflicts, gaps і freshness через read-only API/export. Формат їхніх snapshots, prompt variables, content bindings, creative hypotheses та publication controls визначається самими зовнішніми модулями й не є schema Паспорта.

Зовнішній модуль може створити `passport_feedback_request` для missing fact/evidence, потрібного scope або conflict clarification. Запит створює proposal/clarification route; лише Passport verifier може прийняти факт, evidence link, verification status або conflict resolution.

Asset або результат зовнішнього workflow може повернутися лише як нове source/evidence proposal з locator, version і timestamp. Creative test, CTR, retention, conversion, prompt output або publication decision не підтверджують Product Truth автоматично.

### Invalidation event

Стандартні події: `SKU_OR_VARIANT_CHANGED`, `PRODUCT_VERSION_CHANGED`, `KIT_CHANGED`, `PACKAGING_CHANGED`, `LOGO_OR_MARKING_CHANGED`, `MANUAL_REVISION_CHANGED`, `OFFICIAL_PAGE_CHANGED`, `STRONGER_SOURCE_APPEARED`, `CONFLICTING_SOURCE_APPEARED`.

Кожна подія містить affected fact IDs, previous/new source or version refs, occurred_at, detected_at і re-verification status. Паспорт не редагує downstream brief або контент; зовнішній consumer сам вирішує, як обробляти invalidation signal.

<!-- SCHRAGENHEIM_SKU_DECISION_CONTEXT_2026_09_20_START -->
## Розширення Паспорта SKU: контекст assortment-рішення

### Призначення

Поля нижче не змінюють Product Truth і не створюють маркетингові факти. Вони зберігають decision context, потрібний для retain/delist, replenishment, rotation, seasonal buy та clearance.

```yaml
sku_assortment_decision_context:
  sku_id:
  basket_role: DESTINATION | COMPLEMENT | CHOICE_SUPPORT | TRAFFIC | MARGIN | NICHE | UNKNOWN
  role_evidence_refs: []
  availability_promise: ASSURED | REASONABLE | LIMITED | NONE
  substitution_conditions: []
  substitution_evidence_status: CONFIRMED | OBSERVATIONAL | HYPOTHESIS | UNKNOWN
  replenishment_state: ACTIVE | CONSTRAINED | IRREPLENISHABLE | END_OF_LIFE
  seasonal_or_irreplenishable_window:
  attached_basket_contribution:
  rotation_eligibility:
  move_cost_and_risk:
  post_delist_or_rotation_evidence:
  unresolved_requirements: []
  decision_readiness: READY | EVIDENCE_REQUIRED | NOT_APPLICABLE
```

### Правила й acceptance

- Значення не виводяться автоматично з sales rank, одиничної basket association або stockout period.
- `CONFIRMED` потребує відтворюваного evidence reference; модельний висновок без перевірки лишається `HYPOTHESIS`.
- Відсутність цих полів не блокує базову готовність Product Truth, але блокує автоматичний retain/delist або rotation verdict, якщо рішення на них спирається.
- Product claims, compliance facts і physical attributes залишаються в канонічних секціях Паспорта SKU.

### Межі доказовості

Decision context не доводить causality і не замінює channel economics, privacy review або контрольований experiment.
<!-- SCHRAGENHEIM_SKU_DECISION_CONTEXT_2026_09_20_END -->

<!-- AMAZON_TOTAL_PRODUCT_QUANTITY_FACT_CONTRACT_2026_09_21_START -->
## Quantity fact contract для Amazon `total product quantity`

### Призначення й область застосування

Контракт застосовується до exact child SKU/ASIN, коли для його marketplace і product type доступна variation theme `total product quantity` або коли потрібно звірити поточну кількість у `Size`/listing з фактичною упаковкою. Наявність теми в інших product types/marketplaces не означає eligibility цього listing. Amazon оголосив тему як опційну; Паспорт не запускає автоматичну зміну variation family.

### Вхідні дані та Product Truth

```yaml
quantity_fact_contract:
  sku_id:
  listing_id:
  child_asin:
  marketplace:
  product_type:
  variation_theme_eligibility: VERIFIED_AVAILABLE | VERIFIED_UNAVAILABLE | UNKNOWN
  eligibility_source_and_checked_at:
  total_unit_count:
  unit_type:
  number_of_packs:
  units_per_pack:
  component_manifest_ref:
  separately_packaged_group_definition:
  packaging_evidence_refs: []
  fact_version_ids: []
  verification_state: CURRENT_VERIFIED | PROPOSED | CONFLICT | MISSING | STALE
```

`total_unit_count` — загальна кількість окремих одиниць у пропозиції; `number_of_packs` — кількість окремо запакованих груп, які отримує покупець, а не кількість елементів усередині групи. Для однакових паків перевірка: `total_unit_count = number_of_packs × units_per_pack`. Для змішаного bundle ця формула не застосовується: потрібний component manifest і окреме рішення verifier щодо придатності теми. Одна коробка із 72 стяжками має внутрішній контракт `72 / 1 / 72`; три однакові пакети по 60 — `180 / 3 / 60`. Внутрішнє значення `1` не означає, що Seller Central обов'язково вимагає подати `Number of Packs` для single-pack.

### Правила виконання та handoff

1. Не виводити кількість автоматично лише з free-text `Size`, title або з sibling/parent ASIN. Таке значення може створити proposal, але не `CURRENT_VERIFIED` факт.
2. Verifier звіряє physical packaging/packing specification, exact SKU, фактичний ship unit, `Unit Count`, `Number of Packs`, unit type і effective period; кожний факт має власний evidence/fact version.
3. Variation alert створюється для `QUANTITY_FACT_CONFLICT`, `PACK_RECONCILIATION_FAILED`, `QUANTITY_UNIT_AMBIGUOUS`, `PRODUCT_TYPE_ELIGIBILITY_UNKNOWN` або `CHILD_QUANTITY_MISSING`, із marketplace, parent/child, affected versions і рішенням verifier. Alert не змінює факти та не є окремим publication gate.
4. `surface_observation` звіряє exact child fact із `marketplace_attribute`, `pdp`, `feed`, `packaging` та, де доступно, `cart/checkout`. Неузгодженість не виправляється через sibling fallback.
5. До Listing/Content consumer передати read-only quantity projection: fact versions, eligibility, reconciliation state, unresolved alerts і packaging evidence. Якщо critical quantity змінено, чинні content bindings отримують `REVALIDATION_REQUIRED`.

### Acceptance tests і метрики

- Box із 72 стяжками: `total_unit_count=72`, internal `number_of_packs=1`; внутрішні 72 елементи не стають 72 packs.
- Три однакові пакети по 60: `180 × 3` як total/packs відхиляється; приймається `180 / 3 / 60` за evidence.
- Child ASIN без власного evidence не успадковує quantity від parent або sibling.
- Змішаний набір без component manifest не проходить просту multiplication check.
- Product type/marketplace eligibility `UNKNOWN` не перетворюється на рекомендацію міграції.

Метрики: verified quantity-fact coverage, pack reconciliation failures, child-variation quantity conflicts, surface mismatch, unresolved eligibility і downstream revalidation count.

### Межі доказовості

Правильний quantity contract підтверджує структурованість і узгодженість факту, але не доводить зниження повернень і не визначає результат A-to-z claim. Актуальну доступність theme та обов'язковість полів перевіряти у Seller Central для конкретного product type і marketplace. Джерело БЗ: `C:\Users\ystep\Documents\Агенти и база знаний\knowledge_base_brand_marketing\source_register\2026-09-21__amazon-total-product-quantity-variation__done.md`.
<!-- AMAZON_TOTAL_PRODUCT_QUANTITY_FACT_CONTRACT_2026_09_21_END -->

<!-- DOWNSTREAM_SEMANTIC_CHANNEL_BINDING_2026_09_27_START -->
## Downstream semantic and channel binding

### Призначення та межа

Паспорт залишається authoritative лише для `PRODUCT_TRUTH_PRIMITIVE`: atomic exact-SKU/variant facts, evidence, scope, validity, rights і verification state. `APPROVED_SEMANTIC_INTERPRETATION` та `CHANNEL_COMPONENT` є downstream objects і не стають Product Truth.

Нейтральна verified специфікація може проєктуватися безпосередньо, якщо wording не додає promise, comparison, buyer outcome або implied capability. Persuasive content потребує linked semantic interpretation. Raw/unverified fact не передається в content.

### Read-only downstream binding

```yaml
downstream_content_binding:
  passport_snapshot_id_version:
  fact_version_ids: []
  evidence_ids: []
  semantic_interpretation_id_version:
  channel_asset_id_version:
  binding_status: CURRENT | REVALIDATION_REQUIRED | INVALIDATED | UNKNOWN
  invalidation_reason:
```

Зміна critical fact, variant, evidence validity або rights переводить пов'язаний downstream object у `REVALIDATION_REQUIRED` або `INVALIDATED`. Паспорт не редагує content і не видає publication approval.

### Eval для Collector, Verifier і Auditor

- Collector: source coverage, exact identity, extraction correctness, provenance completeness. Collector не присвоює `verified`.
- Product Truth Verifier: faithfulness, factual correctness, conflict detection, exact SKU/variant/scope applicability. Будь-який blocking fail забороняє `CURRENT_VERIFIED`.
- Independent Auditor: false-accept, missed-conflict, evidence trace і source read-back. Автор не є єдиним verifier власного consequential output.

Вердикти: `PASS | REWORK | BLOCKED | NOT_APPLICABLE`. Blocking dimension не компенсується completeness, confidence чи aggregate score.

### Acceptance tests і межі доказовості

Wrong variant, conflicting sources, missing kit accessory і stale critical fact не можуть дати valid downstream binding. Наявність binding доводить traceability, а не semantic correctness, channel quality, provider capability, publication permission або business outcome.
<!-- DOWNSTREAM_SEMANTIC_CHANNEL_BINDING_2026_09_27_END -->

<!-- CATALOG_IMPORT_PREFLIGHT_2026_09_29_START -->
## Catalog import preflight і record equivalence

### Призначення

Контракт застосовується перед створенням Product Truth proposals із workbook, CSV або іншого record-oriented catalog export. Він визначає, які записи є реальними product rows, які з них actionable, як обробляються exact duplicates і shared identities та скільки незалежних action units може перейти до proposal creation.

Preflight не змінює source workbook, не обирає authoritative duplicate, не переносить значення між SKU і не присвоює `verified`. Він формує traceable import receipt та candidate records для чинного verifier workflow.

### Вхідний контракт

```yaml
catalog_import_preflight:
  import_run_id:
  source_id:
  source_version_id:
  content_hash:
  marketplace:
  account_scope:
  file_locator:
  sheet_inventory: []
  selected_product_sheet:
  data_boundary:
  field_dictionary_ref:
  identity_rules_version:
  applicability_rules_version:
  started_at:
```

Для кожного row candidate зберігаються:

```yaml
catalog_row_assessment:
  source_row_locator:
  row_role: PRODUCT | EXAMPLE | INSTRUCTION | SUBTOTAL | HELPER | EMPTY | UNKNOWN
  stable_identity:
    sku:
    asin:
    product_id_type:
    marketplace:
  identity_strength: EXACT_SKU | EXPLICIT_ASIN | CANDIDATE_IDENTIFIER | TITLE_ONLY | NONE
  action_status: ELIGIBLE | REMOVED | DELETE_ACTION | ROLE_INAPPLICABLE | UNKNOWN
  equivalence_cluster_id:
  equivalence_type: EXACT_SKU_DUPLICATE | SHARED_ASIN_REVIEW | WEAK_MATCH | NONE
  blank_resolution: TRUE_GAP | PRESENT_ON_ALTERNATE_DUPLICATE | SHARED_VALUE_REVIEW | NOT_APPLICABLE | NOT_ASSESSABLE
  exclusion_reason:
  evidence_locators: []
  route: CREATE_PROPOSAL | NEEDS_REVIEW | EXCLUDE_WITH_REASON | BLOCKED
```

### Правила виконання

1. Встановити незмінний `content_hash`, inventory аркушів, product sheet і data boundary до підрахунку прогалин.
2. Усі метрики та findings походять з однієї маски `in_scope_product_rows`; example, instruction, subtotal, helper та empty rows не створюють proposals.
3. Спочатку застосувати eligibility filter, потім record equivalence. Deduplication до вилучення removed/delete-action і role-inapplicable records заборонена.
4. Exact normalized SKU в одному marketplace/import scope утворює duplicate cluster. Один populated duplicate suppresses окрему blank-задачу; blank у всіх copies створює один cluster-level candidate; суперечливі nonblank values переходять у `NEEDS_REVIEW`.
5. Shared ASIN між різними SKU не робить їх duplicate SKU. Сусіднє значення не копіюється й не успадковує evidence або verification; можливий shared value позначається `SHARED_VALUE_REVIEW`.
6. UPC/EAN/GTIN/model/title без exact identity створюють лише review candidate і не suppresses supported gap. Parent/child membership не є record equivalence.
7. Required/conditional gap створює proposal лише за явного applicable rule для exact marketplace, product type і row role. Колір, позиція колонки або локалізована label без internal field mapping не є доказом.
8. Evidence class належить пропонованій дії, а не лише знайденому relation. Масовість впливає на priority після evidence gate, але не підвищує verification state.

### Reconciliation receipt

```yaml
catalog_import_reconciliation:
  import_run_id:
  raw_row_count:
  in_scope_product_row_count:
  eligible_row_count:
  excluded_by_role_count:
  excluded_by_status_or_action_count:
  exact_sku_duplicate_cluster_count:
  shared_asin_review_cluster_count:
  action_unit_count:
  true_gap_candidate_count:
  duplicate_suppressed_blank_count:
  conflict_review_count:
  not_assessable_count:
  denominator_consistency: PASS | FAIL
  unresolved_blockers: []
  verdict: PREFLIGHT_PASS | REVIEW_REQUIRED | BLOCKED
```

`PREFLIGHT_PASS` означає лише, що records узгоджено для передачі у proposal workflow. Він не означає factual correctness, upload safety, marketplace acceptance, publication readiness або дозвіл змінити Seller Central.

### Acceptance tests

- Example/helper/empty-tail rows не породжують Product Truth proposals.
- Усі catalog/content totals використовують `in_scope_product_rows` і збігаються з reconciliation receipt.
- Removed/delete-action rows залишаються видимими для structural reconciliation, але не збільшують active content-gap reach.
- Exact duplicate з populated alternate record не створює окремий blank proposal.
- Duplicate conflict не вирішується автоматичним merge або копіюванням.
- Shared-ASIN sibling без exact-SKU evidence не стає джерелом verified факту іншого SKU.
- Conditional requirement без доведеного trigger повертає `NOT_ASSESSABLE` або `NEEDS_REVIEW`.
- Кожен candidate має source row/column locator, internal field identity, marketplace, scope і route reason.

### Метрики та межі доказовості

Метрики: false proposal rate на ручній вибірці, duplicate-suppressed blanks, conflict-to-review routing, unsupported-requiredness rate, exact-locator coverage, denominator mismatch, action-unit compression і verifier overturn rate.

Контракт походить із документованого Amazon Catalog Triage method. Наданий demo catalog синтетичний, частина internal field names ілюстративна, приватний CLR недоступний, а реальний DM AMAZON catalog export ще не пройшов pilot. До такого pilot статус розширення — `PROPOSAL_ONLY`.
<!-- CATALOG_IMPORT_PREFLIGHT_2026_09_29_END -->
