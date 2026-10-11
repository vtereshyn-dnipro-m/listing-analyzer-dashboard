# Конвейер заполнения Паспорта SKU

Last updated at: 04.10.2026

## Назначение

Папка содержит единый комплект действующих документов для сбора, проверки и итерационного обновления Паспорта SKU.

Паспорт SKU остаётся каноническим хранилищем Product Truth. Документы этой папки определяют работу агентов вокруг него и не создают вторую копию фактов.

Для результата Image Collector действует обязательный delta-route: `passport_media_delta.md → Координатор → Собиратель Паспорта → PASSPORT_DELTA_APPLIED → STOP`. До receipt маршрут имеет `PASSPORT_UPDATE_PENDING`. Собиратель обновляет тот же канонический Паспорт, сохраняет base version, увеличивает version/SHA и выполняет read-back изменённых разделов; повторные Аудитор и Верификатор без прямого запроса пользователя не запускаются.


## Текущий рабочий контур: MVP-пилот

По решению владельца процесса формальный цикл расширенной спецификации остановлен. Для пилота 3–5 SKU используется компактный комплект:

1. [06 — роль и процесс MVP](06_MVP_Агент_верификатор_интервьюер.md)
2. [06A — готовый системный промпт](06A_MVP_Системный_промпт.md)
3. [06B — минимальный шаблон запуска](06B_MVP_Шаблон_запуска.md)
4. [06C — простая форма результата](06C_MVP_Форма_результата.md)
5. [06D — практические сценарии приёмки](06D_MVP_Сценарии_приёмки.md)

Статус контура: `PILOT_ONLY`. Он не является production-ready и всегда заканчивается ручным рассмотрением. Верификатор не редактирует Паспорт; Собиратель как Создатель/Редактор применяет только `APPROVED candidate_update`.


## Розподіл контексту Верифікатора

Після нормалізації 24.09.2026 комплект має одинарну відповідальність:

- `06` — роль, межі та workflow режиму MVP;
- `06A` — короткий runtime prompt і mandatory load order;
- `06C` — тільки форма результату та receipts;
- `06E` — єдине нормативне джерело lifecycle, IDs, Source/Answer/Evidence, status, closure, manifests і follow-up gates.

Копіювання повних правил 06E у prompt, instruction або form заборонене. Кожний RUN фіксує canonical path, SHA-256 і дату читання залежностей.

## Розподіл контексту Собирателя

Після нормалізації 24.09.2026:

- `02` — роль, межі та workflow Собирателя;
- `02A` — runtime prompt, mandatory load order і stop rules;
- `02C` — єдиний collector-specific контракт полів, rows, package sections та admissibility output;
- `00A` — route, receipts, єдиний Паспорт і дозволені виходи;
- `06E` — lifecycle, IDs, Source/Answer/Evidence, status, closure, decisions і manifests.

Instruction, prompt і output contract не копіюють спільний lifecycle. Кожний RUN фіксує canonical path, SHA-256, дату читання та validation result залежностей.

## Shared Context Assembly

Координатор, Собиратель, Аудитор і Верифікатор завантажують [Context Assembly Contract](../09_Shared_Contracts/CONTEXT_ASSEMBLY_CONTRACT.md) зі статусом `active_v1.1`, profile `SKU_PIPELINE`. Спільний manifest визначає identity, scope, freshness, permissions і validation; SKU-specific поля передаються тільки як agent delta. Кожний RUN містить `context_contract_receipt`.

## Состав

1. [Агент-координатор конвейера](00_Агент_координатор_конвейера_Паспорта_SKU.md)
2. [Контракт передач и разрешённых выходов](00A_Контракт_передач_Паспорта_SKU.md)
3. [Описание конвейера](01_Конвейер_заполнения_Паспорта_SKU.md)
4. [Инструкция агента-собирателя](02_Агент_собиратель_Паспорта_SKU.md)
   - [Системный промпт агента-собирателя](02A_Системный_промпт_агента_собирателя_Паспорта_SKU.md)
   - [Шаблон запуска агента-собирателя](02B_Шаблон_запуска_агента_собирателя.md)
   - [Контракт выходного пакета](02C_Контракт_выхода_агента_собирателя.md)
5. [Инструкция агента-аудитора](03_Агент_аудитор_качества_Паспорта_SKU.md)
6. [Шаблон пакета пробелов](04_Шаблон_пакета_пробелов_Паспорта_SKU.md)

Listing Suite actions використовують [інтеграційний контракт](Listing_Suite_Integration_Contract.md): `SUBMIT_SOURCE_EVIDENCE_DELTA` зв'язаний із чинним delta-route, а `RECREATE_PASSPORT` — з окремою lineage/atomic-switch transaction. Обидві функції мають статус `READY_FOR_IMPLEMENTATION`, але feature flags залишаються `OFF` до integration-test PASS.

Для передачі в окремий програмний проєкт використовуй [implementation handoff](Listing_Suite_Implementation_Handoff.md). Він пояснює logical entry/exit points, порядок перевірок, idempotency, atomicity, observability і feature-flag gates, але не додає нового route та не визначає transport technology.

File/folder intake працює лише за [versioned intake policy](Listing_Suite_Source_Intake_Policy.md), а machine-readable outcomes відображаються за [UI message mapping](Listing_Suite_UI_Message_Mapping.md). До затвердження deployment limits `folder_snapshot_v1` залишається `OFF`.

Готові приклади запитів і receipts розміщені у [fixture pack](fixtures/listing_suite/README.md). Schema-negative fixtures мають відхилятися до run, а contract-negative — проходити JSON Schema і відхилятися лише preflight-перевіркою canonical state.

Повний склад передачі окремій команді, порядок реалізації та межі v1 зібрані у [Developer Delivery Package](Listing_Suite_Developer_Delivery_Package.md). Це головна навігаційна точка handoff, але не заміна нормативних контрактів.

Архівні Passport objects підпорядковані [Archive Retention Policy](Listing_Suite_Archive_Retention_Policy.md): deadline створює лише eligibility для admin review, а не право видалення.
Погоджений production-candidate retention profile — `Listing_Suite_Archive_Retention_Profile_v1.0.json`: 1095 днів від `archived_at`, після чого можливий лише `ELIGIBLE_FOR_ADMIN_REVIEW`; feature flag залишається `OFF`.

Authorization визначається [Authority Mapping Contract](Listing_Suite_Authority_Mapping_Contract.md). Канонічна role/action matrix затверджена, але `Listing_Suite_Authority_Profile_v1.0.json` має `BINDING_REQUIRED` до внесення реальних IdP identifiers; до цього mutation та archive access fail-closed.

Локалізація визначена [Localization Contract](Listing_Suite_Localization_Contract.md): активні `uk-UA` і `ru-RU`, fallback `uk-UA`, `en-US` planned. Канонічний каталог — `Listing_Suite_Message_Catalog_v1.0.json`.

Незаповнені product/policy/authority parameters зібрані у [Configuration Decision Register](Listing_Suite_Configuration_Decision_Register.md); їх не можна підміняти fixture values або developer defaults.

[Общие read-only скрипты проверки пакета и ответов](tools/README.md) используются Собирателем, Аудитором и MVP Верификатором; они не заменяют решения агентов.

## Нормативные зависимости

- [Функциональное ТЗ Паспорта SKU](Listing_Suite_ТЗ_Синтез_Паспорт_SKU_v01.md)
- [ТЗ интерфейса Паспорта SKU](Listing_Suite_ТЗ_Синтез_Паспорт_SKU_Интерфейс_v01.md)

При расхождении правила Product Truth, source policy, evidence, статусов и полномочий verifier определяются действующим функциональным ТЗ Паспорта SKU. Инструкции агентов определяют только процесс сбора, проверки и возврата на доработку.

## Правило хранения рабочих запусков

Рабочие материалы конкретного запуска хранятся отдельно от нормативных инструкций по схеме:

`runs/<sku>/<run_id>/`

Минимальный состав запуска:

- входное задание и перечень источников;
- manifest источников;
- версия заполненного паспорта или ссылка на неё;
- отчёт аудитора;
- пакет пробелов;
- ответы и новые материалы;
- журнал повторных проходов.

Факты и evidence не дублируются в служебных документах как новый источник истины. Пакет пробелов содержит ссылки на записи Паспорта и исходные материалы.


Для запусков с видео также обязательны `video_evidence` и `visual_ugc_opportunities`: метаданные, транскрипт/субтитры или журнал аудиотранскрипции, комментарии, атомарные клаймы с таймкодами, сравнительные сигналы и кандидаты сцен для listing/UGC. Сторонний контент нельзя повторно использовать без проверки лицензии и согласий.

## Пилотные запуски

- [MVP-DHR203BCV-001 — проверка Паспорта DHR-203BCV](07_MVP_Пилот_DHR-203BCV_Run001.md)
- `RUN-002` — исторический первичный ограниченный тест DHR-203BCV; каталог не входит в действующий комплект.
- `RUN-003` — исторический углублённый тест видео, комментариев и Visual/UGC; каталог не входит в действующий комплект.
## Навигация мультимедийного контура

- [Нормативная модель и критерии приёмки](Listing_Suite_ТЗ_Синтез_Паспорт_SKU_v01.md#16-мультимедийные-источники-комментарии-и-visualugc-opportunities)
- [Требования интерфейса](Listing_Suite_ТЗ_Синтез_Паспорт_SKU_Интерфейс_v01.md#17-интерфейс-мультимедийных-источников-и-visualugc)
- [Промпт собирателя v03](02A_Системный_промпт_агента_собирателя_Паспорта_SKU.md#20-критерии-приёмки-мультимедийного-сбора)
- [Контракт выхода](02C_Контракт_выхода_агента_собирателя.md#12-обязательное-уточнение-мультимедийного-контракта)
- [Критерии аудитора](03_Агент_аудитор_качества_Паспорта_SKU.md#10-проверка-мультимедийного-контура)

## Уточнение RUN-005 → RUN-006

Нормативный контракт дополнен правилами полной evidence-схемы, разрешения target IDs, закрытого relation enum, независимой проверки visual content и полного UGC rights/risk/owner/action control. Приёмочный повторный пакет хранится в `RUN-006` и не изменяет `RUN-004`/`RUN-005`.

## Research/reference: расширенный агент закрытия пробелов 05–05C

- [Инструкция](05_Агент_верификатор_интервьюер_Паспорта_SKU.md)
- [Системный промпт](05A_Системный_промпт_агента_верификатора_интервьюера_Паспорта_SKU.md)
- [Шаблон запуска](05B_Шаблон_запуска_агента_верификатора_интервьюера.md)
- [Контракт выхода](05C_Контракт_выхода_агента_верификатора_интервьюера.md)

Агент получает gap package и аудит, собирает адресные ответы/evidence и передаёт delta собирателю. Он не изменяет Паспорт/candidate и не подменяет verifier Product Truth.


## Статус режима FULL

Комплект 05/05A/05B/05C является расширенной спецификацией режима `FULL` единого Агента-Верификатора и не объявлен production-ready; открытые document findings и implementation limitations сохраняются. Для режима `MVP` используются документы 06–06E. Оба режима применяют единые ID, статусы и closure из 06E; актуальная FULL package schema — `05C-25-step7o`.

## Статус Шага 1 агента закрытия пробелов

Утверждённая модель INTERVIEW / DIRECT EVIDENCE / SYSTEM EVENT реализована в 05C-05-step1 и синхронизирована с 05/05A/05B/01. Добавлены отдельные intake_event и system_event registries; фиктивные question/answer/respondent IDs и mixed-origin records запрещены. Исторический статус после Шага 1: **STEP_1_IMPLEMENTED_READY_FOR_REVIEW**; superseded последующими шагами. Остальные findings Рецензанта и Скептика этим шагом не закрывались.
### Шаг 7G — typed `scoped_apart`

Текущий нормативный контракт: `05C-25-step7o`, статус `STEP_7O_IMPLEMENTED_READY_FOR_REVIEW`. Единственная модель scope partition находится в §14.3 05C; 05/05A/05B содержат только operational references. C14N profile: `SKU-GAP-C14N-02/3.1`.
### Шаг 7H — question materialization/idempotency

Текущий нормативный контракт: `05C-25-step7o`, статус `STEP_7O_IMPLEMENTED_READY_FOR_REVIEW`. Единственные question intent/materialization schema и idempotency находятся в §6 05C; 05/05A/05B содержат operational references. C14N profile: `SKU-GAP-C14N-02/3.1`.
### Шаг 7I — delivery retry/idempotency

Текущий нормативный контракт: `05C-25-step7o`, статус `STEP_7O_IMPLEMENTED_READY_FOR_REVIEW`. Единственная delivery intent/attempt/receipt/reconciliation модель находится в §7 05C; 05/05A/05B содержат operational references. C14N profile: `SKU-GAP-C14N-02/3.1`.
### Шаг 7J — deterministic gap mapping

Текущий нормативный контракт: `05C-25-step7o`, статус `STEP_7O_IMPLEMENTED_READY_FOR_REVIEW`. Единственный closed gap mapping/evidence policy registry находится в §4.4 05C; 05/05A/05B содержат operational references. Active mapping profile: `GAP-MAP-01/1.0`; C14N profile: `SKU-GAP-C14N-02/3.1`.
### Шаг 7K — package topology и acyclic hashing

Текущий нормативный контракт: `05C-25-step7o`, статус `STEP_7O_IMPLEMENTED_READY_FOR_REVIEW`. Только §2.1–§2.5 05C задают 23-file topology, обязательный JSON-in-Markdown envelope, единственные placements readiness/trusted control и P0–P6 hash DAG. C14N profile: `SKU-GAP-C14N-02/3.1`; 05/05A/05B содержат только operational references.
### Шаг 7L — audit consistency corrections

Исправлены только exact versions 05/05A в 05B, четыре identity/authority C14N paths, readiness count 13/13, историческая формулировка статуса README и spelling `accepted_closed`. Нормативный контракт — `05C-25-step7o`; C14N profile — `SKU-GAP-C14N-02/3.1`.
### Шаг 7M — atomic events, delivery topology и C14N paths

Текущий нормативный контракт: `05C-25-step7o`, статус `STEP_7O_IMPLEMENTED_READY_FOR_REVIEW`. §2.4 задаёт atomic subject+Change Event protocol и P2–P5E–P6 order без unresolved forward references/post-freeze mutation; §2.1/§7 задают пять delivery containers; §4.2.3 задаёт exact wrapper/manifest paths и schema-to-registry checks. C14N profile: `SKU-GAP-C14N-02/3.1`. Иные findings 7L и RUN-009 остаются открыты.
### Шаг 7N — external trust, hash exclusions и non-stage readiness

Текущий нормативный контракт: `05C-25-step7o`, статус `STEP_7O_IMPLEMENTED_READY_FOR_REVIEW`. Reusable trusted control использует внешний input/profile и связывается с run только в reconciliation/preflight; same-run/self anchor запрещён. Hash exclusions закрыты per-object registry, unknown hash-like path fail closed. Quarantine/hold создаёт current `not_admitted` result с `computed_stage=null`, который downstream не может трактовать как READY. C14N: `SKU-GAP-C14N-02/3.1`; external C14N: `SKU-GAP-EXTERNAL-C14N-01/1.0`.
### Шаг 7O — active consistency и audit errata

Текущий нормативный контракт: `05C-25-step7o`, статус `STEP_7O_IMPLEMENTED_READY_FOR_REVIEW`, C14N `SKU-GAP-C14N-02/3.1`. Исправлены только две устаревшие active ссылки профиля, orphan input-reconciliation trigger и terminal typo; даты редакции разделены на original/last-updated. Исторический отчёт 7L не изменён и сопровождается отдельной immutable errata.

## MVP question/answer loop
- [06E — реестр вопросов и ответов](06E_MVP_Реестр_вопросов_и_ответов.md)
- [07A — активные вопросы DHR-203BCV](07A_MVP_DHR-203BCV_Активные_вопросы.md)
- [07B — тест возвращённых ответов](07B_MVP_DHR-203BCV_Тест_возвращённых_ответов.md)
- [08 — сравнение качества вопросов агентов](08_Сравнение_качества_вопросов_агентов.md)

## Формат внешнего запроса ответов

Внутренний реестр вопросов может быть Markdown, но внешний запрос адресату формируется как DOCX по умолчанию либо XLSX для массового/табличного сбора; markdown/chat-only список недостаточен. PDF допускается только как view copy для просмотра/печати и не является основной редактируемой формой возврата. Во всех формах сохраняются stable question IDs и инструкция отвечать по ID.

Исторический PDF-пример запроса DHR-203BCV не входит в действующий комплект и не является runtime dependency.

## Актуальный формат формы ответов

Действующее правило формата: DOCX — основной outbound/return для развёрнутых ответов; XLSX — для массового/табличного сбора; PDF — только outbound view copy. Если респондент фактически вернул заполненный PDF или скан, его не отклоняют: сначала регистрируют как immutable source artifact, затем извлекают и нормализуют данные по 06E. Такой PDF не становится рабочей редактируемой формой.

- Редактируемая DOCX-форма создаётся из действующего шаблона `Шаблон_запроса_ответов_Паспорт_SKU.docx` для конкретного SKU.
- PDF допускается только как производная копия для просмотра/печати и не является runtime dependency.

## Решение владельца о редакторе и closure

Решение владельца от 2026-09-11: Собиратель одновременно является Создателем и Редактором Паспорта; отдельной роли нет. Верификатор принимает решение о достаточности evidence и рекомендует переход статуса, но `CLOSED` не вступает в силу автоматически. Собиратель применяет только `APPROVED candidate_update`, создаёт `change_event` и подтверждение записи с object/version IDs. После проверки подтверждения рекомендованный `CLOSED` становится действующим; при ошибке записи вопрос и gap остаются открытыми.

## Единая модель статусов

Единственная нормативная модель lifecycle и Run status — [06E](06E_MVP_Реестр_вопросов_и_ответов.md#нормативная-модель-статусов).

## Единая система IDs и связей

Единственный нормативный ID-контракт — [06E](06E_MVP_Реестр_вопросов_и_ответов.md#нормативная-система-ids-и-связей). DOCX/XLSX без question ID не сопоставлять по порядку; фиксировать identification error и запрашивать уточнение.

## Один Верификатор два режима

Комплекты 05 и 06 не описывают двух конкурирующих агентов. Это режимы одного Агента-Верификатора: `MVP` — быстрый обязательный контроль/вопросы/answer-delta по 06-серии; `FULL` — расширенный аудит и полный package contract по 05-серии. Режим фиксируется до старта RUN и не меняется. Единые ID, статусы, closure и parent-child handoff заданы только в [06E](06E_MVP_Реестр_вопросов_и_ответов.md).

## Source artifact перед нормализацией

Применяй только нормативную модель [06E](06E_MVP_Реестр_вопросов_и_ответов.md): зарегистрируй `SRC-<RUN>-<NNN>` до извлечения; не изменяй оригинал; Answer/Evidence/candidate_update обязаны ссылаться на `source_artifact_id` и точный locator. PDF, фактически возвращённый респондентом, принимай как immutable source artifact; при ненадёжном question ID фиксируй `IDENTIFICATION_ERROR`. Derived/OCR material не заменяет оригинал.

## XLSX массового сбора

Для массовых/табличных ответов используй [канонический XLSX-шаблон](Шаблон_массового_сбора_ответов_SKU.xlsx) и единственный нормативный контракт в [06E](06E_MVP_Реестр_вопросов_и_ответов.md). Не сопоставляй строки по порядку. До импорта сохрани returned XLSX как immutable Source Artifact; системные answer/source/evidence IDs назначает Собиратель после проверки.

## Run status и запрос информации

Применяй только [нормативное разграничение 06E](06E_MVP_Реестр_вопросов_и_ответов.md). `NEEDS_INFORMATION` не является Run status; используй `required_action=REQUEST_INFORMATION`. Пока самостоятельные search/retry/actions остаются — `NOT_READY`. `BLOCKED` требует внешнего события и валидного active `BLK-<RUN>-<NNN>` с reason, object IDs, responsible party и resume condition. Решение специального владельца требует verified authority scope/evidence.


## Terminal closure и handoff

Применять только [нормативный terminal closure/handoff contract 06E](06E_MVP_Реестр_вопросов_и_ответов.md#terminal-closure-и-handoff-run). Собиратель после успешной записи создаёт immutable `run_closure_package`; Верификатор подтверждает criteria/status, но не редактирует Паспорт. `NOT_READY|BLOCKED` допускают только checkpoint. Следующий RUN не начинает обработку без совпадения `input_passport_version`, `input_passport_sha256` и `parent_closure_package_id`; несовпадение — `STALE_PASSPORT_INPUT/BLOCKED`.


## Decision ID и sealed manifest

Использовать только [нормативный контракт 06E](06E_MVP_Реестр_вопросов_и_ответов.md#decision-events-и-sealed-manifests). Каждая новая оценка получает уникальный `DEC-<RUN>-<NNN>`; повтор ID с иным snapshot запрещён. До handoff payload замораживается, затем создаются manifest revision, detached checksum и ациклический package seal-binding. Любое изменение payload требует нового revision; `STALE_MANIFEST` запрещает продолжение.

## Owner decision 11.09.2026 — единая форма вопросов и rights-as-risk

- Единственный канонический DOCX-шаблон вопросов: [Шаблон запроса ответов Паспорта SKU](Шаблон_запроса_ответов_Паспорт_SKU.docx). Он применяется для `initial`, `follow-up`, `reopened`, `MVP` и `FULL`; наследуются стили, таблицы, поля, интервалы, порядок блоков и page layout. При материализации меняются только IDs, содержание вопросов и критерии закрытия. Новый дизайн без утверждения владельца запрещён.
- Нормативная модель прав и риска находится только в [06E](06E_MVP_Реестр_вопросов_и_ответов.md#rights-as-risk--нормативное-правило). Отсутствие или неподтверждённость прав само по себе не является gate для внутреннего сбора, evidence analysis, claim verification, comparison, timestamps/JTBD/UGC opportunity assessment и обновления Паспорта по независимо достаточным фактам.
- Фактическая надёжность/evidence sufficiency оценивается отдельно от `rights_status` и `rights_risk_level`. Нельзя ставить `REJECTED`, `NOT_READY` или `BLOCKED` только из-за отсутствия rights evidence.

## Завершение тестирования 11.09.2026

Текущий verdict тестирования конвейера: `READY_WITH_LIMITATIONS`. Открытых Blocking/Significant defects нет; обязательная limitation — успешная реальная запись изменения и terminal handoff подтверждаются в первом production pilot. Исторический отчёт закрытия от 11.09.2026 не входит в действующий комплект. Audit/service files сохранены отдельно.

## Решение владельца 22.09.2026 — упрощённая форма запроса

Прежнее требование наследовать сложные таблицы и page layout редакции 11.09.2026 заменено [единым правилом 06E](06E_MVP_Реестр_вопросов_и_ответов.md#единая-форма-вопросов) и обновлённым [каноническим DOCX-шаблоном](Шаблон_запроса_ответов_Паспорт_SKU.docx). Для любого `initial`, `follow-up`, `reopened`, `MVP` или `FULL` запроса используй краткий вопрос со стабильным ID и двумя полями «Відповідь»/«Документ або посилання»; не выноси внутренние gap/status/closure детали в форму адресата. Число блоков определяется открытыми вопросами, а не двумя placeholders шаблона. Перед передачей сверяй IDs и coverage, render/read-back всех страниц; статус доставки и evidence веди отдельно.

## Контроль смысловой полноты внешних вопросов 22.09.2026

До outbound применяй [смысловую сверку 06E](06E_MVP_Реестр_вопросов_и_ответов.md#смысловая-сохранность-вопроса-перед-отправкой): для каждого question ID сопоставь внешний текст со всеми сторонами источников, значениями, единицами и qualifiers из audit/gap package. Внутренний result с полным evidence не компенсирует сокращённый вопрос адресату. После любого упрощения или редакции заново проверь именно DOCX; при потере стороны оставь `DRAFT_NOT_SENT` и выпусти новую immutable revision. Независимый reviewer проверяет эту матрицу перед передачей.

## Catalog import preflight 29.09.2026

Для workbook/CSV catalog imports до створення Product Truth proposals застосовувати розділ [Catalog import preflight і record equivalence](Listing_Suite_ТЗ_Синтез_Паспорт_SKU_v01.md#catalog-import-preflight-і-record-equivalence). Він фіксує єдиний row scope, eligibility-before-equivalence, exact-SKU duplicate clusters, shared-ASIN review, copy-aware blanks і reconciliation `raw rows → eligible rows → action units`.

Розширення має статус `PROPOSAL_ONLY` до реального DM AMAZON catalog pilot. Preflight не змінює source file, не переносить значення між SKU, не присвоює `verified` і не дозволяє live upload.

