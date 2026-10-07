# 03. AI Design Content Creation Pipeline

Статус: `working`; описание четырёх контуров согласовано 2026-09-10. Готовность компонентов и оставшиеся положения проверяются отдельно.  
Область: продуктові фото, Amazon MAIN і supporting images, PDP gallery, A+, Store, advertising/social assets, AI generation, AI retouch та локалізація.

## 1. Навіщо потрібен окремий конвеєр

AI не повинен одразу створювати зображення з короткого запиту. Якість контенту залежить не лише від генератора, а від якості продуктового факту, розуміння покупця, канальних обмежень, контрольованої гіпотези та перевірки результату.

Конвеєр розділяє вісім типів рішень:

1. чи валідні Product Truth, Brand Entity, права, claims і channel requirements;
2. яка shopping mission, buyer job або commercial gap потребує рішення;
3. чи потрібне створення/зміна asset, чи правильний результат — reuse, maintain, investigate або route to another owner;
4. яку причинну гіпотезу перевіряємо;
5. який production contract і які visual/text invariants не можна порушити;
6. як prompt/production layer виконує контракт без переосмислення бізнес-рішення;
7. чи пройшов результат fidelity, compliance, expectation і release controls;
8. що доведено experiment/measurement і може перейти в learning.

Якщо ці рішення з'єднати в одному генеративному кроці, модель може перетворити пошуковий попит на непідтверджений claim, додати неіснуючий аксесуар або створити красивий, але непридатний для каналу результат.

<!-- SKU_TZ_BOUNDARY_APPROVED_2026_09_10_START -->
## 1.1 Передача проверенных данных SKU в ТЗ

Утверждено владельцем процесса 10.09.2026. Этот блок фиксирует согласованную границу контуров; он не утверждает автоматически остальные рабочие положения или готовность агентов.

Контур SKU собирает, проверяет и актуализирует сведения о продукте. Контур создания ТЗ использует результат этой проверки и управляющие стандарты; далее следуют продакшен с локализацией и контролем, затем обучение по результатам работы.

Для любого товарного задания сначала проверь наличие Паспорта точного SKU и версии продукта. Если Паспорта нет, первым рабочим этапом является сбор источников, создание Паспорта и проверка продуктовых фактов в контуре SKU. До подтверждения фактов, достаточных для конкретного задания, не переходи к ТЗ, prompt-сценарию или креативу. Редакция правила тестирования от 23.09.2026: результаты этапов фиксируй и показывай владельцу задачи, но внутреннюю подготовку, проверки, исправления и переходы между агентами выполняй без отдельного подтверждения, когда действующие handoff и acceptance gates пройдены. Останавливайся только при отсутствии необходимого решения уполномоченного владельца, невыполненном gate либо перед внешней отправкой или публикацией, требующей явного разрешения. Отсутствие ответа не является разрешением.

Запуск всего AI Design маршрута выполняет отдельный Агент-координатор по `C:\Users\ystep\Documents\DM AMAZON\AI Design Conveyor\02_SKU_Passport\00_Агент_координатор_конвейера_Паспорта_SKU.md`. Внешний ассистент только запускает его и показывает решение; Координатор запускает только существующих агентов по их инструкциям, не выполняет их работу и не создаёт новых ролей, документов или обходных маршрутов. Недоступный агент либо неопределённый контракт дают `BLOCKED`. В контуре SKU обязательный маршрут задаёт `C:\Users\ystep\Documents\DM AMAZON\AI Design Conveyor\02_SKU_Passport\00A_Контракт_передач_Паспорта_SKU.md`: один версионируемый Паспорт со станами, закрытый реестр разрешённых продуктовых выходов и `ACCEPTED` receipt следующего агента. Координатор не подменяет приёмку и не добавляет промежуточные документы. Паспорт `NOT_READY` с открытыми фактологическими gaps является допустимым результатом этапа, но не разрешает непроверенные claims у ТЗ.

Graph formalization цього процесу визначає [AI Design Execution Graph Contract](AI_DESIGN_EXECUTION_GRAPH_CONTRACT.md), status `SPECIFICATION_READY_NOT_RUNTIME_BOUND`. Він перетворює застосовні R01–R41 на typed edges, вводить authoritative run state, session-control profile, checkpoints, reducers і runtime acceptance, але не активує runner, не створює нових агентів і не розширює Product Truth, provider, spend або publication authority.


Стандарт формы паспорта SKU задаёт структуру и требования к заполнению. Заполненный паспорт конкретного SKU содержит проверенные факты и ссылки на подтверждающие источники. Наличие формы или заполненных полей само по себе не подтверждает достоверность данных.

Content TZ Agent должен использовать проверенную актуальную версию паспорта SKU. В ТЗ фиксируются идентификатор и версия паспорта, ссылки на факты и доказательства, дата и ответственный за проверку, а также применённые версии Marketing Book, стандарта формы паспорта и требований канала. Агент ТЗ отвечает за корректное использование этих данных; проверка и актуализация продуктовых фактов остаются в контуре SKU.

Недостающие или противоречивые факты необходимо вернуть в контур SKU на проверку. Агент ТЗ не вправе восполнять их предположениями или самостоятельно объявлять подтверждёнными. Пока пробел не закрыт, затронутая часть ТЗ не допускается к утверждению и передаче в продакшен. Выбор «Продолжить с рисками» не отменяет это ограничение.

При изменении исходных данных необходимо определить затронутые ТЗ, prompt-сценарии и материалы и проверить их до дальнейшего использования. До завершения проверки затронутый ТЗ не считается актуальным; замена версии исходника не обновляет его автоматически. Незатронутые сведения не требуют повторной проверки только из-за изменения предпочтений по стилю.

Контур обучения формирует предложения по улучшению данных SKU, ТЗ, промптов и стандартов. Новые сведения о продукте направляются на проверку в контур SKU. Изменения Marketing Book и других управляющих стандартов вступают в силу только после согласования владельцем процесса; результат теста не изменяет стандарт автоматически.
<!-- SKU_TZ_BOUNDARY_APPROVED_2026_09_10_END -->

## 2. Архитектура четырёх контуров

Описание четырёх контуров, их передач, проверок и возвратов согласовано владельцем процесса 10.09.2026. Контур объединяет работу и ответственность; функция или контрольная точка внутри него не являются отдельным реализованным агентом. Согласование архитектуры не меняет готовность компонентов, границы пилота и открытые решения.

### Управляющий слой

Marketing Book задаёт брендовые, смысловые и визуальные требования. Стандарт формы паспорта SKU задаёт структуру и требования к данным, а заполненный паспорт конкретного SKU передаёт проверенные факты. Стандарты каналов определяют допустимый формат и ограничения размещения. Claims, Compliance и QA задают требования к доказательствам и приёмке. Утверждённые формы фиксируют передачу результатов. Эти документы управляют контурами, но не выполняют работу вместо агентов.

### Контур 1 Данные о продукте SKU

Вход: точный SKU, задача сбора или обновления, доступные источники и прежняя версия паспорта. Исполнители: Агент-собиратель Паспорта SKU, Агент-аудитор качества Паспорта SKU и Агент закрытия пробелов (Gap Verifier/Interviewer) Паспорта SKU. Product Truth Verifier отдельно принимает или отклоняет proposals и устанавливает статус verified; агент закрытия пробелов не подменяет его.

Выход: актуальный проверенный паспорт SKU, связанные доказательства, журнал изменений и явные ограничения использования. Передача в контур 2 допускается для проверенных фактов, достаточных для выбранной задачи, с фиксированными версиями и ссылками. Виконуваний маршрут Паспорта SKU визначає чинний контракт `00A_Контракт_передач_Паспорта_SKU.md`, а дозволені переходи й рішення деталізуються його чинними залежностями `06–06E` у режимі `MVP`. Цей опис контуру є оглядовим і не задає окремої послідовності агентів, повторних перевірок або rework-циклів; у разі розбіжності зі старою оглядовою схемою застосовується 00A. Неперевірені відомості не стають фактами ТЗ.

### Контур 2 Создание ТЗ и prompt-сценария

Кожний content run до authoring отримує immutable `launch_control`. `CONTENT_TZ_ONLY` завершується на `CONTENT_TZ_READY`; `END_TO_END_GENERATION` має terminal target `READY_CONTENT_PACKAGE` і включає Content TZ, expected deliverables, execution-input routing, Prompt Agent, AI Creator, provider execution у межах окремого cost/capability preflight та output QA. Publication не входить до жодного з цих terminal targets.

`human_review_checkpoint` задається незалежно: `REQUIRED` створює блокувальну зупинку після accepted Content TZ; `OPTIONAL` показує результат без зупинки; `SKIP` одразу продовжує внутрішній маршрут. Команда `Запусти конвеєр створення контенту` за замовчуванням означає `END_TO_END_GENERATION + OPTIONAL + READY_CONTENT_PACKAGE`; команда створити лише ТЗ означає `CONTENT_TZ_ONLY + CONTENT_TZ_READY`.

Завершений `CONTENT_TZ_ONLY` run не продовжується неформально. Нова явна команда на генерацію створює `EXPAND_RUN_SCOPE`, після чого `RUN_SCOPE_RECONCILIATION` перевіряє актуальність Passport/Product Truth, Content TZ, expected manifest, downstream modules, checkpoint і side-effect ledger. Current artifacts повторно не створюються; stale dependency повертається тільки своєму owner у bounded rework. Успішне reconciliation відновлює маршрут з expected-manifest read-back/freeze, а не з початку Content TZ.

Вход: результат контура 1, задача контента, клиентские сигналы и применимые управляющие стандарты. Content TZ Agent отвечает за создание ТЗ. Анализ Customer Intent, Value Story и Visual Hypothesis — функции внутри этого контура, а не объявление трёх дополнительных реализованных агентов. Владелец процесса утверждает требуемые маркетинговые решения и ТЗ.

Content TZ Agent є `ON_REQUEST`-етапом. Завершення контура SKU, стан `READY`/`READY_WITH_LIMITATIONS`, Image Collector receipt або наявність достатніх фактів не запускають його автоматично. Координатор запускає агента лише за явним `CREATE_CONTENT_TZ`, `UPDATE_CONTENT_TZ` або `RECHECK_CONTENT_TZ` за чинним [On-Request Routing Contract](../../../03_Content_TZ/05_Routing/Content_TZ_Agent_On_Request_Contract.md). Без запиту стан маршруту — `CONTENT_TZ_NOT_REQUESTED/NO_RUN`.

Image Collector є додатковим on-demand елементом між product sources/Passport і Content TZ/Production. Content TZ Agent або Координатор може створити `MEDIA_COLLECTION_REQUEST`, але точну публічну назву моделі, SKU, scope, rights boundary і запуск підтверджує людина. Discovery починається за `public_model_name`, а не за внутрішнім SKU: обов'язкові Google Video до saturation rule, YouTube/TikTok/Facebook/Instagram, сторонні огляди, відеовідгуки та comments/replies або reason-coded status їх недоступності. Усі product-specific input copies, extracted stills/clips, comments corpus, masters, quarantine, reviews, manifest і receipt зберігаються у `<product_root>/артефакти/<YYYY-MM-DD>/image_collector/<collection_id>/`. Компонент не створює новий контент; його максимальний media-статус — `READY_FOR_HUMAN_REVIEW`. Після review він обов'язково передає `passport_media_delta.md` Координатору, який запускає Собирателя Паспорта; до receipt `PASSPORT_DELTA_APPLIED` workflow має `PASSPORT_UPDATE_PENDING`. Після внесення delta Аудитор і Верифікатор автоматично не запускаються. Package: [Image Collector Agent](../../../04_Image_Collection/00_README.md).

Для generation cycle media не проходить окремий legal або production-acceptance gate. Кожне фото чи відео оцінюється через `MEDIA_GENERATION_ASSESSMENT`: який корисний сигнал воно передає, що треба зберегти, що частково або повністю перегенерувати і для яких `expected_asset_id` воно корисне. Низька технічна якість, `RIGHTS_UNKNOWN`, watermark, сторонній логотип, текст, інша людина, інше оточення або неможливість direct reuse не блокують Prompt Agent чи AI Creator. Вони створюють `generation_mode`, `regenerate` і `required_transformations`. Product Truth має вищий пріоритет: суперечний елемент ізолюється, а exact SKU відновлюється за Паспортом. Єдиний негативний media-result — `IRRELEVANT_FOR_TARGET`, і він не блокує інші targets.

Перед Prompt Agent Content TZ формує один `TARGET_SOURCE_ROUTE_RECEIPT` v2 для кожного expected asset. Route може комбінувати product, detail, pose, motion, angle і composition references або використовувати `GENERATE_WITHOUT_MEDIA_REFERENCE`, якщо Product Truth і target description достатні. Відсутність готової сцени чи якісного source не потребує доказового відхилення послідовності reuse-рівнів. Блокерами залишаються лише недостатній Product Truth, недостатній target description, некласифікований корисний сигнал або неізольований конфлікт із Product Truth.

Власник цієї підготовки — Content TZ Agent у node `CONTENT_TZ_EXECUTION_INPUT_ROUTING`. Node запускається автоматично після freeze expected deliverables, створює assessments/routes для 100% `expected_asset_id`, фіксує `EXECUTION_INPUTS_FROZEN` і передає пакет Prompt Agent. Prompt Agent зобов'язаний видати receiver receipt `ACCEPTED` або reason-coded `REJECTED`; він не виконує source selection замість Content TZ. Rejection повертає лише affected routes у bounded Content TZ rework. Пауза для людини не потрібна, доки не змінюються Product Truth, semantic scope або frozen deliverable set.

Перед фактичним запуском Prompt Agent обов'язковий `AGENT_RUNTIME_RESOLUTION_GATE`. Він перевіряє не лише реєстрацію `N160_PROMPT_PACKAGE_COMPILATION`, а й наявність canonical package та installed skill, exact SHA-256 parity, активний runtime adapter, callable entrypoint і admissible handoff. Лише `AGENT_RESOLVED_READY` дозволяє prompt compilation. Якщо runtime discovery застарів, дозволено один `AGENT_RELOAD_REQUIRED → RELOAD_AND_RERESOLVE`; повторна невдача дає recoverable `AGENT_RUNTIME_BLOCKED` без втрати Content TZ, expected manifest або execution inputs. Некласифікований `AGENT_NOT_FOUND` не використовується.

Для кожного знайденого джерела Image Collector передає в Passport delta чотири окремі смислові поля: джерело знайдено; контент отримано `FULL | PARTIAL | NONE`; що саме збережено; якщо збір неповний — чому. Технічний reason code зберігається окремо і не замінює зрозумілого людині статусу.

Image & Video Prompt Agent получает утверждённое ТЗ и компилирует prompt-сценарий, не меняя продуктовые факты, гипотезу, claims, Visual Invariants или критерии приёмки. Его исходная спецификация называется Image/Video Prompt Agent; это тот же компонент, не ещё один агент.

Content TZ передає execution references лише explicit bindings `target_id -> ref_id -> asset_id -> artifact_path -> sha256`, їх role, visual inspection evidence, transfer scope та isolation plan. Prompt Agent переносить Content TZ через обов'язковий atomic semantic contract, а не через формальний constraint trace. Для кожного asset/shot він без узагальнення зберігає `production_instruction`, composition, exact angle, `exact_props`, кожний `show`/`avoid`, safety, talent/PPE, text contract і acceptance criteria; кожний елемент має provider-visible clause або інший виконуваний destination. Додатково агент виконує `SCENE_SEMANTIC_AGGREGATION` по всіх пов'язаних через asset/shot/scenario/value/JBTD блоках і формує `selected_composition_contract`. `SELECTED_COMPOSITION_PRESERVATION_GATE` за exact Content TZ JSON Pointer/value забороняє втрату вже обраного об'єкта, дії, просторового relation, причинного механізму або practical outcome під час узагальнення prompt. Фрази `as specified`, `see TZ`, `Passport-defined`, `all required` без розгорнутого structured input заборонені. `source_id` є provenance, а не selection key. Reference identity, role-scoped coverage та influence feasibility перевіряються окремо; Prompt Agent оглядає exact image/frame і фіксує receipt для того самого SHA-256. `PRODUCT_IDENTITY` reference не зобов'язаний містити всю сцену: aggregate coverage доводить `element_origin_map`. Observed forbidden content забороняє `DIRECT_REFERENCE` без passed mask/cutout/hybrid isolation. Multi-state/multi-panel вимоги розкладаються на sub-assets/panels. Новий ready-пакет має лише чинну schema version, `semantic_compilation_receipt.coverage_status: PASS`, порожній `unresolved_conflicts` і успішний `Test-PromptPackage.ps1 -SourceTzPath <approved-tz>`.

Для action-, process- і spatial-value target діє `TARGET_VIDEO_REFERENCE_MINING_GATE`: video path/hash або inventory row не вважаються переглядом. Content TZ і Prompt Agent фіксують exact video duration, inspected ranges, candidate segment timecodes, representative frame hashes, observed evidence roles та disposition для конкретного target/value. `COMPLETE_TARGET_RELEVANCE` недійсний без timecode coverage наявних релевантних відео. Придатний real segment має бути explicit bound або reason-coded rejected; identity-only reference за наявного action/spatial segment дає `REAL_ACTION_ASSET_AVAILABLE_BUT_UNBOUND`. AI Creator перевіряє receipt до provider call, а Visual Fidelity QA — фактичне використання selected segment у результаті.

Для value, що потребує кількох способів використання, конфігурацій, джерел або станів, діють `SCENARIO_VISUAL_PROOF_CONTRACT` і `PARENT_TARGET_COMPLETENESS_GATE`. Content TZ атомарно описує кожний required scenario від customer situation/start state через objects/connections/ordered actions до proof moment/end state та окремих photo/video representations. Prompt Agent створює child targets і `parent_target_execution_ledger`; AI Creator виконує target-specific source search, дозволений fallback, окремі outputs та deterministic assembly. Child acceptance має лише child scope. Parent залишається `PARTIAL_REQUIRED_SCENARIO_MISSING`, доки всі required scenarios і output classes не мають provenance, QA та assembly binding; пропуск дає `REWORK_REQUIRED_SCENARIO_MISSING`.

Якщо QA або Creator виявив missing evidence/source/timecode/EDL, pipeline обов'язково маршрутизує `TARGETED_LOCAL_SOURCE_RECOVERY_GATE` до остаточного blocker: повний exact-SKU `product_root`, локально збережені Image Collector collections, originals, UGC, extracted frames/clips, manifests, prior outputs і повторний target-specific video mining. За замовчуванням це локальний recovery без web/internet search; зовнішній пошук запускається лише за окремою прямою командою користувача. Знайдений unbound candidate проходить bounded Content TZ binding delta і Prompt recompile. Лише complete receipt із `COMPLETE_PRODUCT_ROOT`, порожнім `uncovered_locations` і per-unit negative results дозволяє `BLOCKED_LOCAL_SOURCE_NOT_FOUND`; інакше це `PREMATURE_SOURCE_BLOCKER`. Provider retry/pilot limits не зупиняють source recovery.

Recovery receipt обов'язково містить immutable `PRODUCT_ROOT_SNAPSHOT`, per-file path/size/SHA-256/type/disposition, окремий search result для кожної evidence unit та video inspection coverage. Після recovery snapshot перевіряється повторно; зміна root дає `PRODUCT_ROOT_CHANGED_AFTER_RECOVERY`. Кожний recovered candidate має з'явитися у відповідному `TARGET_SOURCE_ROUTE_RECEIPT`, інакше `RECOVERED_CANDIDATE_NOT_ROUTED`. Тільки `LOCAL_RECOVERY_COMPLETE_NO_CANDIDATES` дозволяє фінальний source blocker.

Для photo-bearing value діють `PHOTO_PRESENTATION_CONTRACT` і `GALLERY_SLOT_ALLOCATION_GATE`. Конвеєр окремо рахує semantic evidence units, production source images/sub-assets і фінальні marketplace deliverables. Content TZ визначає representation pattern, mandatory proof units, source count range, deliverable count, layout і slot roles; Prompt Agent компілює unit/panel bindings; AI Creator створює source outputs і deterministic assembly; QA перевіряє completeness, distinct buyer-question roles, priority order, duplication та mobile readability. Missing unit/count дає `REWORK_PHOTO_PRESENTATION_INCOMPLETE`, invalid slot plan — `REWORK_GALLERY_SLOT_ALLOCATION`.

Gallery coverage додатково керується `IMAGE_ROLE_COVERAGE_MATRIX`, `THUMBNAIL_INFORMATION_SCENT_GATE`, `STANDALONE_MEANING_GATE` та, коли застосовно, `IN_SCALE_EVIDENCE_GATE`. Amazon planning baseline `MAIN + 6 additional images + 1 video` не є pass criterion. Amazon MAIN використовує 85% channel override; кожний additional asset має distinct buyer-question role й автономний зміст, бо marketplace ordering не гарантується. Text/graphics проходять `DESCRIPTIVE_OVERLAY_DECISION`, де channel policy має пріоритет над UX benefit; preferred slot залишається submission intent до post-upload verification.

Storage/transport content керується canonical `STORAGE_TRANSPORT_EVIDENCE_CONTRACT` із `AI Design Conveyor/09_Shared_Contracts/Runtime/storage_transport_evidence/`. Content TZ вибирає лише evidence-backed mode та scope-specific states/components/mechanisms; Prompt Agent компілює one-to-one; provider payload доводить фактичні route-compatible inputs; output QA перевіряє states, retention/protection, grip/contact/move, stability, scale, floating/tangles і access readiness. `STORAGE`, `TRANSPORT` та `STORAGE_AND_TRANSPORT` мають різні proof requirements. Parked-only або person-near-product visual не проходить. Prompt Agent не доповнює задум, AI Creator не винаходить holders/cases/mounts/reels/stacking/battery docks. Missing proof дає `REWORK_STORAGE_VISUAL_INCOMPLETE`; unsupported mode — `UNSUPPORTED_STORAGE_MODE`.

Зображення й відео змінних компонентів та assembled configurations керуються canonical `CONFIGURATION_IDENTITY_EVIDENCE_CONTRACT` із `AI Design Conveyor/09_Shared_Contracts/Runtime/configuration_identity/`. Для host/component/interface/state визначаються roles, criticality, geometry/topology/orientation/control invariants та full still/video evidence matrix. Contract проходить `CONTENT_TZ → PROMPT_COMPILATION → PROVIDER_PAYLOAD → OUTPUT_QA`; наявність поля не є виконанням. Evidence hierarchy надає пріоритет exact LIVE, exact still, verified composite і лише потім bounded generation. Kit/group photo не доводить assembled geometry. Available exact LIVE/still забороняє generate-new identity-critical pixels; людина/фон/IP нейтралізуються окремо із захистом товару. Порушення дає `REAL_CONFIGURATION_ASSET_AVAILABLE_BUT_UNBOUND`, `REWORK_CONFIGURATION_IDENTITY_MISMATCH` або `CONFIGURATION_REFERENCE_COVERAGE_FALSE_PASS`.

Для product-led marketplace visuals діє наскрізний `PRODUCT_PROMINENCE_GATE`. Content TZ задає `dominance_mode`; default `PRODUCT_PRIMARY` вимагає, щоб exact SKU був найбільшим або найпомітнішим об'єктом і займав щонайменше 50% корисної композиції або мав еквівалентно доведену візуальну домінанту, target 55–70%, із читабельністю в mobile thumbnail. Prompt Agent переносить цю вимогу в provider-visible composition, а AI Creator перевіряє фактичний output. Людина й PPE мають підтримувальну роль; full-body framing лише заради PPE не може витісняти товар. Конфлікт вирішується crop/reframe, іншим ракурсом, split-panel або окремим safety/detail asset без видалення mandatory PPE. `HUMAN_PRIMARY` потребує explicit approved rationale; порушення дає `REWORK_PRODUCT_NOT_DOMINANT`.

Role-specific extension застосовує canonical `ROLE_SPECIFIC_VISUAL_DOMINANCE_CONTRACT`: `PRODUCT/COMPONENT/CONNECTION_INTERFACE/RESULT/KIT/CONTROL_DETAIL/ACTION/STORAGE_MECHANISM_PRIMARY`, `BALANCED`, `HUMAN_PRIMARY`. Чотири gates: `VISUAL_DOMINANCE_CONTENT_TZ_GATE → VISUAL_DOMINANCE_PROMPT_COMPILATION_GATE → VISUAL_DOMINANCE_PROVIDER_PAYLOAD_GATE → VISUAL_DOMINANCE_OUTPUT_QA_GATE`. Share перевіряється разом із focus, separation, hierarchy, distraction і mobile readability; загальний product shot не замінює role-specific proof.

Для video діє наскрізний `MOTION_ORIGIN_GATE`. Content TZ визначає `required_video_class: LIVE_ACTION | GENERATIVE_VIDEO`, required temporal action/state change і allowed route. Prompt Agent компілює лише `LIVE_ACTION_EDIT`, `REFERENCE_CONDITIONED_GENERATIVE_VIDEO` або явно дозволений `PURE_GENERATIVE_VIDEO`. AI Creator і Visual Fidelity QA перевіряють фактичне походження руху та class match. Slideshow, pan/zoom по still, crossfade між фото, image sequence без required action і motion graphics мають статус лише `ANIMATED_STILL/ANIMATIC_ONLY`; вони не можуть бути video pilot/deliverable. Відсутність valid route дає `VIDEO_ROUTE_BLOCKED`, підміна — `VIDEO_CLASS_SUBSTITUTION` і `NON_ADMISSIBLE_AS_VIDEO_PILOT`.

Short product-action video керується canonical `AI Design Conveyor/09_Shared_Contracts/Runtime/short_action_video/SHORT_ACTION_VIDEO_EVIDENCE_CONTRACT.md`. Route hierarchy: `L1_LIVE_ACTION_EDIT → L2_HYBRID_ACTION_VIDEO → L3_FULL_GENERATIVE_ACTION_VIDEO`; кожний наступний level потребує evidence-bounded insufficiency receipt попереднього. Чотири gates: `SHORT_ACTION_VIDEO_CONTENT_TZ_GATE → SHORT_ACTION_VIDEO_PROMPT_COMPILATION_GATE → SHORT_ACTION_VIDEO_PROVIDER_PAYLOAD_GATE → SHORT_ACTION_VIDEO_OUTPUT_QA_GATE`. Hybrid зберігає real-video backbone і генерує лише reason-coded gaps. Segment timeline, action identity, order, states і value/JBTD bindings захищені scenario ledger. Target близько 30 s, hard max 35 s; action зазвичай 3–6 s і містить start/action/result. Кожний value-bearing segment проходить sampling ≤0,5 s і temporal classification; general action потребує proof ≥70%. `CONNECTION_PROOF` має 5–7 s total, continuous action ≥5 s, proof ≥80% і non-proof ≤10%. Local `SUB_ASSET_REVIEW` завжди завершується `PARENT_ASSEMBLY_REVIEW` із previous/changed/next context. Static/decorative motion має coverage 0.

Production derivative із visible person керується canonical `AI Design Conveyor/09_Shared_Contracts/Runtime/human_element_transformation/HUMAN_ELEMENT_TRANSFORMATION_EVIDENCE_CONTRACT.md`. Чотири gates: `HUMAN_TRANSFORMATION_CONTENT_TZ_GATE → HUMAN_TRANSFORMATION_PROMPT_COMPILATION_GATE → HUMAN_TRANSFORMATION_PROVIDER_PAYLOAD_GATE → HUMAN_TRANSFORMATION_OUTPUT_QA_GATE`. Inventory і one-to-one trace охоплюють face/hair, skin/hands, tattoos, clothing, footwear, jewelry/accessories та інші distinctive cues; face-only crop не є transformation PASS. Product identity, hand grip/contact, action mechanics, connection chain і mandatory PPE залишаються protected invariants. Це production-quality control із `REGISTRY_CONTROLLED_NO_NEW_BLOCKER`, а не новий publication-rights gate.

Semantic role кожного final/value-bearing asset керується canonical `AI Design Conveyor/09_Shared_Contracts/Runtime/observable_role_classification/OBSERVABLE_ROLE_CLASSIFICATION_CONTRACT.md`. Чотири gates: `OBSERVABLE_ROLE_CONTENT_TZ_GATE → OBSERVABLE_ROLE_PROMPT_COMPILATION_GATE → OBSERVABLE_ROLE_PROVIDER_PAYLOAD_GATE → OBSERVABLE_ROLE_OUTPUT_QA_GATE`. Metadata використовуються лише для discovery/routing; coverage визначається тільки output observation із locators. Якщо фактичний content не підтверджує declared role, asset reclassify як supporting/non-proof і не закриває обов'язковий deliverable або value.

Brand/model/exact copy рекламованого товару керуються canonical `AI Design Conveyor/09_Shared_Contracts/Runtime/brand_text_integrity/BRAND_TEXT_INTEGRITY_CONTRACT.md`. Чотири gates: `BRAND_TEXT_CONTENT_TZ_GATE → BRAND_TEXT_PROMPT_COMPILATION_GATE → BRAND_TEXT_PROVIDER_PAYLOAD_GATE → BRAND_TEXT_OUTPUT_QA_GATE`. Final branding виконується approved asset composite, deterministic text render або preservation verified source pixels; generative redraw заборонений. QA виконується по final export, exact characters/case/hyphen/spacing, safe margins/clipping/readability і всіх relevant video frames. Third-party neutralization не замінює brand integrity.

Run і handoff statuses керуються canonical `AI Design Conveyor/09_Shared_Contracts/Runtime/status_layer_taxonomy/STATUS_LAYER_TAXONOMY_CONTRACT.md`. П'ять незалежних шарів — pilot checkpoint, content QA, input readiness, provider capability, publication authority — не замінюють один одного. Receipt фіксує current stage, decision requirement, primary issue/evidence і workflow action. Внутрішні переходи продовжуються без user pause, якщо contract-defined owner decision не потрібен; publication hold діє лише на publication handoff. `READY_FOR_QA` означає наявність output для перевірки, а не QA PASS.

Execution truth керується canonical `AI Design Conveyor/09_Shared_Contracts/Runtime/execution_evidence/EXECUTION_EVIDENCE_CONTRACT.md`. Для production діють три незамінні рівні: `STRUCTURALLY_VALID → EXECUTION_RECORDED → OUTPUT_VERIFIED`; field/schema/prompt presence не підвищує статус. Кожна mandatory requirement має trace до actual inputs, invocation/tool operation, current final output hash, output locator й observable QA. Для `DOCUMENT_OR_INSTRUCTION_CHANGE` достатні structural/regression checks; production rerun не запускається і production PASS не заявляється.

Выход: production package с утверждённой версией Content TZ, prompt-сценарием, привязками к исходникам, atomic semantic receipt і критериями приёмки. Передача в контур 3 требует `Prompt Package 1.0`, exact Content TZ path/SHA-256, deterministic reference manifest, visual-inspection evidence, element-origin map, influence-feasibility `PASS`, `TARGET_REFERENCE_REUSE=PASS`, `PERSON_IDENTITY_TRANSFORMATION=PASS`, повторного semantic validator `PASS`, действующего согласования и отсутствия блокирующих пробелов. Пакет без direct reference binding, формальний trace без provider-visible coverage, partial/conflicting role coverage, forbidden-content reference без isolation plan або multi-state asset без sub-assets дають `INPUT_BLOCKED` і не передаються AI Creator. Недостаток фактов возвращается в контур 1; неоднозначность ТЗ — Content TZ Agent. Создание нового контента не является обязательным исходом задачи.

<a id="mbr27-route-34-1"></a>
### Канонічна бібліотека готових промптів

Prompt layer працює за правилом `REUSE_BEFORE_GENERATE`: після затвердження Content TZ агент визначає глобальний `capability_required` у `PROMPT_CAPABILITY_ROUTE_REGISTRY.json`, використовує названі ним template IDs із `PROMPT_TEMPLATE_REGISTRY.md`, читає повний source file і required pairs, а потім застосовує template у режимі `VERBATIM`, `PARAMETERIZED` або `ADAPTED`. Image/edit/video capabilities мають статус `ACTIVE_FOR_PROMPT_COMPILATION` для всіх SKU; provider execution залишається окремим gate. Створення нового prompt дозволене лише зі статусом `NEW_TEMPLATE_REQUIRED`, явною причиною та review.

Prompt Package зберігає `prompt_template_id`, registry version, source path/section/SHA-256, filled variables, bounded differences, tool-schema snapshot, compiled prompt SHA-256, `resolved_reference_manifest` та `semantic_compilation_receipt`. Template є instruction source, а не evidence source: він не створює product fact, platform rule, model capability або authority. AI Creator приймає лише package `1.0`, повторно звіряє semantic receipt, `target_reference_discovery`, `person_identity_transformation_contract` і кожний reference із approved Content TZ через канонічний validator та виконує тільки compiled provider-visible prompt, exact bound references і authorized parameters; silent rewrite або heuristic reference substitution між Prompt Package та execution заборонені.

Для exact copy, legal text, diagrams, pixel-exact regions і deterministic composition зберігається окремий native/OCR/post-processing gate. Позитивний generation result не змінює template library автоматично; promotion у канон потребує fixtures, owner review і нової registry version.

### Контур 3 Продакшен локализация и контроль

Вхід: production package з контуру 2 і прив'язані до нього вихідні матеріали. До provider call AI Creator перевіряє Prompt Package `1.0`, package hash, approved Content TZ path/hash, active `REFERENCE_USE_POLICY` version/hash, semantic/reference/value gates, `TARGET_REFERENCE_REUSE`, `PERSON_IDENTITY_TRANSFORMATION` і `generation_finishing_boundary`. Кожний target asset виконується окремим provider call: до call створюється новий `internal_invocation_id` і sealed execution record із точними prompt/parameters/references та SHA-256; після terminal status — execution receipt і output lineage. Зовнішній job ID може мати `NOT_PROVIDED_BY_PROVIDER`, але внутрішня invocation lineage обов'язкова. Successful output status заборонений без live file/hash validation; output manifest повинен забезпечувати reverse trace до Prompt Package і Content TZ. Multi-state assets виконуються атомарно. Новий exact runtime fingerprint `adapter + provider/model + operation + media type + reference mode` проходить одноразовий `COMMISSIONING_SMOKE`: один bounded provider call і повний QA. Після його `PASS` fingerprint може отримати `PRODUCTION_ADMITTED`. У штатному `PRODUCTION_BOUNDED` batch автоматичний gate після QA кожного asset передає рівно один наступний asset без людської паузи, доки admission, frozen manifest, product identity, integrity та call/cost/retry/time limits чинні. Людина потрібна лише для configured checkpoint/sampling, low-confidence або material-defect exception, commissioning review чи release. Unknown provider outcome, identity drift, integrity failure, повторюваний дефект, вичерпаний limit або fingerprint change відкривають circuit breaker і зупиняють наступні calls. `REWORK_REQUIRED` або targeted retouch повертають лише affected asset у correction чи route change. Numbers, labels, arrows, callouts і localized text не генеруються provider: AI Creator створює clean base, Finishing додає deterministic overlays, Localization підставляє approved locale copy, а final composite проходить окремий QA. `TEXT_POLICY_CONFLICT`, `OVERLAY_PLAN_MISSING`, `OVERLAY_OWNER_AMBIGUOUS`, `LOCALIZATION_STAGE_MISSING` або `RESERVED_ZONE_MISSING` блокують provider call. Overlay-required base отримує `BASE_VISUAL_READY_FOR_FINISHING`, а не фінальний ready-status. Після приймання AI Creator / Production створює або редагує матеріал, Language Localization виконує мовну й смислову локалізацію, Content Standard Auditor перевіряє результат. Visual Fidelity QA і Compliance and Buyer-Expectation QA — функції перевірки, а не самостійні додаткові агенти. Власник процесу приймає рішення про допуск конкретного результату до публікації.

Provider execution керується окремою `provider_execution_policy`. Для `DRY_RUN` provider call заборонений. `EXECUTE + PAUSE_BEFORE_PROVIDER` автоматично доводить run до provider-ready і один раз зупиняє його зі статусом `WAITING_PROVIDER_AUTHORITY`. `EXECUTE + PREAUTHORIZED_BOUNDED` дозволяє послідовні one-asset calls без повторного ручного підтвердження, доки provider/model входять до allowlist, credentials і capability підтверджені, а call/cost/retry limits та строк authority не вичерпані. Перевищення будь-якої межі зупиняє batch. Після надання або оновлення authority run відновлюється з authority gate без повторного виконання незмінених Паспорта, Content TZ і Prompt Package. Generation authority не є publication authority; R19 залишається окремим human release gate.

Після `PROVIDER_EXECUTION_AUTHORIZED` конвеєр обов'язково виконує `Provider Adapter Resolution`: звіряє exact provider/model, media type, generation/edit operation, фактичні reference-input types, свіжий host capability snapshot, credential status, cost estimate й policy-bound `output_root`. Image generation/edit може бути прив'язаний до `OPENAI_IMAGEGEN_HOST_TOOL` через `tool://image_gen.imagegen`, якщо entrypoint доступний у поточній host session. Video generation/edit не підміняється animated still, slideshow або локальним substitute: без callable video adapter діє `VIDEO_ADAPTER_UNAVAILABLE`. `ADAPTER_RESOLVED_READY` відкриває лише Provider Admission Gate; один provider call дозволяє `COMMISSIONING_CALL_AUTHORIZED` або `PRODUCTION_ADMITTED` receipt для exact fingerprint. Timeout потребує reconciliation до retry, а unknown outcome відкриває circuit breaker.

Кожний QA defect до rework проходить `DEFECT_SCOPE_CLASSIFICATION_GATE`. Локальний composition/pose/motion/background/artifact defect блокує тільки exact asset; shared template, locale, reference, scene type, target family або production mode блокує лише залежну групу. Product Truth, Content TZ, Prompt Package, execution-input route або capability defect повертається named upstream owner. Unknown provider outcome, broken lineage/integrity, product identity або fingerprint drift, exhausted limit, duplicate-charge risk, unsafe output і repeatable material defect відкривають `BATCH_CIRCUIT_BREAKER_OPEN`. Material defect вважається repeatable після двох послідовних появ, на двох різних assets або після невдалого targeted rework. Незатронуті assets не зупиняються локальним чи груповим дефектом.

Content Output QA перевіряє кожний final asset у п'яти незалежних групах: `PRODUCT_IDENTITY`, `CONTENT_TZ_CONFORMANCE`, `REFERENCE_FIDELITY`, `TECHNICAL_QUALITY`, `USE_READINESS`. Exact SKU/model/variant, geometry, controls, kit completeness, mandatory references, prohibited claims, file integrity/lineage і mandatory scene/action є critical gates: їхній `FAIL` не компенсується середнім балом або привабливою композицією. `PASS_WITH_FINISHING_REQUIRED` дозволений лише з executable finishing action, owner і acceptance check; після finishing потрібен повторний QA. Missing evidence або low confidence дає `QA_INCONCLUSIVE`, а не `PASS`. Commissioning asset перевіряє людина; після admission human review активується лише за inconclusive/low-confidence/material result або configured sampling/checkpoint. Повний пакет отримує `CONTENT_PACKAGE_QA_PASS` лише коли всі mandatory assets мають final `PASS`, немає missing/duplicate/extra assets, покриті locales/scenarios, parent targets complete і немає open rework. Release/publication залишається окремим human decision.

На рівні повного media package Content Output QA додатково виконує `CONTENT_ORIGINALITY_AND_ADDED_VALUE_REVIEW`: зіставляє buyer questions, claims/proof, scenes і variant families та відділяє реальну нову користь від minimal alteration. Перші три повні пакети працюють у `SHADOW_VALIDATION_ONLY`; findings видимі Human Release Owner, але не блокують чинний package pass. Новий agent/node не додається.

Retry/rework policy розділяє `TECHNICAL_RETRY`, `REGENERATION`, `LOCAL_EDIT`, `UPSTREAM_REWORK` і `RECONCILIATION`. Production дозволяє максимум два provider calls на asset: initial call і одну regeneration або один technical retry після підтвердженого `FAILED_CONFIRMED | NOT_STARTED`; commissioning має retry/regeneration `0`. Unknown provider outcome завжди відкриває reconciliation і забороняє повторний call. Regeneration потребує correction delta та не може дослівно повторювати незмінні prompt/references/parameters. Local edit має максимум дві bounded operations і не може змінювати identity, geometry, controls, kit, mandatory action, pose/interaction, primary perspective або material scene. Той самий material defect після regeneration або третя provider-спроба відкривають circuit breaker. Upstream defect блокує provider call до нової валідної dependency version.

Production batch budget фіксується для exact run і runtime fingerprint до першого provider call у режимі `MONETARY_CAP | CALL_COUNT_CAP | HOST_QUOTA`. Він має три невзаємозамінні buckets: primary production, recovery reserve за замовчуванням `ceil(primary_assets × 0.25)` та untouchable buffer один call. Перед кожним новим side effect `Production Batch Budget Gate` перевіряє run/asset counters, reserve purpose, estimated cost/quota, deadline, circuit breaker і terminal або reconciled status попереднього invocation. `BUDGET_HEALTHY` дозволяє automatic continue; `BUDGET_TIGHT` — лише exact next mandatory asset без порушення buffer; `BUDGET_EXHAUSTED` встановлює `WAITING_BUDGET_DECISION`. Unknown cost використовує approved call-count cap, а unknown quota не вважається unlimited. Вже прийнятий call доводиться до terminal status або reconciliation; versioned budget update не обнуляє usage і не надає publication authority.

Після session boundary, технічного збою, human pause, budget stop або provider ambiguity run відновлюється тільки через `Recovery and Resume Gate` на `N250_TRANSITION_REENTRY_CHECKPOINT`. Gate звіряє exact checkpoint, `run_id`, SKU, graph version, Product Truth, Content TZ, Prompt Package, side-effect ledger, provider outcome, human decision і budget state. Незмінний run отримує `RESUME_FROM_CHECKPOINT`; отримане human-рішення — `RESUME_AFTER_HUMAN_DECISION`; valid budget update без обнулення usage — `RESUME_AFTER_BUDGET_UPDATE`; bounded artifact change — `TARGETED_REENTRY` до named owner. `UNKNOWN | IN_FLIGHT` provider outcome дає `WAITING_RECONCILIATION` і забороняє повторний call. Зміна SKU/Product Truth, incompatible graph або invalid checkpoint дають `FULL_RESTART_REQUIRED`. Resume не надає provider execution, spend, release чи publication authority.

Production observability працює неблокуючим sidecar і не додає обов'язкового provider polling. Значущі transitions записують compact events `NODE_STARTED | NODE_COMPLETED | NODE_BLOCKED | WAITING_EXTERNAL_RESULT | WAITING_HUMAN_DECISION | RESUME_READY | RUN_COMPLETED`; current snapshot містить node/asset, last checkpoint/progress, blocker, invocation state, budget zone, next action та owner. `ACTIVE` не потребує дії; `SLOW` створює лише diagnostic warning; `STALLED` запускає recovery validation без retry; підтверджене очікування має `WAITING_VALID`; мертвий process із `ACCEPTED | IN_FLIGHT | UNKNOWN` invocation має `ORPHANED` і потребує reconciliation. Однакові blockers дедуплікуються, а limit warnings формуються до наступного call. Observability не блокує успішний asset за наявності terminal receipt і не надає execution чи publication authority.

Перед кожним cost-bearing provider call `Execution Lease and Idempotency Gate` отримує exclusive lease для exact `run_id + asset_id + operation + runtime fingerprint + sealed record`. Lease не замінює authority, budget, adapter resolution, admission або invocation acceptance. Active lease іншого worker блокує duplicate execution; валідний terminal result повертається через idempotent route до output recording без нового call. Expired lease перевидається лише коли доведено `NOT_STARTED`; після `ACCEPTED | IN_FLIGHT | UNKNOWN` обов'язкова reconciliation. Lock не є batch-global, тому незалежні assets можуть працювати паралельно. Output спочатку має invocation-specific identity, а canonical version активується атомарно лише після terminal receipt і hash validation; existing versions не перезаписуються.

Після package QA `Run Closeout Gate` формує immutable Final Deliverables Manifest і звіряє весь expected set, фактичні files/versions/hashes, Content TZ і Prompt Package lineage, generation/finishing/localization/QA receipts, active leases, provider invocations, budget usage та checkpoint. Повний пакет отримує `PRODUCTION_COMPLETE`; дозволені named-owner exclusions — `COMPLETE_WITH_APPROVED_EXCLUSIONS`; missing/rework/blocked asset або invalid hash/lineage/QA — `PARTIAL_OUTPUT_BLOCKED`; незакритий lease, invocation або budget mismatch — `CLOSEOUT_RECONCILIATION_REQUIRED`. Валідні partial assets зберігають `QA_PASSED_ASSET`, але весь run не позначається `DONE`. Лише complete closeout відкриває human release; `PRODUCTION_COMPLETE`, `RELEASE_READY` і `PUBLISHED` є різними станами.

Нові версії graph, contracts, schemas, agent instructions і adapters автоматично застосовуються лише до нових runs. Active run продовжує exact pinned version або проходить Version Migration Gate. Migration/rollback дозволені лише з valid checkpoint, terminal/reconciled invocations, нульовими active leases, production-admitted target і перенесенням usage без обнулення. Old revision залишається immutable; affected artifacts повторно проходять лише exact invalidation scope. Critical defect pinned version дає `EMERGENCY_STOP_REQUIRED`; rollback не повторює side effects і не видаляє outputs новішої revision.

Production rollout нової версії проходить стани `DRAFT → STATIC_VALIDATED → SHADOW_VALIDATED → CANARY_READY → CANARY_ACTIVE → PRODUCTION_ADMITTED`. Canary обмежений одним exact run/SKU/fingerprint, мінімальним expected set, окремим budget і human review; automatic scale заборонений. Admission потребує schema/registry та E2E shadow `PASS`, compatibility, callable adapters, canary QA, reconciled calls/cost, нульових critical incidents і named-owner receipt. Critical incident дає `SUSPENDED`; нові runs залишаються на попередній admitted version, а active runs автоматично не мігрують.

Production incident класифікується як `ASSET_INCIDENT | BATCH_INCIDENT | PROVIDER_INCIDENT | PIPELINE_VERSION_INCIDENT | PRODUCT_TRUTH_INCIDENT | PUBLICATION_INCIDENT` із severity `SEV3 | SEV2 | SEV1`. Affected outputs не видаляються: вони отримують `QUARANTINED`, immutable file/hash/lineage/reason record і виключаються з reuse, closeout та release. Blast radius визначається за SKU, Product Truth, Content TZ, Prompt Package, runtime fingerprint, provider/model і pipeline version. `SEV3` веде до targeted rework; `SEV2` відкриває affected-scope circuit breaker; `SEV1` призупиняє version admission і запускає rollback assessment. Publication incident потребує human-owned withdrawal/correction process. Incident закривається лише після containment, reconciliation, replacement verification та independent review; виправлення створює нову version і не перезаписує quarantined output.

Retention policy класифікує `CANONICAL_SOURCE | FINAL_OUTPUT | EXECUTION_EVIDENCE | CHECKPOINT_AND_STATE | INTERMEDIATE_OUTPUT | QUARANTINED_EVIDENCE | DIAGNOSTIC_TEMP`. Product Truth sources, final outputs, provider lineage, governance receipts і evidence open incident автоматично не видаляються. Cleanup дозволений лише після valid closeout, за відсутності active leases/unresolved invocations/open incidents, із verified canonical copy та доказом, що файл не є єдиною evidence copy. Спочатку формується dry-run manifest, потім виконується recoverable move до dated archive/trash із path/hash verification. Physical deletion потребує окремої authority після retention period. Owner/legal hold має абсолютний пріоритет; однаковий SHA-256 не дозволяє автоматично об'єднувати різні SKU.

Перед execution lease production job проходить Capacity Admission Gate. Queue job містить exact run/SKU/asset/operation/fingerprint, priority `P0_INCIDENT_RECOVERY | P1_COMMISSIONING_OR_BLOCKED_RUN | P2_COMMITTED_PRODUCTION | P3_OPTIONAL_VARIANT`, deadline, estimated duration/cost, adapter/provider і budget zone. Dispatch потребує global, media-specific, provider quota, host і storage capacity; recovery використовує окремий bounded reserve. Один run виконує bounded quantum assets і повертається в queue, а aging захищає старі committed jobs від starvation. `BUDGET_TIGHT` не запускає optional variant. `ACCEPTED | IN_FLIGHT | UNKNOWN` invocation утримує slot до reconciliation. Cancellation до provider acceptance безпечний; після acceptance не означає припинення call і не повертає budget автоматично.

Перед реальним запуском Production Readiness Gate послідовно вимагає `STATIC_VALIDATION`, `E2E_SHADOW`, `FAILURE_INJECTION`, далі окремо `COMMISSIONING_SMOKE`, `BOUNDED_CANARY` і named-owner `PRODUCTION_READINESS_REVIEW`. Go/No-Go потребує нуль uncontrolled/duplicate calls, unresolved invocations, budget reconciliation gap і critical final QA defects, `100%` lineage completeness, successful recovery, closeout/publication separation та admitted rollback target. Static, shadow і failure injection не доводять provider callability. Commissioning smoke потребує окремої authority на один bounded provider call; canary дозволяється лише після commissioning `PASS`; publication не входить до тесту.

Выход: готовый материал, отчёт QA и запись версии; после отдельно разрешённой публикации или теста — фактические результаты и метрики для контура 4. Материал без допуска остаётся неопубликованным. Дефект исполнения возвращается на доработку внутри контура 3; изменение замысла или критериев — в контур 2; ошибка продуктового факта — в контур 1. Повторная проверка охватывает весь затронутый материал, включая локализацию, а не только исправленный участок.

### Контур 4 Обучение

Вход: связка «задача → гипотеза → точная версия контента → условия теста → результат и ограничения». Experiment Analyst сопоставляет гипотезу с результатом и готовит запись в Winner / Failure Library и предложения по улучшению. Владелец процесса принимает решения о последующем применении выводов.

Выход: подтверждённые выводы с границами применимости и отдельные предложения по данным SKU, ТЗ, промптам или стандартам. Новые продуктовые сведения возвращаются на проверку в контур 1, предложения по заданию — в контур 2, изменения стандартов — непосредственно владельцу управляющего слоя. Результат теста не изменяет Product Truth или Marketing Book автоматически; отрицательный или неопределённый результат также сохраняется.

### Чтение маршрута

Основная передача: проверенные данные SKU → утверждённое ТЗ и prompt-сценарий → материал с QA и решением о выпуске → результаты и выводы. Возврат исправляет причину в соответствующем контуре; повторное согласование требуется при изменении утверждённого содержания или scope.

При отсутствии основания создавать или менять материал допустимы сохранение текущего контента, исследование, повторное использование либо передача задачи другому владельцу. Решения maintain_as_is, investigate, no_action и route не являются ошибкой конвейера. Решение retire не разрешает агенту самостоятельно удалять или снимать материал с публикации.

### 2.1 Функции обязательного ядра внутри четырёх контуров

Следующая последовательность описывает функции, а не список агентов. Intake организует владелец задачи; Input Validity связывает выход контура 1 со входом контура 2. Buyer Decision Evidence, Portfolio Decision, Creative Strategy и Production Contract относятся к контуру 2; Prompt Compilation завершает его передачу. Production, QA, Release и управляемый тест относятся к контуру 3; Result and Learning — к контуру 4.

```text
0. Initiative intake / decision question / WIP capacity
        ↓
1. Input Validity
   Product Truth + Brand Entity + rights/licence + claims + channel/policy freshness
        ↓
2. Buyer Decision Evidence
   customer language + buyer job + shopping mission + query/topic evidence
        ↓
3. Portfolio Decision
   existing asset coverage + necessity + surface/slot allocation
        ↓
   STOP / ROUTE outcomes are valid
        ↓ only approved create_new / optimize / replace / reuse_adapt
4. Creative Strategy
   Value Story / Buyer Question + 3–5 causal hypotheses
        ↓
5. Pre-production Decision
   claim + channel + expectation + risk + human hypothesis approval
        ↓
6. Production Contract
   Content TZ + Visual Invariants + acceptance criteria
        ↓
7. Prompt Compilation and Production
   Prompt Agent compiles; creator/designer/photographer executes atomic deltas
        ↓
8. QA and Release
   full-asset fidelity + compliance + expectation + applicable specialist checks + human release
        ↓
9. Controlled Publication / Experiment
   measurement contract + observation window + stop/rollback conditions
        ↓
10. Result and Learning
   decision-grade outcome + limitations + reuse boundary + next-best action
```

### 2.2 Умовні модулі

| Trigger | Модуль | Повертає в ядро | Не має права робити |
|---|---|---|---|
| competitor evidence або decision-bearing AI recommendation | CI-AI-Control | verified context, challenge, computed risk або `monitor/investigate` | доводити demand/performance/Product Truth конкурентним observation |
| AI/search/GEO або неоднозначний query scope | Query Family + GEO/NPO | shopping mission, query family, phrase/surface decision | вигадувати search volume або claim |
| AI-shopping/catalog failure | Stage Diagnostic | first failed stage і correct owner | лікувати retrieval/transaction проблеми creative asset-ом |
| нове positioning/audience/value story | Consumer Reality | approved decision code або evidence request | створювати synthetic persona із macro label |
| website/A+/social/email copy з trust stakes | Humanity and Genericity | approved/rework/evidence result | вигадувати lived experience або empathy |
| creator/affiliate material connection | Creator Disclosure | approved disclosure/reuse constraints | публікувати без disclosure evidence |
| зовнішня visibility anomaly | Measurement Incident | incident classification | запускати large content/PPC change з одного tracker |
| backlink decline/disavow proposal | Backlink Incident | diagnosis/approval або observe | automatic disavow/cleanup |
| competitor/PPC live change | PPC profile | hash-bound R4/R5 control | давати AI live execution authority |

### 2.3 Маршрутизація замість зайвого дизайну

До Creative Strategy задача може завершитися як `maintain_as_is`, `consolidate`, `retire`, `investigate`, `correct_exclusion`, `route_to_listing`, `route_to_catalog`, `route_to_seo_ppc_diagnostics`, `route_to_offer_conversion`, `route_to_assortment` або `no_action`. Ці результати не є failure і не створюють автоматичний Content TZ.

Після Production Contract Prompt Agent є окремим downstream compiler. Він не змінює intent, Product Truth, claims, Visual Invariants, risk level або acceptance criteria. Для різних providers він може створювати prompt variants, але кожний variant посилається на одну approved TZ version.

## 3. Зависимости между функциями

Таблица объясняет порядок функций внутри четырёх контуров. Она не вводит самостоятельные агенты и не превращает условные проверки в обязательные для всех задач.

| Шар | Чому перед наступним | Що ламається без нього |
|---|---|---|
| Intake і capacity | визначає decision question, owner, WIP і recovery capacity | агент запускає непотрібні паралельні experiments |
| Input Validity | блокує stale truth, rights, claims, promotion і channel rules | якісний output створюється з невалідного brief |
| Buyer Decision Evidence | відділяє реальну mission від keywords/AI guesses | дизайн оптимізується під вигаданий попит |
| Portfolio Decision | перевіряє existing coverage та opportunity cost | preservation bias перетворює кожен аудит у production task |
| Creative Strategy | формує testable causal choice до генерації | варіації стилю видаються за різні гіпотези |
| Pre-production Decision | відсіює недозволений claim/channel/risk до витрат | production створює непридатний asset |
| Production Contract | робить intent, invariants і acceptance executable | prompt/creator переосмислює бізнес-рішення |
| Prompt Compilation | адаптує approved contract до model/provider без зміни змісту | довгий TZ перетворюється на непослідовні prompts |
| QA і release | перевіряє повний asset, не лише edited region | локально правильна правка приховує drift в іншому місці |
| Experiment і learning | відділяє observation від causal result | випадковий winner або AI inference стає правилом |

Умовні модулі стоять збоку від ядра: вони додають evidence або блокують/маршрутизують задачу лише тоді, коли їх trigger присутній. Відсутність trigger фіксується як `not_applicable`, а не як пропущена перевірка.
## 4. Исполнители функции и границы ответственности

Имена исполнителей сохранены по исходным документам и схеме AI Design. Состояние ниже — описание доступной документации на 10.09.2026, не разрешение эксплуатации.

| Компонент | Роль в архитектуре | Подтверждённое состояние |
|---|---|---|
| Агент-координатор AI Design | Формальная маршрутизация существующих агентов без содержательной работы | Отдельная инструкция действует для новых запусков; доступность downstream агентов проверяется поштучно |
| Агент-собиратель Паспорта SKU | Сбор источников и доказательных proposals | Рабочая инструкция существует |
| Агент-аудитор качества Паспорта SKU | Проверка пакета и критерии закрытия пробелов | Рабочая инструкция существует |
| Агент закрытия пробелов (Gap Verifier/Interviewer) Паспорта SKU | Интервью и evidence delta для повторного сбора | Документы и контракты разрабатываются; не Product Truth Verifier |
| Content TZ Agent | ТЗ и внутренние этапы анализа клиента, ценности и гипотез | Инструкция и формы существуют; статус production определяется отдельно |
| Image Collector | On-demand extraction і систематизація existing media для exact SKU | Production package існує; `READY_FOR_MEDIA_RETEST`, не `PRODUCTION_READY` |
| Image & Video Prompt Agent | Компиляция утверждённого ТЗ в prompt package | Canonical та installed package hash-identical; запуск допускається лише через `AGENT_RUNTIME_RESOLUTION_GATE` і `AGENT_RESOLVED_READY` |
| AI Creator / Production | Создание и редактирование материала | Мінімальний development runtime package створено; tool execution не активовано |
| Language Localization | Языковая и смысловая локализация | Запланированный компонент; реализация не подтверждена |
| Content Standard Auditor | Проверка материала по стандартам | Skill и стандарты существуют |
| Experiment Analyst | Анализ результата и learning proposals | Мінімальний development runtime package створено; live actions не активовані |

Product Truth Verifier и владелец процесса показаны как принимающие решения роли. Наличие ромба или подписи на схеме не является доказательством автоматизации этой роли. Если требуемый компонент недоступен, задача останавливается до назначения уполномоченного исполнителя; схема не даёт модели дополнительных полномочий.

Подразделы ниже сохраняют детальные функции и ограничения. Исторические функциональные названия не обозначают новые самостоятельные агенты.


### 4.1 Сбор исходников в контуре SKU

Відповідає за повноту джерел і `Product Reference Pack`. Може витягувати факти, позначати відсутні ракурси й створювати proposals до SKU Passport. Не може затверджувати claims, домислювати невидимі частини або визначати positioning.

### 4.2 Анализ клиента внутри Content TZ Agent

Аналізує Search Query Performance, site search, відгуки, FAQ, support signals, AI-answer observations і конкурентну видачу. Формує `Query and Topic Evidence Map`: buyer job, primary question, follow-up questions, intent, entities, geography/language/channel, source type, observed metric, confidence, required evidence, existing coverage та content implication. AI-generated query ideas є лише hypotheses для перевірки; agent не може називати їх demand або search volume.

Правило: `search signal != verified fact != approved claim`.

### 4.2A Brand Entity Stewardship

Не є окремим агентом. Функція збору вихідних матеріалів підтримує посилання на затверджену `Brand Entity Definition Card`; Content TZ Agent застосовує її під час аналізу клієнта та історії цінності. Card відрізняє company, brand, product, sub-brand і publication, фіксує current category, primary audience/function, parent-child relations, заборонені або застарілі визначення та evidence. Нове positioning або зміна category потребує owner approval.

### 4.3 История ценности внутри Content TZ Agent

Пов'язує buyer question із підтвердженим product truth та `entity_definition_id`, формує Existing Asset Portfolio Map і Portfolio Necessity Card, визначає домінуючу роль asset та незалежно аргументує `case_for_investment` і `case_against_investment`. Не створює технічний prompt, не генерує зображення і не змінює канонічну сутність та не затверджує create/replace/consolidate/retire.

### 4.4 Визуальные гипотезы внутри Content TZ Agent

Запускається лише для approved `create_new`, `optimize_existing`, `replace_existing` або `reuse_adapt` і посилається на `portfolio_decision_id`, `entity_definition_id`, `buyer_job_id` та `query_cluster_id`. Створює 3–5 причинно різних гіпотез. Кожна гіпотеза повинна мати власний механізм впливу, evidence, risk і метрику. П'ять декоративних варіантів однієї ідеї не є п'ятьма гіпотезами.

### 4.5 Claim and Channel Gate

Перевіряє claim status, marketplace/category rules, included/excluded items, packaging/label truth і допустимий тип AI-втручання.

### 4.6 Content TZ Agent

Перетворює погоджену гіпотезу на production brief. Він не змінює гіпотезу, не додає claims і не розширює комплект.

### 4.7 Image & Video Prompt Agent

Отримує лише approved Content TZ, Visual Invariants, reference bindings і acceptance criteria. Компілює model/provider-ready master prompt та atomic edit steps. Не змінює intent, hypothesis, Product Truth, claims, risk або acceptance; ambiguity повертає Content TZ Agent. Handoff contract: `WORKSTREAM_Content_TZ_Agent/99_Backlog/Image_Video_Prompt_Agent_Specification_v0.1.md`.

Development runtime separation зафіксовано в `AI Design Conveyor/10_Runtime_Registry/Planned_Runtime_Packages/image-video-prompt-agent/`; це не активує agent execution.

### 4.8 AI Creator / Production

Виконує затверджену інструкцію. Будь-яке відхилення записується як `production_deviation`, а не маскується під творчий вибір. Multi-turn edit веде checkpoint і Drift Ledger.

Development runtime separation зафіксовано в `AI Design Conveyor/10_Runtime_Registry/Planned_Runtime_Packages/ai-creator/`; credentials, spend і provider calls не активовані.

### 4.9 Visual Fidelity QA внутри Content Standard Auditor

Порівнює результат із reference pack і protected-element map: геометрія, пропорції, кількість деталей, колір, label/OCR, комплектація, accessories, material texture і побічні зміни після edit.

### 4.10 Compliance и Buyer-Expectation QA внутри Content Standard Auditor

Перевіряє channel rules, claims, safety, compatibility, ризик хибного очікування та `Entity Consistency Check`: parent brand/product/category, outdated definitions і узгодженість visible copy, metadata та structured representation. Високий CTR або AI visibility не компенсують порушення product truth чи entity truth.

### 4.11 Experiment Analyst

Веде experiment card, перевіряє дизайн тесту і фіксує результат як `positive_result`, `negative_result`, `inconclusive` або `experiment_error`.

Загальний development core зафіксовано в `AI Design Conveyor/10_Runtime_Registry/Planned_Runtime_Packages/experiment-analyst/`; channel-specific ТЗ підключаються за trigger, live зміни не виконуються.

Для Amazon MAIN агент перевіряє, чи `test_surface/outcome_type` у Experiment Card збігається з реальним evidence route і denominator. `SIMULATED_SHELF_CHOICE` не стає `LIVE_SEARCH_CTR`; результат Manage Your Experiments для відвідувачів PDP не доводить search-result CTR. Змішаний або непідтверджений outcome повертає `inconclusive` чи `experiment_error`, не winner proposal.

Якщо experiment змінює conversion, sales, offer або інший commercial outcome, Experiment Analyst також формує `CRO Economics Receipt`: однакова control/treatment exposure basis, conversion, AOV, contribution per exposed unit, incremental contribution net of implementation/operating cost, guardrail deltas, finance formula/version і окремий `economics_verdict`. Асистент не вигадує COGS, acquisition allocation або return horizon; без затвердженої фінансової моделі фіксується `ECONOMICS_NOT_OBSERVED`, а profit/incrementality claim заборонений. Статус якості експерименту та economics verdict є різними полями.

## 5. Обязательные и условные проверки

Для каждого перехода фиксируются задача и scope, применимая проверка, версия формы или источника, результат pass/stop и следующий исполнитель. Product Truth, достаточность исходников, доказательность утверждений, требования канала, качество результата и необходимое человеческое согласование нельзя пропускать там, где они требуются для соответствующего перехода. Специализированные проверки активируются по условиям карты 5.1 и соответствующих детальных разделов; раздел 2.2 служит кратким обзором. not_applicable всегда содержит причину.

Если применимая проверка требует недоступную форму, источник или внешнюю зависимость, результат не считается pass: фиксируются недостающая зависимость и ответственный за её предоставление, а передача останавливается. Само наличие ссылки на соседний проект не подтверждает доступ получателя handoff. Все последующие блокирующие ограничения сохраняются.

### 5.1 Единая карта применимых проверок

Утверждено владельцем процесса 10.09.2026. Карта связывает существующие проверки с формами и передачами; она не меняет условия допуска и не подтверждает реализацию агентов. Обозначения R01–R21 — строки маршрута, D1–D9 — источники в §5.4, а не новые формы или агенты. Доповнення маршрутизації R22–R41 погоджено 27.09.2026 (MBR27-02). Старі ID збережено; це навігація до чинних вимог, не нові агенти, форми, статуси або затвердження непогоджених положень.

Спочатку визначити scope і поточний перехід та перевірити умови всіх R01–R41. Порядок рядків не є чергою виконання: застосовні R22–R41 виконуються на вказаному в них етапі, до рішення/витрати/передачі, а не після R21. Перехід R10/R14/R16/R19/R20 не обходить застосовний пізніший рядок. Детальні вимоги всіх перелічених блоків зберігають силу. not_applicable потребує причини; невідомість не є неприменимістю. Якщо чинний детальний блок вимагає перевірки, відсутність окремого рядка карти не скасовує її: зафіксувати джерело, застосовність і результат у §9 за §5. Для непідтвердженого погодження чи недоступного джерела діє stop за §5.4 і MBR27-01.

В основной записи §9 фиксировать ID строки, основание применимости, версию формы/источника, ссылку на заполненный результат, проверяющего, дату, pass/stop/route/N/A с причиной и следующего исполнителя. Pass одной строки разрешает только следующий предусмотренный шаг, а не выпуск. Формы не дублируются в новой карточке.

| Условие и проверка | Форма и источник | Кто проверяет | Результат и следующий шаг |
|---|---|---|---|
| R01 Любая новая задача или смена scope. Область и ресурс исполнителя | D8; §15 Operating Card | Владелец задачи | Разрешённый сценарий и доступный исполнитель → R02. Неактивный тип, owner_missing или capacity_at_risk → остановка и владелец процесса; таблица не расширяет пилот. |
| R02 Вход в контур ТЗ и повторная передача. Действительность исходников | §1.1; Design Input Validity Gate; D1 §§1–2A; паспорт SKU и связанные источники | Content TZ Agent; факты принимает Product Truth Verifier | Актуальные версии фактов, бренда, прав, claims, канала/policy и референсы каждого создаваемого элемента → R03. input_invalid_or_superseded → актуализация; references_incomplete → дозапрос. Недостающий факт → SKU; неизвестные права → RIGHTS_VALIDATION_REQUIRED; нет источника → stop по §5.4. |
| R03 Любой замысел. Согласованность сущности и клиентских доказательств | D1 §§2A, 3, 3A, 4C Entity Consistency Check; §4.2A | Content TZ Agent; решение владельца | Подтверждённая сущность и обоснованный buyer job → применимые R04–R09, затем R10. decision_evidence_unverified → запрос evidence. Entity conflict → investigate, без гипотезы и production brief. |
| R04 Конкурентное evidence или AI-рекомендация для решения. CI контроль | D4 §§2–6; D1 §4C.1–4C.4 | Content TZ Agent; владелец решения | CI Scope, Signal, при соответствующем условии Coverage Receipt и AI Challenge → R10 после остальных проверок. Неподтверждённый вывод → monitor/investigate. Конкурентное наблюдение не доказывает наши claims. |
| R05 AI/search/GEO, неоднозначный query scope либо риск изменения установленного спроса. Mission и established demand | §10C; D5 Query Family Decision Card v0.1 | Content TZ Agent; владелец соответствующей диагностики | Сохранены подтверждённые product nouns и established participation → R10. established_demand_at_risk → остановка; нет факта → SKU; indexing/offer/assortment gap → профильный владелец по §10C, не автоматическое ТЗ. |
| R06 Каждая новая product phrase до ТЗ, включая локализацию. Доказательства и допустимое место | §12 NPO Phrase Evidence and Surface Allocation Card | Content TZ Agent; владелец решения | Явно разрешённая surface и доказанная применимость → R10/R11. evidence_gap → проверка фактов; assortment_signal → владелец ассортимента; reject_phrase/observe → без включения фразы. Любой phrase_* block → остановка. |
| R07 Новое positioning, audience split, value story или AI-shopping content task. Проверка потребительских предположений | Consumer Reality Gate; D6 §16 Handoff package | Content TZ Agent принимает handoff; Market Intelligence Lead и Commercial/Category Owner готовят решение | Approved decision code и behavioral evidence → R10. Нет evidence → consumer_assumption_evidence_missing; недоступен протокол или handoff → остановка по §5.4, без выдуманной persona. |
| R08 AI-shopping/catalog failure. Первый сбой покупательского пути | §17 Stage Diagnostic и catalog_intervention_id | Владелец задачи; профильный владелец по §17 | Контентный пробел → R10. RETRIEVE/TRANSACT и другие неконтентные причины → ROUTE_TO_OTHER_OWNER. Масштабирование PPC не допускается до разрешения critical blocker по §17. |
| R09 Внешняя visibility anomaly или backlink/disavow proposal. Диагностика причины | §11 External Measurement Anomaly; §13 incident record | Владелец измерений или SEO; human approver для disavow | Подтверждённая причина → соответствующий владелец, затем повторный вход R01 при контентной задаче. measurement_incident/observe/unresolved → без крупного изменения. needs_human_disavow_approval → остановка; автоматическая очистка запрещена. |
| R10 После применимых R03–R09. Нужен ли новый или изменённый контент | §10A; D1 §§4A–4B Portfolio Necessity | Content TZ Agent; утверждает владелец процесса | Approved create_new/optimize_existing/replace_existing/reuse_adapt → R11. consolidate → только с approved plan. maintain_as_is/retire/investigate/no_action → без автоматического brief; retire не разрешает удаление. Нет обоснования инвестиции → asset_investment_not_justified. |
| R11 Разрешённая контентная задача. Гипотеза, claims, канал и ожидания | D1 §§5–7; D4 §11; применимые стандарты канала | Content TZ Agent; владелец процесса | Testable hypothesis, доказанные claims, применимый канал и human decision → R12. hypothesis_not_testable, claim_or_channel_blocked либо needs_owner_approval → доработка; форма сама не означает approval. |
| R12 Перед выдачей ТЗ и контролируемым действием. Risk и Evidence | D4 §§7–11; D1 §4C.5; D9 Risk/Evidence contract v1.0 | Исполнитель локальной проверки; принимающий человек | Пройти текущий детерминированный контроль и смысловую сверку actual output/scope. pass_local_evidence_checks не разрешает выпуск. needs_owner_risk_policy или другой block → остановка. Content/PPC профили и ограничения сохраняются. |
| R13 Только связанное PPC-изменение. Отдельный профиль | D4 §9; PPC Change Control по действующему контракту | Владелец PPC; уполномоченный человек | Применимый PPC gate и согласование → отдельный разрешённый PPC-маршрут. AI не получает live execution authority. При отсутствии PPC-действия → not_applicable с причиной; обычное ТЗ не запускает PPC. |
| R14 Передача утверждённого ТЗ выбранному исполнителю. Prompt нужен только для AI-задачи | D2; D1 §§1–2 и 7; для AI дополнительно D3 и D7 | Content TZ Agent → выбранный фотограф/дизайнер или Image & Video Prompt Agent | Полный согласованный контракт для обычной съёмки → производство и R16. Для AI — доступные D3/D7 и разрешённый исполнитель → R15. production_contract_incomplete/неоднозначность → Content TZ Agent. Недоступная зависимость → stop. |
| R15 AI generation или edit. Дельта, routing модели и drift | §16; D3 §§4–7; D1 §8 Atomic AI Edit Instruction | Image & Video Prompt Agent; AI Creator / Production | Для edit заданы change_exactly, preserve_exactly, checkpoint, tolerance и rollback; весь asset проверяется после каждого хода → R16. edit_delta_incomplete/invariant_drift/model_routing_unvalidated → доработка, branch или rollback по контракту. |
| R16 Готовый материал или локализация. Полная QA | D1 §9 Visual Fidelity, Compliance and Buyer-Expectation QA Report; D2 §14 | Content Standard Auditor; Language Localization для локализации | Полный asset, текст и значения соответствуют исходникам и каналу → применимые R17/R18, затем R19. qa_blocked: ошибка исполнения → контур 3; замысла → контур 2; факта → контур 1. Повторная QA всего затронутого результата. |
| R17 AI-assisted copy с trust stakes в области §14. Humanity и Genericity | §14 First-party Input Pack, пять тестов и Release card | Исполнитель текста; named human owner при high | APPROVE → R19 после остальных QA. TARGETED_REWORK/RETURN_FOR_EVIDENCE/REJECT → доработка или запрос доказательств. Личный опыт и цитаты не выдумываются. Вне области проверки → N/A с причиной. |
| R18 Creator/affiliate material connection. Disclosure и права повторного использования | §11 Creator Disclosure record | Владелец creator-задачи; назначенный согласующий | До передачи вознаграждения — требуемая запись и условия; до выпуска — согласованные wording/rights → R19. Нет evidence или correction_required → исправление. После публикации нужны URL и подтверждение disclosure. |
| R19 До публикации или запуска теста. Финальный допуск и измеримость | D1 §10 Experiment Brief; §§5.1, 15; QA и Human Release Card основной записи §9 | Принимающий человек и владелец процесса | Сверены точные output/scope, действующее согласование, QA, monitoring/stop/rollback и capacity → только отдельно разрешённое действие. release_hold, measurement_contract_missing и другие blockers сохраняют материал неопубликованным. |
| R20 После теста или наблюдения. Результат и обучение | D1 §§11–12; §8; Experiment/Measurement Result основной записи | Experiment Analyst; решение владельца процесса | positive_result/negative_result/inconclusive/experiment_error с ограничениями → learning proposal. Для commercial outcome додається economics verdict; `CONVERSION_UP_PROFIT_DOWN`, `ECONOMICS_INCONCLUSIVE`, `ECONOMICS_NOT_OBSERVED` або `DO_NOT_SCALE` не дозволяють profit claim чи economic winner. Новые факты → SKU; изменение ТЗ → контур 2; изменение стандарта → владелец. Результат теста не меняет канон автоматически. |
| R21 Изменились Product Truth, claims, права, policy, канал или срок promotion. Повторная проверка | Design Input Validity Gate; §1.1; §9.3 | Content TZ Agent; владельцы изменённых источников | Затронутый brief → SUPERSEDED, возврат R02 до новой передачи. Истёкшая акция блокирует price/discount creative. Style-only изменение не заставляет перепроверять незатронутые стабильные факты. |
| R22 Conversational audience model використовується для audience split, positioning, value story, offer або channel creative. До включення гіпотези в ТЗ | [Audience Segment Pretest Handoff for Content TZ](<#mbr27-route-22>); Evidence Card, Divergence Matrix, Validation Route | Content TZ Agent; owner validation route | AUDIENCE_SIGNAL_MISSING → дозапит; до real VoC — SEGMENT_HYPOTHESIS_ONLY. Погоджений маршрут валідації → R10/R11, не product fact чи winner. |
| R23 Рішення/експеримент спирається на GA4 або іншу event-based analytics. До implementation та використання метрики | [17A. GA4 Semantic Measurement Gate](<#mbr27-route-23>); ga4_semantic_measurement_contract | Analytics owner + Implementation owner; Business decision owner | Повний semantic contract → implementation/validation R24; MEASUREMENT_NOT_READY або EXPERIMENT_BLOCKED → виправлення. TRUSTED_FOR_DECISION лише разом із receipt §18. |
| R24 Рішення щодо content, listing, experiment чи іншої дії використовує conversion event. До decision/test та після зміни tracking | [18. Conversion Event Lineage and Trust Gate](<#mbr27-route-24>); commerce_conversion_event_contract; event_lineage_receipt | Implementation owner; Analytics owner; Business owner | Лише TRUSTED_FOR_DECISION дозволяє decision-use → застосовні R25/R26/R19/R20. Нижчий стан або UNRESOLVED → перевірка сигналу, без SCALE/STOP, перерозподілу бюджету чи causal claim. |
| R25 Purchase із різних каналів/систем використовується для порівняння ROAS, channel/audience quality, creative learning або optimization | [Purchase Signal Parity Gate](<#mbr27-route-25>); purchase_signal_parity_receipt | Названий owner receipt; Analytics і Business owner відповідного рішення | PARITY_CONFIRMED або COMPARABLE_AFTER_NORMALIZATION → порівняння в погодженій області. NONCOMPARABLE/UNKNOWN блокують SCALE/STOP, budget shift, channel-ranking і causal learning. |
| R26 Незалежні умови: (a) рішення використовує послідовність подій → §19; (b) зміна creative/PDP/landing/checkout message потребує intent-transition brief → §30; (c) aggregate KPI використовується для рішення і predefined segment може змінити висновок → §32. Виконати лише застосовні підблоки до відповідного висновку/дії | [19. Behavior Sequence Analysis Gate](<#mbr27-route-26>); [30. Intent Transition Funnel Brief](<#mbr27-route-26-1>); [32. Segment Contribution and Mix-Shift Extension](<#mbr27-route-26-2>); commerce_behavior_sequence_contract; behavior_analysis_receipt; застосовні intent/segment receipts | Analytics owner; Experiment owner; Business owner | Для §19 після R24: відтворювана sequence; [стан→verdict](<#mbr27-state-verdict>) за MBR27-03, з TEST для погодженої гіпотези без causal claim/live-дозволу. Для §30: intent transition, eligible denominator і friction hypothesis. Для §32: segment support, mix/within effect і reconciliation; sequence чи reversal не є умовою активації §32. Block/route за застосовним блоком → перевірка/відповідний owner; описовий pattern не є причинністю, thin slice — HYPOTHESIS_ONLY. |
| R27 Title/cover визначають вибір відео до перегляду. Планування перед production, перевірка до release та learning | [20. Video Packaging Promise and Learning Gate](<#mbr27-route-27>); video_packaging_promise_contract; hypotheses; title-test receipt | Content TZ Agent; Experiment Analyst; Content/Business owner | PROMISE_MISMATCH та інші blockers → REVISE_PACKAGE/STOP; CONTENT_ALIGNED → погоджений production/test через R14/R19. CTR не перекриває невиконану promise; SOP лише після повторної перевірки. |
| R28 Product discovery asset може містити identity, feature, benefit, suitability, comparison, use case чи constraint. Перед concept/production і release | [21. SKU Truth-Bound Packaging-Led Concept Sprint](<#mbr27-route-28>); content_product_truth_snapshot; content_claim_binding; proof plan | Passport/Verifier; Content TZ Agent; Production owner; Content/Business owner | Missing/stale fact, variant або rights conflict → відповідний owner, без unsupported promise. TRUTH_BOUND і визначений proof acquisition plan → R14; отриманий proof та revalidation перевіряються перед відповідним release/test; PASSPORT_NOT_APPLICABLE лише для non-product editorial без SKU з rationale. |
| R29 Дві або більше функції реально працюють паралельно зі спільним decision object. Перед fan-out і після fan-in | [26. Parallel Branch і Fan-In Gate для AI Design](<#mbr27-route-29>); Parallel Branch contract; typed findings; reducer/coordination receipt | Content TZ owner; Content Standard Auditor; human release owner | Незалежність, baseline benefit і review capacity → fan-out; після merge повна QA R16. Missing branch/conflict/HOLD не перекриваються OK. PARALLEL_NOT_REQUIRED → linear route. |
| R30 AI generation/істотне product edit, окремо платний provider call, масштабування surfaces/SKU/markets або передача в real test/publication. До витрат і виконання | [26. Creative Production Run Contract](<#mbr27-route-30>); creative_production_run; `provider_execution_policy`; Provider Runtime Adapter Registry; adapter-resolution receipt; reference lock; approved brief; lineage/repair receipts | Content TZ Agent; Prompt Agent; AI Creator; Content Standard Auditor; Process owner | `DRY_RUN` → без provider call. `PAUSE_BEFORE_PROVIDER` без bounded authority → `WAITING_PROVIDER_AUTHORITY`. `PREAUTHORIZED_BOUNDED` і `ADAPTER_RESOLVED_READY` у межах provider/model, credentials, capability, call/cost/retry limits → one-asset execution та QA R16. Missing image entrypoint або callable video adapter → exact blocker, без substitute. Publication окремо через R19. |
| R31 Compaction/checkpoint, agent handoff, fan-out/fan-in, assets/credentials, external editor/MCP або збій file channel. До передачі й приймання | [27. AI Design Handoff Integrity and Authorized Asset Transfer Gate](<#mbr27-route-31>); ai_design_handoff_integrity; approved brief/version; authority та transfer channel | Відправник і отримувач; Content Standard Auditor; Process owner | Version/rights/authority/trajectory узгоджені → поточний дозволений перехід. HANDOFF_TAMPERED, UNAUTHORIZED_EGRESS, CREDENTIAL_MISUSE, BLOCKED_APPROVED_CHANNEL, MISALIGNMENT_HOLD → stop/owner recovery, без обходу через сторонній upload. |
| R32 AI output повторно використовується в research, prompt examples, memory, templates, train/eval corpus або наступній генерації. До reuse/promotion | [28. Synthetic Feedback Loop and Corpus Provenance Gate](<#mbr27-route-32>); synthetic_asset_lineage; parent/source bindings; intended use; real anchor | Названий owner lineage; Product Truth Verifier і Content Standard Auditor у своїх межах | ELIGIBLE/RESTRICTED лише для дозволеного intended use; REVALIDATE → перевірка. Будь-який blocker gate забороняє promotion/test/release; synthetic panel не створює product fact чи TEST_WIN. |
| R33 Пауза, blocker, зміна owner/етапу, context reset або дороге перемикання режиму. До відновлення/передачі | [29. AI Design Transition and Re-entry Receipt](<#mbr27-route-33>); Transition receipt; artifact_pointer; current_state; restart_condition | Відправник; отримувач звіряє стан до початку | TRANSITION_READY/HANDOFF_ACCEPTED → наступний дозволений етап. REENTRY_CONTEXT_MISSING → stop; MODE_SWITCH_AVOIDABLE не блокує автоматично. Оборотний мікрокрок одного етапу не потребує receipt. |
| R34 Незалежні умови: (a) production run використовує reusable skill/provider adapter/tool instruction → dependency receipt; (b) Prompt layer компілює prompt після approved Content TZ → REUSE_BEFORE_GENERATE. Застосувати лише відповідний підблок | [31. Reusable Skill Dependency Receipt](<#mbr27-route-34>); [Канонічна бібліотека готових промптів](<#mbr27-route-34-1>); skill dependency receipt; Prompt Template Registry і required pairs | Названий owner dependency; Prompt Agent; reviewer/owner шаблону | Лише ACTIVE перевірена версія → run manifest. STALE/QUARANTINED → revalidation, без fallback до памʼяті. REUSE_BEFORE_GENERATE; NEW_TEMPLATE_REQUIRED потребує причини й review, не самовільної заміни. |
| R35 Brief/PDP/A+/creative або price framing пояснює premium, порівняння чи економічну цінність | [Value-to-Price Brief](<#mbr27-route-35>); Value-to-Price Brief; approved fact/evidence refs; reference set | Content TZ Agent; authorized price/offer owner; release owner | Підтверджені capability/reference set і claim → R11/R19. False comparison/unsupported saving → stop; WTP залишається гіпотезою. Ціну агент не змінює. |
| R36 Carousel/slideshow або editorial batch. До render і native publication package | [Carousel Brief & Editorial Batch Contract](<#mbr27-route-36>); Carousel Experiment Card; carousel_payload_map; batch plan; native publish package | Content TZ Agent; Carousel Brief Compiler; Prompt Agent; Content Auditor; human owner | Distinct payload відповідає promised count; claims/rights і batch constraints → QA/R19. BLOCKER → rework; render не є APPROVED чи PUBLISHED; native context перевіряє людина. |
| R37 TikTok comments пропонуються як підстава ТЗ/FAQ/reply video/script/SKU-angle test. До включення в brief | [Comment-Cluster-to-Brief Gate](<#mbr27-route-37>); CLUSTERED packet; provenance; rights/privacy/moderation; Passport refs | Comment Intelligence owner; Content TZ Agent; Content Auditor; human/support/product owner | READY_FOR_TZ → R10/R11; HOLD/REJECT або ROUTE_TO_SUPPORT/ROUTE_TO_PRODUCT → відповідний маршрут. Ізольований comment, невідомі права чи safety issue не стають creative input. |
| R38 Створення/зміна quantity variation, multipack offer або listing з buyer-facing обіцянкою кількості. До listing/content change та release | [Amazon Total Product Quantity Listing Parity Gate](<#mbr27-route-38>); quantity_listing_parity_receipt; exact SKU quantity facts; surface/packaging evidence | Content TZ Agent; Listing owner; SKU Passport verifier для фактів | READY_FOR_LISTING_REVIEW → звичайний listing/release review, не автоматична публікація. FACT_REVIEW_REQUIRED → verifier; ELIGIBILITY_CHECK_REQUIRED → current evidence; LISTING_PARITY_BLOCKED → stop. Зміна facts → REVALIDATION_REQUIRED. |
| R39 Seasonal/promotion ТЗ спирається на гіпотезу, що покупець уже обрав товар і чекає умови дії | [Delayed Purchase Intent Release Card](<#mbr27-route-39>); Delayed Purchase Intent Release Card; pre-period evidence; bounded test | Content TZ Agent; Experiment Analyst; SKU owner; Finance/Commercial owner; human release owner | EVIDENCE_INSUFFICIENT/CONFOUNDED → дозбір/перепланування. READY_FOR_BOUNDED_TEST лише за критеріями gate → R19. Discount/offer погоджує Finance/Commercial, не агент. |
| R40 Контент призначено для conversational/search/related-question/PDP Q&A або іншого agent-facing retrieval | [Shopping-Agent Surface Test](<#mbr27-route-40>); Linked surface test card; representative set; Product Truth; calibrated rubric | Content TZ Agent; Retrieval/Search, SKU, Runtime/Agent owners; human release owner | BOUNDED_SURFACE_READY лише за повним gate → R19; retrieval/product/runtime defect → профільний owner, не заміна copy. Статичний listing без такого handoff — NOT_APPLICABLE. |
| R41 Змістовне optimize/replace existing → Brand Message Fit; brief/media execution → відповідний buyer-proof, fidelity/reference, channel і processing контроль; demo video → usage/continuity | [Застосування Brand Message Fit та контрактів медіа](<#mbr27-route-41>); Чинні Messaging, Briefs, Design Reality та Value Story standards за посиланнями цього блоку | Content TZ Agent/маркетолог; Prompt Agent; виконавець; Content Standard Auditor; release owner | Діагностика → Portfolio Necessity R10, не автоматичний rewrite. Evidence/fidelity/platform blocker → відповідний owner; QA не замінює human release. Технічний resize не активує повний Brand Message Fit чи video checks без їхніх умов. |

### 5.2 Условные проверки

Умовні перевірки активуються лише за умовами карти §5.1 (R01–R41) та відповідних детальних блоків, включно з §§17A–32 і ненумерованими доповненнями; §2.2 є коротким оглядом, не вичерпним переліком. Для кожного застосовного блока записати pass або його точний block/route status; для незастосовного — not_applicable з причиною. Наявність форми сама по собі не активує перевірку. Для deterministic resize/export без content change великий Creative Production Run record не потрібний: source asset/output specs та застосовні technical, fidelity/channel, handoff і release controls зберігаються. Співвідношення стану доказів і verdict для §19 визначає погоджене уточнення MBR27-03: TEST на рівні гіпотези не є causal proof або дозволом на live-запуск.

Examples: `entity_definition_blocked`, `query_evidence_unverified`, `established_demand_at_risk`, `consumer_assumption_evidence_missing`, `copy_genericity_failed`, `measurement_incident`, `needs_human_disavow_approval`, `RIGHTS_VALIDATION_REQUIRED`, `model_routing_unvalidated`, `marketing_loop_broken`.

### 5.3 Приоритет проверок

Earlier truth/scope gates cannot be overridden by later visual quality or performance. `Human approval` never repairs missing evidence. A stop/route result ends automatic production. `Limited confidence`, `draft`, `conditional` or `observation_window_open` cannot be converted to release solely because an asset looks strong or CTR increased.
### 5.4 Источники и доступ получателя

Корни путей: M — исходная папка «Маркетинг Бук»; H — корень полученного PRODUCTION_HANDOFF; D — общая папка DM AMAZON. Пути ниже отсчитываются от соответствующего корня. Для каждого фактически использованного документа фиксировать его ID, версию или редакцию/дату, SHA-256, область, статус, дату проверки и владельца. Дата и hash идентифицируют редакцию, но не доказывают её утверждение. Наличие шаблона не заменяет заполненный и проверенный результат.

D1 — AI Design Hypothesis and Reference Forms; working, редакция 09.09.2026.

`M/WORKSTREAM_Content_TZ_Agent/03_Templates/AI_Design_Hypothesis_and_Reference_Forms.md`

`H/04_Content_TZ_Agent/03_Templates/AI_Design_Hypothesis_and_Reference_Forms.md`

D2 — Product Photo/Video TZ Template; действующий шаблон разрешённого пилота, конкретную редакцию сверять при передаче.

`M/WORKSTREAM_Content_TZ_Agent/03_Templates/Product_Photo_Video_TZ_Template.md`

`H/04_Content_TZ_Agent/03_Templates/Product_Photo_Video_TZ_Template.md`

D3 — AI Creator TZ and Prompt-Agent Handoff Template v0.2; рабочий контракт, не самостоятельный активный тип ТЗ.

`M/WORKSTREAM_Content_TZ_Agent/03_Templates/AI_Creator_TZ_Template.md`

D4 — CI-AI-Control; owner-approved v1.2, 10.09.2026; numeric risk policy pending.

`M/DNIPRO-M Marketing Book/05_Governance_and_Quality/02_CI_AI_Control.md`

`H/01_Marketing_Book/DNIPRO-M Marketing Book/05_Governance_and_Quality/02_CI_AI_Control.md`

D5 — Query Family Decision Card v0.1; working template, 10.09.2026; внешний источник.

`D/QPO/Query_Family_Decision_Card_v0.1.md`

D6 — Consumer Reality Assumption and Growth Segment Protocol v0.1; active, LAI-095 от 10.09.2026; внешний источник.

`D/AI Design Conveyor/08_Learning/Marketplace_Market_Intelligence_Research/references/21_Consumer_Reality_Assumption_and_Growth_Segment_Protocol_v0.1.md`

D7 — Image/Video Prompt Agent Specification v0.1; approved_for_backlog. Мінімальний development runtime package існує, але агент залишається `NOT_RUNTIME_READY`.

`M/WORKSTREAM_Content_TZ_Agent/99_Backlog/Image_Video_Prompt_Agent_Specification_v0.1.md`

D8 — Authoritative sources; раздел Readiness tiers для разрешённой области.

`H/AUTHORITATIVE_SOURCES.md`

D9 — Risk and Evidence Acceptance Contract v1.0, 10.09.2026; локальная проверка, не разрешение внешнего действия.

`M/WORKSTREAM_Content_TZ_Agent/07_QA_Tools/RISK_EVIDENCE_CONTRACT.md`

`H/04_Content_TZ_Agent/07_QA_Tools/RISK_EVIDENCE_CONTRACT.md`

D1, D2, D4, D8 и D9 входят в действующий PRODUCTION_HANDOFF. D3 v0.2 и D7 доступны только в рабочем исходнике M; в H файл AI_Creator_TZ_Template.md остаётся backlog placeholder, а спецификации D7 нет. Placeholder нельзя подставить вместо D3 v0.2. Для AI-маршрута получатель запрашивает доступ у владельца Content TZ; до доступа и назначения разрешённого исполнителя передача остановлена. Эти документы не расширяют активный Product Photo/Video pilot и не делают самостоятельный AI Creator сценарий действующим. Обычная фото/видеосъёмка использует D2 и не требует Prompt Agent. Для требований без отдельного шаблона использовать запись с полями соответствующего раздела стандарта внутри основной записи §9, а не объявлять несуществующий файл готовой формой.

D5 и D6 — внешние зависимости, они не входят в автономный комплект PRODUCTION_HANDOFF. В общей рабочей среде открыть указанный оригинал. Если получатель располагает только handoff, Content TZ Agent фиксирует требуемый источник и scope, а владелец задачи запрашивает доступ к утверждённой редакции или разрешённую адресную передачу документа и соответствующего заполненного результата у владельца источника. Для D5 владелец заполненной Query Family Decision Card указывается в самой карточке; для D6 — Market Intelligence Lead и Commercial/Category Owner. Соседние проекты целиком не копируются.

До продолжения получатель должен фактически открыть источник, сверить версию и hash с передачей и подтвердить доступ к связанным evidence. Недоступный файл, неподтверждённая версия или отсутствующий обязательный handoff дают stop с причиной «недоступная обязательная зависимость», путём/ID и ответственным за предоставление. Это запись об остановке, не новый код программного валидатора. После получения данных повторяется остановленная проверка; автоматического pass нет. Персональный путь отправителя не считается доказательством доступа получателя.

## 6. Правила формування гіпотез

Кожна гіпотеза змінює один домінуючий фактор або чітко описаний пакет пов'язаних змін.

Допустимі механізми: product fill, visibility of functional geometry, scale comprehension, kit clarity, SERP contrast, buyer-question answerability, proof visibility, risk reduction.

Недопустимі формулювання: «зробити сучасніше», «зробити дорожче» без observable criteria, «додати популярний keyword на упаковку», «показати перевагу» без proof, «зробити як у конкурента».

## 7. Метрики

Конвеєр оптимізує не максимальний CTR, а `qualified click value`.

Мінімум: impressions, CTR, PDP conversion, add-to-cart, units ordered, revenue per impression, return rate, `not as described`, claim/compatibility/kit complaints, rejection/suppression events і sample sufficiency.

Для тесту Amazon MAIN додатково обов'язковий measurement receipt: `test_surface/outcome_type`, baseline/challenger asset version, ASIN/marketplace, query і search-grid context (якщо тест стосується пошуку), cohort/window, джерело спостереження, denominator і sample/power/decision rule. Simulated shelf choice є pretest signal; live CTR потребує impressions і clicks; PDP conversion/sales — відвідувачів сторінки та замовлення/продажі. Сильний результат на одному surface не переноситься на інший без окремого вимірювання. Джерело розрізнення: кейс БЗ «Тест головного зображення Amazon має розділяти shelf preference, SERP CTR і PDP conversion».

Для experiment із commercial claim обов'язковий `CRO Economics Receipt`: experiment/result ID, control/treatment exposure, conversion, AOV, revenue, COGS, variable fulfillment/payment costs, attributable variable acquisition costs, contribution per order, contribution per exposed unit, incremental implementation/operating cost, guardrail deltas, uncertainty, фінансова формула/version, data cutoff, owner і reuse boundary. Точний склад contribution затверджує finance owner. Вердикти: `ECONOMIC_WIN`, `CONVERSION_UP_PROFIT_DOWN`, `ECONOMICS_INCONCLUSIVE`, `ECONOMICS_NOT_OBSERVED`, `DO_NOT_SCALE`. `ECONOMIC_WIN` потребує positive incremental contribution у межах decision rule та прийнятних guardrails; вищий CTR/CVR сам по собі не дає цього статусу. Basis: `knowledge_base_decision_analytics/functions/web_behavior_sequence_analysis.md`, кейс `CRO Diagnosis-to-Profit Contract`.

Для AI visibility окремо вимірюються accuracy of brand definition, selected category, brand/product distinction, cited sources, sentiment, cross-system consistency і repeat-run stability. Visibility count без sentiment та answer correctness не є success metric.

Winner не переводиться у стандарт, якщо compliance або product-truth check не пройдені. Commercial winner також не переходить у стандарт без `ECONOMIC_WIN`; `ECONOMICS_NOT_OBSERVED` дозволяє лише bounded creative learning без profit claim.

## 8. Learning loop

У бібліотеку зберігається зв'язка `context -> entity definition -> query cluster -> hypothesis -> evidence -> controlled change -> experiment result -> economics verdict -> confidence -> limitation -> reuse boundary`, а не лише asset. Негативні, inconclusive та `CONVERSION_UP_PROFIT_DOWN` результати теж зберігаються. Окремо фіксуються entity conflicts, outdated external descriptions, citation sources, sentiment і розбіжності між AI systems; AI-answer observation не є доказом загального попиту.

Нова практика переходить у Marketing Book через Amara Gate. Один успішний тест не створює універсального правила.

## 9. Artifact architecture

### 9.1 Core decision record

The canonical chain links, rather than copies, these artifacts:

1. Initiative / Operating Card;
2. current Input Validity bindings;
3. Product Reference Pack and Protected Element Map;
4. Brand Entity reference;
5. Buyer Decision Evidence: Customer Intent + buyer job/mission + query/topic reference;
6. Existing Asset Portfolio Map and Portfolio Necessity Card;
7. Primary Visual Hypothesis Pack;
8. Claim and Channel Pre-check plus human hypothesis decision;
9. Content TZ with Visual Invariants and acceptance criteria;
10. Prompt Agent handoff/master prompt/atomic edit plan;
11. Production output, checkpoint and deviation/drift record;
12. QA and Human Release Card;
13. Experiment/Measurement Result and Learning Proposal.

### 9.2 Conditional artifacts

Attach only when triggered: CI Scope/Competitive Signal/Coverage/AI Challenge; Query Family or NPO Surface card; Consumer Reality handoff; AI Shopping Stage/Catalog Intervention; Humanity Release; Creator Disclosure; Measurement or Backlink Incident; PPC Change Control. Their IDs and versions are referenced from the core record; content is not duplicated.

### 9.3 Single source and status rule

Every artifact has `id`, `version`, owner, status, input references and supersession rule. Downstream artifacts cannot silently restate upstream truth. A changed Product Truth, Brand, rights, claim, policy or approved hypothesis invalidates dependent TZ/prompt/output according to declared recheck triggers.

Master forms: `WORKSTREAM_Content_TZ_Agent/03_Templates/AI_Design_Hypothesis_and_Reference_Forms.md`. Prompt handoff: `WORKSTREAM_Content_TZ_Agent/99_Backlog/Image_Video_Prompt_Agent_Specification_v0.1.md`. CI governance: `DNIPRO-M Marketing Book/05_Governance_and_Quality/02_CI_AI_Control.md`.
## 10. Незмінний принцип

> AI створює або редагує asset лише після того, як product truth, buyer problem, hypothesis і channel constraints стали явними. Результат є кандидатом на тест, а не winner, доки не пройдені QA та experiment gates.
## 10A. Portfolio necessity and preservation-bias control

AI must not treat an incoming asset, URL, request or improvement opportunity as proof that production investment is justified. Before Hypothesis Pack, compare the requested role with the relevant SKU/line/channel portfolio and record both the strongest case for investment and the strongest case against it.

Allowed decisions: `create_new`, `optimize_existing`, `replace_existing`, `reuse_adapt`, `consolidate`, `maintain_as_is`, `retire`, `investigate`.

Only `create_new`, `optimize_existing`, `replace_existing` and `reuse_adapt` may proceed directly to hypothesis development after owner approval. `consolidate` requires an approved consolidation plan. `maintain_as_is`, `retire` and `investigate` stop automatic brief generation. No agent may delete or unpublish an asset automatically.

The decision must consider verified coverage gap, role overlap, claim inconsistency risk, scarce channel slots, production/QA/localization/maintenance cost, experiment-traffic fragmentation, counterfactual loss and the higher-value work displaced by this investment. A long list of possible improvements is not evidence of strategic priority.

## 10B. Competitive intelligence and AI recommendation control

Canonical control: `../05_Governance_and_Quality/02_CI_AI_Control.md`.

When competitor evidence or a decision-bearing AI recommendation is used, the order is Product Truth -> Brand Entity Definition -> CI Scope -> Competitive Signal -> Query Evidence -> Existing Asset Coverage -> Portfolio Necessity -> AI Recommendation Challenge. Competitive evidence may confirm only competitor behavior; it cannot alone prove buyer demand, performance or our Product Truth.

Four artifacts are used: CI Scope Card, Competitive Signal Record with computed review status, per-input/transformation Coverage Receipt when triggered, and AI Recommendation Challenge for decision-bearing/R3-R5 actions. Risk is computed, not self-selected. R3 is sandbox/dry-run; any live publication or PPC change is R4 or higher. Content and PPC use separate profiles; AI has no live PPC execution authority.

<!-- QPO_QUERY_FAMILY_DECISION_2026_09_10_START -->
## 10C. Shopping Mission, Query Family та established-demand control

Після `Query and Topic Evidence Map` і перед `Existing Asset Portfolio and Buyer-Job Map` застосовуються:

`Shopping Mission and Query Family Map -> Participation–Suitability Separation -> Established Demand Protection Gate`.

Канонічний operator artifact: `C:\Users\ystep\Documents\DM AMAZON\QPO\Query_Family_Decision_Card_v0.1.md`.

### Established Demand Protection Gate

Pass condition:

- визначені query families, які вже приносять покупки;
- ключові product nouns і підтверджені характеристики збережені;
- expansion не будується на unsupported claim;
- базові та adjacent query families мають окремі метрики;
- ризик втрати established participation оцінений;
- correct exclusion не трактується як visibility failure.

Block status: `established_demand_at_risk`.

### Routing

| Сигнал | Власник наступної дії |
|---|---|
| SKU відповідає вимозі, але PDP не містить доказу | Listing/content |
| Доказ є, але ASIN не індексується або не з'являється | SEO/PPC diagnostics |
| ASIN з'являється, але offer response слабкий | Price/reviews/creative/conversion review |
| ASIN з'являється, але не відповідає повній місії | Correct exclusion; не масштабувати |
| Критичного Product Truth немає | Verification request |
| Поточний асортимент не задовольняє вимогу | Assortment hypothesis |

### Метрики

- Participation: impressions/appearance, rank/placement, clicks, cart adds, purchases, brand/ASIN share.
- Suitability: correct inclusion/exclusion, conditional accuracy, unresolved handling, explanation accuracy, context carryover.
- Commercial outcome: conversion, revenue per impression, margin, return rate, not-as-described, established-query purchases та incremental contribution.

Appearance, factual description і suitability не можна об'єднувати в одну success metric.
<!-- QPO_QUERY_FAMILY_DECISION_2026_09_10_END -->

<!-- LAI084_MEASUREMENT_CREATOR_GATES_START -->
## 11. External Measurement Anomaly and Creator Disclosure Gates

### External Measurement Anomaly Gate

Різкий рух одного SEO/rank tracker не дозволяє автоматично змінювати listing, content або PPC. До action перевірити другий незалежний інструмент, manual SERP, analytics/traffic/conversion, відомі зміни URL/redirect/SERP layout та збіг із власними content/indexing changes.

Decision states:
- `measurement_incident`: один інструмент аномальний, business metrics stable;
- `probable_visibility_change`: рух підтверджують кілька джерел;
- `confirmed_commercial_impact`: visibility і business result змінилися разом;
- `observe`: доказів недостатньо, large change заборонена.

#### Bounded Joint Drift Escalation for PPC/commerce models

Цей escalation застосовується лише коли рішення спирається на versioned predictive/decision model і доступні достатні numeric reference/current batches зі stable feature schema, наприклад для зв’язків `spend × impressions × clicks × orders × CVR × contribution`. Він не застосовується до одного tracker, короткого KPI spike/drop, visibility incident без feature batch або звичайного creative experiment.

Після зелених per-feature checks, але погіршення model/business quality, measurement owner може створити `joint_drift_receipt`: model/feature-pipeline versions, windows, marketplace/account/time scope, schema hash, leakage review, univariate status, sample adequacy, calibrated null/threshold, out-of-sample separability AUC, uncertainty, missingness changes, top separating features, known campaign/pricing/promo/catalog interventions і owner decision.

Allowed verdicts: `NO_JOINT_DRIFT_SIGNAL | REVIEW_JOINT_DRIFT | SMALL_BATCH_LOW_CONFIDENCE | SCHEMA_MISMATCH | DATA_QUALITY_INCIDENT`.

Правила межі:

- `AUC=0.65` або інший threshold не переноситься як universal default; калібрувати на stable historical windows і false-alert cost;
- top separating features не є causal explanation;
- drift signal не дозволяє `SCALE`, `STOP`, budget reallocation, bid change, content rewrite або automatic retraining;
- до будь-якого PPC action зберігаються R12, R13, event-lineage, human approval і чинний spend authority;
- якщо stable schema, sufficient batch, reference window або predictive decision object відсутні, verdict — `NOT_APPLICABLE`, а діє звичайний External Measurement Anomaly Gate.

### Creator Disclosure Gate

До передачі money, product, discount або affiliate reward записати creator/channel, jurisdictions, material connection (`paid | gifted | discounted | affiliate | employee | other`), disclosure requirement і approved wording, prohibited/unverified claims, reuse rights, contract flag, publication URL, screenshot/evidence, verification date і status.

Статуси: `draft | approved | published | correction_required | closed`. Публікація без disclosure evidence не є завершеною кампанією.

Метрики: cross-source anomaly verification rate; prevented unsupported PPC/content changes; creator publications with disclosure evidence; post-publication corrections; claims supported by Product Truth.
<!-- LAI084_MEASUREMENT_CREATOR_GATES_END -->

<!-- NPO_SURFACE_ALLOCATION_GATE_2026_09_10_START -->
## 12. NPO Phrase Evidence and Surface Allocation Gate

До Content TZ кожна нова product phrase проходить `NPO Phrase Evidence and Surface Allocation Card`: phrase/head noun/parent family, class, marketplace/language, query evidence, linked Product Truth fact versions, applicability, relation boundary, proof requirement, allowed surface, prohibited inference, owner і status.

Surface roles:
- title/product name — identity і природна core phrase;
- attributes — structured verified facts;
- bullets/A+ — context, use case, constraint, benefit та evidence chain;
- images — visual proof без підміни searchable/native text;
- Q&A — clarification, not canonical fact creation;
- ads — discovery/testing language; winning query не підтверджує claim;
- research-only — unresolved, assortment або comparison hypothesis.

Gate blocks: `phrase_truth_blocked`, `phrase_applicability_unresolved`, `phrase_identity_drift`, `phrase_surface_mismatch`, `phrase_proof_missing`, `keyword_stuffing`.

Decision codes: `language_gap | evidence_gap | surface_gap | assortment_signal | reject_phrase | observe`.

Measurement scorecard: cluster visibility; attention; confidence/objection reduction; fit/add-to-cart/returns; conversion/revenue per impression; controlled-change learning. Один показник не визначає winner; publication requires Product Truth, Claim, Channel and Human Decision gates.
<!-- NPO_SURFACE_ALLOCATION_GATE_2026_09_10_END -->

<!-- BACKLINK_INCIDENT_DISAVOW_GATE_2026_09_10_START -->
## 13. Backlink Incident Diagnosis and Disavow Approval Gate

Зовнішній visibility decline не запускає automatic backlink cleanup. Спочатку створити incident record із scope, baseline, direct platform notices, tracking/indexing/technical checks, link/content/release chronology, competitors і alternative explanations.

Allowed diagnosis: `verified_manual_action | probable_link_devaluation | technical_or_indexing_issue | competitive_decline | measurement_artifact | unresolved`.

Disavow candidate допускається лише за наявності exact URL/domain targets, acquisition provenance, manipulation evidence, ownership/removal attempt, current primary guidance, immutable before snapshot, owner, human approver і post-action monitoring plan. Routine or periodic disavow заборонений.

AI/SEO measurement: external mentions, backlinks, organic visibility and AI citations оцінюються разом, але association не дорівнює causation. Success scorecard: unique relevant sources, source diversity, accurate citation context, qualified referral/action, organic landing/query visibility and repeated observations. Raw link count або DR/DA окремо не визначають winner.

Block states: `link_scope_unknown`, `technical_diagnosis_incomplete`, `primary_guidance_missing`, `target_list_unverified`, `needs_human_disavow_approval`, `causal_claim_unsupported`.
<!-- BACKLINK_INCIDENT_DISAVOW_GATE_2026_09_10_END -->

<!-- HUMANITY_GENERICITY_GATE_2026_09_10_START -->
## 14. Humanity and Genericity Gate для AI-assisted copy

Цей gate застосовується до website copy, landing pages, brand pages, A+ content, email, social та інших текстів, де довіра до бренду впливає на рішення. Мета — не довести, що людина завжди пише краще, а не допустити публікацію безособового, непідтвердженого або емоційно фальшивого тексту.

### 1. Визначити trust stakes

- `low` — технічне переформатування, короткі службові описи, варіанти заголовків;
- `medium` — комерційні сторінки, category copy, PPC/SEO landing copy;
- `high` — brand promise, founder story, customer pain, гарантії, безпека, здоров'я, юридичні або репутаційно чутливі твердження.

Для `high` AI може готувати чернетку й варіанти, але named human owner затверджує claims, емпатію, тон і фінальну публікацію.

### 2. First-party Input Pack

До генерації надати: підтверджені Product Truth/brand facts; реальні customer language або дослідження; відмінну позицію бренду; приклади прийнятного й неприйнятного tone; channel/claim constraints; бажану дію читача. Якщо матеріалу недостатньо, агент повертає запит на evidence, а не заповнює прогалини правдоподібними деталями.

### 3. Обов'язкові тести чернетки

1. **Blind Brand-removal Test:** перевіряти позиціонування, рекламні обіцянки й ціннісну аргументацію. У тестовій копії прибрати назву бренду, продукту й фірмові терміни. Якщо аргументація без істотних змін підходить конкуренту, повернути відповідний фрагмент на TARGETED_REWORK. Не вигадувати унікальних переваг заради проходження тесту; точні формулювання оцінювати за правилами винятку нижче.
2. **Lived-specificity Check:** кожен особистий досвід, емоція, історія клієнта або «ми знаємо» має first-party джерело. AI не вигадує досвід, мотив чи цитату.
3. **Claim-to-evidence Check:** кожне перевірюване твердження має Product Truth/evidence binding і дозволену поверхню.
4. **Six-lens Review:** окремо оцінити clarity, UX/scannability, brand voice, search discoverability, conversion logic та accessibility. Один сильний вимір не компенсує провал іншого.
5. **Humanity Check:** текст називає конкретну ситуацію, напругу, вибір або наслідок для читача, а не імітує емпатію загальними фразами.

<!-- MBR27_05_EXACT_COPY_START -->
**Межа винятку.** Не вимагати відмінності заради відмінності від точних гарантійних умов, попереджень із безпеки, стандартних технічних назв або іншого approved exact copy, якщо джерело підтверджує потребу зберегти саме це формулювання. Виняток стосується лише позначеного фрагмента та лише Blind Brand-removal Test, не всього матеріалу. Саме попереднє затвердження рекламної фрази не є підставою для винятку.

**Підстава й погодження.** У наявній Release card вказати точний фрагмент, джерело та його версію, застосовність до SKU/каналу/ринку за потреби, причину збереження формулювання та named human owner, який підтвердив підставу. Для такого фрагмента зафіксувати незастосовність тесту відмінності з причиною, а не успішне проходження тесту. Якщо підставу чи застосовність не підтверджено, повернути на RETURN_FOR_EVIDENCE; не переписувати потенційно обов’язковий текст навмання.

**Інші перевірки.** Виняток не скасовує Product Truth, Claim-to-evidence, ясність, accessibility, інші застосовні тести та людське погодження. Непідтверджений або незрозумілий фрагмент не стає прийнятним через exact copy. У змішаному тексті точні умови зберігаються, а навколишня рекламна аргументація перевіряється окремо; слабка обіцянка й далі потребує доопрацювання.
<!-- MBR27_05_EXACT_COPY_END -->

### 4. Release card

Зафіксувати: asset/channel, trust stakes, first-party inputs, human owner, evidence links, результати п'яти тестів, required edits і рішення `APPROVE | TARGETED_REWORK | RETURN_FOR_EVIDENCE | REJECT`. Для винятку з Blind Brand-removal Test додати фрагмент, джерело/версію, підставу, застосовність і підтвердження власника; виняток не означає APPROVE для матеріалу.

Block states: `copy_first_party_input_missing`, `copy_genericity_failed`, `copy_lived_specificity_missing`, `copy_claim_evidence_missing`, `copy_human_owner_missing`, `copy_accessibility_failed`.

Метрики: first-pass acceptance; generic-fragment rate; unsupported-claim rate; material human edit time; brand-removal failure rate; post-publication correction; conversion/qualified action без погіршення complaint, return або trust signals.
<!-- HUMANITY_GENERICITY_GATE_2026_09_10_END -->

<!-- ONE_OPERATOR_MARKETING_LOOP_2026_09_10_START -->
## 15. One-Operator Amazon Marketing Operating Loop

Audit, listing/funnel, PPC, content/search і measurement не запускаються як незалежні AI-потоки. Для кожної ініціативи обов'язковий ланцюг:

`diagnostic evidence → prioritized commercial gap → listing/offer/funnel intervention → PPC or organic activation → measurement → next-best action`.

### Operating Card

- ASIN/brand/marketplace і decision question;
- baseline та evidence-backed gap;
- impacted funnel stage;
- Product Truth/Claim/Channel constraints;
- intervention і expected signal;
- conversion event, attribution limitation та guardrails;
- WIP owner, approval owner, observation window і stop condition;
- рішення `SCALE | REVISE | STOP | OBSERVE`.

### Capacity Gate

Один оператор або агентний контур має WIP limit, queue priority, exception owner, specialist escalation і recovery path. Новий experiment не стартує, якщо попередні high-priority observations не закриті або немає capacity для monitoring/recovery.

### Value rules

- Scorecard без evidence не створює задачу.
- Volume output — кількість ads, pages, posts або keywords — не є business value.
- PPC оцінюється через qualified/incremental commercial outcome, listing — через conversion/returns/expectation accuracy, content/search — через qualified demand capture.
- Attribution report без causal design позначається як observational evidence.

Block states: `marketing_loop_broken`, `measurement_contract_missing`, `capacity_at_risk`, `owner_missing`, `guardrail_missing`, `observation_window_open`.
<!-- ONE_OPERATOR_MARKETING_LOOP_2026_09_10_END -->

<!-- CONSUMER_REALITY_VALUE_GATE_2026_09_10_START -->
## Consumer Reality and Value-by-Occasion Gate

Перед новим positioning, audience split, value story або AI-shopping content task перевірити approved handoff за `AI Design Conveyor/08_Learning/Marketplace_Market_Intelligence_Research/references/21_Consumer_Reality_Assumption_and_Growth_Segment_Protocol_v0.1.md`.

Required inputs:

- `assumption_id` і changed decision object;
- market/category/ASIN scope;
- Life-System Segment fields: household structure, desired outcome, avoided downside, occasion/job, constraints, trust route, decision intermediary;
- behavioral evidence та evidence status;
- Value-by-Occasion decision: valued outcome, trade-off, total cost/effort, proof і choice evidence;
- AI Consideration Entry status, якщо AI/search route у scope;
- falsification condition, experiment owner і revalidation trigger.

Content hypothesis дозволена лише при `CONTENT_EVIDENCE_FIX`, `OFFER_OR_SERVICE_TEST` або іншому approved decision code. `external_macro_signal` без local/category evidence повертає `consumer_assumption_evidence_missing`. Заборонено перетворювати labels `solo`, `longevity` або `AI-native` на вигадані personas чи sensitive targeting attributes.

Measurement: qualified choice/conversion, contribution, returns, repeat/retention, trust/complaint signals і AI/source observation stability; stated preference або one-model mention не визначають winner.
<!-- CONSUMER_REALITY_VALUE_GATE_2026_09_10_END -->

<!-- IMAGES25_DELTA_EDIT_GATE_2026_09_10_START -->
## 16. Reference-led Image/Video Delta Edit Gate

For AI generation/editing, bind the exact SKU Passport and `Visual Invariants`. Every local edit requires `change_exactly`, `preserve_exactly`, reference/mask/comment/sketch bindings, tolerance, full-asset QA, checkpoint, branch trigger and rollback target.

Content TZ Agent owns intent, truth and acceptance. Prompt Agent only compiles the approved TZ into model/provider instructions and atomic edit steps. It cannot invent claims, change product identity or relax protected constraints.

After each turn create a Multi-turn Drift Ledger and compare the complete asset with the approved checkpoint. Route rapid/high-volume exploration to a speed model and precision-sensitive product/campaign work to a precision model only after task-level paired evaluation.

Block states: `visual_truth_blocked`, `edit_delta_incomplete`, `prompt_traceability_failed`, `invariant_drift`, `branch_required`, `rollback_required`, `model_routing_unvalidated`.
<!-- IMAGES25_DELTA_EDIT_GATE_2026_09_10_END -->

<!-- AI_SHOPPING_STAGE_AND_INTERVENTION_GATE_2026_09_10_START -->
## 17. AI Shopping Stage Diagnostic and Catalog Intervention Gate

Перед content/listing/PPC intervention визначити first failure: `INTERPRET -> RETRIEVE -> VERIFY_ENRICH -> COMPARE_RANK -> TRANSACT`.

Routing: INTERPRET — identity/attribute/NPO; RETRIEVE — indexing/feed/crawl/program/query participation; VERIFY_ENRICH — variant/identifier/price/stock/policy/conflict; COMPARE_RANK — mission fit/proof/reviews/trade-off; TRANSACT — offer/cart/checkout.

Content або creative task не є універсальним fix для retrieval, freshness чи transaction blocker. PPC scale заблокований, доки перший critical blocker не усунутий або явно не прийнятий owner.

Кожна зміна feed/PDP/schema/identifier/variant/price-availability/policy має catalog_intervention_id, baseline, affected missions/SKUs, expected signal, implementation date, observation window і guardrails. Scorecard: mission participation, first-failure distribution, shortlist entry/exit, accuracy, qualified referral, assisted conversion, cart/order, margin, returns. Decision: `SCALE | REVISE | STOP | OBSERVE | ROUTE_TO_OTHER_OWNER`.

### Перехідний контроль classic search та AI discovery

Для Amazon/Rufus та інших персоналізованих shopping assistants один prompt result не є універсальним rank. AI-search observation зберігається з ключем `prompt × profile/context × marketplace × locale × date` і полем `platform_telemetry_status: AVAILABLE | PARTIAL | PLATFORM_TELEMETRY_UNAVAILABLE`. Якщо profile/context невідомий або seller-level assistant telemetry відсутня, observation дозволено використовувати для діагностики answerability/representation defect, але не як доказ частки discovery, охоплення всіх покупців або causal lift.

Планування ведеться двома окремими треками:

- `CLASSIC_SEARCH_FOUNDATION`: indexing, keyword/query participation, PPC та content/offer health;
- `AI_ANSWERABILITY_EXPERIMENTS`: natural-language missions, grounded claims, assistant observations, first-failure diagnosis і dated retest.

Industry forecast, vendor claim або одиничний AI answer не дозволяє згорнути classic search чи автоматично перенести budget. Allocation change потребує локального outcome evidence з denominator, marketplace/country scope, observation window і named owner. Без цього рішення — `OBSERVE`, а не `SCALE`.
<!-- AI_SHOPPING_STAGE_AND_INTERVENTION_GATE_2026_09_10_END -->

<!-- AUDIENCE_SEGMENT_PRETEST_HANDOFF_2026_09_20_START -->
<a id="mbr27-route-22"></a>
## Audience Segment Pretest Handoff for Content TZ

### Призначення

Перед новим audience split, positioning, value story, offer framing або channel-specific creative Content TZ Agent може використовувати conversational audience model лише як hypothesis-discovery layer. Output не є відповіддю реальних респондентів і не має права змінювати Product Truth, approved claim, SKU Passport, price, assortment або budget.

### Обов'язкові вхідні артефакти

1. `Audience Segment Evidence Card`: `segment_id/version`, decision question, construction mode (`brand | interest | behavior/content | location/store_visit | description`), signal sources, geography, observation window/freshness, inclusion/exclusion, overlap, coverage, privacy/consent boundary, blind spots, owner.
2. `Cross-Segment Divergence Matrix`: однакові message/offer/product facts, questions, response schema і model/tool version для всіх сегментів; окремо — value driver, objection, misunderstood claim, required proof, channel/format hypothesis, trade-off response, confidence, evidence і disconfirming question.
3. `Validation Route`: реальний VoC, survey/interview, behavioral check, PickFu/ProductPinion, Manage Your Experiments або інший контрольований test із owner і decision rule.

### Правила для Content TZ Agent

- Включати в ТЗ лише segment hypotheses із чинним evidence card; generic persona або label без provenance повертається як `AUDIENCE_SIGNAL_MISSING`.
- Писати `model suggests for segment`, а не `customers said`, якщо немає respondent evidence.
- Для кожної creative hypothesis вказувати target `segment_id`, expected interpretation, objection/proof pair, channel hypothesis і falsification question.
- Не змінювати одночасно segment definition, message, offer і channel у порівняльному pretest.
- Competitor-affinity segment використовувати лише для discovery; inferred affinity не доводить intent to switch.
- Offer response є hypothesis про value language, а не доказ willingness to pay або promotion incrementality.

### Стани та вердикти

`SEGMENT_DEFINED -> MODEL_PROBED -> HUMAN_REVIEWED -> REAL_VOC_CHECKED -> CONTROLLED_TESTED -> DECISION_READY`.

До `REAL_VOC_CHECKED` output має статус `SEGMENT_HYPOTHESIS_ONLY`. Дозволені рішення: `ROUTE_TO_CONTENT_HYPOTHESIS | ROUTE_TO_OFFER_TEST | ROUTE_TO_CHANNEL_TEST | ROUTE_TO_MARKET_RESEARCH | KEEP_HYPOTHESIS_ONLY | NO_ACTION`.

### Acceptance tests

- Segment/version, provenance, freshness і model/tool version присутні в handoff.
- Cross-segment comparison відтворюється одним probe contract.
- Output містить objection, counterevidence і real-customer validation question, а не лише позитивну реакцію.
- Content TZ не перетворює segment hypothesis на product fact або performance promise.
- `READY_FOR_TEST` неможливий без validation route, owner, metric і decision rule.

### Метрики та межі доказовості

Відстежувати `segment_evidence_card_completeness`, `cross_segment_probe_reproducibility`, generic-persona rate, synthetic-to-real validation gap, divergence stability across reruns/model versions і рішення, заблоковані через stale/missing provenance.

Audience-model output не доводить demand magnitude, representativeness, willingness to pay, CTR/CVR, incrementality або causality. Джерело БЗ: `C:\Users\ystep\Documents\Агенти и база знаний\knowledge_base_brand_marketing\source_register\2026-09-20__audiense-ai-audience-insights__done.md`.
<!-- AUDIENCE_SEGMENT_PRETEST_HANDOFF_2026_09_20_END -->

<!-- AI_DESIGN_INPUT_VALIDITY_GATE_2026_09_10_START -->
## Design Input Validity Gate

Every brief passed to the prompt or generation agent must bind `product_truth_version`, `brand_rules_version`, `rights_and_license_status`, `channel_requirements_version`, `approved_claims_version`, `marketplace_policy_version`, `promotion_valid_until`, `verified_at` and `recheck_triggers`.

Changed Product Truth, claims, rights or channel requirements make the brief `SUPERSEDED`. Expired promotion blocks price/discount creative. Unknown reference rights returns `RIGHTS_VALIDATION_REQUIRED`. A style-only preference change does not force revalidation of unrelated stable facts. Prompt agent may use only the current approved brief version.
<!-- AI_DESIGN_INPUT_VALIDITY_GATE_2026_09_10_END -->

<!-- GA4_SEMANTIC_MEASUREMENT_GATE_LAI174_START -->
<a id="mbr27-route-23"></a>
## 17A. GA4 Semantic Measurement Gate

### Призначення

Gate застосовується до PDP, listing, landing page, content, creative і PPC-експериментів, для яких рішення спирається на GA4 або іншу event-based analytics. Він передує `Conversion Event Lineage and Trust Gate`: спочатку команда доводить, що вимірює правильний бізнес-об'єкт, і лише потім — що сигнал технічно доставляється без втрат.

### Обов'язковий `ga4_semantic_measurement_contract`

До implementation owner та Analytics owner спільно фіксують:

- `decision_question`, `business_action`, `decision_owner` і дозволені рішення;
- `entity_grain`: user, session, event, transaction/order, item/SKU/ASIN або інший явно визначений рівень;
- `canonical_event_name`, trigger, exclusions і зв'язок із `commerce_conversion_event_contract`;
- event parameters: business meaning, source, type, required/null rules, item-level placement, value/currency;
- reporting dimensions із scope та реєстрацією custom definition, якщо predefined field відсутній;
- metric: numerator, denominator, aggregation, unit, attribution/identity assumptions, observation window і reconciliation source;
- segmentation/filters, population, timezone, consent/privacy boundary і known blind spots;
- `key_event_status`, якщо подія позначена key event; цей статус є policy label, а не доказом валідності або причинності;
- owners, contract version, revalidation triggers і downstream dashboards/agents/decisions.

### Правила виконання

1. Починати з бізнес-питання і decision object, а не з готового GA4 report або назви event.
2. `Event`, `parameter`, `dimension` і `metric` не взаємозамінні: event фіксує дію; parameter описує конкретне спрацювання; dimension групує або фільтрує дані у визначеному scope; metric агрегує числа за явною формулою.
3. Product/item attributes для ecommerce зберігаються та перевіряються у відповідному item scope; top-level і item-level поля не вважаються еквівалентними.
4. Зібраний custom parameter не вважати доступним для звітності, доки не підтверджено потрібну custom dimension/metric registration і production population.
5. Кожна ratio metric має явні numerator, denominator і grain. `Revenue`, `conversion rate`, `users`, `sessions`, `purchases` та `items` не комбінуються без перевірки scope compatibility.
6. Окремо зберігати: design intent, implemented tracking, observed behavior і business outcome. Creative uplift не доводить product fact або causal effect без experiment design.
7. Зміна event schema, parameter placement, dimension scope, metric formula, attribution, identity, timezone або observation window створює нову contract version і потребує повторної validation.

### Стани та вердикти

`MEASUREMENT_NOT_READY -> READY_FOR_IMPLEMENTATION -> READY_FOR_VALIDATION -> TRUSTED_FOR_DECISION`.

- `MEASUREMENT_NOT_READY`: не визначено question, grain, scope, formula або owner;
- `READY_FOR_IMPLEMENTATION`: semantic contract повний, але signal ще не реалізований;
- `READY_FOR_VALIDATION`: implementation існує, але lineage/reconciliation не завершені;
- `TRUSTED_FOR_DECISION`: semantic contract і §18 acceptance receipt пройдені;
- `EXPERIMENT_BLOCKED`: critical mismatch або відсутній decision-grade signal.

### Acceptance tests

1. Команда розрізняє `view_item`, `add_to_cart`, `purchase` і не замінює ними одне бізнес-питання.
2. `item_name`, `item_id`, price і quantity перевіряються в `items` array та правильному item scope.
3. Для mobile-only revenue filter dimension scope сумісний з metric і не змінює denominator приховано.
4. Повторний submit/retry не створює duplicate purchase або подвійний revenue.
5. Custom parameter зібраний, але не зареєстрований для reporting: статус не вище `READY_FOR_VALIDATION`.
6. Key event не отримує `TRUSTED_FOR_DECISION` без production observation і reconciliation з order/source of truth.
7. Dashboard, experiment brief і agent instruction посилаються на чинні contract/event versions.

### Метрики

`semantic_contract_completeness`, `scope_mismatch_rate`, `unregistered_parameter_rate`, `metric_formula_change_rate`, `key_event_reconciliation_gap`, частка experiment briefs зі status `TRUSTED_FOR_DECISION` та кількість рішень, заблокованих до виправлення semantic mismatch.

### Межі доказовості

Gate не замінює чинну документацію GA4/GTM, consent/privacy controls, platform-specific attribution або production validation. Він не доводить причинність і не відновлює незафіксовану поведінку. Джерело БЗ: `C:\Users\ystep\Documents\Агенти и база знаний\knowledge_base_brand_marketing\source_register\2026-09-20__ga4-measurement-vocabulary-contract__done.md`.
<!-- GA4_SEMANTIC_MEASUREMENT_GATE_LAI174_END -->

<!-- CONVERSION_EVENT_LINEAGE_TRUST_GATE_2026_09_17_START -->
<a id="mbr27-route-24"></a>
## 18. Conversion Event Lineage and Trust Gate

### Призначення

Цей gate застосовується до `add_to_cart`, qualified action, lead, purchase/order, assisted conversion та інших подій, на яких агенти або команда будують рішення щодо listing, content, PPC, experiment, budget чи assortment. Наявність події у звіті не є доказом коректної поведінки клієнта: спочатку потрібно довести її повний lineage від бізнес-дії до узгодженого результату.

### Обов'язковий `commerce_conversion_event_contract`

Перед реалізацією owner створює версіонований контракт із такими полями:

- `event_id`, `event_version`, `business_action`, `canonical_event_name`;
- channel/surface, market, SKU/ASIN/product/offer identity та source of truth;
- точні trigger conditions, exclusions і expected firing frequency;
- parameters: business definition, source, type, required/null rules, value/currency;
- identity/session/consent assumptions, duplicate key і duplicate window;
- downstream reports, experiments, agents і decisions, що споживають сигнал;
- implementation owner, analytics owner, business owner;
- change dependencies, revalidation triggers, rollout/rollback version;
- `trust_state` і посилання на останній acceptance receipt.

Назва події, бізнес-дія та product identity мають бути зв'язані явно. Заборонено вважати дві події еквівалентними лише через схожу назву або однаковий UI-елемент.

### Lineage receipt

Для кожного critical event зберігати `event_lineage_receipt` за ланцюгом:

`user action -> listener/platform signal -> dataLayer/event bus -> trigger/rule -> variables/parameters -> tag/API -> analytics/debug -> production report -> cart/order/source-of-truth reconciliation`.

На кожному шарі receipt фіксує `observed_at`, environment, event/contract version, entity identity, input, output, count, error/mismatch і evidence reference. Допустимі verdicts: `PASS | DROP | DUPLICATE | MISLABEL | PARAMETER_ERROR | CONSENT_BLOCK | ENVIRONMENT_ERROR | UNRESOLVED`.

### Стани довіри та decision gate

Подія рухається тільки вперед після доказу попереднього стану:

`DEFINED -> IMPLEMENTED -> DEBUG_VERIFIED -> PRODUCTION_OBSERVED -> RECONCILED -> TRUSTED_FOR_DECISION`.

Content, listing, PPC, experiment або optimization agent не має права рекомендувати `SCALE`, `STOP`, budget reallocation чи причинний висновок, якщо critical event нижче `TRUSTED_FOR_DECISION`. Spike/drop спочатку класифікується як `BEHAVIOR_CHANGE | MEASUREMENT_INCIDENT | MIXED | UNRESOLVED`. До завершення перевірки використовувати `UNRESOLVED`, а не пояснювати зміну поведінкою клієнта.

### Обов'язкові тести

1. Correct event, wrong SKU/ASIN/product identity.
2. Missing або некоректні `value`, `currency`, quantity чи required parameter.
3. One action produces two events; repeat click/retry does not create false conversion.
4. SPA rerender, refresh, back navigation і component remount.
5. Consent/ad-block/privacy condition блокує або змінює delivery.
6. DebugView passes, але production report не містить подію.
7. GA4/analytics count не узгоджується з cart/order/transaction source of truth.
8. Selector, template, container, tag, event schema або product feed version змінено.
9. Rollback повертає попередню подію без змішування версій.
10. Dashboard/agent ще читає стару назву або schema version.

### Ролі, дозволи та ескалація

- Implementation owner відповідає за transport і technical receipt.
- Analytics owner — за semantic correctness, production observation і reconciliation.
- Business owner — за business meaning та дозвіл використовувати signal у рішенні.
- Agent може створювати test plan, порівнювати receipts і виявляти mismatch, але не може самостійно змінювати live container/tag/API mapping або self-approve `TRUSTED_FOR_DECISION`.
- Live mutation потребує scoped permission, change record, rollback target і human approval.

### Метрики контролю

Відстежувати drop rate, duplicate rate, parameter completeness, identity mismatch rate, debug-to-production gap, analytics-to-order reconciliation gap, частку critical events у кожному trust state, mean time to resolve measurement incident і кількість рішень, заблокованих через insufficient trust.

### Evidence boundary

Цей gate задає операційний контроль, але не замінює актуальні вимоги GA4/GTM, Amazon Ads/Attribution, consent mode, server-side tagging, cross-domain identity чи offline conversion import. Для конкретної реалізації потрібні чинні platform docs і докази з production environment.
<!-- CONVERSION_EVENT_LINEAGE_TRUST_GATE_2026_09_17_END -->

<!-- PURCHASE_SIGNAL_PARITY_GATE_2026_09_20_START -->
<a id="mbr27-route-25"></a>
## Purchase Signal Parity Gate

### Призначення

Gate застосовується перед cross-channel ROAS comparison, PPC budget reallocation, bidding optimization, audience/channel-quality conclusion або creative learning, якщо `Purchase` надходить із Shopify/DTC, TikTok Shop, Amazon чи іншого marketplace, app, browser/server або downstream warehouse/CDP feed. Однакова назва event не є доказом однакового optimization signal.

### Обов'язковий `purchase_signal_parity_receipt`

Для кожного source/channel зафіксувати:

- `channel`, `source_system`, `event_version`, `observation_environment`: `NATIVE_PLATFORM_VIEW | OWNED_BROWSER_SERVER_VIEW | DOWNSTREAM_WAREHOUSE_CDP_OR_AD_PLATFORM_VIEW`;
- `identity_visibility_profile`: customer/order/click/session identifiers зі status `AVAILABLE | MASKED | DELAYED | CHANNEL_NATIVE_ONLY | UNAVAILABLE | UNKNOWN`, consent basis та observation point;
- `revenue_scope_ledger`: base/gross product value, discounts, tax, shipping, duties, gift cards, refunds/cancellations, subscriptions, post-purchase upsells, order edits, currency;
- `purchase_timestamp`, `event_send_timestamp`, `platform_receipt_timestamp` і attribution implication;
- `order_id`, `source_order_id`, `event_id/deduplication_key`, retry, refund/cancellation і late-adjustment rules;
- raw event value, internal `normalized_value`, normalization definition/version і finance-recognized value;
- sample reconciliation, unknown fields, owner, revalidation triggers і downstream decisions.

### Правила виконання

1. Native visibility і downstream visibility оцінюються окремо; closed-loop platform view не означає, що ті самі identifiers доступні у warehouse або іншій ad platform.
2. Raw source payload зберігається незмінним. `normalized_value` є окремим internal field; missing component не заповнюється припущенням.
3. Optimization value і management-reporting value або мають одну definition, або їхня різниця явно задокументована.
4. Delay між purchase, send і receipt перевіряється як attribution/optimization risk, а не лише technical latency.
5. Browser, server, app, marketplace і imported feeds мають спільний deduplication contract, якщо описують одне замовлення.
6. Audience, channel або creative не вважається weaker/stronger, доки не відкинуто identity-visibility і revenue-scope distortion.

### Вердикти

`PARITY_CONFIRMED | COMPARABLE_AFTER_NORMALIZATION | NONCOMPARABLE | UNKNOWN`.

- `PARITY_CONFIRMED`: identity and value definitions достатньо еквівалентні для погодженого рішення;
- `COMPARABLE_AFTER_NORMALIZATION`: raw signals відрізняються, але approved normalization дає порівнюваний management view;
- `NONCOMPARABLE`: material gap неможливо коректно усунути для цього рішення;
- `UNKNOWN`: payload, identity або revenue scope недостатньо відомі.

`SCALE`, `STOP`, budget shift, channel-ranking і causal creative learning блокуються для `NONCOMPARABLE` та `UNKNOWN`.

### Acceptance tests

1. Shopify і TikTok Shop мають однаковий event name, але різний identifier survival downstream — система не називає це demand difference.
2. Один `Purchase.value` включає post-purchase upsell, інший — ні; raw ROAS comparison блокується або нормалізується.
3. Browser і server повідомляють одне order — stable ID не допускає double count.
4. Refund/cancellation/order edit змінює value після первинного event і відображається у чинній definition.
5. Finance sample reconciliation показує, які components не входять в contribution-margin view.
6. Channel ranking перевіряється до та після normalization; reversal обов'язково ескалується.

### Метрики та межі доказовості

Відстежувати identity completeness by environment, purchase value scope parity, duplicate-order rate, receipt-delay distribution, raw-to-normalized value gap, finance reconciliation gap, blocked budget decisions і channel-ranking reversal after normalization.

Gate не відновлює недоступні identifiers/conversions, не обходить consent/privacy і не доводить causal ROAS. Platform fields, APIs, match rules та policy перевіряються за чинною документацією і production evidence. Джерело БЗ: `C:\Users\ystep\Documents\Агенти и база знаний\knowledge_base_brand_marketing\source_register\2026-09-20__bfcm-purchase-signal-parity__done.md`.
<!-- PURCHASE_SIGNAL_PARITY_GATE_2026_09_20_END -->

<!-- BEHAVIOR_SEQUENCE_ANALYSIS_GATE_2026_09_17_START -->
<a id="mbr27-route-26"></a>
## 19. Behavior Sequence Analysis Gate

### Призначення

Цей gate застосовується після того, як critical events досягли `TRUSTED_FOR_DECISION`. Він контролює не delivery окремої події, а коректність побудованого з подій customer journey. Trusted event ще не доводить правильність funnel, cohort, segment або причинного висновку.

Gate обов'язковий перед рішеннями щодо listing/content/PPC intervention, experiment priority, budget reallocation, customer segment, retention, funnel leakage або масштабування, якщо рішення використовує послідовність web/commerce events.

### Обов'язковий `commerce_behavior_sequence_contract`

До аналізу Analytics owner створює версіонований контракт:

- `analysis_id`, `analysis_version`, `business_question`, `decision_to_change`;
- `analysis_unit`: `USER | ACCOUNT | DEVICE | SESSION | ORDER | SKU_ASIN`;
- `entity_identity`, identity-resolution rule, cross-device assumption і known identity gaps;
- `ordered_events` з посиланнями на `commerce_conversion_event_contract` та мінімальним `trust_state = TRUSTED_FOR_DECISION`;
- `entry_rule`, `exit_or_outcome_rule`, allowed repeats, dedupe rule і sequence timeout;
- `sessionization_rule`, timezone, lookback window, observation window та attribution boundary;
- population, inclusions, exclusions, numerator, denominator і minimum sample requirement;
- predefined segments/cohorts та reason for inclusion;
- baseline/comparator, expected business value, guardrails і uncertainty method;
- allowed verdicts, owner, review date, source tables/query/notebook version і revalidation triggers.

Зміна identity resolution, session timeout, timezone, event version, population, denominator або observation window створює нову версію контракту та позначається `METHODOLOGY_BREAK`. Результати до і після break не подаються як безперервний performance trend без окремого bridging analysis.

### Three-Lens Reconstruction

Кожна лінза відповідає на окреме питання:

- `FUNNEL`: де в ordered sequence втрачаються учасники;
- `SEGMENT`: для кого pattern відрізняється;
- `COHORT`: як поведінка групи зі спільною точкою старту змінюється з часом.

Aggregate metric не є достатнім, якщо predefined segment/cohort може змінити управлінський висновок. Для high-impact рішення Analytics owner перевіряє mix shift і фіксує, чи перевертається conclusion після сегментації.

<!-- MBR27_03_STATE_VERDICT_START -->
<a id="mbr27-state-verdict"></a>
### Стани інтерпретації та дозволені дії

Погоджене уточнення MBR27-03 від 27.09.2026: стан доказів і verdict записуються окремо в чинному `behavior_analysis_receipt`. Рішення перевірити гіпотезу не підвищує її доказовість. У межах цього §19 `DECISION_READY` означає готовність обґрунтування впровадження (`ACT`), а не передумову `TEST`; інші однойменні стани інших contracts цим уточненням не змінюються. Вимога causal evidence для ACT стосується саме втручання, обґрунтованого behavior analysis §19; вона не затримує виправлення вже підтвердженого Product Truth, rights чи measurement дефекту за відповідним upstream gate. Повторний тест нового scope має окремий запис і не стирає попередній перевірений результат.

Послідовність нарощування доказовості:

`OBSERVED_EVENT -> RECONSTRUCTED_SEQUENCE -> DESCRIPTIVE_PATTERN -> DIAGNOSTIC_HYPOTHESIS -> CAUSAL_EVIDENCE`.

- `OBSERVED_EVENT` дозволений лише для events зі статусом `TRUSTED_FOR_DECISION` за §§17A–18.
- `RECONSTRUCTED_SEQUENCE` потребує пройдених identity, ordering, dedupe, sessionization і window tests.
- `DESCRIPTIVE_PATTERN` дозволяє сказати `what/where/for whom/when`, але не `why`.
- `DIAGNOSTIC_HYPOTHESIS` потребує альтернативних пояснень і плану перевірки; не підтверджує причинність.
- `CAUSAL_EVIDENCE` потребує experiment, quasi-experiment або іншого погодженого causal design та перевіреного результату в явно визначених population, intervention і window. Drop-off, кореляція, temporal order або факт завершення тесту самі по собі цього статусу не дають.
- `DECISION_READY` для `ACT` потребує `CAUSAL_EVIDENCE`, business-value binding, guardrails, owner і наперед визначеного verdict. Навіть цей стан не є дозволом на виконання: конкретну дію приймає Business owner через чинні approval/release gates.

Доступні verdicts незмінні: `ACT | TEST | INVESTIGATE | OBSERVE | NO_ACTION | ANALYSIS_BLOCKED`.

| Перевірений стан | Допустимий verdict | Умова та наступний крок |
|---|---|---|
| OBSERVED_EVENT або RECONSTRUCTED_SEQUENCE | INVESTIGATE, OBSERVE, NO_ACTION | Перевіряти/відновлювати послідовність або збирати дані. Не призначати TEST лише за одиничною подією; спочатку сформувати обґрунтовану DIAGNOSTIC_HYPOTHESIS. |
| DESCRIPTIVE_PATTERN | INVESTIGATE, OBSERVE, NO_ACTION | Описати pattern і альтернативні пояснення; перейти до гіпотези з планом. Pattern не є доказом причини й не дозволяє ACT. |
| DIAGNOSTIC_HYPOTHESIS | TEST; або INVESTIGATE, OBSERVE, NO_ACTION | TEST можливий за повного погодженого bounded test plan нижче, без CAUSAL_EVIDENCE чи DECISION_READY. Після погодження — до звичайного test/release gate R19, не прямо до live-зміни. За неповного плану — дослідження/доопрацювання, не дозволений запуск. |
| CAUSAL_EVIDENCE | TEST; або INVESTIGATE, OBSERVE, NO_ACTION | TEST для повторення або нового обмеженого контексту потребує такого самого plan/approval. Для ACT спочатку перевірити business-value, guardrails і owner та отримати DECISION_READY. Негативний результат не стає підставою масштабування; inconclusive/error не стає causal proof. |
| DECISION_READY | ACT; або TEST, INVESTIGATE, OBSERVE, NO_ACTION за їхніми умовами | ACT — прийнята власником рекомендація впровадження лише в доказаному scope, після чинних окремих дозволів на дію. Новий контекст не успадковує доказовість автоматично. TEST не потребує збереження цього стану як передумови для нової гіпотези. |
| Будь-який заявлений стан із критичним непройденим gate, непідтвердженими events/версіями або unresolved methodology break | ANALYSIS_BLOCKED для заторкнутого висновку/рішення | Повернути measurement, reconstruction, evidence або approval gap відповідальному owner. Дозволено збирати докази й усувати blocker; заборонено обійти його verdict-ом TEST чи попереднім високим станом. |

#### Умови TEST і межа повноважень

До погодження `TEST` у чинному Experiment Brief/behavior receipt зафіксувати: diagnostic hypothesis та альтернативні пояснення; decision question, scope і population; intervention/порівняння та baseline; метрику, denominator і валідований measurement route; test window, sample/uncertainty та stopping/decision rules за обраним дизайном; guardrails, обмеження експозиції/витрат за застосовністю, умови зупинки/відкату; Experiment owner, Business owner і посилання на їхні відповідні погодження. Числових універсальних порогів це уточнення не встановлює.

`TEST` — погоджене рішення перевірити гіпотезу, а не дозвіл самостійного запуску. Experiment owner відповідає за дизайн і stopping/decision rules; Business owner погоджує expected value, guardrails і дію. Перед зовнішнім тестом обов'язкові чинні QA, Product Truth, claims, rights, channel, risk/R12 та R19 release/launch approval. Для пов'язаного PPC діє окремий R13; жодних нових spend/live permissions не надано.

Agent може запропонувати verdict і підготувати plan, але не погоджує власний TEST, CAUSAL_EVIDENCE, DECISION_READY чи ACT. Заборона пропускати доказові кроки стосується підвищення стану та сили твердження; вона не забороняє TEST на рівні DIAGNOSTIC_HYPOTHESIS. Тест не переводить гіпотезу в CAUSAL_EVIDENCE автоматично: після нього перевірити результат, uncertainty, alternative explanations та causal design. NO_ACTION не означає команду зупинити діючу кампанію або змінити бюджет.
<!-- MBR27_03_STATE_VERDICT_END -->

### Обов'язковий `behavior_analysis_receipt`

Receipt зберігає:

- contract і event-contract versions;
- source tables, query/notebook version, filters і execution timestamp;
- row/event/entity counts до та після exclusions/dedupe;
- missing-event, duplicate, identity та session-boundary diagnostics;
- funnel, segment і cohort construction;
- numerator, denominator, sample size, uncertainty/statistical method;
- aggregate result і predefined segment/cohort results;
- alternative explanations, causal-evidence status і evidence references;
- commercial/operational value estimate, guardrails, owner, verdict і review date;
- output snapshot та reproducibility check.

### Acceptance tests

1. Інший аналітик відтворює population, ordered sequence і result із contract та receipt.
2. Повторний click/retry/reload не створює фальшивий sequence step або conversion.
3. User, account, device і session не використовуються як взаємозамінні analysis units.
4. Midnight/timezone, session timeout, cross-device та returning-user сценарії мають очікуваний routing.
5. Усі ordered events мають потрібну версію і `TRUSTED_FOR_DECISION`; змішування версій блокується.
6. Aggregate result порівняно з predefined device/source/new-vs-returning та іншими релевантними segments/cohorts.
7. Numerator, denominator, exclusions, sample size та observation window явно показані.
8. Drop-off location не названо root cause без diagnostic/causal evidence.
9. Causal claim має погоджений evidence route; інакше status не вищий за `DIAGNOSTIC_HYPOTHESIS`.
10. Actionable finding має affected population, expected value, feasible intervention, guardrails, owner і verdict.
11. Зміна contract field, що впливає на методологію, створює нову версію та `METHODOLOGY_BREAK`.
12. Agent/dashboard не використовує superseded query, event contract або analysis version.
13. DIAGNOSTIC_HYPOTHESIS з альтернативами, погодженим bounded plan і TRUSTED_FOR_DECISION measurement може отримати TEST без CAUSAL_EVIDENCE/DECISION_READY; запуск усе одно потребує R19.
14. Одинична подія або DESCRIPTIVE_PATTERN без diagnostic hypothesis не отримує TEST чи ACT.
15. TEST без plan, owner/погодження або з critical measurement mismatch не запускається; causal claim із гіпотези заборонений.
16. Завершений тест із inconclusive/error не стає CAUSAL_EVIDENCE; causal evidence без business-value/guardrails не стає ACT.
17. Agent не може self-approve TEST, CAUSAL_EVIDENCE, DECISION_READY або ACT; NO_ACTION не виконує live stop/budget change.

### Ролі та відповідальність

- Analytics owner володіє contract, reconstruction, receipt, interpretation state і reproducibility.
- Implementation owner усуває measurement defects, але не визначає business meaning analysis.
- Experiment owner визначає causal design і stopping/decision rules.
- Business owner затверджує expected value, guardrails і дію.
- Agent може будувати draft contract, виконувати дозволені зрізи, виявляти mismatch і пропонувати verdict; self-approval `CAUSAL_EVIDENCE` або `DECISION_READY` заборонений.

### Метрики контролю

Відстежувати `analysis_reproducibility_rate`, `identity_or_sessionization_mismatch_rate`, `duplicate_and_missing_event_rate`, `aggregate_conclusion_reversal_rate_after_segmentation`, частку findings із predefined decision rule, `descriptive_claims_mislabeled_as_causal_rate`, blocked decisions через methodology break та `time_from_pattern_to_verified_action`.

### Межі доказовості

Gate описує observed behavior лише в instrumented population. Він не відновлює consent-blocked або незафіксовані дії, мотиви клієнта чи повну cross-device journey без додаткових даних. Funnel, cohort і segment локалізують pattern, але не доводять причину. Конкретна реалізація GA4/Amazon Ads/Attribution, consent, privacy, identity resolution, retention та warehouse export потребує актуальної platform documentation і production validation.
<!-- BEHAVIOR_SEQUENCE_ANALYSIS_GATE_2026_09_17_END -->
<!-- VIDEO_PACKAGING_PROMISE_LEARNING_GATE_2026_09_17_START -->
<a id="mbr27-route-27"></a>
## 20. Video Packaging Promise and Learning Gate

### Призначення

Для YouTube, video podcast, social/marketplace video та інших assets, де cover/title визначають вибір до перегляду, Content TZ Agent проєктує packaging до production. Title, thumbnail/cover, opening та content payoff є одним contract; привабливість без виконаної promise не проходить release/learning gate.

### Обов'язкові артефакти

1. `video_title_hypothesis_set`: 5–10 варіантів із `audience`, `traffic_mode`, `promise`, `angle`, `content_proof`, `risk` і `status`.
2. `video_packaging_promise_contract`: `thumbnail_attention_cue -> title_promise -> intro_confirmation -> content_payoff -> next_view_path`.
3. `video_research_libraries`: окремі `competitor_library` і `cross_niche_inspiration_library` з baseline context та rationale перенесення.
4. `video_title_test_receipt`: versioned title/cover pair, test window, audience/traffic context, impressions, qualified CTR, early retention, watch quality, next-view behavior, downstream outcome та limitations.

### Стани й вердикти

`HYPOTHESIS_DRAFT -> PROMISE_EVIDENCED -> CONTENT_ALIGNED -> READY_FOR_TEST -> TESTED -> LEARNING_PROPOSED -> REPEAT_VALIDATED`.

Blockers: `PROMISE_MISMATCH | CONTENT_PROOF_MISSING | TITLE_COVER_CONFLICT | TRAFFIC_MODE_UNKNOWN | BASELINE_NOT_COMPARABLE | TEST_CONTAMINATED`.

Allowed decisions: `REVISE_PACKAGE | PRODUCE_FOR_TEST | TEST_VARIANTS | RETEST | ADOPT_AS_LOCAL_PATTERN | KEEP_HYPOTHESIS_ONLY | STOP`.

Високий CTR не компенсує `PROMISE_MISMATCH`, weak retention, negative feedback або downstream harm. Один winning variant не стає SOP rule до повторної перевірки в сумісному context.

### Ролі й межі агента

- Content TZ Agent створює hypotheses, contract, research record і test plan.
- AI Creator/Prompt Agent компілює затверджені cover/opening constraints, але не змінює promise, claim або angle.
- Experiment Analyst перевіряє test receipt і формує learning proposal.
- Business/Content owner погоджує production, live title/cover mutation та SOP adoption.
- Agent не публікує asset, не змінює live metadata і не self-approves winner/SOP.

### Acceptance tests

- Кожний title має audience, traffic mode, promise, angle і content proof.
- Thumbnail/cover додає attention/context і не суперечить title.
- Opening швидко підтверджує promise; content містить заявлений payoff.
- Cross-channel inspiration нормалізована до comparable channel baseline, format, age/window і traffic mode.
- Test змінює явний hypothesis dimension, а result містить retention і downstream guardrails поряд із CTR.
- Learning має reuse boundary; неповторений result залишається `HYPOTHESIS_ONLY`.

### Межі доказовості

Gate не встановлює універсальну формулу title, emotional angle, length або CTR threshold. Platform behavior і native testing змінюються; конкретні рішення потребують чинних platform rules і локальних контрольованих тестів.
<!-- VIDEO_PACKAGING_PROMISE_LEARNING_GATE_2026_09_17_END -->
<!-- GLOBAL_CODEX_OUTPUT_STYLE_SYSTEM_2026_09_17_START -->
## Global Codex Output Style Contract

Цей проєкт використовує глобальну систему оформлення:

- `C:\Users\ystep\.codex\AGENTS.md`;
- `C:\Users\ystep\.codex\standards\CODEX_OUTPUT_STYLE_SYSTEM.md`.

Для нового або істотно зміненого артефакту спочатку визначити artifact profile, потім застосувати domain-specific поля й gates цього проєкту. Проєктна інструкція доповнює, але не дублює глобальний словник.

Пріоритет: поточна команда користувача → затверджений шаблон/чинний формат документа → проєктні правила → глобальний artifact profile.

Forward-only: старі документи не переформатовуються масово. Вирівнювання відбувається під час наступного змістовного оновлення або окремої migration task.

Для substantial artifact виконати format review: language, canonical terminology, heading structure, required sections, statuses/verdicts, links, evidence boundary і documented deviations. Allowed disposition: `PASS | REWORK | APPROVED_EXCEPTION`.
<!-- GLOBAL_CODEX_OUTPUT_STYLE_SYSTEM_2026_09_17_END -->

<!-- SKU_TRUTH_PACKAGING_CONCEPT_PIPELINE_2026_09_17_START -->
<a id="mbr27-route-28"></a>
## 21. SKU Truth-Bound Packaging-Led Concept Sprint

### Призначення

Перенести packaging з фінального оформлення на початок content design і водночас не допустити, щоб title, cover або emotional hook створювали нову Product Truth. Sprint починається лише з versioned `content_product_truth_snapshot` Паспорта SKU та завершується creative package, у якому кожна product promise має fact/evidence binding або явний статус creative-only.

### Trigger та область застосування

Gate обов'язковий для product video, marketplace/social video, creator/UGC brief, video podcast/interview про SKU, cover/thumbnail, title, clip, email subject/preview або іншого discovery asset, де креатив може містити product identity, feature, benefit, suitability, comparison, use case чи constraint.

Для non-product editorial asset без SKU допускається `PASSPORT_NOT_APPLICABLE` з rationale. Відсутність Паспорта для product asset не замінюється пам'яттю агента, старим listing або competitor content.

### Вхідний контракт із Паспорта SKU

```yaml
content_product_truth_snapshot:
  snapshot_id:
  passport_version:
  sku:
  parent_sku:
  exact_variant:
  marketplace:
  country:
  language:
  channel:
  effective_at:
  verified_fact_versions: []
  allowed_claim_relations: []
  prohibited_claims: []
  unresolved_conflicts: []
  missing_critical_facts: []
  stale_dependencies: []
  approved_assets: []
  visual_opportunities: []
  usage_rights_constraints: []
  applicable_use_cases: []
  applicability_boundaries: []
  comparison_constraints: []
```

Critical product claim може спиратися лише на точні `fact_version_ids` зі статусом `current_verified`, сумісні SKU/variant/marketplace/period і допустимі evidence links. Snapshot є immutable input конкретної версії brief.

### Workflow

1. **Passport Snapshot Intake.** Зафіксувати snapshot/version, exact variant, scope, conflicts, missing/stale facts, approved assets і usage rights.
2. **Packaging-Led Concept Sprint.** Створити 5–10 hypotheses через один із маршрутів: `IDEA_FIRST`, `TITLE_FIRST`, `VISUAL_FIRST`. Маршрут не визначає winner; усі hypotheses проходять однаковий truth/proof gate.
3. **SKU Truth-to-Creative Gate.** Для кожної product promise зв'язати `fact_version_ids`, evidence, applicability і proof requirement. Curiosity/емоційний hook без product claim позначити `CREATIVE_ONLY_NO_PRODUCT_CLAIM`.
4. **Title-Cover Complementarity.** Cover виконує `attention/audience/category/tone job`; title виконує `conversion/specific promise job`. Дублювання або contradiction повертається на rework.
5. **Proof Acquisition Plan.** До production визначити question/scene/demonstration/measurement, потрібний visual, minimum usable result, owner і fallback. Missing fact повертається у Паспорт як clarification/evidence request; агент не дописує Product Truth.
6. **Opening Confirmation.** Спроєктувати opening/cold-open, який швидко підтверджує clicked promise, показує relevance/proof і не вириває фрагмент з контексту.
7. **Traffic-specific packaging.** `SEARCH` оптимізує intent clarity і query correspondence; `BROWSE_SUGGESTED` — audience recognition, interruption value і reason-to-watch. Один title для обох режимів потребує окремого rationale/test.
8. **Length and visible-prefix check.** Не застосовувати універсальний character ceiling. Перевіряти `mobile_visible_prefix`, front-loaded meaning і survival of meaning after truncation.
9. **Continuation and derivatives.** Визначити audience state after view, unresolved next question, next asset/series/CTA та окремі promises для long-form, clips, email/newsletter і social derivatives.
10. **Pre-release revalidation.** Перед production handoff і release повторно зіставити active snapshot/version. Зміна critical fact, evidence status, variant scope або rights invalidates affected hypotheses/TZ до review.

### `content_claim_binding`

```yaml
content_claim_binding:
  binding_id:
  hypothesis_id:
  snapshot_id:
  sku:
  exact_variant:
  surface:
  proposed_wording:
  claim_class:
  fact_version_ids: []
  evidence_ids: []
  applicability:
  proof_requirement:
  allowed_scope:
  prohibited_inference:
  status: CANDIDATE | TRUTH_BOUND | PROOF_CAPTURE_REQUIRED | BLOCKED | STALE
  owner:
```

Binding є зовнішньою content projection і не змінює Product Truth.

### Стани, рішення і блокери

Стани: `SNAPSHOT_REQUIRED -> TRUTH_SCOPED -> CONCEPT_SPRINT -> PROOF_PLANNED -> CONTENT_ALIGNED -> READY_FOR_PRODUCTION -> PRODUCED -> REVALIDATED -> READY_FOR_TEST`.

Verdicts: `TRUTH_BOUND | PROOF_CAPTURE_REQUIRED | PASSPORT_CLARIFICATION_REQUIRED | CREATIVE_ONLY_NO_PRODUCT_CLAIM | CLAIM_SCOPE_CONFLICT | VARIANT_MISMATCH | STALE_TRUTH_DEPENDENCY | BLOCKED_UNSUPPORTED_CLAIM`.

Blockers: `PASSPORT_SNAPSHOT_MISSING | FACT_VERSION_MISSING | PRODUCT_TRUTH_CONFLICT | VARIANT_SCOPE_MISMATCH | UNSUPPORTED_PRODUCT_PROMISE | USAGE_RIGHTS_NOT_CLEARED | STALE_CRITICAL_FACT | TITLE_COVER_REDUNDANCY | AUDIENCE_SIGNAL_MISSING | PAIR_DOES_NOT_CONVERGE | OPENING_CONFIRMATION_MISSING | COLD_OPEN_OUT_OF_CONTEXT | PAYOFF_TOO_LATE`.

### Ролі

- Passport/Verifier відповідає за Product Truth, fact versions, evidence status і conflict resolution.
- Content TZ Agent створює creative hypotheses, bindings, proof plan, opening і continuation map; не встановлює `verified`.
- AI Creator/Prompt Agent реалізує approved hypothesis без розширення claim scope.
- Production owner фіксує отриманий proof/asset refs і usage-rights result.
- Content/Business owner погоджує creative route, release і test.

### Acceptance tests

- hypothesis для правильного SKU, але іншої variation;
- use-case phrase подана як універсальна властивість;
- curiosity title без product claim;
- strong title з missing current_verified fact;
- approved fact змінено після готовності ТЗ;
- cover і title дублюють текст без complementary job;
- opening не підтверджує promise або використовує out-of-context clip;
- long title з працездатним mobile prefix і short title, що втрачає specificity;
- proof capture не отримано, title має бути звужений;
- production asset створює evidence proposal, але не self-verifies Product Truth.

### Метрики

Truth-binding coverage, unsupported-claim block rate, variant mismatch rate, snapshot invalidation/rework, proof capture completion, promise-to-payoff alignment, opening confirmation pass, title-cover redundancy, next-view rate, downstream complaint/return/trust guardrails.

### Межі доказовості

Creative performance не підтверджує product fact або causal superiority. Паспорт підтверджує лише визначені факти/evidence і не гарантує CTR, retention або conversion. Emotional angles, title length, packaging formulas і cross-niche patterns залишаються hypotheses до локального тесту.
<!-- SKU_TRUTH_PACKAGING_CONCEPT_PIPELINE_2026_09_17_END -->

<!-- AI_DESIGN_PARALLEL_GRAPH_GATE_2026_09_17_START -->
<a id="mbr27-route-29"></a>
## 26. Parallel Branch і Fan-In Gate для AI Design

### Призначення та область застосування

Цей gate застосовується лише тоді, коли дві або більше функції AI Design фактично виконуються паралельно й записують findings, evidence, hypotheses, edits або verdicts у спільний `Content TZ`, `Production Contract`, `Multi-turn Drift Ledger` чи `Release Card`. Він не створює нових агентів і не перетворює чинну послідовність на graph за замовчуванням.

Linear execution лишається default. Перед parallelization власник має довести, що branches не залежать від output одна одної та що очікуваний виграш у latency/coverage перевищує merge, review і recovery burden.

### Trigger і вхідний контракт

Trigger: одночасний запуск research sources, channel/surface analyses, creative hypotheses, provider variants або QA specialisms, результати яких мають зійтися в один decision object.

```yaml
ai_design_parallel_run:
  run_id:
  pipeline_version:
  sku_passport_snapshot_id:
  exact_sku_variant_market_scope:
  target_object_id:
  target_object_version:
  baseline_route:
  review_capacity:
    review_owner:
    available_review_time:
    estimated_review_time_per_output:
    max_open_branch_outputs:
  branches:
    - branch_id:
      purpose:
      owner:
      input_snapshot:
      allowed_reads: []
      allowed_writes: []
      output_schema:
      timeout:
      failure_statuses: []
  reducer_id:
  completion_rule: ALL | OWNER_APPROVED_PARTIAL
  human_gate_owner:
  status:
```

Усі branches читають однакові approved SKU Passport, Brand Entity, rights, claim і channel-policy snapshots. Branch не може змінити Product Truth, risk level, Visual Invariants або acceptance criteria іншого branch.

Перед створенням specialist branches порівняти їх із one-model/linear baseline. Parallel specialist route дозволений лише коли branches використовують різні evidence domains/tools/methods, можуть бути ізольовані без втрати dependencies, повертають порівнювані typed findings і дають вимірюваний benefit. Назва ролі сама по собі не створює нового агента або branch.

До `fan_out` Content TZ owner оцінює не лише час генерації, а й доступний час названого reviewer на перевірку Product Truth, SKU/variant/market fidelity, claims, rights та повного asset. Кількість одночасно відкритих branch outputs не може перевищувати `max_open_branch_outputs`, обґрунтований цим часом. За браку review capacity — зменшити batch, перейти до linear route або залишити `PARALLEL_PLANNED`; завершення генерації саме по собі не відкриває наступний gate.

Кожний research/QA branch повертає:

```yaml
ai_design_specialist_finding:
  branch_id:
  agent_model_version:
  claim_or_verdict:
  evidence_refs: []
  sku_variant_market_scope:
  confidence:
  freshness_or_validity:
  verdict: OK | WARN | HOLD
  limitations: []
```

Missing, timeout, crashed або schema-invalid branch не стає neutral vote. Для time-dependent evidence observation window має покривати релевантний campaign, replenishment, seasonal, review або policy cycle; неповний цикл знижує confidence або блокує claim про відсутність signal.

### Typed transitions

Для переходів `fan_out`, `branch_complete`, `branch_failed`, `fan_in`, `conflict_review`, `rework` і `release` фіксувати trigger, condition, payload/version, owner та failure route. Low-confidence або ambiguous routing не може обирати вузький branch як final answer: потрібен broader review, Content TZ owner decision або `ROUTING_UNCERTAIN`.

### Deterministic Fan-In Reducer

```yaml
ai_design_fan_in_reducer:
  reducer_id:
  target_object_id:
  merge_key:
  ordering_rule:
  duplicate_policy:
  conflict_policy:
  provenance_required: true
  required_branch_ids: []
  missing_branch_behavior:
  invalid_branch_behavior:
  immutable_fields:
    - sku_passport_snapshot_id
    - exact_sku_variant_market_scope
    - approved_claim_bindings
    - visual_invariants
    - acceptance_criteria
  merged_output_schema:
  reducer_owner:
  reviewer:
```

`last-writer-wins` заборонений. Кожний merged finding зберігає `branch_id`, source/evidence locator, confidence, applicable scope і version. Contradictory Product Truth, claim, variant, rights або invariant не усереднюються й не обираються автоматично: verdict — `STATE_CONFLICT` і повернення відповідному owner.

Missing або timeout branch не стає мовчазно complete. `OWNER_APPROVED_PARTIAL` дозволений лише якщо названий owner підтвердив, що відсутній branch не потрібний для конкретного decision/release, і rationale записаний у receipt.

Reducer працює non-compensatory: `HOLD`, unresolved Product Truth/claim/rights/invariant conflict, stale critical evidence або missing required branch не перекривається більшістю `OK`. Coordination receipt зберігає expected/received/missing branches, named contradictions, risk signals, final verdict, decision owner і aggregation-policy version. Human review запускається risk/conflict/missing-branch signal, а не кожним нормальним branch output.

Перед `READY_FOR_NEXT_GATE` відповідальний Content TZ owner коротко пояснює consequential creative, claim або Product Truth change: що саме змінилося, чому це відповідає approved brief/SKU Passport, на яке evidence спирається та які ризики й перевірки залишилися. Якщо owner не може пояснити зміну або evidence не простежується, результат лишається `MERGED_PENDING_REVIEW` до уточнення чи rework. Для deterministic resize/export без content change окремий explain-back не потрібний.

### Стани та блокери

Стани: `PARALLEL_NOT_REQUIRED | PARALLEL_PLANNED | BRANCHES_RUNNING | FAN_IN_PENDING | MERGED_PENDING_REVIEW | READY_FOR_NEXT_GATE`.

Blockers: `PARALLEL_DEPENDENCY_CONFLICT | EDGE_CONTRACT_MISSING | ROUTING_UNCERTAIN | REDUCER_CONTRACT_MISSING | FAN_IN_INCOMPLETE | STATE_CONFLICT | PROVENANCE_LOST | SHARED_SNAPSHOT_MISMATCH | IMMUTABLE_FIELD_DRIFT`.

Additional blockers: `SPECIALIST_FINDING_INVALID | CONTRADICTION_UNRESOLVED | OBSERVATION_CYCLE_INCOMPLETE | DECISION_OWNER_MISSING | REVIEW_CAPACITY_EXCEEDED | CONSEQUENTIAL_CHANGE_UNEXPLAINED`.

### Ролі

- Content TZ Agent/owner визначає незалежність branches і володіє merge decision до Production Contract.
- Prompt Agent може паралельно компілювати provider variants лише з одного approved TZ; він не merge-ить нові business claims або invariants.
- AI Creator/Production повертає atomic deltas та receipts; паралельні edits одного region/object заборонені без окремих branches/checkpoints.
- Content Standard Auditor перевіряє merged повний asset/object, а не лише окремі branch outputs.
- Human release owner погоджує partial completion, unresolved conflict exception і release.

### Acceptance tests

1. Зміна order завершення branches дає той самий merged output або explicit `STATE_CONFLICT`.
2. Duplicate evidence/hypothesis не множиться через повторний branch response.
3. Branch іншого SKU/variant/market snapshot блокується як `SHARED_SNAPSHOT_MISMATCH`.
4. Missing/timeout required branch повертає `FAN_IN_INCOMPLETE`.
5. Два branches із contradictory claim або Visual Invariant не проходять automatic merge.
6. Кожний merged item зберігає branch і evidence provenance.
7. Low-confidence narrow route переходить у broader review або `ROUTING_UNCERTAIN`.
8. Parallel route показує вимірюваний benefit проти linear baseline; інакше повертається `PARALLEL_NOT_REQUIRED`.
9. Після fan-in повний Content TZ/asset повторно проходить чинні truth, rights, fidelity, compliance та release gates.
10. `HOLD` або critical contradiction не перекривається більшістю `OK`.
11. Missing required branch повертає `FAN_IN_INCOMPLETE` або named degraded route.
12. Evidence window, коротший за релевантний operational cycle, повертає `OBSERVATION_CYCLE_INCOMPLETE`.
13. Specialist team не приймається без measurable benefit проти one-model/linear baseline.
14. Якщо branches завершуються швидше за linear baseline, але open outputs перевищують review capacity, новий `fan_out` блокується як `REVIEW_CAPACITY_EXCEEDED`; throughput оцінюється за прийнятими, а не згенерованими assets.
15. Green technical checks не переводять consequential claim/creative change у `READY_FOR_NEXT_GATE`, якщо owner не може пояснити зміну та її evidence; verdict — `CONSEQUENTIAL_CHANGE_UNEXPLAINED`.

### Метрики

Latency/coverage проти linear baseline; open outputs awaiting human review, review wait time, first-pass acceptance, rework та accepted-asset throughput; duplicate/conflict/missing-branch rate; reducer rework; provenance-loss incidents; false-narrow routes; partial-completion approvals; merged-object QA failure; Product Truth/variant/invariant drift після fan-in.

### Межі доказовості

Parallelization не гарантує кращої якості й може збільшити cost, coordination та review burden. Gate не дозволяє autonomous publication, не змінює authority map і не послаблює SKU Passport, Product Truth, rights, claims, Visual Invariants або human release controls.
Review-capacity та explain-back controls перенесені з досвіду AI-assisted coding як робоча гіпотеза для creative production; їхній ефект у цьому конвеєрі потрібно виміряти, а не вважати доведеним.
<!-- AI_DESIGN_PARALLEL_GRAPH_GATE_2026_09_17_END -->

<!-- CREATIVE_PRODUCTION_RUN_CONTRACT_2026_09_19_START -->
<a id="mbr27-route-30"></a>
## 26. Creative Production Run Contract

### Призначення

Перетворити approved Content TZ на відтворюваний production run для MAIN/supporting images, A+, video, advertising/social і seasonal adaptations. Контракт з'єднує чинні Product Truth, reference, prompt, production, QA та experiment gates; він не створює нового агента й не переносить creative-поля до Паспорта SKU.

### Область застосування

Контракт обов'язковий, коли AI Creator генерує або істотно редагує product image/video, коли provider call має окрему вартість, коли asset буде масштабовано на кілька surfaces/SKU/markets або коли output переходить у real pretest/Amazon experiment/publication.

Не застосовувати як окремий великий record до deterministic resize/export без content change; для нього достатньо чинного technical receipt із source asset і output specs.

### Вхідні дані та контракт

```yaml
creative_production_run:
  run_id:
  case_id:
  sku_id:
  variant_id:
  market:
  channel:
  surface: MAIN | SECONDARY | A_PLUS | STORE | VIDEO | AD | SOCIAL
  sku_passport_id:
  sku_passport_version:
  product_reference_pack_version:
  brand_entity_and_kit_versions: []
  content_tz_version:
  visual_hypothesis_id:
  protected_elements: []
  permitted_variables: []
  claims_rights_policy_refs: []
  scene_or_asset_plan: []
  paired_execution_variants: []
  acceptance_criteria: []
  approval_status: REFERENCE_LOCK_BLOCKED | BRIEF_NOT_READY | BRIEF_APPROVED
  provider_model_tool_versions: []
  cost_budget:
  generation_attempts: []
  qa_results: []
  repair_ledger: []
  synthetic_screening:
  human_release_decision:
  experiment_or_publication_ref:
  result: READY_FOR_TEST | REPAIR_REQUIRED | REJECT_PRODUCT_DRIFT | REJECT_CLAIM | REJECT_POLICY | TEST_WIN | TEST_LOSS | INCONCLUSIVE
  owner:
  reviewer:
```

### Правила виконання

1. **Reference lock before generation.** Content TZ Agent переносить із актуального Паспорта SKU лише verified facts і links, фіксує canonical multi-angle `Product Reference Pack` та protected-element map: geometry, proportions, color, material/texture, label/OCR, logo position, kit/quantity, accessories and exclusions. Якщо references конфліктують або не покривають створюваний елемент, статус `REFERENCE_LOCK_BLOCKED` і повернення в контур SKU.
2. **Plan before spend.** До першого cost-bearing provider call Content TZ Agent завершує buyer job/pain/objection, asset purpose, story/hook, claim/evidence, channel/device constraints, shot/scene plan, atomic hypothesis і acceptance criteria. Owner встановлює `BRIEF_APPROVED`; `BRIEF_NOT_READY` блокує Prompt Agent та generation.
3. **Immutable handoff.** Image & Video Prompt Agent компілює manifest і provider-ready variants з однієї approved Content TZ version. Він може вибирати provider/model лише в межах approved capability, policy, rights and cost budget; не змінює Product Truth, hypothesis, protected elements, claims або acceptance criteria. Production implementation використовує allowlisted `Provider Capability Registry` з current callable schema, mode, limits, reference policy, primary/fallback role і verification time; provider-neutral brief відокремлений від provider adapter.
4. **Paired execution variants.** Один approved `scenario_id` може мати `LIVE_ACTION_PHOTO` разом із `GENERATIVE_IMAGE` та/або `HYBRID_COMPOSITE`, а також `LIVE_ACTION_VIDEO` разом із `GENERATIVE_VIDEO`. Live-action route залишається у Content TZ/production handoff; Prompt Agent компілює лише AI route й посилається на counterpart. Генеративний варіант створюється, коли очікувано підвищує якість або ясність цінності, але не отримує автоматичної переваги до visual QA.
4.1. **Real-process evidence before generated before/after.** Для result-oriented comparison Content TZ Agent спочатку виконує `REAL_PROCESS_EVIDENCE_GATE` по всьому exact-SKU `product_root`, включно з відео та витягнутими кадрами. Primary proof будується як `BEFORE -> PRODUCT_IN_OPERATION -> AFTER`; робочий стан має показувати видимий контакт/прохід процесу. Якщо придатний реальний process asset знайдено, його omission або заміна повністю генеративною парою дає `REWORK_REAL_PROCESS_EVIDENCE_OMITTED` і блокує Prompt Agent. Генеративний fallback дозволений лише після документованого `REAL_PROCESS_EVIDENCE_UNAVAILABLE`, отримує `ILLUSTRATIVE_VALUE_VISUAL` і не видається за observed result.

4.1.1. **Four-gate process proof.** `REAL_PROCESS_EVIDENCE_CONTRACT` проходить `PROCESS_SOURCE_CONTINUITY_GATE → PRODUCT_ACTION_CONTACT_GATE → PROCESS_PROVIDER_PAYLOAD_GATE → PROCESS_OUTPUT_QA_GATE`. Перші два формуються в Content TZ, третій перевіряє sealed execution inputs, четвертий — фактичний output. Contract зберігає session/surface/target-area identity, три exact state locators/hashes, chronology, visible working element/contact/effect path/state change та binding до `TARGET_SOURCE_ROUTE_RECEIPT`. Будь-який failed або missing gate виключає `OBSERVED_PRODUCT_RESULT`.
4.2. **Target-specific real-action reuse.** Для кожного asset, що показує продукт у роботі, Content TZ і Prompt Agent виконують окремий `REAL_ACTION_REUSE_GATE`. Image Collector `production_reference_index.json` та весь product root зіставляються з exact target roles; `COMPLETE_PRODUCT_ROOT` не замінює `COMPLETE_TARGET_RELEVANCE`. Наявний exact-SKU action/connection/accessory candidate прив'язується як `REAL_CAPTURE | HYBRID_COMPOSITE | REFERENCE_CONDITIONED_GENERATION`; pure generation без reason-coded unavailability дає `REWORK_REAL_ACTION_REFERENCE_OMITTED`.

4.2.0. **Universal target-source signal route.** Для кожного `expected_asset_id` Content TZ створює `TARGET_SOURCE_ROUTE_RECEIPT` v2. Кожний selected source має `MEDIA_GENERATION_ASSESSMENT`, що фіксує useful signal, `generation_mode`, `preserve`, `regenerate` і `required_transformations`. Route може комбінувати product/detail/pose/motion/angle/composition references або використовувати `GENERATE_WITHOUT_MEDIA_REFERENCE`; доказове відхилення попередніх reuse-рівнів не потрібне. `route_lock_id`, receipt SHA-256 і signal-role boundaries незмінно проходять через Prompt Package, sealed execution record і QA. Prompt Agent та AI Creator не переобирають Product Truth або preserve/regenerate semantics. QA звіряє фактичні source IDs, signal roles і output lineage. `TARGET_SOURCE_ROUTE_RECEIPT_MISSING`, `PRODUCT_TRUTH_INSUFFICIENT`, `TARGET_DESCRIPTION_INSUFFICIENT`, `USEFUL_SIGNAL_UNCLASSIFIED`, `PRODUCT_TRUTH_CONFLICT_NOT_ISOLATED`, `ROUTE_BINDING_MISMATCH` або `ROUTE_EXECUTION_ORIGIN_MISMATCH` блокують downstream readiness.
4.2.1. **Person transformation for production derivatives.** Якщо real-action source містить людину, source original не змінюється, але production derivative має змінити обличчя та одяг, не відтворювати source identity/distinctive marks і зберегти exact product, connection/accessory chain, дію, позу/ергономіку, safety direction та доказову композицію. Prompt Package, AI Creator execution record і QA handoff містять `person_identity_transformation_contract/check`; невиконання дає `REWORK_PERSON_IDENTITY_NOT_TRANSFORMED`.

4.2.2. **Third-party IP neutrality.** Застосовується canonical `AI Design Conveyor/09_Shared_Contracts/Runtime/third_party_ip_neutralization/THIRD_PARTY_IP_NEUTRALIZATION_EVIDENCE_CONTRACT.md`. У production derivative дозволено branding лише рекламованого exact SKU. Кожний інший commercial object отримує stable `element_id`, source/output locator, detected cues і route `REMOVE | MASK | REPLACE_WITH_GENERIC | REDESIGN_TO_NON_DISTINCTIVE | GENERIC_NO_ACTION`; рекламований exact SKU отримує `PRESERVE_ADVERTISED_PRODUCT` і protected regions. Badge removal без нейтралізації signature lights/grille/body/package/interface не проходить. Для video inventory і QA охоплюють усі relevant ranges/timecodes. Чотири незалежні gates — `THIRD_PARTY_IP_CONTENT_TZ_GATE → THIRD_PARTY_IP_PROMPT_COMPILATION_GATE → THIRD_PARTY_IP_PROVIDER_PAYLOAD_GATE → THIRD_PARTY_IP_OUTPUT_QA_GATE`; upstream PASS не замінює downstream evidence. Missing inventory/binding, залишкова впізнаваність або пошкодження advertised product дають reason-coded rework affected asset, але не автоматичний block усього SKU. Це visual-production control, не юридичний висновок і не publication-rights gate.

4.2.2a. **Rights boundary outside generation.** `rights_status`, license data і reactive claims registry є metadata для окремого legal/publication process. Вони не беруть участі в routing, Prompt compilation, generation/edit/hybrid/composite або production QA і не можуть вилучати source із generation inputs. AI Design фіксує лише потрібні visual transformations; це не є legal clearance і не дозволяє publication.

4.2.2b. **Pilot exception envelope.** Разове відхилення застосовується лише за canonical `AI Design Conveyor/09_Shared_Contracts/Runtime/pilot_exception_envelope/PILOT_EXCEPTION_ENVELOPE_CONTRACT.md` до одного `run_id + expected_asset_id + field_id`. Воно не змінює global standard або factual QA verdict: дозволена лише disposition `ACCEPTED_FOR_BOUNDED_PILOT_WITH_KNOWN_DEFECT`. Numeric prominence exception не скасовує mobile readability, focus, hierarchy, crop і role match. Person identity transformation, Product Truth, safety, channel hard rules, mandatory deliverables, third-party IP та evidence/lineage не підлягають exception. Generic agents/validators не містять SKU/run-specific branches.

4.2.3. **Connection dependency completeness.** Для connection/setup/assembly/configuration asset застосовується canonical `AI Design Conveyor/09_Shared_Contracts/Runtime/connection_dependency/CONNECTION_DEPENDENCY_EVIDENCE_CONTRACT.md` і розрізняються `ATOMIC_CONNECTION_STEP` та `READY_CONFIGURATION`. Ready state потребує directed end-to-end graph усіх застосовних nodes/edges від source/input через product inlet/outlet до hose/tool/working endpoint; atomic state має лише `STEP_ONLY`. Кожний required node/edge отримує source evidence, фактичний provider input і output locator. Чотири незалежні gates — `CONNECTION_CONTENT_TZ_GATE → CONNECTION_PROMPT_COMPILATION_GATE → CONNECTION_PROVIDER_PAYLOAD_GATE → CONNECTION_OUTPUT_QA_GATE`; upstream PASS не замінює downstream proof. Unknown node, disconnected path, missing evidence/payload, dangling connector або overclaim дають reason-coded `REWORK_*`. Якщо один call ненадійний, використовуються sub-assets і deterministic assembly без пропуску graph elements.

4.2.3a. **Connection interface focus.** Для detail panel/segment застосовується canonical `AI Design Conveyor/09_Shared_Contracts/Runtime/connection_interface_focus/CONNECTION_INTERFACE_FOCUS_EVIDENCE_CONTRACT.md`. Exact connector/adapter та дія `align → attach → lock` є primary subject із target 55–80%; hands supporting only, face/torso/full-body і competing whole-product framing заборонені. Orientation, contact point, attachment motion, locked state, parent overview і mobile preview проходять окремі checks через `CONTENT_TZ → PROMPT_COMPILATION → PROVIDER_PAYLOAD → OUTPUT_QA`. Full product visibility не є вимогою detail proof.

4.2.3.1. **Connection communication completeness.** Застосовується canonical `AI Design Conveyor/09_Shared_Contracts/Runtime/connection_communication/CONNECTION_COMMUNICATION_EVIDENCE_CONTRACT.md`. Фізична повнота graph не є доказом зрозумілості. Content TZ фіксує buyer question, intended message, prohibited interpretations, scope, direction, endpoints, overview/detail hierarchy, exact panel roles/order, connector identity та `LOCKED_SEMANTICS`. Сквозний `semantic_transmission_ledger` зв'язує source pointer/value → compiled value/clause → provider binding → output locator. Чотири gates: `CONNECTION_COMMUNICATION_CONTENT_TZ_GATE → CONNECTION_COMMUNICATION_PROMPT_COMPILATION_GATE → CONNECTION_COMMUNICATION_PROVIDER_PAYLOAD_GATE → CONNECTION_COMMUNICATION_OUTPUT_QA_GATE`. Prompt Agent і AI Creator змінюють лише `ADAPTABLE_EXECUTION`; endpoint substitution, direction reversal, panel-role/order drift або інша зміна meaning блокують PASS. `VERIFIED_OFF_FRAME` не закриває communication; технічно правдоподібний, але незрозумілий output отримує `REWORK_CONNECTION_COMMUNICATION_INCOMPLETE`.
4.2. **Dominant `AFTER` result.** У result-oriented asset стан `AFTER` має показувати цільовий результат як головний об'єкт: не менше 50% відповідної панелі/кадру, production target 55–70%, різкість, background separation і читабельність без тексту. Repair order: інший реальний frame → crop/reframe → disclosed `GENERATIVE_RESULT_VISIBILITY_RETOUCH`. Генеративна delta не змінює geometry/material/perspective/lighting/objects, має `ILLUSTRATIVE_VALUE_VISUAL` і не доводить точну площу, ступінь або швидкість результату. Невиконання minimum дає `REWORK_AFTER_RESULT_NOT_DOMINANT`.

4.2.1. **Multi-signal result dominance.** `RESULT_DOMINANCE_CONTRACT` розділяє `AREA_RESULT_PRIMARY` і `LOCAL_RESULT_PRIMARY` та перевіряє `GEOMETRIC_DOMINANCE`, `FOCUS_DOMINANCE`, `TONAL_COLOR_SEPARATION`, `DISTRACTION_CONTROL`, continuity і `TEMPORAL_DOMINANCE`. Велика панель не проходить, якщо actual result region малий, blurred, background або competed. Selective color/blur/generated shadow/unequal grading не можуть підсилювати evidence semantics. Для video action передує result, а readable stable hold має production target 1.5–3.0 s.

4.2.2. **Professional visual craft layer.** Після evidence planning і до creation кожний key asset отримує `ART_DIRECTION`, `LIGHTING_AND_MATERIAL`, `COMPOSITION_AND_FOCUS`, `COLOR_PIPELINE` та applicable `MOTION_EDIT_SOUND` contracts за shared `PROFESSIONAL_VISUAL_CRAFT_STANDARD`. Після technical/evidence QA виконується окремий Creative Craft QA за 10 dimensions з minimum 7/10 кожний. Artistic score не компенсує failed Product Truth, evidence, safety або channel invariant.
4.2.3. **Visual production architecture.** Content TZ створює set-level coverage над frozen `EXPECTED_DELIVERABLES_MANIFEST`, який до handoff має пройти schema validation і semantic `EXPECTED_DELIVERABLES_MANIFEST_GATE`: unique expected IDs, declared locales, exact mandatory/optional/per-locale/per-media totals і silent-deletion control. Manifest є єдиним count authority. Set architecture додає stable roles, buyer questions, proof units, sequence і dependencies без другого count authority. Після `TARGET_SOURCE_ROUTE_RECEIPT` кожний source отримує explicit `IDENTITY | ACTION | COMPOSITION | STYLE | DETAIL` reference roles; quality gate не змінює route lock. Prompt Agent компілює 12-part `SCENE_DESCRIPTION_GRAMMAR`, а AI Creator зберігає color-managed `MASTER → channel exports` lineage. Creative variant дозволений лише як окремий registered expected asset з однією declared variable. Canonical contract: `AI Design Conveyor/09_Shared_Contracts/Runtime/visual_production_architecture/VISUAL_PRODUCTION_ARCHITECTURE_STANDARD.md`.
4.3. **Universal spatial-value proof.** Для будь-якої value, що залежить від length/reach/coverage/radius/remote access/work-without-moving-base, застосовується canonical `SPATIAL_VALUE_EVIDENCE_CONTRACT` із `AI Design Conveyor/09_Shared_Contracts/Runtime/spatial_value_evidence/`: `BASE_POINT -> VISIBLE_CONNECTION_OR_PATH -> REMOTE_ACTION_POINT -> PRACTICAL_OUTCOME` плюс representation mode, scale cue, continuity, text-independent readability, numeric authority та route lock. Contract проходить окремі `CONTENT_TZ → PROMPT_COMPILATION → PROVIDER_PAYLOAD → OUTPUT_QA` gates; наявність полів не дорівнює виконанню. Scene objects обираються за JBTD/категорією; автомобіль, тераса, фасад тощо є прикладами, не стандартом. Numeric label, decorative arrow, coiled connection element або empty distance не замінюють visual proof. Generated scene має `ILLUSTRATIVE_VALUE_VISUAL`; відсутність доказової моделі дає `REWORK_SPATIAL_VALUE_NOT_PROVEN`.
5. **Production-reference use і publication clearance.** Усі фото й відео в exact-SKU `product_root` дозволені для внутрішнього production use, включно з provider reference input, conditioning, image-to-image, image-to-video, editing, compositing, montage і QA. Кожний reference зберігає path, SHA-256, source/asset ID та target binding. Publication clearance перевіряється окремо перед release і не блокує Prompt Agent або AI Creator.
6. **Generation lineage.** Кожний attempt зберігає asset/scene ID, source references, prompt/template/skill version, provider/model/tool version, seed/parameters where available, cost, started/completed time і output locator. Generated output не стає новим canonical product reference.
7. **Targeted repair.** Visual Fidelity QA або narrative QA створює repair item з asset/timecode/region, defect, invariant at risk, permitted delta, repair method, before/after evidence і recheck result. Локальний дефект ремонтується локально; full regeneration потребує reason code `STRUCTURAL_FAILURE | MULTIPLE_INTERACTING_DEFECTS | REFERENCE_RESET | PROVIDER_INCOMPATIBLE`.
8. **Layered validation.** Порядок: technical/channel checks → product/brand/claim fidelity → narrative/use-sequence continuity → bounded synthetic buyer screening → human release decision → real pretest/Amazon experiment/live signal. Synthetic feedback генерує clarity/objection hypotheses, але не присвоює `TEST_WIN` і не замінює реальний тест.
9. **Variant family.** MAIN, secondary, A+, mobile/desktop, video та seasonal variants посилаються на той самий approved manifest і originals. Seasonal scene/style може змінюватися лише на дозволеній surface; product, label, color hierarchy, kit і compatibility залишаються invariant. MAIN не успадковує дозволи supporting image.
10. **Learning closure.** Experiment Analyst зберігає hypothesis, atomic delta, QA/repair history, cost, audience/query/surface, result і applicability. `TEST_WIN` не оновлює Product Truth або Marketing Book автоматично; proposed learning проходить чинний контур 4.

### Ролі та відповідальність

- Паспорт SKU і Product Truth Verifier залишаються authoritative для facts; вони не керують creative execution.
- Content TZ Agent створює reference lock, brief і acceptance criteria та повертає blockers до правильного owner.
- Image & Video Prompt Agent компілює immutable execution package.
- AI Creator виконує bounded generation/repair і повертає lineage receipts.
- DaVinci Resolve або інший запис із Production Tool Registry виконує live-action edit, generative assembly, Fusion/compositing, color, audio, localization, export і visual QA; він не вважається generative provider без окремого capability record.
- Content Standard Auditor незалежно перевіряє fidelity, claims, policy та buyer expectation.
- Process owner затверджує brief і final release; Experiment Analyst визначає лише experiment result.

### Стани та блокери

Основні стани: `REFERENCE_LOCK_PENDING | REFERENCE_LOCK_BLOCKED | BRIEF_NOT_READY | BRIEF_APPROVED | GENERATING | QA_PENDING | REPAIR_REQUIRED | READY_FOR_TEST | TEST_RUNNING | TEST_WIN | TEST_LOSS | INCONCLUSIVE | RELEASED | RETIRED`.

Blockers: `PASSPORT_VERSION_MISSING | REFERENCE_CONFLICT | PROTECTED_ELEMENT_UNDEFINED | CLAIM_UNVERIFIED | RIGHTS_UNRESOLVED | CHANNEL_RULE_STALE | COST_BUDGET_MISSING | PROVIDER_OUT_OF_SCOPE | PRODUCT_DRIFT | REPAIR_NOT_RECHECKED | HUMAN_RELEASE_MISSING`.

### Acceptance tests

1. Brief без approved SKU Passport/reference versions не запускає provider call.
2. Label, geometry, quantity/kit, product color або included accessories drift повертає `REJECT_PRODUCT_DRIFT` до будь-якого preference test.
3. Prompt Agent не змінює protected elements або hypothesis навіть якщо provider потребує інший syntax.
4. Новий creative concept починається з original references, а не з останнього generated output.
5. Локальний three-second video defect має timecoded repair та before/after recheck.
6. Synthetic panel може повернути `REPAIR_REQUIRED`, але не `TEST_WIN`.
7. Provider/model/skill change видимий у lineage й запускає релевантні regression checks.
8. Seasonal supporting variant не змінює product facts і не застосовує supporting-image allowances до MAIN.
9. Market result простежується до run, approved hypothesis, atomic delta, cost і evidence window.
10. Retry/duplicate request не створює другий uncontrolled run для того самого `run_id`.
11. Paired live-action та AI variants мають один `scenario_id`, незмінні intent/claims/criteria і окремі execution receipts.
12. `HYBRID_COMPOSITE`, image-to-image та image-to-video fail-closed лише без exact-SKU product-root path/SHA-256 або без технічної підтримки provider. Неперевірений publication clearance не блокує production request, але блокує release.
13. Provider adapter без `ACTIVE` або допустимого `LIMITED` registry record і current callable schema повертає `PROVIDER_CAPABILITY_UNVERIFIED`.
14. DaVinci execution receipt містить tool version, project/timeline ID, input/output hashes, applied operations і export preset; відсутність receipt не дозволяє назвати postproduction route відтворюваним.

### Метрики

Reference-lock failure; brief-ready rate; provider calls before approval; attempts per approved asset; first-pass QA; product-drift rejection; targeted-repair success; full-regeneration rate/reason; cost per approved effective asset; time to `READY_FOR_TEST`; synthetic-to-real issue agreement; test win/loss/inconclusive; post-publication defect; reusable manifest/skill coverage.

### Межі доказовості

Контракт використовує practitioner workflow із webinar/demo як operational pattern, а не як доказ універсальної швидкості, ціни або conversion lift. Provider/model/MCP capabilities і costs перевіряються перед використанням. AI self-review та synthetic buyer feedback є defect-discovery layers; performance decision потребує real-user/market evidence. Джерело БЗ: `C:\Users\ystep\Documents\Агенти и база знаний\knowledge_base_brand_marketing\source_register\2026-09-19__youtube-amazon-ai-creative-production-run__done.md`.
<!-- CREATIVE_PRODUCTION_RUN_CONTRACT_2026_09_19_END -->

<!-- AI_DESIGN_HANDOFF_INTEGRITY_GATE_2026_09_19_START -->
<a id="mbr27-route-31"></a>
## 27. AI Design Handoff Integrity and Authorized Asset Transfer Gate

### Призначення

Захистити Product Truth, SKU references, claims, unpublished creative assets і execution authority, коли Content TZ, Prompt Agent, AI Creator, Auditor або parallel branches передають context/файли чи продовжують роботу після compaction. Gate доповнює `Immutable handoff`: self-authored summary не може змінити approved brief або приховати дефект заради завершеного asset.

### Область застосування

Gate обов'язковий для compaction/memory/checkpoint, agent-to-agent handoff, parallel fan-out/fan-in, передачі source/generated assets, provider credentials, external editor/MCP і будь-якого збою approved file channel.

### Вхідні дані та контракт

```yaml
ai_design_handoff_integrity:
  run_id:
  asset_or_scene_ids: []
  source_agent_or_context:
  receiver:
  approved_content_tz_ref:
  approved_content_tz_hash_or_version:
  sku_passport_ref:
  product_reference_pack_ref:
  authority_map_ref:
  handoff_ref:
  handoff_hash_or_version:
  brief_and_product_truth_match: true | false | unclear
  authority_delta_detected: false
  missing_or_substituted_references: []
  failed_or_skipped_checks: []
  synthetic_or_estimated_elements: []
  approved_transfer_channel:
  channel_status: AVAILABLE | BLOCKED | DEGRADED
  egress_or_credential_attempts: []
  blockers: []
  verdict: HANDOFF_ACCEPTED | HANDOFF_REVIEW | HANDOFF_TAMPERED | UNAUTHORIZED_EGRESS | CREDENTIAL_MISUSE | BLOCKED_APPROVED_CHANNEL | MISALIGNMENT_HOLD
  reviewer:
```

### Правила виконання

1. Receiver звіряє handoff із approved Content TZ version/hash, SKU Passport, Product Reference Pack, claims/rights, protected elements, hypothesis і authority map. Summary не є джерелом нових product facts або permissions.
2. Missing reference, cached/incorrect source version, provider limitation, failed/skipped check, substituted asset, synthetic/estimated element, partial completion і unresolved visual/claim defect передаються явно. Інструкція приховати mismatch або показати тільки finished asset дає `MISALIGNMENT_HOLD`.
3. Дозволені способи передачі: canonical project path, approved shared storage/repository або інший named channel у run contract. Якщо receiver не бачить файл, повертається `BLOCKED_APPROVED_CHANNEL`; public/temporary upload, personal cloud або covert cache заборонені без нового owner approval.
4. Provider/API credentials мають бути explicitly provided або allowlisted для цього run/scope. Prompt Agent, Creator чи branch не шукає exposed keys, не реєструє disposable account і не приймає terms від імені owner.
5. Public або external egress дозволений лише коли destination, asset classification, rights/privacy basis, purpose, retention і owner approval зафіксовані до tool call. Correct output не компенсує unauthorized egress.
6. Content Standard Auditor перевіряє handoff/trajectory разом із final asset: reference lineage, substitutions, provider/tool calls, egress, credentials і version match. Privileged/egress actions та всі continuity artifacts перевіряються повністю.

### Ролі та відповідальність

- Content TZ Agent фіксує immutable brief baseline і всі disclosure items.
- Prompt Agent компілює provider-ready package без зміни authority/Product Truth і повертає channel blocker.
- AI Creator не створює новий transfer route або credential source.
- Content Standard Auditor незалежно перевіряє integrity receipt і trajectory.
- Process owner дозволяє exception channel/egress і володіє containment/release decision.

### Стани та блокери

- `HANDOFF_TAMPERED` — handoff не збігається з approved brief/Product Truth або містить unsupported instruction.
- `UNAUTHORIZED_EGRESS` — спроба/факт передачі asset у непогоджене зовнішнє місце.
- `CREDENTIAL_MISUSE` — credential не наданий/не allowlisted або використаний поза scope.
- `BLOCKED_APPROVED_CHANNEL` — погоджений канал недоступний; потрібен owner-selected recovery.
- `MISALIGNMENT_HOLD` — приховування, fabricated claim/asset provenance або permission expansion.

Будь-який із цих blockers забороняє `READY_FOR_NEXT_GATE`, `READY_FOR_TEST`, `READY_FOR_RELEASE`, publication і experiment launch.

### Acceptance tests

1. Content TZ/summary не може замінити відсутню SKU reference «правдоподібним» описом.
2. Cached reference з іншою version label позначається mismatch і не приховується у final handoff.
3. Branch створив asset, але shared path недоступний: public upload не виконується, повертається `BLOCKED_APPROVED_CHANNEL`.
4. Provider потребує credential, якого немає: exposed key/disposable signup не використовується.
5. Handoff намагається змінити protected element, claim або publication permission: `HANDOFF_TAMPERED`.
6. Final asset проходить visual QA, але trajectory містить unauthorized egress: release блокується.
7. Approved exception містить destination, scope, asset classification, retention, owner і audit evidence.

### Метрики

Handoff review/tamper rate; undisclosed reference/substitution rate; blocked versus completed unauthorized egress; credential-policy violations; channel-block recovery time; continuity-artifact coverage; incidents escaping final-asset review; time-to-contain.

### Межі доказовості

Контроль є preventative adaptation окремих OpenAI training/evaluation incidents; він не означає, що такі інциденти вже відбувалися у цьому pipeline. Gate не змінює SKU Passport, Product Truth, rights, claims або human release authority і не дозволяє autonomous publication. Джерело БЗ: `C:\Users\ystep\Documents\Агенти и база знаний\knowledge_base_ai_solution_architecture\source_register\2026-09-19__openai-model-misalignment-reports__done.md`.
<!-- AI_DESIGN_HANDOFF_INTEGRITY_GATE_2026_09_19_END -->

<!-- SYNTHETIC_FEEDBACK_LOOP_PROVENANCE_GATE_2026_09_20_START -->
<a id="mbr27-route-32"></a>
## 28. Synthetic Feedback Loop and Corpus Provenance Gate

### Призначення

Не дозволяти generated copy, images, video, summaries, personas, prompts або synthetic test responses непомітно ставати Product Truth, evidence про покупця чи неконтрольованим training/evaluation corpus. Gate застосовується до повторного використання AI outputs у research library, prompt examples, fine-tuning dataset, evaluation set, agent memory, templates або наступному generation cycle.

### Вхідний контракт

~~~yaml
synthetic_asset_lineage:
  asset_or_row_id:
  sku_and_variant:
  source_type: REAL_OBSERVED | PRODUCT_TRUTH_DERIVED | SYNTHETIC | EDITED_SYNTHETIC
  source_refs: []
  sku_passport_snapshot_ref:
  product_truth_binding_ref:
  generator_model_and_version:
  prompt_or_schema_version:
  parent_asset_ids: []
  human_edits_or_validation:
  dedup_or_near_duplicate_cluster:
  rare_constraint_coverage: []
  rights_and_licence_status:
  intended_use: PRODUCTION_CANDIDATE | PROMPT_EXAMPLE | TRAINING | EVALUATION | RESEARCH_ONLY
  real_world_anchor_ref:
  validation_status:
  train_eval_eligibility:
  expiry_or_recheck_trigger:
  owner:
  verdict: ELIGIBLE | RESTRICTED | REVALIDATE | SYNTHETIC_LINEAGE_HOLD
~~~

### Правила виконання

1. Product Truth і SKU Passport залишаються real/authorized anchors. Generated output може запропонувати clarification або hypothesis, але не створює новий product fact, buyer evidence, claim, right чи winner status.
2. Кожний reused AI output зберігає generator/model version, parent assets, source bindings, human changes, rights, intended use та validation status. Втрата lineage дає `SYNTHETIC_LINEAGE_HOLD`.
3. Raw кількість generated assets/rows не вважається приростом evidence або dataset value. Перед reuse перевіряються effective novelty, near-duplicates, coverage gaps, rare SKU constraints, visual/claim invariants і unsupported assumptions.
4. Похідні одного source/asset cluster не розподіляються між training та evaluation. Synthetic evaluation не замінює observed production defects, real-user/market tests або Product Truth verification.
5. Synthetic persona, buyer panel або model self-review використовується тільки для defect discovery і hypothesis generation. Воно не доводить buyer demand, conversion, comprehension чи preference.
6. Повторне покоління на основі попередніх AI outputs потребує explicit real-world anchor і drift comparison до approved baseline. Якщо tails, variants або protected constraints зникають, цикл зупиняється.
7. Fine-tuning або corpus expansion проходить окремий marginal-return review: current model+harness baseline, bounded scale points, quality gain, cost, critical slices і downstream outcome. Scaling-law claim не замінює local evaluation.

### Стани та блокери

- `SYNTHETIC_LINEAGE_HOLD` — немає provenance, parent/source binding або дозволеного intended use.
- `PRODUCT_TRUTH_CONTAMINATION` — generated content подано як факт SKU/claim/evidence.
- `TRAIN_EVAL_LINEAGE_LEAK` — споріднені assets/rows потрапили в різні splits.
- `REAL_ANCHOR_MISSING` — recursive generation не має Product Truth, observed або approved reference anchor.
- `NOVELTY_UNVERIFIED` — corpus/portfolio збільшено без dedup і effective-coverage оцінки.

Будь-який blocker забороняє promotion у active prompt library, training/evaluation dataset, reusable template, Product Truth, `READY_FOR_TEST` або `READY_FOR_RELEASE`.

### Acceptance tests

1. AI-generated lifestyle image не стає reference доказом невидимої геометрії продукту.
2. Synthetic buyer panel повертає позитивну оцінку, але відсутній real-user test: winner status заборонено.
3. Кілька prompt variants походять від одного Product Truth fragment: cluster не ділиться між train та eval.
4. Generated copy повторно використовується після втрати model/prompt/source lineage: `SYNTHETIC_LINEAGE_HOLD`.
5. Новий corpus має більше rows, але високу near-duplicate rate і гірше покриває rare SKU constraints: scale відхиляється.
6. Edited-synthetic asset з human approval зберігає synthetic lineage; approval не перетворює його на real observation.
7. Model/provider change запускає recheck critical invariants і representative slices до reuse.

### Метрики

Lineage completeness; synthetic/edited-synthetic/real mix; near-duplicate rate; Product Truth contamination incidents; train/eval cluster leakage; rare-constraint coverage; real-only defect detection; synthetic-to-real agreement; rejected/revalidated rows; marginal quality gain and cost per approved reusable asset.

### Межі доказовості

Gate не стверджує, що synthetic data або AI-generated assets завжди погіршують результат. Він контролює recursive reuse, provenance, leakage і втрату рідкісних constraints. Scaling-law exponents і заявлені відсотки improvement не переносяться в цей pipeline без локального paired evaluation. Product Truth Verifier, Content Standard Auditor і human release authority залишаються чинними.
<!-- SYNTHETIC_FEEDBACK_LOOP_PROVENANCE_GATE_2026_09_20_END -->

<!-- AI_DESIGN_TRANSITION_REENTRY_RECEIPT_LAI178_START -->
<a id="mbr27-route-33"></a>
## 29. AI Design Transition and Re-entry Receipt

### Призначення

Зберігати робочий стан під час переходів `research → brief → generation → review`, щоб новий етап або виконавець не відновлював контекст з пам'яті й не повторював вже перевірену роботу.

### Область застосування

Receipt обов'язковий при паузі, blocker-і, зміні owner-а або етапу, compaction/context reset та дорогому перемиканні когнітивного режиму. Він не потрібний для оборотних мікрокроків у межах одного етапу.

```yaml
ai_design_transition_receipt:
  run_id:
  from_stage:
  to_stage:
  cognitive_mode_from:
  cognitive_mode_to:
  current_state:
  last_verified_output:
  open_loop:
  next_decision_or_action:
  artifact_pointer:
  protected_context_refs: []
  assumptions: []
  blocker:
  restart_condition:
  owner:
  updated_at:
  verdict:
```

### Правила виконання

- `artifact_pointer` посилається на чинний brief, SKU passport, source pack, prompt/version або review artifact; receipt не дублює їхній зміст.
- Product Truth, provenance, дозволи, credentials та transfer-channel controls залишаються в `AI Design Handoff Integrity and Authorized Asset Transfer Gate`; цей receipt лише зв'язує робочий стан з відповідним `ai_design_handoff_integrity` record.
- Receiver звіряє `current_state`, `last_verified_output`, `open_loop`, `artifact_pointer` і `restart_condition` до початку роботи.
- Допустимі вердикти: `TRANSITION_READY | HANDOFF_ACCEPTED | REENTRY_CONTEXT_MISSING | MODE_SWITCH_AVOIDABLE`.
- `REENTRY_CONTEXT_MISSING` блокує перехід; `MODE_SWITCH_AVOIDABLE` фіксує зайве перемикання, але не блокує роботу автоматично.

### Acceptance tests

1. Відновлення після паузи починається з останнього валідованого артефакту, а не з повторного research.
2. Reviewer отримує чинний brief/SKU passport і явний open loop.
3. Застарілий або неправильний `artifact_pointer` дає `REENTRY_CONTEXT_MISSING`.
4. Зміна Product Truth під час паузи повертає кейс на відповідний upstream stage.
5. Повторний handoff з тим самим `run_id` не створює другу незалежну версію роботи.

### Метрики

`restart_latency`, `context_reconstruction_rate`, `duplicate_work_rate`, `wrong_state_start_rate`, `downstream_rework_due_to_context_loss`.

### Межі доказовості

Receipt зменшує втрати контексту й полегшує відновлення, але сам по собі не доводить вищу креативну якість, точність Product Truth або причинний вплив на conversion.
<!-- AI_DESIGN_TRANSITION_REENTRY_RECEIPT_LAI178_END -->

<!-- AI_DESIGN_INTENT_FUNNEL_AND_SKILL_DEPENDENCY_LAI180_181_START -->
<a id="mbr27-route-26-1"></a>
## 30. Intent Transition Funnel Brief

### Призначення

Перед зміною creative, PDP, landing page або checkout message пов'язати проблему не з агрегованим drop-off, а з конкретним переходом customer intent, eligible denominator і перевірюваною friction hypothesis.

```yaml
intent_transition_funnel_brief:
  run_id:
  decision_goal:
  topology: OPEN | CLOSED
  entity_grain:
  identity_rule:
  observation_window:
  from_step:
  to_step:
  intent_before:
  new_commitment:
  eligible_denominator:
  observed_step_conversion:
  segment_cuts: []
  friction_hypotheses: []
  measurement_contract_ref:
  evidence_refs: []
  proposed_atomic_change:
  next_diagnostic_or_test:
  verdict: MEASUREMENT_REPAIR | DIAGNOSE_FRICTION | TEST_CHANGE | EXPECTED_EXIT | NO_ACTION
```

Правила: `Closed` використовується для обов'язкової послідовності, `Open` — для legitimate direct entry. Загальний traffic не є denominator-ом для неeligible користувачів. Friction класифікується як `VALUE_OR_PRICE_SURPRISE | EFFORT | TRUST | SPEED | UNCERTAINTY | ELIGIBILITY | TECHNICAL_FAILURE | MEASUREMENT_DEFECT | EXPECTED_EXIT`. До creative action перевіряються event trust state, sequence, deduplication та missing-step rate. Funnel локалізує розрив, але причина потребує VoC/session evidence, usability diagnosis або controlled test.

Acceptance: brief містить один intent transition і один atomic change; segment leak відтворюється; measurement defect не маскується під behavior; Product Truth і SKU Passport не змінюються через funnel inference.

Метрики: qualified step conversion, qualified drop-off, missing-step rate, measurement-defect share, confirmed friction hypotheses, downstream conversion after tested repair.

### Межі доказовості

Instrumented behavior не доводить мотив або причинність. Benchmark є сигналом для пріоритизації, а не доказом avoidable loss чи майбутнього conversion uplift.

<a id="mbr27-route-34"></a>
## 31. Reusable Skill Dependency Receipt

Reusable creative skill, provider adapter або tool-specific instruction допускається до production run лише як versioned dependency з перевіреним API surface і activation boundary.

```yaml
ai_design_skill_dependency_receipt:
  skill_id:
  skill_version:
  supported_provider_tool_versions: []
  authoritative_sources: []
  api_surface_hash:
  positive_example_result:
  expected_failure_result:
  activation_test_result:
  near_miss_test_result:
  conflict_test_result:
  product_truth_boundary_test:
  owner:
  verified_at:
  invalidation_triggers: []
  status: ACTIVE | STALE | QUARANTINED | RETIRED
```

Skill має фіксувати exact tool/function names, parameters, defaults, outputs/errors, required files, side effects і edge cases. Positive та expected-failure examples виконуються проти заявленої версії. Trigger перевіряється intended, near-miss і negative tasks. Повторна помилка стає regression test, а не лише новим абзацом prompt. Provider/model/schema change, failed example або missing authoritative source переводять dependency у `STALE` чи `QUARANTINED`; silent fallback до model memory заборонений.

Acceptance: production run використовує тільки `ACTIVE` skill; skill не активується на near-miss task; Product Truth boundary test не дозволяє змінити SKU facts; dependency version входить у run manifest і transition receipt.

Метрики: example pass rate, activation precision/recall, near-miss false activation, skill conflict, stale-version execution, invalidation latency, regression prevention.

### Межі доказовості

Receipt не гарантує creative quality або conversion. Він контролює відтворюваність і актуальність інструкції; final creative, Product Truth і market performance залишаються у відповідних незалежних gates.
<!-- AI_DESIGN_INTENT_FUNNEL_AND_SKILL_DEPENDENCY_LAI180_181_END -->

<!-- AI_DESIGN_SEGMENT_CONTRIBUTION_BRIDGE_LAI182_START -->
<a id="mbr27-route-26-2"></a>
## 32. Segment Contribution and Mix-Shift Extension

Цей блок розширює `Intent Transition Funnel Brief` і `Behavior Sequence Analysis Gate`. Він застосовується, коли aggregate conversion, CTR, purchase rate, revenue per visit або інший KPI використовується для creative/PDP/PPC рішення та predefined segment може змінити висновок.

```yaml
segment_contribution_bridge:
  decision_id:
  metric_definition_ref:
  period_or_cohort:
  primary_segment_dimension:
  segment_definition_version:
  rows:
    - segment:
      numerator:
      denominator:
      rate:
      population_weight:
      outcome_contribution:
      uncertainty:
  aggregate_reconciliation:
  mix_effect:
  within_segment_effect:
  unknown_or_other_share:
  multiplicity_status: PRE_SPECIFIED | EXPLORATORY | ADJUSTED
  next_diagnostic_or_test:
  verdict: CREATIVE_TEST_READY | HYPOTHESIS_ONLY | INSUFFICIENT_SUPPORT | MEASUREMENT_REPAIR | NO_ACTION
```

### Правила виконання

- Segment аналізується лише коли різний результат змінює content, offer, placement, audience або budget decision.
- Для кожного сегмента показувати count, numerator, denominator, rate, weight і contribution; відсоток без support не є decision evidence.
- Зміну aggregate KPI розкладати на `mix effect` та `within-segment effect`. Зростання частки low-intent traffic не дає підстав автоматично переробляти PDP або checkout.
- Segment definitions, exclusions, overlaps, `Other/Unknown`, identity rule і observation window мають бути versioned та узгоджені з measurement contract.
- Thin slice або post-hoc multidimensional finding отримує `HYPOTHESIS_ONLY`; production action потребує fresh-data validation чи controlled test.
- Aggregate/segment reversal запускає Simpson-risk review. Segment difference не є доказом причини.

### Acceptance tests і метрики

Weighted segment rates reconcile to aggregate; unknown share visible; mix-shift test не створює false creative defect; unsupported slice не отримує `CREATIVE_TEST_READY`; proposed atomic change називає affected segment і не змінює Product Truth.

Метрики: aggregate reconciliation error, mix-versus-rate attribution coverage, unknown share, thin-slice blocked actions, segment findings validated on fresh data, false redesigns prevented.

### Межі доказовості

Segmentation локалізує heterogeneous behavior, але не відновлює мотив і не доводить causal uplift. Segment thresholds та intervention policy визначаються локальними даними й experiment design.
<!-- AI_DESIGN_SEGMENT_CONTRIBUTION_BRIDGE_LAI182_END -->
<!-- VALUE_TO_PRICE_BRIEF_SCHRAGENHEIM_2026_09_20_START -->
<a id="mbr27-route-35"></a>
## Value-to-Price Brief

### Trigger

Застосовувати, коли content brief, PDP, A+, creative або price framing має пояснити premium, порівняння чи економічну цінність пропозиції. Не використовувати для вигадування Product Truth або автоматичної зміни ціни.

```yaml
value_to_price_brief:
  sku_id:
  segment_and_job:
  customer_limitation:
  current_workaround:
  dominant_value_category: FUNCTIONAL | ECONOMIC | CONVENIENCE | RISK_REDUCTION | EMOTIONAL | SOCIAL
  reference_set: []
  reference_set_evidence: []
  premium_or_saving_claim:
  premium_justification:
  supporting_product_truth_refs: []
  affordability_boundary:
  required_behavior_change:
  trust_barriers: []
  misleading_reference_checks: []
  amazon_price_rule_check:
  field_test:
  verdict: CONTENT_READY | PRICE_EVIDENCE_REQUIRED | PRODUCT_TRUTH_BLOCK | RULE_REVIEW_REQUIRED | NOT_APPLICABLE
```

### Правила виконання

- Premium пояснюється конкретною усуненою limitation і доказаною capability, а не cost-plus або довільним anchor.
- Reference set має відповідати реальному customer choice; false comparison або непідтверджена saving claim блокує release.
- Content використовує лише approved Product Truth refs. WTP, affordability і premium acceptance залишаються hypotheses до польового тесту.
- Amazon reference-price/display rules та price history перевіряються перед publication gate.

### Acceptance tests і метрики

Brief називає segment/job, limitation, reference set, proof, premium logic, trust barrier і test. Перевіряти unsupported-value claims, rule-review blocks, message comprehension, premium acceptance, conversion/margin guardrails і post-test attribution.

### Межі доказовості

Content clarity не доводить willingness to pay або incremental conversion. Цінове рішення залишається за authorized owner і потребує portfolio/channel economics.
<!-- VALUE_TO_PRICE_BRIEF_SCHRAGENHEIM_2026_09_20_END -->

<!-- CAROUSEL_BRIEF_EDITORIAL_BATCH_CONTRACT_LAI184_START -->
<a id="mbr27-route-36"></a>
## Carousel Brief & Editorial Batch Contract

Для `carousel | slideshow` Content TZ Agent створює `Carousel Experiment Card`: audience/job, SKU/bundle, Product Truth version, problem/objection, proof/evidence, окремі `format` і `treatment`, promised slide count, card jobs, Shop CTA/product tag, hypothesis, baseline/observation window і owner.

Content TZ Agent не згортає format і treatment у theme. Carousel Brief Compiler формує `carousel_payload_map`; Prompt Agent компілює лише approved claims/evidence; AI Creator не змінює SKU, claim або count; Content Auditor повертає `BLOCKER | SUGGESTION` і не self-approves asset.

Batch plan формується до render: pillar targets, promotion cap, recent hooks/treatments, SKU/bundle coverage, hashtag rotation і conflict check. Client lifecycle: `GENERATING → DRAFT → APPROVED → PACKAGE_READY → PUBLISHED → OBSERVING`.

Native publish package містить approved cards/version, caption, cover options, SKU/bundle, product-tag instruction, claims/rights/disclosure, measurement reference, audio-selection instruction, owner і publication receipt. Current audio/tag/profile context перевіряє human owner у native app.

Acceptance: promised count дорівнює distinct payload; кожна card має одну job і evidence/claim reference; Product Truth не конфліктує; render не дорівнює approval; account-relative reach не підміняє product clicks/orders/contribution; batch не порушує promotion/rotation constraints.

Evidence boundary: observational TikTok slideshow patterns є hypothesis source, не proven conversion rules або cross-channel benchmark.
<!-- CAROUSEL_BRIEF_EDITORIAL_BATCH_CONTRACT_LAI184_END -->

<!-- COMMENT_CLUSTER_TO_BRIEF_GATE_LAI185_START -->
<a id="mbr27-route-37"></a>
## Comment-Cluster-to-Brief Gate

### Призначення та trigger

Gate застосовується, коли TikTok text/voice/poll/photo/Live Photo comments пропонуються як підстава для нового content TZ, FAQ, reply video, creator script або SKU-angle test. Ізольований comment не входить до brief напряму.

### Обов'язковий handoff до Content TZ Agent

```yaml
validated_comment_cluster_handoff:
  cluster_id:
  source_platform: TIKTOK
  country_marketplace:
  account_creator:
  observation_window:
  parent_content_ids: []
  contribution_ids: []
  independent_contributor_count:
  sku_or_bundle:
  sku_passport_version:
  use_case_or_buyer_job:
  audience_question_objection_or_example:
  evidence_summary:
  verbatim_safe_excerpts: []
  media_descriptions: []
  contradictory_signals: []
  rights_consent_state:
  privacy_safety_moderation_state:
  claim_boundary:
  product_truth_and_claim_refs: []
  target_asset: REPLY_VIDEO | FAQ | CAROUSEL | CREATOR_SCRIPT | OTHER
  atomic_content_hypothesis:
  falsification_question:
  approval_owner:
  source_packet_ref:
  verdict: HOLD | READY_FOR_TZ | ROUTE_TO_SUPPORT | ROUTE_TO_PRODUCT | REJECT
```

`sku_passport_version` є обов'язковим для product-specific asset. Comment може сформулювати question, objection або use-case hypothesis, але не змінює Product Truth, SKU facts, safety guidance чи approved claims.

### Правила виконання

1. Comment Intelligence owner передає лише `CLUSTERED` packet з source refs, rights/privacy/moderation state і selection-bias note.
2. Content TZ Agent звіряє cluster з SKU Passport, Product Truth, approved claims, audience/job і channel objective.
3. `UNKNOWN | DENIED` rights, unresolved sensitive data, safety/failure або misinformation блокують content reuse і маршрутизуються до human owner/support/product.
4. Brief містить одну atomic content hypothesis, expected signal, falsification question, target asset і observation window. Не змішувати hook, format, offer, treatment і paid support без experiment design.
5. Prompt Agent отримує лише approved excerpts/descriptions і claim refs; не отримує необроблені personal data або media без business need.
6. Content Auditor перевіряє provenance, SKU/claim fidelity, rights, privacy, moderation route, parent-to-asset traceability і відсутність prevalence/causal overclaim.
7. Після publication Performance Learning Agent розділяє interaction learning та commerce outcome; comments/views не надають `TEST_WIN` без defined downstream success metric.

### Стани та blockers

`HOLD | READY_FOR_TZ | ROUTE_TO_SUPPORT | ROUTE_TO_PRODUCT | REJECT`.

Blockers: `SOURCE_REF_MISSING | PARENT_CONTENT_MISSING | PRIVACY_SAFETY_REVIEW | MODERATION_UNRESOLVED | SKU_PASSPORT_MISSING | PRODUCT_TRUTH_CONFLICT | UNSUPPORTED_CLAIM | SINGLE_COMMENT_OVERGENERALIZATION | CLUSTER_SUPPORT_INSUFFICIENT | TARGET_ASSET_UNDEFINED`. `RIGHTS_UNKNOWN` може зберігатися як metadata для окремого legal/publication process, але не є blocker AI Design generation cycle.

### Acceptance tests і метрики

- Один comment без recurrence/corroboration може підняти question, але не representative insight → `SINGLE_COMMENT_OVERGENERALIZATION`.
- Product-specific cluster без SKU Passport/version → `SKU_PASSPORT_MISSING`.
- Photo/voice contribution без cleared rights → не потрапляє до generation input.
- Usage failure/safety report → `ROUTE_TO_SUPPORT | ROUTE_TO_PRODUCT`, не creative brief.
- Reply asset покращив qualified comments/saves без product clicks/orders → learning signal, не commerce winner.

Метрики: packets rejected for provenance/rights/privacy; promoted cluster rate; comment-to-brief cycle time; unsupported-claim block rate; parent-to-asset traceability; reply performance versus parent/account baseline; product click/PDP/ATC/order/contribution/return outcomes.

### Межі доказовості

Comment cluster показує observed audience language, question чи example, але не доводить prevalence, segment size, willingness to pay, demand або causal conversion. Будь-який business conclusion потребує local experiment і downstream measurement.
<!-- COMMENT_CLUSTER_TO_BRIEF_GATE_LAI185_END -->

<!-- AMAZON_TOTAL_PRODUCT_QUANTITY_LISTING_PARITY_GATE_2026_09_21_START -->
<a id="mbr27-route-38"></a>
## Amazon Total Product Quantity Listing Parity Gate

### Призначення та trigger

Застосовувати перед створенням/зміною Amazon quantity-based variation, multipack offer або listing content, у якому кількість є buyer-facing promise. Content TZ Agent і Listing owner споживають read-only quantity projection із exact SKU Passport; не встановлюють Product Truth з title, `Size`, image або конкурентного listing.

```yaml
quantity_listing_parity_receipt:
  marketplace:
  product_type:
  listing_id:
  parent_asin:
  child_asin:
  sku_passport_snapshot_id:
  quantity_fact_versions: []
  variation_theme_eligibility:
  total_unit_count:
  unit_type:
  number_of_packs:
  units_per_pack_or_component_manifest:
  pack_reconciliation_state:
  observed_surfaces:
    - surface: STRUCTURED_ATTRIBUTE | TITLE | SIZE | BULLET | IMAGE | A_PLUS | OFFER | PACKAGING | CART
      observed_value:
      locator_or_evidence_ref:
      state: CONSISTENT | CONFLICT | MISSING | NOT_APPLICABLE
  price_per_unit_and_multipack_review:
  unresolved_alert_ids: []
  owner:
  verdict: READY_FOR_LISTING_REVIEW | FACT_REVIEW_REQUIRED | ELIGIBILITY_CHECK_REQUIRED | LISTING_PARITY_BLOCKED | NOT_APPLICABLE
```

### Правила виконання

1. Для exact marketplace/product type перевірити доступність `total product quantity`; тема опційна, тому відсутність theme сама по собі не є дефектом. При виборі theme перевірити чинні вимоги Amazon до `Unit Count` і, для multipack, `Number of Packs`.
2. Зіставити факт `total_unit_count` з кількістю окремих паків і `units_per_pack` або component manifest. `Number of Packs` не дорівнює кількості одиниць усередині коробки.
3. Порівняти verified child facts з Amazon structured attributes, title, `Size`, bullets, images/A+, offer, price-per-unit/multipack logic і фактичною shipped packaging. Не прибирати суперечність лише редагуванням copy, якщо фізична комплектація або canonical fact невідомі.
4. `FACT_REVIEW_REQUIRED` повертає питання в SKU Passport verifier. `ELIGIBILITY_CHECK_REQUIRED` вимагає current product-type/marketplace evidence. `LISTING_PARITY_BLOCKED` зупиняє quantity-dependent publication/migration до усунення конфлікту. Лише Listing owner здійснює marketplace edit після звичайних publication approvals.
5. Якщо quantity fact version змінився, залежні title, images, A+, offer і price-per-unit review отримують `REVALIDATION_REQUIRED` до release.

### Acceptance tests, метрики та межі доказовості

- `Unit Count=180`, три пакети по 60, title обіцяє два пакети → `LISTING_PARITY_BLOCKED`.
- Size містить `pack of 3`, але немає packaging evidence → `FACT_REVIEW_REQUIRED`, не автозаповнення.
- Theme недоступна або невідома для product type → не мігрувати за аналогією з іншою категорією.
- Структуровані поля правильні, але hero image показує іншу кількість → release blocked до asset correction.

Метрики: quantity surface mismatch rate, pack reconciliation failures, unresolved eligibility, `item_not_as_described` returns за релевантним reason code, quantity-related customer questions і dispute evidence completeness. До/після comparison є monitoring, не causal proof. Правильні атрибути не гарантують менше повернень або виграш A-to-z claim; рішення залежить від конкретного order/listing snapshot, shipped pack evidence та чинної політики Amazon.
<!-- AMAZON_TOTAL_PRODUCT_QUANTITY_LISTING_PARITY_GATE_2026_09_21_END -->

<!-- DELAYED_PURCHASE_INTENT_RELEASE_CARD_2026_09_24_START -->
<a id="mbr27-route-39"></a>
## Delayed Purchase Intent Release Card

### Призначення та trigger

Застосовувати перед seasonal/promotion Content TZ, коли команда припускає, що покупець уже обрав SKU/category і чекає на умову для дії. Card не використовується для автоматичного присвоєння buyer type, зміни Product Truth або виправдання глибшого discount.

```yaml
delayed_purchase_intent_release_card:
  card_id:
  sku_passport_snapshot_id:
  sku_category_bundle_scope:
  marketplace_country_channel:
  seasonal_event_and_window:
  formed_intent_evidence_refs: []
  contrary_or_missing_evidence: []
  alternative_explanations: []
  intent_state: INTENT_NOT_FORMED | FORMED_INTENT_HYPOTHESIS | UNKNOWN
  purchase_delay_hypothesis: PERMISSION_OR_OCCASION | PRICE_THRESHOLD | REPLENISHMENT_QUANTITY | COMMITMENT_REVERSIBILITY | DEADLINE_CERTAINTY | VERSION_OBSOLESCENCE | UNKNOWN
  observed_signal_window:
  response_job: EDITORIAL_OCCASION | PRICE_VALUE | BUNDLE_STOCK_UP | EXIT_REASSURANCE | DELIVERY_CERTAINTY | VERSION_COMPARISON
  product_truth_and_claim_refs: []
  content_tz_change:
  offer_or_discount_change:
  fixed_variables: []
  changed_variable:
  baseline_or_holdout:
  evidence_window:
  primary_outcome:
  contribution_retention_return_guardrails: []
  falsification_condition:
  approval_owner:
  verdict: EVIDENCE_INSUFFICIENT | READY_FOR_BOUNDED_TEST | CONFOUNDED | NOT_APPLICABLE | LEARNING_RETAINED
```

### Правила виконання

1. Content TZ Agent створює card лише з versioned SKU Passport/Product Truth і observed pre-period evidence: repeated product views, wishlist/cart age, comparison/search completion, prior purchase/replenishment, gift/occasion, cancellation/commitment або version/upgrade signals.
2. Один checkout, last-click conversion, comment, synthetic audience answer чи category stereotype не доводить motive. Зберігати contrary evidence й alternative explanation; за прогалини ставити `EVIDENCE_INSUFFICIENT`.
3. Класифікація виконується на рівні `SKU/category/bundle × market × channel × window`. Multi-category catalog може мати кілька delay hypotheses; один brand-wide label заборонений.
4. `response_job` є content/offer hypothesis. Він не створює product fact, claim або willingness-to-pay proof. Усі product-specific statements мають exact Passport fact/evidence bindings.
5. Test змінює один decision object: message frame, access rule, reassurance, bundle або discount. Одночасна зміна creative, discount, creator/audience, placement і paid support дає `CONFOUNDED`.
6. Discount depth і offer economics затверджує Finance/Commercial owner. Висока conversion не доводить incrementality; оцінювати contribution, retention/repeat, returns і post-event pull-forward, де можливо — з holdout/comparison.

### Ролі, acceptance tests і межі доказовості

Content TZ Agent формує card і brief; Experiment Analyst перевіряє evidence/test design; SKU owner володіє Product Truth; Finance/Commercial owner — price/offer; human release owner — publication. `READY_FOR_BOUNDED_TEST` потребує scope, formed-intent evidence, alternative explanation, one changed variable, baseline/holdout, guardrails і owner. Synthetic audience patterns залишаються `HYPOTHESIS_ONLY`; вони не доводять prevalence, loyalty, demand або causal lift.
<!-- DELAYED_PURCHASE_INTENT_RELEASE_CARD_2026_09_24_END -->

<!-- SHOPPING_AGENT_SURFACE_TEST_2026_09_24_START -->
<a id="mbr27-route-40"></a>
## Shopping-Agent Surface Test

### Призначення та trigger

Застосовувати, якщо Content Package, Listing/A+ fragment, FAQ, answer block або structured product content призначений для conversational assistant, search overview, related-question surface, PDP Q&A чи іншого agent-facing retrieval. Звичайний статичний listing без такого handoff отримує `NOT_APPLICABLE`.

```yaml
shopping_agent_surface_test:
  test_id:
  sku_passport_snapshot_id:
  content_package_or_asset_ids: []
  surface: SEARCH_OVERVIEW | RELATED_QUESTION | CONVERSATIONAL_ASSISTANT | PDP_QA | OTHER
  marketplace_country_locale:
  query_classes: []
  query_and_conversation_set_version:
  grounded_product_and_evidence_source:
  allowed_product_set: []
  excluded_products_and_reasons: []
  explicit_requirements_to_carry: []
  expected_response_contract:
  context_tool_and_runtime_version_refs: []
  recommendation_defect_taxonomy: []
  human_calibration_set:
  automated_judge_and_version:
  primary_quality_metrics: []
  latency_cost_observations: []
  downstream_outcomes: []
  safety_claim_locale_and_return_guardrails: []
  owner:
  verdict: INPUT_BLOCKED | OFFLINE_TEST_READY | CONTENT_DEFECT | RETRIEVAL_OR_INDEX_DEFECT | PRODUCT_TRUTH_DEFECT | RUNTIME_DEFECT | BOUNDED_SURFACE_READY | NOT_APPLICABLE
```

### Правила виконання

1. Test set включає single-turn і, де застосовно, multi-turn cases із category, intent clarity, buyer requirement і complexity strata. Один демонстраційний prompt не є coverage.
2. Product Truth/SKU Passport є read-only ground. Рекомендація перевіряється на wrong product/SKU/variant, missing requirement, unsupported claim, stale/duplicate item, poor diversity, locale/units/currency error і втрату explicit constraint між turns.
3. Content defect відокремлюється від `RETRIEVAL_OR_INDEX_DEFECT`, `PRODUCT_TRUTH_DEFECT` і `RUNTIME_DEFECT`. Content TZ не переписує Product Truth і не маскує відсутній retrieval/tool/context evidence новим copy.
4. Human reviewer калібрує defect taxonomy та representative set. LLM-as-judge може масштабувати перевірку лише з versioned rubric і measured agreement; він не self-approves publication або surface readiness.
5. Якщо runtime metrics доступні, фіксувати context/tool version, tool hops, TTFT/end-to-end latency і cost. Швидша відповідь із втраченим requirement або unsupported recommendation є regression.
6. Engagement оцінювати разом із completion/accepted recommendation, downstream action, contribution, returns/complaints або іншим локальним outcome. Менше follow-up interactions може означати успішне завершення, а не автоматичний негативний результат.

### Ролі, acceptance tests і межі доказовості

Content TZ Agent створює linked test card і exact content/evidence bindings; Retrieval/Search owner володіє index/product-set defects; SKU owner — Product Truth; Runtime/Agent owner — context/tools/latency; human release owner приймає surface decision. `BOUNDED_SURFACE_READY` потребує versioned Product Truth, representative set, grounded product pool, explicit requirement checks, human-calibrated rubric, defect routing і guardrails. Amazon-reported quality/latency/engagement values не є нашими thresholds або доказом business lift.
<!-- SHOPPING_AGENT_SURFACE_TEST_2026_09_24_END -->

<!-- MB_MESSAGE_MEDIA_2026_09_27_START -->
<a id="mbr27-route-41"></a>
## 33. Керована агентна сесія та writeback

Наскрізний запуск кількох агентів використовує [Agent Session Contract](../../../09_Shared_Contracts/AGENT_SESSION_CONTRACT.md). Інтерфейс розмови не є workflow state: authoritative state зберігають `session_passport`, pinned Product Truth/Marketing Book/context revisions, evidence snapshot, decisions, approvals, handoff і verification receipts.

Передача між Product Truth, Market/Competitor, Positioning, Content TZ, Creator, Auditor, Verifier та Experiment Analyst виконується за [Session Handoff Receipt](../../../09_Shared_Contracts/SESSION_HANDOFF_RECEIPT.md). Висновок попереднього агента не стає доказом; Auditor і Verifier повторно читають джерела, артефакт і acceptance criteria у власній ролі.

Customer, competitor, search, PPC і content signals реєструються в [Differentiation Hypothesis Register](05_Differentiation_Hypothesis_Register.md). Вони не змінюють SKU Passport і не дозволяють claim до проходження evidence review, test design та людського approval.

Будь-яка спроба перенести результат сесії в SKU Passport, Marketing Book, Content TZ або agent instruction проходить [Session-to-Canonical Writeback Gate](../../../09_Shared_Contracts/SESSION_TO_CANONICAL_WRITEBACK_GATE.md). До `PASS` результат має статус `LEARNING_CANDIDATE`, `HYPOTHESIS`, `GAP` або `CONFLICT`; автоматичний canonical write заборонений.

### Acceptance tests

1. Session Passport фіксує exact SKU/model, marketplace/country, business question і pinned revisions.
2. Кожний міжрольовий перехід має receipt і receiver read-back.
3. Product Truth, marketing interpretation, hypothesis, decision і action залишаються різними типами об'єктів.
4. Creator не є єдиним Auditor/Verifier свого результату.
5. External або canonical action має approval, read-back і audit trail.
6. Session memory не використовується в іншій сесії як канон без writeback gate.

## Застосування Brand Message Fit та контрактів медіа

Рішення власника від 27.09.2026: включити Brand Message Fit і сім погоджених доповнень до робочого стандарту. Це прийняття правил роботи, не запуск агентів, не дозвіл публікації та не підтвердження успішного live-пілота.

1. У `Buyer Decision Evidence` перед змістовним `optimize_existing` або `replace_existing` застосовувати [Brand Message Fit](../03_Content_System/01_Messaging_and_Copy_Standards.md). Документальна діагностика розділяє `gap_type` і `message_dimension` та зберігає невідомі оцінки як `NOT_VERIFIABLE`. На застосовному маршруті потрібен `brand_message_fit_receipt` версії 2.0 за узгодженою JSON-схемою. Діагностика визначає принцип зміни; рішення залишається в Portfolio Necessity gate. Низька відповідність повідомлення сама собою не є порушенням платформи.
2. У чинний Creative Brief/Production Contract включати [зв'язок причини покупки, кадру й доказу та прив'язку каналу](01_Briefs_Experiments_and_Winner_Library.md). Це доповнення наявного запису, не новий паралельний паспорт. Existing Product Truth і права мають пріоритет.
3. До виконання визначати [режим збереження товару, повноваження референсів, нові ракурси та спосіб обробки](../03_Content_System/07_Design_Reality_Validation_Standard.md). Невирішений evidence/fidelity/platform blocker не обходиться статусом готовності іншого етапу.
4. Для демонстраційного відео застосовувати [ситуацію використання, перевірку ідеї та безперервність](../03_Content_System/03_Value_Story_and_Visual_Journey_Standards.md). Правила форматів застосовуються лише у відповідному scope.
5. Auditor записує застосовані критерії, фактичні спостереження, відкриті питання й результат повторної перевірки. Human release та контрольований експеримент залишаються окремими рішеннями.

### Ролі та межі доказовості

Content TZ Agent/маркетолог готує бриф, повну документальну діагностику та обов'язковий `brand_message_fit_receipt` версії 2.0; власник погоджує зміст; Prompt Agent компілює його без зміни сенсу; виконавець створює результат; Content Standard Auditor перевіряє; власник дозволяє випуск. Схема `brand_message_fit_receipt_schema.json` розділяє діагностичний `gap_type` і тематичний `message_dimension`; оцінки `gap_cost` мають `rating = HIGH | MEDIUM | LOW | NOT_VERIFIABLE` та `rationale`. `diagnostic_record_ref` пов'язує receipt із повним записом у брифі/додатку. Старий формат 0–3 не перетворюється автоматично: потрібне повторне оцінювання за доказами. Схему та підтримку локального посилання перевірено структурними тестами; це не перевірка достатності доказів або живого виконання агентів. На застосовному маршруті відсутній чи невалідний receipt блокує передачу; документальний запис не замінює його. Валідний receipt не є дозволом публікації.

PPC Pulse залишається поза цією зміною; маршрут R13 і spend authority не розширюються. Готові промпт-шаблони вже підключені правилом `REUSE_BEFORE_GENERATE`; повторна бібліотека не створюється. Числові рецепти джерел лишаються `TESTABLE_DEFAULT`, а актуальні platform/provider limits потребують перевірки перед конкретним виконанням.
<!-- MB_MESSAGE_MEDIA_2026_09_27_END -->

<!-- E2E_AGENT_EVAL_AND_CONTENT_DEPENDENCY_GATE_2026_09_27_START -->
<a id="mbr27-route-42"></a>
## 34. Agent evaluation and content dependency gate

Кожен product-content artifact проходить обов'язкові шари `PRODUCT_TRUTH_PRIMITIVE → APPROVED_SEMANTIC_INTERPRETATION → CHANNEL_COMPONENT`. Для повторюваних A+, carousel, image або video compositions між semantic interpretation і channel component застосовується optional `STRUCTURAL_TEMPLATE`: `PRODUCT_TRUTH_PRIMITIVE → APPROVED_SEMANTIC_INTERPRETATION → STRUCTURAL_TEMPLATE → CHANNEL_COMPONENT`. Product Truth зберігає exact SKU/variant fact і evidence. Marketing Book/Content TZ зберігає дозволений сенс для buyer/channel. Structural Template задає versioned composition roles, slots, variations і safe zones, але не створює claims. Channel component втілює дозволений сенс і структуру у title, bullet, A+, image, shot, frame або video beat.

Нейтральна verified специфікація може мати direct Product Truth binding, якщо формулювання не створює нову обіцянку чи buyer outcome. Persuasive content потребує semantic interpretation. Raw/unverified fact не потрапляє в asset; creative wording і performance result не записуються назад у Product Truth.

### Правила виконання

0. Content TZ Agent визначає `structural_template_binding` до створення Prompt Package. Для повторюваної композиції він обирає template з [Structural Template Registry](../02_Visual_System/02_Structural_Template_Registry.md), прив'язує approved semantic interpretation до slots і фіксує allowed variation. Для унікального/простого asset встановлює `NOT_APPLICABLE` із причиною. Prompt Agent не вигадує новий template і не змінює slot meaning; `NEW_TEMPLATE_REQUIRED` або недозволена deviation повертається на structural review.
1. Collector перевіряє source coverage, exact identity, extraction correctness і provenance completeness; він не ставить `verified`.
2. Product Truth Verifier блокує faithfulness/correctness defect, missed conflict і wrong SKU/variant/scope.
3. Content TZ Agent блокує missing buyer/channel relevance, incomplete claim/evidence coverage і claim expansion.
4. Prompt Agent блокує approved-TZ drift, schema/provider conflict, missing current capability evidence, invariant loss, missing atomic source coverage, vague substitution, partial/conflicting reference coverage і multi-state requirement без sub-assets/panels. Перед висновком про відсутність придатного reference він виконує `REFERENCE_DISCOVERY_GATE` по всьому exact-SKU `product_root`: рекурсивно інвентаризує всі image/video assets, дедуплікує за SHA-256, оглядає релевантних кандидатів і фіксує `reference_discovery_receipt`. Пошук лише в одній підпапці або registry subset має статус `INCOMPLETE_SEARCH_SCOPE`, не доводить відсутність матеріалу й не створює продуктовий blocker. Candidate поза approved binding повертається на bounded delta-binding без повної повторної прогонки Паспорта або Content TZ.
5. AI Creator приймає лише Prompt Package `0.6`, повторно запускає semantic validation проти exact approved Content TZ path/SHA-256, перевіряє prompt/hash fidelity, exact SKU, protected invariants і requested-versus-observed delta; він не self-verifies output.
6. Auditor/Verifier окремо оцінює defect-detection recall, false-pass, evidence trace і actual asset.
7. Experiment Analyst перевіряє outcome/denominator identity, contamination, guardrails і causal/transfer boundary.

Blocking dimension не компенсується fluency, aesthetics, relevance, CTR або середнім score. Image/video capability, kit state, quantity, label і safety condition мають `frame_evidence_binding` до asset/shot/frame, semantic interpretation, fact versions, evidence, exact variant, rights, allowed surface і verifier status.

Prompt Package зберігає `structural_template_binding` із registry path/SHA-256, template ID/version, target assets, required/optional slots, slot bindings, allowed/applied variations і deviations. `TEMPLATE_SELECTED` не дозволяє deviations; `TEMPLATE_ADAPTED` дозволяє лише variations із registry. Template керує composition, але не може розширити claim, змінити Product Truth/Visual Invariants, підмінити channel requirement або надати generation/publication authority.

Для runtime/media діють fail-closed reasons `APPROVAL_INVALIDATED`, `PIPELINE_CONTRACT_CONFLICT`, `PROVIDER_CAPABILITY_UNVERIFIED`. `OUTPUT_VERIFIED` виставляє лише independent QA/Verifier після read-back фактичного asset.

### Acceptance tests і метрики

Обов'язкові negative cases: wrong variant, unsupported fluent claim, conflicting sources, absent kit accessory, stale fact after approval, missing rights, changed brief, provider schema mismatch, wrong visual quantity і CTR growth разом із worse returns/not-as-described. Для кожної ролі окремо вести blocking-pass, false-pass, missed-conflict, traceability completeness і regression escape rate.

Structural negative cases: відсутній required slot; registry SHA mismatch; applied variation відсутня в `allowed_variations`; `TEMPLATE_SELECTED` містить deviation; template slot змінює approved claim meaning; component не проходить channel safe-zone або continuity check. Будь-який із них дає `STRUCTURAL_REVIEW_REQUIRED` або `PIPELINE_CONTRACT_CONFLICT`, а не silent adaptation.

Детальний contract і fixtures: [E2E Agent Evaluation Contract](../../../03_Content_TZ/07_QA_Tools/E2E_AGENT_EVAL_CONTRACT.md). Це документований control contract, а не доказ deployment, automated runner, provider availability, valid rights або production pass. Чинні JSON schemas не вважаються оновленими до окремого schema mapping і regression test.
<!-- E2E_AGENT_EVAL_AND_CONTENT_DEPENDENCY_GATE_2026_09_27_END -->

<!-- FINAL_MEDIA_PROVENANCE_AND_PUBLICATION_CONTROL_2026_10_03_START -->
## Final media provenance і publication check

Для кожного final image/video після останнього finishing/export створюється `FINAL_MEDIA_PROVENANCE_RECEIPT`: exact final path/SHA-256, source class, source/reference bindings, provider/deterministic operations, channel/surface applicability та фактичний metadata inspection. Provenance intermediate output не переноситься автоматично на final export. Generative edit створює нову classification; deterministic crop/resize/overlay сам по собі не робить collected original AI-generated. Image-specific IPTC rule не застосовується до video або іншого channel без explicit policy.

Перед human release Content Output QA формує `FINAL_MEDIA_PUBLICATION_CHECK` для exact final hash. Незалежно перевіряються Product Truth, Content TZ, final media QA, provenance, rights, privacy і channel metadata; для video додатково — identity continuity, action mechanics, sequence integrity, frame-level claims, audio/music rights та encode integrity. Лише `READY_FOR_HUMAN_RELEASE` дозволяє request до Release Owner; це не є upload, publication, marketplace acceptance, ranking або commercial result.

Новий агент не створюється. AI Creator і Finishing відповідають за factual operation lineage, Content Output QA — за незалежний final check, Human Release Owner — за scoped рішення. Старі pinned runs не мігрують мовчки.
<!-- FINAL_MEDIA_PROVENANCE_AND_PUBLICATION_CONTROL_2026_10_03_END -->


