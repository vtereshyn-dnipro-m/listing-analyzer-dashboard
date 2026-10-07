# Конвейер заполнения и обновления Паспорта SKU

Версия: 01-mvp-pilot.16  
Статус: `MVP_PILOT_CURRENT_WORKING_CONTOUR`  
Original date: 10.09.2026
Last updated at: 04.10.2026

## 1. Назначение

Обязательный исполнимый маршрут, допустимые продуктовые документы и договор передачи между агентами заданы в [00A — Контракт передач Паспорта SKU](00A_Контракт_передач_Паспорта_SKU.md) v2.13. Lifecycle, IDs, статуси та subject-bound decision controls беруться лише з чинної [06E](06E_MVP_Реестр_вопросов_и_ответов.md), exact version/SHA якої фіксується під час запуску. При коллизии со старыми описательными шагами этого файла действует 00A. Координатор не принимает решения о пропуске gate, создании дополнительного продуктового документа или самостоятельной передаче без receipt принимающего агента. Неизвестные коды, свободные названия gates и ошибки совместимости инструментов не имеют блокирующей силы; применяется authority check и прямой read-back по 00A. Аудитор выполняет один риск-ориентированный проход: служебные diagnostics не создают rework, а открытые знания передаются Верификатору.

Кожне змістовне рішення передається з `rule_provenance_ids[]` і subject-bound `state_axis_record_id`. Цей файл не дублює їхні schemas або enums із 06E/02C.

Конвейер обеспечивает повторяемый цикл сбора, заполнения, аудита и дополнения Паспорта SKU. Он нужен, чтобы неизвестные значения, слабое evidence, противоречия и ошибки структуры не скрывались и возвращались на адресную доработку.

Конвейер не подтверждает Product Truth автоматически. Окончательное принятие, отклонение и установка `verified` принадлежат verifier.

Автоматический конвейер выполняется для товара один раз. После первого результата последующие команды обрабатываются только как ограниченные delta-update по прямому запросу пользователя. Верифицируются только изменённые значения; после их применения повторный Аудитор и Верификатор не запускаются. Новый полный прогон допустим только если пользователь прямо просит повторную проверку или добавляет новые данные в Паспорт.

Нове завантаження сертифіката, декларації, протоколу, інструкції, фото, відео або іншого продуктового документа запускає `source_evidence_delta`, а не новий Паспорт. Збирач архівує оригінал, порівнює artifact SHA і кожне атомарне твердження з current Passport/source registry та повертає disposition за 00A: duplicate, additive evidence/fact, conflict, wrong scope або standards material. Duplicate не створює нового fact; additive data записуються лише як traceable proposal/evidence; conflict не перезаписує current value до owner decision. Creator та його стандарти не є маршрутом продуктових джерел: документ-інструкція відокремлюється від product evidence і не змінює Паспорт.

Для Image Collector действует обязательное продолжение: `media review → passport_media_delta → Собиратель apply → PASSPORT_DELTA_APPLIED → STOP`. Media-статус не завершает end-to-end workflow сам по себе. Если delta создано, но не применено, конвейер возвращает `PASSPORT_UPDATE_PENDING`. Собиратель регистрирует все найденные источники, URL, local artifacts, права/доступ, quarantine/unavailable statuses и evidence-bounded JBTD/use rows; затем увеличивает Passport version/SHA и не запускает повторный аудит/верификацию.

Discovery Image Collector виконується за `public_model_name`, не за внутрішнім SKU. Перед media completion обов'язкові Google Video saturation, YouTube/TikTok/Facebook/Instagram checks, сторонні огляди/відеовідгуки та comments status для кожного відео. Неповне coverage запускає лише delta-пошук відсутніх surfaces і не затримує внесення вже знайдених source/JBTD records до Паспорта.


## 1.1. Текущее решение владельца процесса: упрощённый MVP

Формальный цикл разработки расширенного агента остановлен. Текущий рабочий контур для практического пилота — отдельный комплект 06/06A/06B/06C/06D. Він використовує чотири нормативні Run statuses із 06E, ручне розглядання та простий цикл `Verifier → Collector → Verifier`.

Комплект 05/05A/05B/05C является спецификацией режима `FULL` того же Агента-Верификатора. Его формальные schemas, hashes и package topology применяются только к FULL RUN и не являются обязательными условиями MVP-пилота по 06-серии. Паспорт SKU не редактируется Верификатором ни в одном режиме.

Точки входа:

- [MVP инструкция агента](06_MVP_Агент_верификатор_интервьюер.md);
- [MVP системный промпт](06A_MVP_Системный_промпт.md);
- [MVP шаблон запуска](06B_MVP_Шаблон_запуска.md);
- [MVP форма результата](06C_MVP_Форма_результата.md);
- [MVP сценарии приёмки](06D_MVP_Сценарии_приёмки.md).

## 2. Роли

### 2.0. Агент-координатор

Отдельный [Координатор конвейера](00_Агент_координатор_конвейера_Паспорта_SKU.md) запускает агентов и маршрутизирует только по 00A. Внешний ассистент является интерфейсом запуска и показа результата. Ни Координатор, ни внешний ассистент не создают содержательные результаты других ролей. Повторный дефект handoff-схемы останавливает автоматический цикл по инструкции Координатора.

### 2.1. Агент-собиратель

Собирает источники, извлекает evidence, создаёт атомарные proposals, фиксирует конфликты и обрабатывает пакет пробелов после аудита. Эта же роль является Создателем и Редактором Паспорта; отдельной роли нет. Она применяет `APPROVED candidate_update` и `change_event` только при изменении значения, источника или scope. Decision-only решение закрывает gap без записи в Паспорт и без `change_event`.

Он не устанавливает `verified`, не разрешает конфликт и не принимает решения по claims, позиционированию, генерации или публикации.

### 2.2. Агент-аудитор качества

Проверяет заполнение относительно действующего ТЗ, даёт положительную и отрицательную обратную связь и формирует пакет пробелов с проверяемыми критериями закрытия.

Он не исправляет паспорт, не подменяет собирателя и не принимает решения verifier.

### 2.3. Verifier

Принимает или отклоняет proposals, подтверждает допустимость evidence, разрешает конфликты и устанавливает или снимает `verified`.

### 2.4. Владелец данных или продукта

Предоставляет документы и ответы, принимает бизнес-решения о торговом объекте, комплектации, scope и других вопросах, которые нельзя вывести из источников.

## 3. Объекты конвейера

- канонический Паспорт точного SKU;
- source и immutable asset version;
- evidence fragment;
- evidence link к конкретной версии объекта;
- fact proposal и fact version;
- conflict;
- factual gap;
- evidence request;
- clarification request;
- audit report;
- gap package;
- Change Event.

Этот перечень описывает логические объекты, а не разрешает создавать отдельный документ на каждый объект. Реестр разрешённых файлов и единый версионируемый Паспорт определены в 00A. `candidate_update`, `collector_handoff` и audit report являются служебными выходами агентов, а не альтернативными Паспортами.

Один паспорт относится к одному точному `sku_id`. Комплект имеет собственный SKU и паспорт; факты компонентов остаются в паспортах компонентов. Паспорт комплекта хранит relation состава и ссылки, но не наследует подтверждение фактов компонентов.

## 4. Основной цикл

1. **Инициализация.** Фиксируются SKU, scope, marketplace context при наличии, run ID, версия ТЗ и список входных источников.
2. **Сбор.** Собиратель регистрирует источники и immutable версии либо явно фиксирует невозможность такой регистрации.
3. **Извлечение.** Создаются точные evidence fragments с локализацией.
4. **Заполнение.** Собиратель создаёт атомарные proposals и отдельные evidence links.
5. **Самопроверка.** Собиратель проверяет обязательные поля, scope, единицы, идентичность SKU и запрет маркетинговых выводов.
6. **Аудит.** Аудитор проверяет полное покрытие записей и формирует verdict.
7. **Возврат.** При пробелах создаётся gap package. Паспорт не исправляется аудитором.
8. **Догрузка.** Собиратель получает дополнительные материалы или ответы и создаёт новые либо обновлённые proposals, evidence и Change Events.
9. **Повторный аудит.** Аудитор проверяет каждый критерий закрытия и сохраняет историю открытых и закрытых gap ID.
10. **Передача verifier.** Пакет передаётся Верификатору для evidence decision; Run status вычисляется только по 06E.

Перед внешним запросом Верификатор выполняет поштучную смысловую сверку текста каждого вопроса со всеми сторонами source/evidence и audit/gap package по 06E. Независимый review фактического DOCX обязателен после любого сокращения текста; потеря значения, единицы, qualifier или отдельного источника оставляет форму `DRAFT_NOT_SENT`.
11. **Поддержание.** Новые источники, stale-сигналы и изменения продукта запускают новый run без стирания истории.

## 5. Статусы run

| Статус | Значение |
|---|---|
| `READY` | Все обязательные gaps `CLOSED`, все approved changes `APPLIED` |
| `READY_WITH_LIMITATIONS` | Открыты только явно необязательные допустимые gaps |
| `NOT_READY` | Есть mandatory open/partial gap, но агент/Собиратель может продолжать in-scope работу самостоятельно |
| `BLOCKED` | Продолжение невозможно без внешнего события и существует валидный active block record по 06E |

Единственная нормативная модель lifecycle и Run status — [06E](06E_MVP_Реестр_вопросов_и_ответов.md#нормативная-модель-статусов).

## 6. Типы пробелов

| Тип | Определение | Маршрут |
|---|---|---|
| structural_gap | Нет обязательного поля или нарушена структура записи | Собиратель |
| factual_gap | Неизвестно значение характеристики | До аудита — Собиратель; после принятого аудита — Верификатор через gap package |
| evidence_gap | Значение есть, но нет допустимого evidence | До аудита — Собиратель; после принятого аудита — Верификатор через gap package |
| identity_gap | Неясно, к какому SKU относится значение | Владелец данных |
| scope_gap | Неясны партия, комплект, период или условия применимости | До аудита — Собиратель; после принятого аудита — Верификатор через gap package |
| conflict | Есть несовместимые значения или scope | Verifier после подготовки evidence |
| classification_gap | Не определён source policy, value type или relation | До аудита — Собиратель; после принятого аудита — Верификатор при споре |
| boundary_violation | В паспорт внесено решение внешнего домена | Собиратель удаляет из проекции и маршрутизирует владельцу домена |
| process_decision | Требуется бизнес-решение, а не поиск факта | Владелец процесса или продукта |

Отсутствие значения не создаёт факт со значением «НЕТ ДАННЫХ». Оно создаёт `factual_gap` или `clarification_request`.

## 7. Уровни замечаний

- **Blocking:** нарушена идентичность SKU, отсутствует обязательное evidence для заявленного подтверждения, скрыт конфликт, присвоен недопустимый статус или есть риск ложного Product Truth.
- **Significant:** запись нельзя надёжно использовать без уточнения, но остальные части паспорта могут продолжать обработку.
- **Improvement:** улучшение ясности, навигации или качества без изменения фактического вывода.

Каждое замечание содержит положительное наблюдение, проблему, доказательство, требуемое действие, владельца и критерий закрытия.

## 8. Контракт передачи

Собиратель передаёт аудитору:

- точный SKU и run ID;
- версию паспорта и ТЗ;
- manifest источников;
- перечень созданных или изменённых fact versions;
- evidence links;
- открытые gaps, conflicts и clarification requests;
- Change Events;
- ограничения доступа и сделанные допущения.

Аудитор возвращает:

- verdict;
- положительную обратную связь;
- реестр замечаний;
- gap package;
- перечень проверенных объектов;
- критерии следующего прохода.

## 9. Правила обновления

- Новое значение в том же scope создаёт новую fact version.
- Новый scope создаёт отдельную identity записи.
- Дополнительное совпадающее evidence не создаёт лишнюю версию факта.
- Старые значения и конфликты не удаляются.
- Закрытый gap сохраняется в истории со ссылкой на evidence или решение.
- Собиратель изменяет только proposals и связанные служебные объекты.
- Аудитор не изменяет паспорт.
- единый Агент-Верификатор в зафиксированном режиме принимает решения по evidence/Answer и `APPROVED`; запись в Паспорт и `APPLIED` выполняет Собиратель по 06E.

## 10. Definition of Done конвейера

Конвейер готов к передаче verifier, если:

- выбран один точный SKU;
- каждый факт атомарен и имеет полный обязательный контракт;
- source и evidence имеют устойчивую идентичность и локализацию;
- relations оформлены отдельными evidence links;
- статусы внутренне согласованы;
- открытые конфликты и gaps видимы;
- отсутствуют немаркированные догадки;
- отсутствуют решения Marketing Book, Listing, FAQ или публикации внутри Product Truth;
- каждый открытый gap имеет владельца, следующий шаг и критерий закрытия;
- история run и изменений воспроизводима.


## 11. Нормативное уточнение конвейера после независимого ревью

Дата: 10.09.2026. При расхождении с более общими формулировками этого документа раздел имеет приоритет.

Gap является отдельной записью о недостатке. Единственный закрытый справочник `gap_type`, mapping в domain/routes/owner/authority/evidence/severity/readiness и правила deprecated/new types находятся в §4.4 05C (`05C-25-step7o`). Этот документ не задаёт второго списка. Evidence_request и clarification_request являются request, а не gap type. Process_decision является отдельным запросом решения владельца.

Каждый gap содержит severity, object/field, cause, significance, next action, owner role, acceptance criteria, required output objects и closure status. Собиратель применяет только `APPROVED candidate_update`, если меняется значение, источник или scope. Decision-only решение по уже записанному факту закрывает gap без `candidate_update`, `change_event` и повторного аудита; при фактическом изменении после `change_event` выполняется только целевой аудит изменённого объекта.

Каждый run имеет режим initial_full_snapshot, update_delta или gap_response_delta. Delta требует валидный base package ID, SHA-256, object inventory и операции add/update/no_change. Повторная операция использует idempotency key и не создаёт дубли.

Самопроверка является доказательной: каждый check содержит checked object IDs, method/result, exceptions и связанные gap IDs. Общий PASS без покрытия запрещён.

Полнота контролируется coverage matrix. Если обязательный каталог характеристик не предоставлен, создаётся coverage baseline gap; ограниченное извлечение не выдаётся за полный паспорт.

Перед передачей ограниченного пакета Собиратель сверяет его с исходным заданием и ранее извлечёнными значениями того же SKU. Каждая ожидаемая группа и каждый ранее открытый кандидат или gap, относящиеся к заявленному scope, получают в текущем пакете ссылку, явный статус вне scope с основанием либо запись о переносе в открытый gap. Молчаливое исчезновение элемента внутри заявленного scope запрещает `package_admissible_for_audit=true`. Аудитор независимо повторяет эту сверку только по заявленному scope и явно перенесённым ID; отсутствие элементов вне scope не является blocking finding. Это правило не превращает диагностический пакет в утверждённую базу Product Truth.

Выход дополняется внешним package manifest, который создаётся последним и содержит SHA-256 остальных файлов без самохеша.
## 12. Мультимедийная ветка

Разрешённые видео исследуются полностью: metadata, описание, transcript/audio, кадры и комментарии. Claim, evidence, comment/use-case/JTBD signal, comparison signal та observed multimedia record — різні об'єкти. Creative/UGC opportunity, approved asset, placement, montage і publication decision не входять до Passport loop. Перед аудитом перевіряються locators, provenance, хибні висновки та порівнюваність; rights information і coverage denominator є неблокуючою довідковою або method-diagnostic інформацією, access gap не приховується.
## 13. Ветка верификации/интервью

При необходимости внешней информации аудитор передаёт gap package единому Агенту-Верификатору в активном режиме MVP по [06E](06E_MVP_Реестр_вопросов_и_ответов.md). К этому классу относятся неизвестные значения, междокументные конфликты, отсутствующий scope, внешний документ и owner decision. Агент формирует атомарные вопросы, регистрирует ответы и evidence, затем передаёт машинно-проверяемый delta Собирателю. Собиратель создаёт новый candidate package; статусы, approval, запись и closure выполняются по 06E. Аудитор не возвращает такие gaps Собирателю, иначе возникает петля.


## 14. Нормативное уточнение ветки закрытия пробелов v02

Это единый Агент-Верификатор/Интервьюер активного режима MVP, а не отдельная конкурирующая Verifier role. Исторические FULL-правила не загружаются в новые запуски. Ветка использует question N:1 gap, новые IDs для follow-up, status-dependent ответы без фиктивного evidence, closure matrix по required evidence/authority, полную state machine с reopening, детерминированную idempotency, respondent authentication, input quarantine и отдельный UGC rights register. Completion определяется покрытием заявленного scope и preflight, а не количеством вопросов. Readiness вычисляется по активному MVP-контракту 06E. Интервьюер может сформировать `ready_for_handoff` без unresolved Blocking либо non-ready `handoff_with_blockers`; `ready_for_audit` возникает после collector package gates, а `accepted_closed` устанавливает только последующий уполномоченный аудитор/gate. Исторические правила 05/05A/05B/05C не загружаются в новый MVP-run и не могут добавлять ему gates или переходы.

## 15. Шаг 1 ветки закрытия пробелов — маршруты происхождения

Ветка использует три независимых маршрута: INTERVIEW (`gap → question → answer → evidence`), DIRECT EVIDENCE (`gap → intake_event → evidence`) и SYSTEM EVENT (`gap/conflict → system_event → observation или request`). Вопрос, ответ и респондент обязательны только для interview origin и запрещены для остальных маршрутов. Независимо найденный источник получает intake event; системно выявленный duplicate/superseding conflict — system event. System observation без evidence и owner decision не подтверждают Product Truth. Для нового MVP-run применяются только правила 06E; расширенная authoritative-схема 05C сохраняется как историческая и не добавляет gates.
## 16. Шаг 7C — canonical serialization

В ветке закрытия пробелов raw file hash и canonical object hash разделены. Для новых MVP-run применяется только нормативный pipeline 06E. Исторический профиль `SKU-GAP-C14N-02/3.1` и расширенные правила §4.2 05C (`05C-25-step7o`) не загружаются и не добавляют gates. Нормативные scenario specifications не считаются программно исполненными без test artifacts.
## 17. Шаг 7D — conflict exhaustion

Conflict `cannot_resolve` допускается только по единому gate §14.2 05C: typed exhaustion decision в существующем exhaustion register, полный policy route coverage, проверяемые attempts/impossibility evidence, distinct routes, authority и независимый approval. Gap Agent только предлагает. Статус остаётся unresolved, не выбирает winner и не меняет Product Truth; effective Blocking допускает только `handoff_with_blockers`. Новые массивы зарегистрированы в `SKU-GAP-C14N-02/3.1`.
## 18. Шаг 7E — security incident fingerprint/dedup

Security incident identity определяется только §19.9 05C. Immutable raw artifact identity, safely computed payload digest, normalized signature, domain-separated fingerprint, correlation cluster и occurrence разделены. Redacted excerpt/display не участвует как достаточное основание dedup. Missing/unreadable/mismatch/collision создаёт отдельный provisional event и applicable hold; correlation/rekey не объединяет события, holds или custody. Новые arrays зарегистрированы в `SKU-GAP-C14N-02/3.1`.
## 19. Шаг 7F — identity/authentication provenance

Identity subject, account binding, authentication event, identity proofing, affiliation, claimed role и scoped authority разделены и определяются только §8.2 05C. Каждый received answer/respondent decision связан с current session/account/auth event. Generic email/chat/name/shared account не подтверждает человека, должность или authority. Privacy-safe typed records, assurance gates, continuity/re-auth и spoofing holds используют `SKU-GAP-C14N-02/3.1`.
## 20. Шаг 7G — typed partition для `scoped_apart`

`scoped_apart` определяется только §14.3 05C (`05C-25-step7o`). Gap Agent создаёт typed proposal; downstream auditor/authorized gate принимает его после проверки взаимной исключительности, полного denominator coverage, evidence sufficiency, residual unresolved cell/gap и authority/independence. Accepted partition создаёт только scoped propositions, не global winner и не переписывает Product Truth. Изменение dimension/source/evidence переоткрывает partition/conflict и инвалидирует readiness. C14N profile: `SKU-GAP-C14N-02/3.1`.
## 21. Шаг 7H — question intent/materialization idempotency

Question semantics и exact sendable text разделены по §6 05C (`05C-25-step7o`). Stable semantic intent key не зависит от materialization, timestamp/run ID или recipient display name. Изменение смысла создаёт новый immutable intent/question; изменение текста при том же смысле создаёт новую materialization version. Follow-up всегда отдельный intent, а answer связан с реально доставленным materialization/text hash. C14N profile: `SKU-GAP-C14N-02/3.1`.
## 22. Шаг 7I — delivery retry/idempotency

Delivery command, physical attempts и provider receipts разделены по §7 05C (`05C-25-step7o`). Same logical send переиспользует delivery intent; retry создаёт append-only attempt, а late receipt — observation/state event без переписывания истории. Provider acceptance не равна delivery; ambiguous timeout требует reconciliation. Exactly-once не заявляется без доказанной provider support, а unsupported mode фиксируется как at-least-once with local dedup. C14N profile: `SKU-GAP-C14N-02/3.1`.
## 23. Шаг 7J — deterministic gap type mapping

Active `GAP-MAP-01/1.0` в §4.4 05C единственным образом сопоставляет 17 canonical gap types с domain, allowed route, owner/authority, typed evidence requirement, severity floor и readiness impact. Raw type сохраняется; unknown/missing/deprecated/collision/unknown predicate блокирует routing. Source/system unavailability не преобразуется в отсутствие product fact. Profile change инвалидирует mapping-derived question/proposal/readiness. C14N profile: `SKU-GAP-C14N-02/3.1`.
## 24. Шаг 7K — canonical package topology

Единственная topology 23 output files, JSON-in-Markdown envelope, размещение readiness/trusted-control, hash vocabulary и acyclic P0–P6 build определены §2.1–§2.5 05C (`05C-25-step7o`). Readiness существует только в `preflight_report`; trusted-control payload — только внешний input. Package manifest создаётся последним, содержит 22 predecessor entries и не включает собственный hash. C14N profile: `SKU-GAP-C14N-02/3.1`.
## 25. Шаг 7L — audit consistency corrections

Синхронизированы exact document versions, четыре identity/authority array paths C14N, readiness scenario count, README current/historical status и terminal enum spelling. Единственный контракт: `05C-25-step7o`; C14N: `SKU-GAP-C14N-02/3.1`. Иные findings и RUN-009 не изменялись.
## 26. Шаг 7M — исполнимая topology событий и C14N paths

05C (`05C-25-step7o`) определяет atomic subject+Change Event commit до freeze, открытый append-only event ledger P2–P5 с финальным freeze P5E и manifest P6 без forward references или post-freeze mutation. Delivery artifact имеет единственные пять containers §7. C14N `SKU-GAP-C14N-02/3.1` использует exact JSON-root provenance paths и nested `package_manifest.normative_payload.build_result` arrays; обязательный schema-to-registry check отклоняет missing, orphan, duplicate и wrong-container paths. Остальные findings после 7L и RUN-009 не изменялись.
## 27. Шаг 7N — external trust, closed hash exclusions и non-stage readiness

05C (`05C-25-step7o`) отделяет reusable external trusted-control input/profile от run binding в reconciliation/preflight, задаёт закрытый per-object registry включения content hashes и исключения только generated/self hashes, а также однозначный `not_admitted` readiness result с `computed_stage=null`. Same-run/self trust anchor и unknown hash-like path fail closed. Null stage не означает READY. Основной C14N: `SKU-GAP-C14N-02/3.1`; внешний профиль: `SKU-GAP-EXTERNAL-C14N-01/1.0`.
## 28. Шаг 7O — active profile, registry и audit errata

05C (`05C-25-step7o`) использует единый active C14N `SKU-GAP-C14N-02/3.1`, не содержит orphan `input_reconciliation.records[*].recheck_trigger`, сохраняет внешний `trusted_control_input.trusted_control_artifact.recheck_triggers` и использует exact terminal token `accepted_closed`. Active и historical scopes проверяются отдельно; ложные PASS claims старого отчёта 7L исправляются отдельной immutable errata.

## 29. MVP-контур агента-верификатора/интервьюера

MVP проверяет паспорт и источники, различает факт/claim/мнение/пробел/конфликт, даёт positive/negative feedback, создаёт вопросы и исполнимые задания Собирателю, включая web/YouTube/comments, observed multimedia evidence, timestamps, use-case/JTBD signals, claim/plus/minus/comparison signals та evidence boundaries. Він не створює creative/UGC opportunity, placement, montage або publication decision і не редагує Паспорт чи Product Truth. Допустимы только `READY`, `READY_WITH_LIMITATIONS`, `NOT_READY`, `BLOCKED`; критичные compliance/safety/identity claims требуют подтверждения и ручного решения. Пилот ограничен 3–5 SKU и не объявляется production-ready.

## 30. MVP question/answer loop
Вопросы ведутся в [06E](06E_MVP_Реестр_вопросов_и_ответов.md) со стабильными `Q-<RUN>-<NNN>`; ID не переиспользуется, ответ содержит question ID; новый `answer_id` назначает Собиратель при регистрации. Partial создаёт новый `related_question_id`. Собиратель проверяет exact ID/scope/evidence, классифицирует `ANSWER_WITH_EVIDENCE/CLAIM_ONLY/PARTIAL/CONFLICT/DECLINED/NO_ANSWER/WRONG_SCOPE` и готовит `candidate_update/conflict/no_change`, не активирует closure. Верификатор устанавливает Answer `VERIFIED/PARTIAL/REJECTED` и при достаточности переводит Change в `APPROVED`; Собиратель применяет изменение, создаёт `change_event` и фиксирует `APPLIED` либо `APPLY_FAILED`, после чего Gap и Question вычисляются по 06E и downstream findings. Примеры: [07A](07A_MVP_DHR-203BCV_Активные_вопросы.md), [07B](07B_MVP_DHR-203BCV_Тест_возвращённых_ответов.md), [08](08_Сравнение_качества_вопросов_агентов.md).

## 31. Формат внешнего запроса ответов

Внутренний реестр вопросов может быть Markdown, но внешний запрос адресату формируется как DOCX по умолчанию либо XLSX для массового/табличного сбора; markdown/chat-only список недостаточен. PDF допускается только как view copy для просмотра/печати и не является основной редактируемой формой возврата. Во всех формах сохраняются stable question IDs и инструкция отвечать по ID.

## 32. Основная форма возврата ответов

Действующее правило формата: DOCX — основной outbound/return для развёрнутых ответов; XLSX — для массового/табличного сбора; PDF — только outbound view copy. Если респондент фактически вернул заполненный PDF или скан, его не отклоняют: сначала регистрируют как immutable source artifact, затем извлекают и нормализуют данные по 06E. Такой PDF не становится рабочей редактируемой формой.

## Единая система IDs и связей

Единственный нормативный ID-контракт — [06E](06E_MVP_Реестр_вопросов_и_ответов.md#нормативная-система-ids-и-связей). DOCX/XLSX без question ID не сопоставлять по порядку; фиксировать identification error и запрашивать уточнение.

## Один Верификатор два режима

Для новых запусков действует только режим `MVP` — контроль/вопросы/answer-delta по 06-серии. Комплекты 05 и FULL сохраняются только для исторической трассировки и не загружаются. Режим MVP фиксируется до старта RUN и не меняется. Единые ID, статусы и closure заданы только в [06E](06E_MVP_Реестр_вопросов_и_ответов.md).

## Source artifact перед нормализацией

Применяй только нормативную модель [06E](06E_MVP_Реестр_вопросов_и_ответов.md): зарегистрируй `SRC-<RUN>-<NNN>` до извлечения; не изменяй оригинал; Answer/Evidence/candidate_update обязаны ссылаться на `source_artifact_id` и точный locator. PDF, фактически возвращённый респондентом, принимай как immutable source artifact; при ненадёжном question ID фиксируй `IDENTIFICATION_ERROR`. Derived/OCR material не заменяет оригинал.

## XLSX массового сбора

Для массовых/табличных ответов используй [канонический XLSX-шаблон](Шаблон_массового_сбора_ответов_SKU.xlsx) и единственный нормативный контракт в [06E](06E_MVP_Реестр_вопросов_и_ответов.md). Не сопоставляй строки по порядку. До импорта сохрани returned XLSX как immutable Source Artifact; системные answer/source/evidence IDs назначает Собиратель после проверки.

## Run status и запрос информации

Применяй только [нормативное разграничение 06E](06E_MVP_Реестр_вопросов_и_ответов.md). `NEEDS_INFORMATION` не является Run status; используй `required_action=REQUEST_INFORMATION`. Пока самостоятельные search/retry/actions остаются — `NOT_READY`. `BLOCKED` требует внешнего события и валидного active `BLK-<RUN>-<NNN>` с reason, object IDs, responsible party и resume condition. Решение специального владельца требует verified authority scope/evidence.


## Terminal closure и handoff

Применять только [нормативный terminal closure/handoff contract 06E](06E_MVP_Реестр_вопросов_и_ответов.md#terminal-closure-и-handoff-run). Собиратель после успешной записи создаёт immutable `run_closure_package`; Верификатор подтверждает criteria/status, но не редактирует Паспорт. Обычный `NOT_READY` продолжается в текущем run и не создаёт checkpoint; checkpoint допускается только для `BLOCKED` или административного сбоя по 06E. Следующий успешный RUN сверяет `input_passport_version` и `input_passport_sha256` с принятым closure; несовпадение препятствует только этому новому RUN и не возвращает текущий run в цикл.


## Decision ID и sealed manifest

Использовать только [нормативный контракт 06E](06E_MVP_Реестр_вопросов_и_ответов.md#decision-events-и-sealed-manifests). Каждая новая оценка получает уникальный `DEC-<RUN>-<NNN>`; повтор ID с иным snapshot запрещён. До handoff payload замораживается, затем создаются manifest revision, detached checksum и ациклический package seal-binding. Любое изменение payload требует нового revision; `STALE_MANIFEST` запрещает продолжение.

## Owner decision 11.09.2026 — единая форма вопросов и rights-as-risk

- Единственный канонический DOCX-шаблон вопросов: [Шаблон запроса ответов Паспорта SKU](Шаблон_запроса_ответов_Паспорт_SKU.docx). Он применяется для `initial`, `follow-up`, `reopened`, `MVP` и `FULL`; наследуются стили, таблицы, поля, интервалы, порядок блоков и page layout. При материализации меняются только IDs, содержание вопросов и критерии закрытия. Новый дизайн без утверждения владельца запрещён.
- Нормативная модель прав и риска находится только в [06E](06E_MVP_Реестр_вопросов_и_ответов.md#rights-as-risk--нормативное-правило). Отсутствие или неподтверждённость прав само по себе не является gate для внутреннего сбора, evidence analysis, claim verification, comparison, timestamps, observed use-case/JTBD signals і оновлення Паспорта за незалежно достатніми фактами.
- Фактическая надёжность/evidence sufficiency оценивается отдельно от `rights_status` и `rights_risk_level`. Нельзя ставить `REJECTED`, `NOT_READY` или `BLOCKED` только из-за отсутствия rights evidence.

## Завершение тестирования 11.09.2026

Verdict тестирования на 11.09.2026: `READY_WITH_LIMITATIONS`. Это историческое решение; после инцидента INC-009 от 23.09.2026 текущая приёмка маршрута возврата ответов открыта до сценариев LOOP-01..05 в 06D. На дату исторического verdict открытых Blocking/Significant defects не было; обязательная limitation — успешная реальная запись изменения и terminal handoff подтверждаются в первом production pilot. Исторический отчёт закрытия не входит в действующий комплект. Audit/service files сохранены отдельно.
## Контроль маршрута источников и файлов (22.09.2026)

В run control до запуска собирателя фиксируются точный SKU/версия и абсолютный `product_root`. `sku_id` извлекается только из значения возле явного поля/подписи `SKU` в предоставленном документе; оно может состоять из цифр, букв или их сочетания и сохраняется дословно. Модель, название товара, другое поле, имя файла или папки не используются как SKU. Если явное поле `SKU` отсутствует, не читается или содержит конфликтующие значения, агент обязан запросить точный SKU у пользователя и не создавать `run_id`, Паспорт или `product_root` до ответа. Имя `product_root` должно совпадать с подтверждённым `sku_id`; версия/модель хранится отдельно. Собиратель предъявляет реестр всех ссылок входных документов, фактических продуктовых файлов и отношений версий источников. До аудита обязательны path containment, полнота ссылок в заявленном scope, raw/decoded HTML, роли артефактів, SHA-256 исходних файлов и `ACTIVE/OLD` lineage. Ошибка технического manifest или parent linkage показывается как диагностика и не возвращает пакет в новый цикл. Аудитор независимо перепроверяет источники непосредственно в `артефакти/YYYY-MM-DD/`. После выполнения handoff и acceptance gates внутренний переход к следующему агенту выполняется без отдельного подтверждения владельца теста.
## Gate смысловой полярности порогов (23.09.2026)

До передачи пакета на независимый аудит собиратель выполняет `PF-NEGATION-COMPARATOR`: полная фраза источника с переносами строк должна совпадать с fact/evidence/link по отрицанию, направлению порога, числу, единице, объекту и условиям. Substring `MATCH` без смыслового сравнения не даёт PASS. Blocking FAIL возвращает пакет собирателю. Аудитор независимо проверяет эти признаки; при противоречии выдаёт `RETURNED_FOR_REWORK`, и переход к Верификатору запрещён до исправленной sealed revision и повторного аудита.
## Gate повторного вопроса после полученного ответа (23.09.2026)

На входе Верификатора весь возвращённый документ регистрируется как Source Artifact и оценивается по содержанию, даже если active Question registry предыдущего теста утрачен. Неизвестный Q ID блокирует нормативный Answer link/closure, но не чтение ответа. До создания новых вопросов обязательна матрица покрытия всех полученных ответов и проверка на повтор. Выходной follow-up запрашивает только конкретный отсутствующий документ, scope или owner decision и указывает, что уже было отвечено. Отсутствие реестра и недостаточность доказательства фиксируются раздельно; ни одно из них не оправдывает повторного запроса того же ответа.
## Gate возврата ответов после reset (23.09.2026)

**До отправки вопроса.** Верификатор материализует exact Q ID и текст в DOCX, Собиратель сохраняет outbound DOCX и снимок active Question registry как immutable product artifacts в `артефакти/YYYY-MM-DD/`, регистрирует SHA-256 обоих файлов и связь Question↔Gap. Outbound DOCX получает Source Artifact ID с ролью `outbound_request` по 06E; внутренний снимок Question registry получает запись архивного реестра и ссылку на outbound ID, но не выдается за внешний источник. `SENT` запрещён, пока оба объекта не сохранены и не связаны. Очистка рабочего RUN не удаляет эти архивные опорные объекты.

**При получении ответа.** До содержательного решения Верификатора Собиратель регистрирует returned файл/URL как новый immutable Source Artifact с точным locator, Q IDs из документа, `received_at`, sender/authority status, SHA-256 и relation к outbound artifact, если он найден. Если старый registry утрачен, `question_registry_found=false`, `parent_request_id=unknown`, но регистрация документа и анализ его содержания продолжаются. Нормативные Answer IDs и Question transitions при этом не создаются; историческое восстановление — отдельная задача, не блокирующая source intake.

**Перед новым вопросом.** Верификатор предъявляет матрицу 1:1 `question_id → source_artifact_id → answer_locator → response_received → stated_answer → evidence_sufficiency_reason → residual_evidence → same_intent_repeat → follow_up_question_id_or_none`. Равный по смыслу вопрос при `response_received=true` получает `follow_up=false`. Новый вопрос обязан явно назвать уже полученный ответ и запрашивать иной отсутствующий документ, scope или owner decision. Проверка выполняется по тексту/смыслу, не только по Q ID. Если матрица неполна либо найден повтор, внешняя форма остаётся `DRAFT_NOT_SENT`, а verifier handoff возвращается на исправление. Отсутствие active registry — trace issue; недостаток доказательства — evidence gap; эти причины не объединяются в «ответ не получен».

Приёмка этого маршрута требует сценариев LOOP-01..05 из 06D на текущем returned документе, а не только формального наличия 5 вопросов, checksum или валидного Run status. Результат и статус перехода показываются владельцу теста без отдельного подтверждения внутреннего перехода; действующие proof и acceptance gates сохраняются.
## Gate необходимости повторного внешнего запроса (23.09.2026)

Полученный ответ и остаточный evidence gap не создают автоматического `REQUEST_INFORMATION`. После `response_coverage` Верификатор для каждого остатка проверяет, какой именно текущий результат он блокирует: ограниченную запись Паспорта, принятие Product Truth или конкретный downstream claim. До новой внешней формы используются доступные внутренние источники и допустимые состояния `unknown`/disputed с явными границами. Если можно подготовить честный `NOT_READY` черновик, такой черновик готовится без повторного запроса. Внешний запрос допустим лишь при указанном обязательном gate, доказанной недостающей части и отсутствии достаточного внутреннего маршрута; `no_repeat_gate=PASS` и архивный `LOOP-01=PASS` сами по себе не разрешают отправку. Отменённая неотправленная черновая форма сохраняется в архиве с `action_status=cancelled`, `delivery_status=DRAFT_NOT_SENT` и отдельным решением об отмене маршрутизации без редактирования sealed packages.

## Gate максимального сбора знаний о продукте (24.09.2026)

Для первичного или существенного обновления Паспорта default scope — максимально полный сбор доступных знаний о точном SKU/версии. Он включает все входные файлы, все ссылки и вложения внутри них, доступные публичные и разрешённые корпоративные источники: официальные страницы, инструкции, каталоги, сертификаты, документы, фото, видео, обзоры, листинги, отзывы и наблюдаемые use cases. Поиск ограничен exact identity/scope и не превращает signal в Product Truth.

Ссылка, встроенная в предоставленный файл, считается предоставленным источником. `provided_sources_only` не запрещает открывать такую ссылку, загружать доступное содержание и создавать производные evidence. Публичный read-only доступ и загрузка в `product_root` не требуют нового решения владельца. Исключение допустимо только по явному решению владельца, из-за недопустимых учётных данных/прав или после документированных неудачных попыток.

Переход к аудиту запрещён, если URL только извлечён или зарегистрирован. `PROCESSED` требует архивного source artifact либо воспроизводимой выгрузки/перечня объектов, содержательной обработки и связи с фактами/evidence/gaps. Иначе нужен `FAILED_WITH_ATTEMPTS` с журналом или `OWNER_EXCLUDED` с решением. До этого `package_admissible_for_audit=false`.

Единый Паспорт сохраняет полную утверждённую структуру. Отсутствие данных не удаляет обязательный раздел: он остаётся с явным `MISSING`, gap и требуемым источником. JBTD/Buyer Episodes отображаются как read-only relations или явная прогалина; наблюдаемые use cases из фото/видео не выдаются за подтверждённые JBTD.

## Gate повторного доступа к источникам из Паспорта (24.09.2026)

Единый Паспорт обязан хранить в разделе `Джерела і походження` все ссылки на источники, которые входили в source scope или были обнаружены при исследовании. Для каждого `source_id` покажи `source_title`, `source_type`, полный `original_url` или исходный file locator, устойчивый/canonical URL при наличии, локальный archived artifact, status, `captured_at`, `last_checked_at` и связанный gap. Сокращения вида `dnipro-m.ua/...`, `Drive file rId9`, ID видео без URL или только локальный путь не заменяют полный locator.

В DOCX веб-URL должен быть реальным clickable hyperlink с exact target в OOXML relationship, а не только видимым текстом. Длинный URL может иметь короткую display label, но hyperlink target хранится полностью. Временный signed URL с секретным token не копируется в Паспорт: храни безопасный stable locator и ссылку на архивный artifact.

`PF-PASSPORT-SOURCE-LINK-COMPLETENESS` сопоставляет каждый source/link из source manifest и `knowledge_coverage_matrix` с одной строкой Паспорта и проверяет exact hyperlink target. Missing, shortened или non-clickable URL даёт FAIL и `package_admissible_for_audit=false`.

## Маршрут `passport_recreate` (04.10.2026)

Recreate є окремою transaction поза звичайним життєвим циклом initial/delta. Координатор утримує per-SKU lock, старий Паспорт залишається canonical до atomic switch, а Собиратель будує новий `NOT_READY` object тільки у staging. Старі Product Truth values і verification states не копіюються автоматично.

Після read-back candidate Координатор перемикає один canonical pointer, commit-ить archive receipt і створює `STALE_PASSPORT_BINDING` для незавершених downstream artifacts old SHA. До commit будь-яка помилка повертає старий стан без приховування Паспорта; після commit повернення потребує окремого `RESTORE_ARCHIVED_PASSPORT`.

Open runs використовують збережені snapshots старих контрактів і не мігрують посеред виконання. Нові routes доступні лише для запусків, створених після effective date v2.13 і ввімкнення відповідного feature flag.










