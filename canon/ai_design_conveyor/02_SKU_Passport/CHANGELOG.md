## 04.10.2026 — Финализация ТЗ области «Паспорт SKU» v1.0

- Утверждены четыре вкладки: `Реестр Паспортов`, `Создание Паспорта`, `Взаимодействие с Верификатором`, `Image Collection`.
- Удалены отдельные верхнеуровневые вкладки `Обновления`, `Медиа` и `История`; их функции распределены по утверждённым пользовательским сценариям.
- Ответ Верификатору оставлен только в специализированной вкладке; `Создание Паспорта` показывает уведомление и переход к exact question ID.
- Документные источники направляются в `Создание Паспорта`, фото/видео и media-intent URL — в `Image Collection`.
- ТЗ переведено в `APPROVED_FOR_IMPLEMENTATION`; feature flags остаются `OFF` до integration-test receipts.

## 04.10.2026 — Listing Suite localization v1.0

- Закрито `LS-CFG-006`: enabled locales `uk-UA` і `ru-RU`, default/fallback `uk-UA`, `en-US` planned.
- Додано localization contract, locale profile, повний двомовний message catalog і resolution receipt schema.
- UI Message Mapping v1.1 доповнено authority codes; fixture pack підвищено до v2.0.
- Production UI flag залишено `OFF` до rendering та UI acceptance tests.

## 04.10.2026 — Listing Suite authority mapping v1.0

- Зафіксовано сім canonical roles, action permissions, окремий SKU scope та fail-closed authorization.
- `PASSPORT_ADMIN` явно дозволено evidence delta; UI `actor_authority` більше не може вважатися authorization evidence.
- Додано authority profile/evaluation schemas, production-candidate unbound profile та fixture pack v1.9.
- `LS-CFG-005` переведено в `CONTRACT_READY_BINDING_REQUIRED`; реальні IdP identifiers не вигадувалися, feature flags залишено `OFF`.

## 04.10.2026 — Listing Suite retention profile v1.0

- Закрито `LS-CFG-003/004`: погоджено 1095 днів від `archived_at`, `PASSPORT_ADMIN` як review owner і legal-hold authorities `PASSPORT_ADMIN | LEGAL_OWNER | AUDIT_OWNER`.
- Додано production-candidate retention profile, immutable legal-hold apply/release receipt та retention boundary matrix.
- Fixture pack підвищено до v1.8; feature flags залишено `OFF`, physical deletion authority не надано.

## 04.10.2026 — Implementation handoff для Listing Suite

- Додано ненормативний `Listing_Suite_Implementation_Handoff.md` з точками входу/виходу та коментарями для окремої команди реалізації.
- Зафіксовано межу між source intake, UI action, Координатором, receipts і UI mapping без вибору HTTP/RPC/queue technology.
- Виправлено schema mismatch: `RECREATE_REJECTED`, уже дозволений 00A і Координатором, додано до UI receipt schema.
- Feature flags залишаються `OFF`; adapter, endpoints, storage, lock service і recovery worker не реалізовувалися.
- Додано fail-closed Source Intake Policy: конкретні file types і числові limits мають бути затверджені deployment profile, а не вигадані в контракті.
- Додано закритий UI Message Mapping для всіх delta/recreate results і основних rejection reasons.
- Додано executable fixture pack: два valid requests, два valid receipts, два schema-negative requests і один schema-valid stale-snapshot contract rejection.
- Fixture pack v1.1 розширено archive/transaction/concurrency/downstream cases; transaction schema тепер відхиляє два canonical pointers і суперечливий `SWITCH_COMMITTED + rollback`.
- Fixture pack v1.2 і дві intake schemas формалізують deployment profile, partial/zero acceptance, path containment та count reconciliation для `SELECT_FOLDER_SNAPSHOT`.
- Fixture pack v1.3 додає confirmation lifecycle і read-only status lookup. Action request тепер вимагає спільний `recreate_request_id` та рівно по одному confirmation кожного required type.
- Fixture pack v1.4 додає deployment manifest та feature activation receipt; flag `ON` без verified implementation і test receipt тепер schema-invalid.
- Додано Developer Delivery Package v1.0: canonical inventory, implementation order, responsibility matrix, configuration gates і явна заборона домислювати майбутній restore route.

## 25.09.2026 — Обов'язкове застосування Image Collector delta

- Image Collector media delta отримав нормативний маршрут `Image Collector → Координатор → Собиратель → PASSPORT_DELTA_APPLIED → STOP`.
- До receipt використовується `PASSPORT_UPDATE_PENDING`; media-review status сам по собі не завершує workflow.
- Собиратель v14 оновлює єдиний Паспорт, архівує base version, збільшує version/SHA, виконує read-back змінених блоків і повертає ідемпотентний receipt.
- Quarantine, unavailable sources, unknown rights і відсутність нових clips не блокують реєстрацію джерел та evidence-bounded JBTD/use rows.
- Після застосування delta повторний Аудитор і Верифікатор без прямого запиту користувача не запускаються.

## 24.09.2026 — Підключення Shared Context Assembly Contract

- Координатор, Собиратель, Аудитор і MVP Верифікатор підключені до `AI Design Conveyor/09_Shared_Contracts/CONTEXT_ASSEMBLY_CONTRACT.md` зі статусом `active_v1.1`, profile `SKU_PIPELINE`.
- Кожний RUN тепер вимагає `context_contract_receipt`; SKU-specific context оформлюється як delta, а не як паралельний manifest.
- Missing/stale contract або identity/scope/freshness/permission mismatch дає контрольований block/reject за контрактом агента.

## 24.09.2026 — Нормалізація контексту Агента-Собирателя

- `02` обмежено роллю, межами, workflow та agent-specific preflight.
- `02A` отримав mandatory canonical load order і runtime stop rules без копії lifecycle/ID/closure policy.
- `02C` закріплено як єдиний collector-specific output/schema contract; cross-agent route і lifecycle маршрутизуються до `00A` та `06E`.
- Збережено multimedia, Visual Invariants, first-value/review queue, extension fields, comparator/negation, full-matrix і exact-schema gates.
- Рішення власника від 11, 22 і 23.09.2026 не змінювалися; їх authority routes зафіксовано явно.

## 24.09.2026 — Нормалізація контексту Єдиного Агента-Верифікатора

- `06E` закріплено як єдине нормативне джерело lifecycle, IDs, Source/Answer/Evidence, Run status, closure, Decision Events, manifests і follow-up gates.
- `06` скорочено до ролі, меж, workflow, canonical dependencies і stop rules.
- `06A` перетворено на thin runtime prompt із mandatory load order без копії policy/schema.
- `06C` залишено формою результату з dependency receipt, operational fields і evidence boundary.
- Рішення власника від 11, 22 і 23.09.2026 збережені через точні canonical routes до 06E; їх decision meaning не змінено.
- Business logic MVP/FULL, ручне рішення, DOCX/XLSX routes і historical sealed packages не змінювалися.

## 22.09.2026 — Смысловая сохранность вопросов при упрощении формы

- Инцидент PW-14B: в rev5–rev7 внешние Q3/Q4 сохранили IDs, но потеряли отдельные стороны источников и исходные единицы; визуальный/ID QA этого не обнаружил.
- В 06E введена обязательная `question_semantic_coverage` по каждой стороне с gate до outbound; в MVP/FULL инструкциях и конвейере добавлена повторная сверка после каждого сокращения, в 06D — два регрессионных сценария.
- Текущая форма PW-14B требует новой immutable revision и независимой смысловой проверки; старые sealed формы остаются историей.

## 22.09.2026 — Упрощённая внешняя форма вопросов Паспорта SKU

- По решению владельца компактная форма PW-14B rev6 обобщена в едином каноническом DOCX-шаблоне без продуктовых данных; прежний сложный layout заменён.
- Обновлены нормативное правило 06E, инструкции и системные промпты MVP/FULL, шаблоны запуска и README. Внешняя форма: стабильный ID, один вопрос и два поля ответа; evidence/closure остаются во внутреннем реестре.
- Прицельный тест: нейтральный шаблон отрендерен на одной странице; SKU-форма rev6 — на двух, четыре Q ID и поле 390 л/год сохранены. Старые materialized forms не менялись.

## 22.09.2026 — Внутренний SKU и официальный сайт Dnipro-M

- Агент принимает назначенный владельцем внутренний SKU без требования дублирования в публичном источнике и записывает источник, автора и дату назначения в Паспорт.
- https://dnipro-m.ua/ добавлен как допустимый источник Dnipro-M при явно разрешённой search policy; точная страница архивируется, применимость к редакции товара проверяется.
- Обновлены инструкция, системный промпт, шаблон запуска и контракт выхода; Product Truth не меняется автоматически.
# 11.09.2026 — команда владельца «Аудит закончен»

- Выполнена ограниченная очистка известных detailed audit/service files завершённого pilot-аудита; canonical и pilot history сохранены.
- Closure marker: `ЗАКРЫТИЕ_АУДИТА_КОНВЕЙЕРА_SKU_2026-09-11.md`.
- Verdict: `READY_WITH_LIMITATIONS`; limitation — real change + terminal handoff подтверждаются первым production pilot.
- Prior independent review requests: `WAIVED_BY_OWNER` согласно действующему waiver; история вне cleanup scope сохранена.

# 11.09.2026 — завершение тестирования READY_WITH_LIMITATIONS

- Full technical read-back выполнен после исправления DEC-count QA assertion.
- QA assertion rights прозрачно исправлен: старое `"not because of GAP-007" not in d` противоречило 06E; новые проверки требуют `PARTIAL_OPTIONAL_RISK`, `optional/risk_management` и исключение GAP-007 из оснований `NOT_READY/BLOCKED`. Aggregate QA: `25/25 PASS`.
- Шесть неблокирующих pilot findings разобраны: пять закрыты revisions/gates, один source/question coverage перенесён в production coverage; пять реальных end-to-end сценариев имеют `DEFERRED_TO_PRODUCTION_PILOT`.
- Единственное ограничение: успешная реальная запись изменения и terminal handoff должны быть подтверждены первым production pilot.
- Passport SKU не изменён; audit/service files не удалялись.

# 11.09.2026 — Remediation DEC identity и sealed manifests

- В 06E добавлены immutable `DEC-<RUN>-<NNN>` и запрет duplicate decision identity.
- Введён ациклический sealed-manifest DAG с exact scope, detached checksum, stale detection и revision/supersedes.
- Stage 1/2 получают новые DEC, manifests и decision-package revisions; старые artifacts сохранены.
- Статус исправлений остаётся `READY_FOR_INDEPENDENT_RETEST`, не PASS. Паспорт SKU не изменён.

# 11.09.2026 — Terminal closure/handoff и закрытие LA-011

- В 06E добавлен единственный нормативный `run_closure_package`/checkpoint/receipt contract и ID `RCP-<RUN>-<NNN>`, `HRC-<RUN>-<NNN>`.
- READY/READY_WITH_LIMITATIONS требуют APPLIED + Change Events; NOT_READY/BLOCKED не считаются terminal success.
- Следующий RUN обязан сверить parent closure, input Passport version/hash; stale input блокирует старт.
- Добавлены восемь нормативных сценариев; LA-011 закрыт решением владельца после read-back.
- Паспорт SKU не изменён.

# 11.09.2026 — Разграничение Run statuses и REQUEST_INFORMATION

- `NEEDS_INFORMATION` исключён из Run statuses; запрос сведений оформляется `required_action=REQUEST_INFORMATION`.
- `NOT_READY` означает, что агент может продолжать in-scope работу; `BLOCKED` — только подтверждённую зависимость от внешнего события.
- Добавлен `BLK-<RUN>-<NNN>` и отдельные active/resolved block records; несколько блоков снимаются независимо.
- Получение ответа снимает соответствующий Block, но RUN остаётся NOT_READY до VERIFIED+APPLIED.
- Для внешних специальных решений обязательны responsible party role, authority scope и authority evidence.
- LA-010 и LA-014 закрыты; LA-011 остаётся открытым. Паспорт SKU не изменён.

# 11.09.2026 — XLSX-контракт массового сбора ответов

- Создан `Шаблон_массового_сбора_ответов_SKU.xlsx` с листами Инструкция/Ответы/Справочники, 200 строками, Excel validation, duplicate warnings, формулами readiness/error, freeze panes и фильтрами.
- 06E дополнен единственным нормативным XLSX-контрактом: обязательные IDs, import rules, repeated answers, multi-source и safe sorting.
- Системные answer/source/evidence IDs отделены от ввода респондента; returned XLSX сохраняется immutable.
- LA-007 закрыт после structural/visual QA; LA-010/011/014 остаются открытыми.
- Паспорт SKU не изменён.

# 11.09.2026 — Разделение returned source artifact и normalized data

- Добавлен восьмой ID `SRC-<RUN>-<NNN>` и обязательная регистрация immutable Source Artifact до извлечения.
- Answer/Evidence/candidate_update стали производными с обязательными source artifact + locator и двусторонней traceability.
- DOCX остаётся default, XLSX — mass/tabular, PDF — outbound view copy; фактически возвращённый PDF принимается как immutable source artifact.
- Duplicate hash сохраняет обе записи с `relation=duplicates`; ненадёжный question ID → `IDENTIFICATION_ERROR`.
- Паспорт SKU не изменён.

# 11.09.2026 — Один Агент-Верификатор с режимами MVP и FULL

- `verifier_mode=MVP|FULL` обязателен до старта и immutable внутри RUN; missing mode → `BLOCKED/CONFIGURATION_MODE_REQUIRED`, mixed inputs → `CONTRACT_MODE_MISMATCH`.
- 06-серия закреплена за MVP, 05-серия — за FULL; единые ID/status/closure остаются в 06E.
- MVP→FULL разрешён только как новый дочерний RUN с `parent_run_id`, explicit `mode_handoff` и mapping rows.
- Паспорт SKU не изменён.

# Журнал изменений конвейера Паспорта SKU

## 11.09.2026 — Единая система IDs и связей

- 06E назначен единственным нормативным ID-контрактом для Run, Gap, Question, Answer, Evidence, Change и Change Event.
- `answer_id` создаёт только Собиратель при регистрации; повторный ответ получает новый immutable ID.
- Закреплена цепь `RUN→GAP↔QUESTION→ANSWER→EVIDENCE→CHANGE→CHANGE_EVENT→passport field/version` и обязательные поля provenance.
- DOCX/XLSX без question IDs дают identification error и запрос уточнения; сопоставление по порядку запрещено. Исторические записи не переписывались; Паспорт SKU не изменялся.

## 11.09.2026 — Единая модель статусов MVP

- 06E назначен единственным нормативным контрактом Question, Answer, Change, Gap и Run status.
- Question `OPEN→SENT→ANSWER_RECEIVED→RESOLVED`; Answer `RECEIVED→VERIFIED|PARTIAL|REJECTED`; Change `CANDIDATE→APPROVED→APPLIED|APPLY_FAILED`; Gap `OPEN→PARTIAL→CLOSED`.
- `CLOSED` требует `VERIFIED+APPLIED` по всем обязательным связям; Question `RESOLVED` учитывает many-to-many gaps и follow-up IDs.
- Run status: `READY|READY_WITH_LIMITATIONS|NOT_READY|BLOCKED`. Исторические записи не переписывались; Паспорт SKU не изменялся.

## 11.09.2026 — MVP-DHR203BCV-001: проверка Паспорта DHR-203BCV

- Паспорт не изменён.
- Найдены официальные инструкции DHR-203BCV/ZA-DS-515, BP-240, FC-230.
- Результат по 06C со статусом `NEEDS_INFORMATION`.
- Сформировано 8 заданий Собирателю, включая YouTube/comments/media/UGC.
- Визуальный render DOCX не выполнен из-за отсутствия bundled LibreOffice; структурное чтение выполнено.

## 10.09.2026 — Collector prompt v03 и RUN-003

- Уточнено: `provided_sources_only` ограничивает перечень, но требует глубокого исследования каждого перечисленного источника.
- Добавлены классификация видео, обязательное получение metadata/описания/транскрипта, fallback аудиотранскрипции, анализ комментариев и точные видеометки.
- Разделены brand claim, наблюдение в кадре, измерение автора, субъективная оценка и пользовательский комментарий.
- Добавлены сравнительные сигналы, Visual/UGC opportunity log, JTBD, права/бренд/privacy и алиас `UGS (alias of UGC)`.
- Добавлены обязательные метрики покрытия видео, комментариев и визуального просмотра.
- Создан RUN-003 на источниках из тестового DOCX; результаты и ограничения хранятся в папке запуска.
- Канонический Паспорт SKU и оба ТЗ не изменялись.
## 10.09.2026 — Нормативный мультимедийный контур

- Синхронизированы функциональное ТЗ, UI, prompt/contract v03, pipeline, collector и auditor.
- Claim/evidence разделены many-to-many; добавлен author_statement и защита от ложных выводов.
- Закреплены exact competitor SKU, comment sample metrics, denominator control и usage-rights gate.
- Visual opportunity отделена от approved assets; продуктовые факты DHR-203BCV не вносились.

<!-- SKU_VISUAL_INVARIANTS_CHANGELOG_2026_09_10 -->
## 2026-09-10 — Visual Invariants for AI Design

- Agent Collector now extracts evidence-bound visual invariants for exact SKU/variation.
- Output contract now exposes a versioned Visual Invariants block and `visual_truth_blocked` state for downstream image/video generation.

## 2026-09-10 — remediation независимого аудита RUN-005

- В 02B/02C минимально уточнены критерии PF-03, PF-08 и PF-09.
- Закреплены полный evidence registry, fact-only targets для Collector, закрытый relation enum и полная UGC control schema.
- Уточнено, что visual content PASS требует отдельного hashed frame/crop и независимого content read-back.
- RUN-004 и RUN-005 не изменялись; новый результат формируется отдельным RUN-006.

## 10.09.2026 — Агент-верификатор/интервьюер v01

- Созданы документы 05/05A/05B/05C: инструкция, системный промпт, шаблон запуска и машинно-проверяемый контракт выхода.
- Закреплены atomic questions, adaptive interview, conflict decomposition, evidence validation, gap transitions, pause/resume и partial progress.
- Разделены stakeholder statement, technical evidence, comments/JTBD и UGC rights.
- Установлена integrity-цепочка gap↔question↔answer↔evidence↔handoff action и возврат только через собирателя и аудитора.
- Учебный пример 2,8 кг / 1,3 кг явно не является нормативным продуктовым фактом.
- Продуктовые факты DHR в нормативные документы не переносились; функциональное и интерфейсное ТЗ не изменялись.


## 10.09.2026 — rework комплекта Gap Verifier/Interviewer v02

- закрыты 3 Blocking и 5 Significant findings независимого ревью;
- добавлены question N:1 gap и immutable follow-up IDs;
- разрешены terminal answers без evidence, фиктивное evidence запрещено;
- введены closure/authority matrix, respondent authentication и decision object;
- формализованы transition/reopening/completion/idempotency;
- добавлены input reconciliation/quarantine, reproducibility fields и UGC rights schema;
- исправлены терминология, управляющий символ и опечатки;
- статус ограничен READY_FOR_REVIEW до следующего независимого контроля.

## 10.09.2026 — Консолидация комплекта 05, schema 03

- 05C переписан как единая authoritative схема; legacy-таблицы и override-on-top устранены.
- 05/05A/05B синхронизированы с 05C-03-consolidated без альтернативных enums и переходов.
- Закрыты замечания повторного ревью по answer disposition/nullability, eligibility, Blocking readiness, idempotency, question/respondent/decision/delivery schemas, cardinality и precedence.
- Статус комплекта: READY_FOR_REVIEW.
## 10.09.2026 — Комплект 05, schema 05C-04

- Разделены proposal и acceptance: Gap Agent формирует `proposed_resolved/ready_for_audit`, а `accepted_closed` устанавливает только downstream auditor/authorized gate.
- UGC rights получили object-presence и conditional value policy; отсутствие rights evidence всегда даёт `not_cleared`.
- Добавлена воспроизводимая схема `verification_result` для trusted control с fail-closed quarantine при отсутствии trust anchor.
- `conflict_register` типизирован: 2..N alternatives, cardinality/nullability, закрытые enums, dimensions, decision/resolution/reopen controls.
- Сценарии substantive handoff, UGC missing rights, trusted artifact pass/fail/no-anchor и conflict create/resolve/reopen, cross-file lint и read-back — PASS.

## 10.09.2026 — Безопасное pilot-scope упрощение 05C-04

- Из автоматической conflict state machine удалены `merge_conflict` и `supersede_conflict`, terminal-link поля и side effects переноса связей.
- Возможный duplicate/superseding conflict теперь оформляется только как `conflict_relationship_proposal` в `decision_register` и переводится в `decision_required` для решения аудитора/владельца.
- Агенту запрещено автоматически объединять, закрывать, замещать конфликты или переносить их связи.
- Change Events оставшихся переходов получили обязательные `from_status`, `to_status`, actor, event/operation, timestamp и object ID.
- Pilot-сценарии, cross-file lint и read-back пройдены; статус — `READY_FOR_REVIEW`.
## 10.09.2026 — Разделение workflow mutation и content immutability в 05C-04

- Для duplicate/superseding proposal задан закрытый allowlist workflow-изменений subject conflict при переходе в `decision_required`.
- Содержательные поля и все связи subject conflict остаются неизменными; target conflict и его связи полностью read-only.
- Любая мутация вне allowlist отклоняется атомарно с `CONFLICT_PILOT_MUTATION_FORBIDDEN` без success Change Event.
- Уточнены поля pending decision/proposal, next action и owner/escalation routing, а также проверки четырёх pilot-сценариев и negative mutation tests.
- Статус после read-back, lint и сценарных проверок — `READY_FOR_REVIEW`.

## 10.09.2026 — Утверждённый Шаг 1: разделение interview/direct/system intake

- В 05C-05-step1 введены три взаимоисключающих маршрута: INTERVIEW, DIRECT EVIDENCE и SYSTEM EVENT.
- Добавлен закрытый enum origin_type и conditional required/forbidden/null rules для question, answer, respondent, intake event, system event, source и evidence.
- Добавлены authoritative-схемы intake_event и system_event с provenance, timestamps, actor/system, discovery scope и trust status.
- Independent official source больше не требует фиктивного answer/respondent; duplicate/superseding conflict регистрируется через system_event.
- System observation без evidence и owner decision не закрывают Product Truth gap.
- Добавлены route preflight gates и семь сценариев приёмки Шага 1.
- Статус ограничен STEP_1_IMPLEMENTED_READY_FOR_REVIEW; другие findings Рецензанта/Скептика не исправлялись.

## 10.09.2026 — Утверждённый Шаг 2: identity и authority респондента

- В 05C-06-step2 разделены respondent identity, organization role, authority scope и authority evidence.
- Добавлены закрытые authority types и verification statuses, typed scope по SKU/product family, рынку/юрисдикции, claim type, организации и сроку.
- Verified требует проверяемый authority evidence с locator/provenance; self-declared role не подтверждает полномочия.
- Запрещён перенос authority между комплектацией, safety/compliance, pricing/business decisions и UGC rights.
- Multi-authority хранится отдельными records; expiry, revocation и role/scope change требуют reverification без перезаписи истории.
- Добавлены privacy classification, access control, retention и запрет хранения секретов/лишних PII.
- 05/05A/05B синхронизированы; другие findings Рецензанта и Скептика не исправлялись.
- Максимальный статус: STEP_2_IMPLEMENTED_READY_FOR_REVIEW.
## 10.09.2026 — Агент 05, утверждённый Шаг 3

- Добавлены `attempt_register` и `exhaustion_decision_register`.
- `cannot_resolve` определён как окончание текущего цикла попыток, но не закрытие gap.
- Введён `risk_accepted_open` с обязательным сохранением unknown/conflict и usage limitation.
- Формализованы два независимых маршрута и documentary-impossibility exception.
- Созданы отдельные register и state machine для `system_capability_gap`.
- READY отделён от handoff и completion; любой нерешённый Blocking блокирует READY.
- Другие findings Рецензанта и Скептика не исправлялись.

## 10.09.2026 — Шаг 4 input manifest, trusted control и deterministic hashing

- Утверждённая модель Шага 4 внесена в 05/05A/05B/05C.
- Missing/unreadable inputs сериализуются без фиктивных actual values.
- Trust bootstrap требует внешней опоры; self-signing агентом запрещён.
- Raw file SHA-256 отделён от canonical object SHA-256.
- Зафиксирован профиль `SKU-GAP-C14N-01/1.0`, quarantine/recompute при version mismatch.
- Другие findings Рецензанта и Скептика не исправлялись.


## 10.09.2026 — Утверждённый Шаг 5: severity normalization

- В 05C-09-step5 создан authoritative `severity_normalization_register` с раздельными `source_severity`, `normalized_severity` и `effective_gating_severity`.
- Canonical enum ограничен `Blocking|Significant|Minor`; утверждена lossless alias mapping table, включая `Critical → Blocking` для RUN-009.
- Trim/case-fold применяется только к match-копии; raw source сохраняется без изменений.
- Unknown, missing, empty и conflicting source values получают `unmapped` и fail-closed gate `Blocking`; READY запрещён.
- Rule-based impact gate для safety, compliance, SKU identity и legal restriction имеет приоритет над downgrade.
- Downgrade требует verified process-owner decision, authority evidence, scope, reason, normalization event и Change Event; mandatory impact upgrade понижать запрещено.
- Новая версия mapping не переписывает историю; добавлены prior link, event rules, canonical input/result hashes и stable batch order.
- 05, 05A, 05B синхронизированы; другие findings Рецензанта и Скептика не исправлялись.
- Максимальный статус: STEP_5_IMPLEMENTED_READY_FOR_REVIEW.

## 10.09.2026 — Утверждённый Шаг 6: security event register

- В 05C-10-step6 добавлен authoritative `security_event_register` как 23-й обязательный файл.
- Зафиксированы closed enums событий, статусов, severity, impact, containment, hold и resolution.
- Добавлены severity/impact matrix, isolation scope, pause/continue rules, release-from-hold, re-scan/retest, dedup/idempotency, retention/redaction, safe display и chain of custody.
- Security event не считается доказательством ложности product claim; affected evidence исключается через `security_hold`.
- Whole-package pause ограничен compromise trusted control/manifest/identity/system boundary и non-isolatable impact.
- Шаг 6 интегрирован с origin routing, authority, Blocking exhaustion, trust/quarantine и severity normalization.
- 05/05A/05B синхронизированы; другие findings Рецензанта и Скептика не исправлялись.
- Максимальный статус: STEP_6_IMPLEMENTED_READY_FOR_REVIEW.

## 10.09.2026 — Шаг 7A: system/security authority и typed holds

- Добавлены system_owner, security_owner, security_investigator с закрытыми scope/actions/evidence/forbidden actions.
- Добавлен security_incident SYSTEM_EVENT и маршрутизация GAP-007/GAP-012.
- Введены privacy-safe typed held_object_refs, impact/isolation matrix и separation-of-duties release.
- Missing verified owner создаёт Blocking capability gap; security roles не меняют Product Truth.
- Другие findings повторных ревью намеренно не исправлялись.

## 10.09.2026 — Шаг 7B: single authoritative readiness

- Единственная readiness-модель перенесена в §15 05C; 05/05A/05B оставляют только ссылки и входные параметры.
- Введены пять вычисляемых стадий, `readiness_result`, gate matrix, transitions, precedence и atomic recompute/rollback.
- `handoff_with_blockers` определён как non-ready disposition: при unresolved Blocking стадия остаётся `interview_in_progress`, а `ready_for_handoff|ready_for_audit|accepted_closed` запрещены.
- `readiness_result` использует точные `target_stage|target_status`, `PASS|FAIL|NA`, evidence locator, blocking reason, affected scope и next action; результат и handoff disposition вычисляются.
- Unresolved Blocking и `risk_accepted_open` запрещают READY; Significant/Minor требуют owner+next_action и условные deadline/limitation для handoff.
- README и общее описание конвейера синхронизированы с `05C-12-step7b`.
- Security holds применяются по scope; `accepted_closed` доступен только authorized downstream auditor/gate.
- Остальные findings не исправлялись.
## 10.09.2026 — Шаг 7C: canonical serialization и воспроизводимые hashes

- 05C обновлён до `05C-13-step7c` и назначает `SKU-GAP-C14N-02/2.0` единственным профилем canonical object hash.
- Добавлен исчерпывающий registry верхнеуровневых и вложенных arrays/collections с ordered/set, sort/order keys, duplicate и null/empty/absent rules.
- Определён детерминированный UTF-8/NFC/JSON/number/timestamp/object-key/array pipeline и точные bytes SHA-256 envelope; raw file hash остаётся отдельным.
- Незарегистрированный array path, ambiguous key, duplicate-key collision, invalid timestamp/number и version mismatch fail closed без source mutation.
- Добавлены closed error codes, canonicalization events/provenance и versioned migration/recompute с сохранением prior hashes.
- VF-20 и 15 сценариев закреплены как scenario specifications; schema/lint/read-back отделены от programmatic execution.
- 05/05A/05B, 01 и README синхронизированы ссылками; security fingerprint, conflict exhaustion и прочие findings не изменялись.
- Статус: `STEP_7C_IMPLEMENTED_READY_FOR_REVIEW`.
## 10.09.2026 — Шаг 7D: conflict cannot_resolve / exhaustion

- 05C обновлён до `05C-14-step7d`; §14.2 стал единственным нормативным conflict exhaustion gate.
- Typed `conflict_exhaustion_decision` размещён отдельной коллекцией в существующем `exhaustion_decision_register` без добавления нового package file.
- Обязательны policy route snapshot, assessment каждой route, verifiable attempts/impossibility evidence, distinct accountable owners/systems/source paths, impacts, owner/actions, review/expiry/reopen и authority.
- Gap Agent только предлагает; approval и transition в `cannot_resolve` атомарны. Blocking требует независимого downstream auditor/authorized gate.
- Один failed delivery/no_response/no_access и повторы тому же owner/system не доказывают exhaustion; unknown/missing route fail closed.
- `cannot_resolve` остаётся unresolved, не выбирает winner и не меняет Product Truth; Blocking допускает только `handoff_with_blockers` по §15.
- Добавлены lifecycle, deterministic errors, idempotency/conflicting-proposal handling, VF-21 и 14 scenario specifications.
- C14N profile повышен до `SKU-GAP-C14N-02/2.1`; все новые arrays зарегистрированы.
- 05/05A/05B, 01 и README синхронизированы. Security fingerprint, scoped_apart partition, общая idempotency/mapping и другие findings не изменялись.
- Статус: `STEP_7D_IMPLEMENTED_READY_FOR_REVIEW`.
## 10.09.2026 — Шаг 7E: security incident fingerprint/dedup

- 05C обновлён до `05C-15-step7e`; §19.9 — единственная нормативная identity/dedup policy.
- Разделены immutable raw artifact identity/hash, safely computed payload digest, normalized detection signature, domain-separated incident fingerprint, correlation cluster и append-only occurrence.
- Redacted excerpt/display исключён как единственное или достаточное основание identity/dedup.
- Введён `SKU-GAP-SEC-FP-02/2.0` с tenant/case/SKU, event/source/version/locator/raw/payload/rule/affected-object envelope и SHA-256 domain separation.
- Missing/unreadable/quarantined identity, unknown locator, version mismatch и collision создают отдельные provisional events без merge и с применимыми hold/quarantine.
- Exact envelope repeat добавляет occurrence; другое raw/payload/source version/locator/rule/boundary создаёт distinct event. Correlation не объединяет events/holds/custody.
- Добавлены collision handling, rekey/migration, lifecycle, idempotency, immutable history, custody и deterministic errors.
- Hold/release/readiness/Product Truth invariants 7A/7B сохранены.
- C14N profile повышен до `SKU-GAP-C14N-02/2.2`; новые occurrence/history/correlation arrays зарегистрированы.
- Добавлены VF-22 и 16 scenario specifications; executable tests не заявляются без artifacts.
- 05/05A/05B, 01 и README синхронизированы. Остальные findings не исправлялись.
- Статус: `STEP_7E_IMPLEMENTED_READY_FOR_REVIEW`.
## 10.09.2026 — Шаг 7F: identity/authentication provenance

- 05C обновлён до `05C-16-step7f`; §8.2 — единственный нормативный identity/authentication contract.
- Разделены identity subject, account/channel binding, authentication event, identity proofing, organizational affiliation, claimed role и scoped authority.
- Добавлены privacy-minimized typed collections в существующем respondent register; secrets/raw credentials/tokens запрещены.
- Generic chat/email/display name/self-declared role, shared mailbox/account и authenticated account без person proof не дают verified identity/authority.
- Добавлены IAL/AAL/BAL/FAL и минимальные gates для product, compliance/legal, UGC rights, system/security, risk acceptance и downstream audit decisions.
- Каждый received answer/respondent decision требует session/account/auth event binding; определены replay, account switch, forward, shared account, stale session, continuity и re-auth.
- Добавлены lifecycle, separation of duties, merge prohibition/correlation proposal, idempotency, immutable history, deterministic errors и spoofing route to security holds.
- C14N profile повышен до `SKU-GAP-C14N-02/2.3`; новые identity arrays зарегистрированы.
- Добавлены VF-23 и 20 scenario specifications; executable tests не заявляются без artifacts.
- 05/05A/05B, 01 и README синхронизированы. Остальные findings не исправлялись.
- Статус: `STEP_7F_IMPLEMENTED_READY_FOR_REVIEW`.
## 10.09.2026 — Шаг 7G: typed scoped-apart partition

- 05C повышен до `05C-17-step7g`, статус `STEP_7G_IMPLEMENTED_READY_FOR_REVIEW`.
- В `conflict_register.scope_partition_records` введены typed partition/cells/dimensions/boundaries/coverage/scoped propositions, acceptance lifecycle, authority/independence, rollback, errors и 20 нормативных сценариев.
- Прямой переход Gap Agent в `scoped_apart` удалён: proposal/ready_for_audit не меняют conflict status; принятие выполняет downstream auditor/authorized gate.
- C14N profile повышен до `SKU-GAP-C14N-02/2.4`; новые arrays зарегистрированы.
- 05/05A/05B, 01 и README синхронизированы ссылками; другие открытые замечания не исправлялись.
## 11.09.2026 — Шаг 7H: question materialization/idempotency

- 05C повышен до `05C-18-step7h`, статус `STEP_7H_IMPLEMENTED_READY_FOR_REVIEW`.
- `question_intent`, `materialized_question` и typed idempotency records разделяют semantic identity, exact sendable text и operation replay.
- Intent key domain-separated/versioned и не включает поздние IDs, exact text, timestamps, run IDs или recipient display data.
- Определены sameness/versioning, follow-up lineage, lifecycle, concurrency, collisions, immutable history, security/privacy и delivery-answer text-hash boundary.
- C14N profile повышен до `SKU-GAP-C14N-02/2.5`; добавлен VF-25 и 21 normative scenario specification.
- 05/05A/05B, 01 и README синхронизированы ссылками. Delivery retry/idempotency, gap mapping и RUN-009 trust artifact не исправлялись.
## 11.09.2026 — Шаг 7I: delivery retry/idempotency

- 05C повышен до `05C-19-step7i`, статус `STEP_7I_IMPLEMENTED_READY_FOR_REVIEW`.
- Разделены immutable delivery intent, append-only delivery attempt, provider receipt/status observation, append-only state projection и idempotency records.
- Введён versioned/domain-separated delivery intent key без attempt/timestamp/run/provider request/message volatility.
- Определены at-least-once/provider-idempotent guarantee model, concurrency, retry/backoff/expiry, ambiguous timeout reconciliation, trusted receipt/replay/security и answer/no_response gates.
- Старый Delivery key удалён; question/materialization §6 не переопределены.
- C14N profile повышен до `SKU-GAP-C14N-02/2.6`; добавлен VF-26 и 23 normative scenario specifications.
- 05/05A/05B, 01 и README синхронизированы. Gap mapping и RUN-009 trust artifact не исправлялись.
## 11.09.2026 — Шаг 7J: deterministic gap type mapping

- 05C повышен до `05C-20-step7j`, статус `STEP_7J_IMPLEMENTED_READY_FOR_REVIEW`.
- Добавлен единственный active `GAP-MAP-01/1.0`: 17 canonical gap types, 18 typed evidence requirements и exhaustive predicate set.
- Domain, routes, owner/authority, evidence, severity floor и readiness impact вычисляются только по registry; caller values используются лишь для mismatch check.
- Unknown/missing/deprecated/collision/predicate unknown fail closed, запрещают INTERVIEW и создают отдельный capability gap при недоступности mapping/control.
- Определены evidence AND/OR groups, exact scope/authority/recency/hash rules, lifecycle/migration/invalidation/idempotency/errors и 25 сценариев.
- C14N profile повышен до `SKU-GAP-C14N-02/2.7`; добавлен VF-27.
- 05/05A/05B, 01 и README синхронизированы. RUN-009 trusted-control artifact не создавался.
## 11.09.2026 — Шаг 7K: package topology, JSON envelope и acyclic hashing

- 05C повышен до `05C-21-step7k`, статус `STEP_7K_IMPLEMENTED_READY_FOR_REVIEW`; C14N profile — `SKU-GAP-C14N-02/2.8`.
- Закреплена topology ровно 23 output Markdown files с exact role/filename/object type/container/cardinality/hash/manifest/build-phase mapping.
- Для каждого output обязателен один marked fenced JSON payload; display prose non-normative, extraction bytes и fail-closed parsing определены детерминированно.
- Единственный readiness container — `preflight_report.normative_payload.readiness_results`; history/invalidation остаются в нём, другие файлы содержат только ссылки.
- Единственный trusted-control payload — внешний `trusted_control_input`; preflight хранит только verification observations. Self-contained/same-run anchor запрещён.
- Content identity отделена от append-only provenance; определён acyclic P0–P6 DAG, detached manifest finalization и запрет self/cross-cycle.
- Добавлены VF-28 и 21 normative scenario specifications; executable fixtures не создавались. RUN-009 trusted-control artifact не создавался.
- 05/05A/05B/01/README синхронизированы только по 7K; остальные findings повторного аудита не исправлялись.
## 11.09.2026 — Шаг 7L: audit consistency corrections

- 05/05A/05B синхронизированы на version `05-step7l-audit-sync`; 05B normative baseline больше не требует obsolete Step 7A versions.
- 05C повышен до `05C-22-step7l`, статус `STEP_7L_IMPLEMENTED_READY_FOR_REVIEW`; C14N profile — `SKU-GAP-C14N-02/2.9`.
- В C14N registry добавлены ровно четыре ранее пропущенных identity/authority array paths.
- VF-19 синхронизирован с фактическими 13 readiness scenarios.
- README различает current 7L status и superseded historical Step 1 status.
- Исправлено `ccepted_closed` → `accepted_closed` в terminal-stage запрете 05.
- Другие findings, Паспорт SKU, RUN-009, временные и audit-файлы не изменялись и не удалялись.
## 11.09.2026 — Шаг 7M: atomic events, delivery topology и C14N paths

- 05/05A/05B синхронизированы на `05-step7m-topology-sync`; 05C повышен до `05C-23-step7m`, статус `STEP_7M_IMPLEMENTED_READY_FOR_REVIEW`.
- Введён выполнимый atomic subject+Change Event protocol: совместный commit/rollback до subject freeze, append-only event ledger P2–P5, freeze P5E, manifest P6; unresolved forward refs и post-freeze mutation запрещены.
- Sole delivery topology синхронизирована с пятью контейнерами §7; undefined `delivery_observations` удалён.
- C14N profile повышен до `SKU-GAP-C14N-02/3.0`; wrapper provenance и manifest build-result arrays привязаны к фактическим JSON paths, добавлен обязательный schema-to-registry check и deterministic errors.
- 01/README синхронизированы. Иные findings после 7L, Паспорт SKU, runtime/fixtures и RUN-009 не изменялись.
## 11.09.2026 — Интеграция MVP question/answer loop
## 11.09.2026 — Формат внешнего запроса ответов DOCX/PDF
## 11.09.2026 — Основная форма ответов DOCX/XLSX
## 11.09.2026 — Собиратель как Создатель/Редактор и подтверждаемый closure

- Отдельной роли Создателя/Редактора нет: функции выполняет Собиратель.
- Верификатор решает достаточность evidence и рекомендует переход; `CLOSED` не действует до применения `APPROVED candidate_update`.
- Собиратель создаёт `change_event` и подтверждение записи; только после проверки подтверждения closure становится действующим.
- Паспорт SKU не изменялся.


- DOCX назначен основной формой развёрнутых ответов, XLSX — массового/табличного сбора; PDF остаётся только view copy.
- Создан редактируемый DOCX-запрос DHR-203BCV со stable question IDs и полями ответа.
- Собиратель сохраняет возвращённый DOCX/XLSX неизменным как source artifact и применяет answer-delta protocol.
- PDF не удалён; Паспорт SKU не изменён.


- Внутренний Markdown-реестр разрешён, но outbound request адресату формируется отдельным DOCX или PDF со stable question IDs и инструкцией отвечать по ID.
- DOCX предпочтителен для редактируемых ответов; PDF допустим для печати/аннотаций или стабильной отправки.
- Возвращённый DOCX/PDF сохраняется неизменным как source artifact; ответы извлекаются по `question_id`/`answer_id` и обрабатываются как answer delta.
- Паспорт, 05–05C, 06E/07A/07B/08 и существующий PDF не изменялись.


- 06E подключён как отдельный реестр стабильных question/answer ID; partial создаёт новый связанный question ID.
- Собиратель проверяет exact ID/scope/evidence, классифицирует answer delta и готовит `candidate_update/conflict/no_change`, но не закрывает вопрос и не редактирует Паспорт.
- Верификатор назначает ровно один статус `CLOSED/PARTIAL/OPEN` и пересматривает downstream findings.
- Добавлены ссылки на 06E, 07A, 07B и 08; указанные исходные файлы, Паспорт, 05–05C и прежние audit reports не изменялись.


## 11.09.2026 — Шаг 7N: external trust, closed hash exclusions и non-stage readiness

- 05C повышен до `05C-24-step7n`; основной C14N — `SKU-GAP-C14N-02/3.1`, внешний trusted-control input — `SKU-GAP-EXTERNAL-INPUT-01/1.0` / `SKU-GAP-EXTERNAL-C14N-01/1.0`.
- Reusable control/anchor отделены от текущего run/package; binding разрешён только в input reconciliation и preflight, same-run/self anchor fail closed.
- Широкое исключение hash-полей заменено закрытым per-object classification registry; content-binding hashes включаются, unknown hash-like path отклоняется.
- Readiness non-admission представлен current result с `stage_admission_status=not_admitted`, `computed_stage=null` и закрытым reason; downstream трактует его fail closed.
- 05/05A/05B, 01 и README синхронизированы только по Шагу 7N. Иные findings и RUN-009 не изменялись.
- Статус: `STEP_7N_IMPLEMENTED_READY_FOR_REVIEW`.

## 11.09.2026 — Шаг 7O: active consistency и immutable errata

- 05/05A/05B повышены до `05-step7o-active-consistency`; 05C — до `05C-25-step7o`; статус — `STEP_7O_IMPLEMENTED_READY_FOR_REVIEW`.
- Две active нормативные ссылки C14N 2.8 исправлены на текущий `SKU-GAP-C14N-02/3.1`; историческая запись Шага 7K не переписывалась.
- Из C14N registry удалён orphan `input_reconciliation::$.records[*].recheck_trigger`; актуальный `trusted_control_input::$.trusted_control_artifact.recheck_triggers` сохранён.
- Exact active typo `ccepted_closed` исправлена на `accepted_closed`; прежняя запись 7L о якобы выполненном исправлении сохраняется как историческое ложное утверждение и корректируется отдельной errata.
- Для изменённых канонических документов добавлены `Original date` / `Last updated at` либо явный `Last updated at`.
- Создана immutable correction record `.audit-review/current/Errata_к_Шагу_7L_false_PASS_claims_2026-09-11.md`; исходный отчёт 7L не изменён.
- Runtime/fixtures и RUN-009 не изменялись; Паспорт SKU не затронут.

## 11.09.2026 — Создан упрощённый MVP агента-верификатора/интервьюера

- По явному решению владельца процесса прекращён формальный цикл доработки расширенного комплекта 05/05A/05B/05C.
- Расширенный комплект сохранён без переписывания как research/reference specification; его открытые формальные findings не являются gate для MVP-пилота.
- Созданы 06/06A/06B/06C/06D: компактная инструкция, готовый prompt, минимальный запуск, простая Markdown-форма результата и 15 практических сценариев.
- MVP использует только `READY_FOR_MANUAL_REVIEW|NEEDS_INFORMATION|BLOCKED`, не редактирует Паспорт/Product Truth и требует ручного решения для критичных compliance/safety/identity claims.
- Определён handoff loop `Verifier → Collector → Verifier → Manual reviewer`, задания на web/YouTube/comments/media timestamps/UGC opportunities и controlled pilot 3–5 SKU.
- 01 и README переключены на MVP как текущий рабочий контур. Production readiness не заявлена; runtime/fixtures и RUN-009 не изменялись.

## Owner decision 11.09.2026 — единая форма вопросов и rights-as-risk

- Единственный канонический DOCX-шаблон вопросов: [Шаблон запроса ответов Паспорта SKU](Шаблон_запроса_ответов_Паспорт_SKU.docx). Он применяется для `initial`, `follow-up`, `reopened`, `MVP` и `FULL`; наследуются стили, таблицы, поля, интервалы, порядок блоков и page layout. При материализации меняются только IDs, содержание вопросов и критерии закрытия. Новый дизайн без утверждения владельца запрещён.
- Нормативная модель прав и риска находится только в [06E](06E_MVP_Реестр_вопросов_и_ответов.md#rights-as-risk--нормативное-правило). Отсутствие или неподтверждённость прав само по себе не является gate для внутреннего сбора, evidence analysis, claim verification, comparison, timestamps/JTBD/UGC opportunity assessment и обновления Паспорта по независимо достаточным фактам.
- Фактическая надёжность/evidence sufficiency оценивается отдельно от `rights_status` и `rights_risk_level`. Нельзя ставить `REJECTED`, `NOT_READY` или `BLOCKED` только из-за отсутствия rights evidence.

## 23.09.2026 — Единый Паспорт и контракт передач 00A

- Утверждён закрытый маршрут Collector → Auditor → Verifier с приёмочным receipt следующего агента, проверкой exact version/SHA и запретом координаторского override. NOT_TESTED не даёт handoff.
- Первый проход создаёт одну версию Паспорта `NOT_READY` с кандидатными значениями. Дополнительные «проекции» и «черновики Паспорта» как отдельные документы запрещены; разрешённые выходы перечислены в 00A.
- Добавлена обязательная сверка прежних OPEN GAP/REQ с профилем и полученными ответами до нового запроса. Уточнены шаблоны, выход 02C, аудитор, MVP-верификатор, проектные правила и граница AI Design.
- Acceptance tests 00A охватывают отсутствие Паспорта, устаревший gap профиля, 5/5 ответов после reset, NOT_TESTED QA, целевой аудит и checkpoint.

## 23.09.2026 — Общий read-only checker пакета Паспорта

- Добавлен `tools/passport_package_check.js` для Собирателя, Аудитора и MVP Верификатора. Скрипт проверяет механические связи, hashes, PF statuses, current contract pin, дополнительный паспортный файл, stale profile request и полный аудиторский handoff; Product Truth и receipt остаются за агентами.
- Инструкции 02A/02B/03/06 и README указывают этап вызова и правило новой immutable ревизии после FAIL. Сценарии `node:test` проверяют PASS, stale request, запрещённый документ и full-scope audit gate.
- Добавлен `tools/response_coverage_check.js`: проверка 1:1 returned Q, source hash, counts, повторного intent и заполнения необходимости перед outbound. MVP инструкции и шаблоны указывают два режима запуска. Три сценария `node:test` покрывают receipt PASS, запрет преждевременного outbound и проверку повторного intent.


## 23.09.2026 — отдельный агент-Координатор

Добавлен `00_Агент_координатор_конвейера_Паспорта_SKU.md`; 00A, 01 и README направляют запуск через отдельного диспетчера, а внешнему ассистенту оставляют только запуск и показ результата. Повторный дефект handoff-схемы останавливает автоматический цикл. Основание: решение владельца после теста PW-14B.

Контракт 00A обновлён до v1.1 для будущих запусков; существующие RUN сохраняют зафиксированный v1.0. Навигация и язык инструкции Координатора проверены.

Добавлен read-only `tools/handoff_integrity_check.js`: проверяет sealed route files, parent ID/SHA, revision, scope, preflight state reconciliation, base manifest, паспортные source IDs и provenance warnings. Новый checker обязателен до handoff; исторические RUN не переписываются.
## 23.09.2026 — Расширяемая схема полей Паспорта

- Уточнено: затверджений категорійний профіль є мінімальним baseline, а не закритим переліком фактів.
- Додано `extension_field` з обов’язковими ID, label, value/unit, scope, provenance/evidence, status і reason; приблизне маппування та мовчазне відкидання фактів заборонені.
- У 00A, Координаторі, Собирателі, контракті 02C, Аудиторі, Верифікаторі та профілі мийки додано правила й acceptance tests для `PF-EXTENSION-FIELD-RECONCILIATION`.

## 24.09.2026 — Один физический файл Паспорта на SKU

- Исправлено противоречие 00A: раньше «один логический Паспорт» сочетался с требованием неизменяемых файловых версий, что породило `v1/v2/v3`.
- Теперь для каждого SKU разрешён один физический файл; `passport_version` и `state` изменяются внутри него, а исторические byte snapshots остаются в sealed manifests и Change Events.
- Координатор, Собиратель, аудит и инструменты обязаны отклонять второй физический файл Паспорта.
- Контракт 00A повышен до v1.2; исторические RUN по v1.1 не переписываются.

## 24.09.2026 — REMEDIATION_RUN после заблокированного запуска

- Контракт 00A повышен до v1.3.
- Добавлен нормативный `REMEDIATION_RUN`: после исторического `BLOCKED/NOT_READY` допускается новый запуск с immutable checkpoint, `parent_checkpoint_package_id`, owner decision и совпадением canonical Passport version/SHA.
- Такой запуск не объявляет предыдущий RUN успешным и не использует его sealed handoff/binding как шаблон.

## 24.09.2026 — Административный checkpoint для повреждённого RUN

- Контракт 00A повышен до v1.4.
- Добавлен `ADMINISTRATIVE_BLOCKED_CHECKPOINT` для исторического RUN без принятого аудиторского receipt, если причина остановки относится к целостности маршрута или пакета.
- Такой checkpoint не создаёт Product Truth и не заменяет аудит; он разрешает только `REMEDIATION_RUN`.


## 24.09.2026 — Упрощение контроля передачи Паспорта SKU

- Manifest пакета, parent linkage и package seal переведены из обязательных блокирующих gates в необязательную диагностическую проверку.
- Обязательными остаются единственный Паспорт, архив источников в `артефакти/YYYY-MM-DD/`, реестр источников, SHA исходных файлов, path containment и содержательная приемка.
- Ошибки manifest/parent linkage больше не создают новый цикл Собирателя.
- Неизвестные факты и конфликты после принятия пакета маршрутизируются Аудитором к Верификатору через `gap_package` и 06E.

## 24.09.2026 — Защита от ложных блокеров и DOCX-aware preflight

- 00A v1.7 ввёл закрытый словарь блокеров и обязательный authority check: неизвестные коды и свободные названия gates не имеют операционной силы.
- Координатор, Собиратель и Аудитор разделяют содержательный defect и техническую диагностику; checker не выдаёт receipt и не создаёт маршрут.
- `passport_package_check.js` научен читать OOXML DOCX и не принимает `passport_section_matrix` за второй Паспорт.
- Решение действует forward-only; sealed исторические RUN не переписываются.

## 25.09.2026 — Риск-ориентированный Аудитор без административных rework-петель

- По решению владельца Аудитор сохранён как независимый контроль существенного продуктового риска, но больше не блокирует маршрут из-за служебных ID, numbering, manifest/parent/SHA, attempt-link и route metadata.
- Блокирующий класс ограничен `CRITICAL_PRODUCT_RISK`: identity/configuration, противоречащий или фантомный evidence/claim, скрытый safety/compliance/rights риск и отсутствие обязательного источника для claim текущего scope.
- Введён `ACCEPTED_WITH_DIAGNOSTICS`: receipt остаётся `ACCEPTED`, verdict — `READY_FOR_VERIFIER`, diagnostics передаются дальше без возврата Собирателю.
- После одного адресного rework повторный служебный дефект вне scope не создаёт новую ревизию; владелец может принять его как `OWNER_ACCEPTED_DIAGNOSTIC`.

## 25.09.2026 — Fast path для відповідей власника

- Відповіді на вже активні питання обробляються одним маршрутом `Verifier answer intake → Collector apply` без нового Аудитора, package/revision, web research або повторної форми.
- Прямі рішення `помилка`, `не потрібно для контенту` та `невідомо` одразу керують content scope, але не створюють технічний чи compliance claim.
- До п’яти відповідей мають завершуватися одним безперервним агентським проходом із поверненням нової версії/SHA Паспорта та residual gaps.

## 25.09.2026 — Один прогін та delta-only зміни

- Для товару дозволено один автоматичний повний прогін; повторні RUN/audit/verification запускаються лише за прямим запитом користувача або для додавання нових даних.
- Повернені відповіді перевіряються лише в межах змінених значень і прямих evidence links без повторного читання всього Паспорта та всіх джерел.
- Після застосування approved delta Собирателем маршрут завершується; Аудитор і Верифікатор повторно не запускаються.

## 27.09.2026 — Універсальний шаблон Паспорта SKU

- До основного ТЗ Паспорта внесено погоджене універсальне ядро, незалежне від конкретної категорії товару.
- Додано `semantic_consistency_check`, мінімальний зв’язок факту з джерелом, автоматичне вилучення зовнішніх ознак і OCR, поштучну комплектацію, source completeness, типи знання та стандартні invalidation events.
- Права й ліцензії визначено як довідкову неблокуючу інформацію; `PARTIAL`, `UNKNOWN` і `NOT_OBSERVED` не знижують статус Паспорта без доведеного впливу на заявлене застосування.
- Customer signals, JTBD hypotheses, claim candidates і продуктові факти розділено; кількість згадувань не є самостійним доказом.
- `Prompt Template Variable Projection`, creative reference selection, Visual/UGC authoring, continuity, preservation mode, generation і publication rules виведено за межі Паспорта.
- ТЗ інтерфейсу навмисно не змінюється до завершення відлагодження конвеєра; його синхронізація виконується окремим наступним етапом.
- Після review Рецензента і Скептика виконано bounded consolidation pass: вимоги інтегровано в чинні секції, тимчасовий override видалено, суперечливі Prompt/Visual-UGC/rights/comment-coverage моделі прибрано.
- Повторний verdict: Рецензент `accepted`, Скептик `withstands_challenge`.
- Контракт 00A оновлено до v2.3; синхронізовано Координатора, Збирача/Редактора, Аудитора та активну MVP-гілку Верифікатора 06–06E.
- Автоматичні visual/OCR/kit extraction outputs визначено як proposals; confidence керує лише exception routing.
- Visual/UGC opportunity, approved asset, montage і publication controls виведено з Passport agent contracts; multimedia handoff містить evidence, observations та insight signals.
- Rights/status model уніфіковано як неблокуючий `rights_information`; старі `rights_status/rights_risk_level` прибрано з активної MVP-гілки.

# 2026-09-27 — provenance, незалежні стани та наскрізний claim-chain

- Джерело зміни: окремий аудит portable product-research agent; перенесено лише універсальні contract controls.
- 06E підвищено до MVP-08 і залишено єдиним нормативним джерелом lifecycle/status/IDs: додано `rule_provenance`, чотири незалежні осі стану та продовження trace до downstream stable refs.
- 00A підвищено до v2.4; синхронізовано Координатора, Збирача, Аудитора й активну MVP-гілку Верифікатора.
- ТЗ Паспорта підвищено до v02: у самому Паспорті зберігаються лише stable refs, не runtime logs/tool envelopes/full manifest.
- 06D MVP-04 містить сім negative fixtures: missing normative rule, optional example promoted to default, empty evidence, success without measurements, stale Passport after handoff, wrong SKU/variation, structural PASS without Product Truth proof.
- Не переносилися Jungle Scout thresholds, 13-week formulas, primary-keyword logic, `accio-mcp-cli` або `js_*` response shapes.
- Marketing Book, downstream AI Design files, Product Truth authority, ролі та publication gates не змінювалися.

## 29.09.2026 — Catalog import preflight і record equivalence

- До `Listing_Suite_ТЗ_Синтез_Паспорт_SKU_v01.md` додано preflight перед створенням proposals із workbook/CSV catalog exports.
- Зафіксовано єдиний `in_scope_product_rows`, порядок eligibility-before-equivalence, exact-SKU duplicate та shared-ASIN review clusters, copy-aware blank resolution і reconciliation receipt.
- `PREFLIGHT_PASS` не означає factual correctness, upload safety, publication readiness або дозвіл змінити Seller Central.
- До реального DM AMAZON catalog pilot розширення має статус `PROPOSAL_ONLY`; чинні Product Truth, verifier, conflict і downstream publication boundaries не змінено.

## 04.10.2026 — Listing Suite Creation bindings і Passport recreate

- 00A підвищено до v2.12, Координатор до v2.6, pipeline до `01-mvp-pilot.15`, Собиратель і його system prompt до v23, launch template до v20, output contract до v22, Аудитор до v19 і MVP launch template до MVP-12.
- Додано typed `SUBMIT_SOURCE_EVIDENCE_DELTA` binding без зміни чинної змістовної логіки `source_evidence_delta`.
- Додано окремий `RECREATE_PASSPORT` route: lineage, два confirmations, per-SKU lock, immutable archive receipt, staging build, atomic switch, rollback/recovery та idempotency.
- Зафіксовано folder snapshot v1 без subscription і downstream `STALE_PASSPORT_BINDING` після recreate commit.
- Post-commit повернення old Passport відділено в адміністративний `RESTORE_ARCHIVED_PASSPORT`; user operation не видаляє archive фізично.
- Listing Suite ТЗ підвищено до v0.3 зі статусом `READY_FOR_IMPLEMENTATION`; feature flags залишаються `OFF` до integration-test PASS.

## 04.10.2026 — Admin-only restore route

- 00A оновлено до v2.13, Координатора до v2.7, Integration Contract і handoff до v1.1.
- `RESTORE_ARCHIVED_PASSPORT` створює новий Passport object із archived snapshot; immutable archive не реактивується.
- Readiness скидається до `NOT_READY`, fact verification — до `PROPOSED/UNVERIFIED`; provenance зберігається.
- Додано окремі request/receipt schemas і feature flag `listing_suite.passport_restore=OFF`.
- Fixture pack v1.5 додає restore request, committed/rolled-back receipts і contract-negative спробу реактивувати archived Passport ID.
- Fixture pack v1.6 та Archive Retention Policy формалізують retention configuration, legal hold, dependency block і admin-review eligibility без physical deletion authority.
- Додано Configuration Decision Register v1.0 і виправлено застаріле позначення restore як future route у handoff v1.2.
- `LS-CFG-001/002` закриті owner decision receipt; додано production-candidate intake profile і fixture pack v1.7 з exact boundary matrix.

