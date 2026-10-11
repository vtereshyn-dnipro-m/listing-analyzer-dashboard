# Product Requirements — Image Collector Agent v1.7

Статус документа: `OWNER_APPROVED_REQUIREMENTS`  
Готовність компонента: `READY_FOR_MEDIA_RETEST`, не `PRODUCTION_READY`  
Дата актуалізації: 02.10.2026  
Власник рішення: власник процесу

Редакція v1.7 закриває `IC-09–IC-10`: Listing Suite запускає collection лише через `START_MEDIA_COLLECTION` binding, а користувач отримує агрегований result receipt із чесним Passport delta status.

Редакція v1.6 закриває `IC-07–IC-08`: UI відображає доказову проєкцію фактичних receipts, а кожне рішення людини має typed request/receipt, exact targets, stale-input та idempotency control.

Редакція v1.5 закриває `IC-05–IC-06`: preflight-router media/document/mixed inputs і первинний Image Collection лише після мінімального canonical Passport exact SKU з read-back.

Редакція v1.4 закриває `IC-01–IC-04`: existing media snapshot, purpose-specific collection, typed media intake і явний вибір між локальною обробкою та internet discovery.

Production-reference policy 2026-09-28: будь-який фото/відео asset, збережений у межах exact-SKU `product_root`, має `production_reference_use: ALLOWED`. Publication clearance перевіряється окремо перед release і не є blocker збору, prompting, generation, editing, conditioning, montage або QA.

## Призначення

Image Collector — додатковий on-demand компонент AI Design/Content pipeline. Його головна функція — активний пошук і збір релевантних фото, відео та медіасторінок exact product/model в інтернеті. Доступні матеріали він перетворює на простежувану бібліотеку stills і clips для Content TZ, Prompt, AI Creator або іншого дозволеного production route.

Компонент не створює новий контент, не виконує художній монтаж, не підтверджує Product Truth/claims/rights/compliance і не дозволяє публікацію.

UI не маршрутизує агентів і не змінює agent verdict. Він показує state projection за `Image_Collection_UI_State_and_Human_Action_Contract_v1.0.md`. Людина працює лише через типізовані адресні actions; тільки `CONFIRM_COLLECTION_COMPLETE` після `READY_FOR_HUMAN_REVIEW` у режимі `STANDARD` може встановити `COLLECTION_READY`.

Запуск із Listing Suite відповідає `Image_Collection_Listing_Suite_Binding_and_Result_Contract_v1.0.md`: UI передає exact scope Координатору через binding, а повтор exact request повертає існуючий run. UI result є проєкцією технічних receipts; `COMPLETED` заборонено до `PASSPORT_DELTA_APPLIED`.

Image Collector також створює `production_reference_index.json`: downstream-searchable перелік exact-SKU photo/frame/segment із observed action, connection, accessory/nozzle, scene/use-case, result і person-presence tags. Якщо в source присутня людина, index обов'язково встановлює `person_deidentification_required: true`; source original лишається незмінним, а downstream production derivative має змінити обличчя та одяг без зміни продукту, робочої збірки, дії й доказової композиції.

## Місце й trigger у конвеєрі

`Product sources + current SKU Passport -> MEDIA_COLLECTION_REQUEST -> human confirmation -> Image Collector -> Reviewer + Skeptic -> human review -> Content TZ / Prompt / Production`

Content TZ Agent або Координатор може створити request. Виконання починається тільки після human confirmation exact SKU, scope, sources, rights boundary, downstream use і `product_root`. Зміна scope потребує нового підтвердження.

Canonical package: `PRODUCTION_HANDOFF/04_Content_TZ_Agent/08_Image_Collector_Agent/`.

## Область застосування

Одна задача охоплює один exact SKU і одну collection. Допускаються одиночні, пакетні або змішані локальні/URL sources. Компоненти іншого SKU не змішуються з collection; для них потрібна окрема задача.

Use cases:

- пошук кількох сильних stills за visual targets;
- extraction окремих clips з однією повною операцією або циклом;
- збереження максимально доступної якості source-derived master;
- quarantine невпевненого SKU/revision, прав, якості або incomplete action;
- machine-readable manifest і handoff для downstream відбору.
- structured Passport media delta для реєстрації всіх опрацьованих джерел і evidence-linked способів/JBTD у чинному Паспорті SKU.

## Обов'язкові входи

- human-confirmed `task_id`, `collection_id`, owner, request source та internet search scope;
- exact SKU та current Passport path/ID/version/status/SHA-256;
- окремий `public_model_name`; SKU є внутрішнім binding і не використовується як основний пошуковий ключ;
- visual targets з IDs і описом;
- seed source inventory з provenance, access status, rights status і allowed downstream use; seed не обмежує internet discovery;
- `product_root` та artifact date;
- mode `STANDARD | PILOT_REVIEW_ONLY`;
- DaVinci/runtime availability і відомі технічні обмеження.
- schema-valid `existing_media_snapshot` із current Passport, media registry, previous collections/sources/counts/lineage та open actions;
- `collection_purpose: INITIAL_COLLECTION | ADDITIONAL_DISCOVERY | USER_MEDIA_INTAKE | RECOVERY_DELTA`;
- purpose-compatible `discovery_mode`, previous cutoff/coverage або recovery source IDs;
- typed source inventory за `IMAGE_FILE | VIDEO_FILE | DIRECT_IMAGE_URL | DIRECT_VIDEO_URL | MEDIA_PAGE_URL | MEDIA_FOLDER`.
- classification receipt для кожного input за Passport Boundary Contract;
- для `INITIAL_COLLECTION` — eligibility receipt `AVAILABLE`, що підтверджує current canonical Passport exact SKU та snapshot.

Missing identity, Passport, source, target, rights boundary, product root або human confirmation повертає контрольований intake/context block. Значення не відновлюються з пам'яті.

Правила purpose визначає [Collection Model Contract v1.0](Image_Collection_Collection_Model_Contract_v1.0.md). `USER_MEDIA_INTAKE` не запускає internet discovery. `ADDITIONAL_DISCOVERY` дедуплікує результати проти всієї попередньої медиабази SKU. `MEDIA_FOLDER` заборонений без окремого folder contract.

Межу між media і документними inputs та порядок першого запуску визначає [Passport Boundary Contract v1.0](Image_Collection_Passport_Boundary_Contract_v1.0.md). Mixed page не створює два runs без explicit user choice. Мінімальний Passport `NOT_READY` робить `INITIAL_COLLECTION` доступним після read-back, але не запускає його автоматично.

## Storage requirement

Усі product-specific input copies, source records, derivatives, masters, quarantine, Reviewer/Skeptic reports, manifest і handoff receipt зберігаються тільки в:

`<product_root>/артефакти/<YYYY-MM-DD>/image_collector/<collection_id>/`

Оригінал, уже зареєстрований у product artifact inventory, залишається за exact path/SHA і не дублюється без потреби. Shared instructions, schemas, validators і tests залишаються у production package. Product-specific файл поза `product_root` не входить до valid collection.

## Required capabilities

Компонент повинен:

- починати discovery зі звичайного Google-пошуку за `public_model_name`, далі проходити Google Video до двох послідовних порцій без нового exact-model URL;
- виконувати platform matrix YouTube, TikTok, Facebook і Instagram за назвою моделі, а не за внутрішнім SKU;
- пріоритезувати сторонні огляди, відеовідгуки, досвід експлуатації та customer voice; офіційні джерела самі не закривають independent-review coverage;
- виконувати internet discovery поза межами seed URLs, вести search log і розрізняти new/duplicate/inaccessible sources;
- для кожного релевантного відео збирати доступні comments/replies або фіксувати reason-coded status недоступності;
- використовувати постійний portable downloader з version/self-test preflight; після його ремонту виконувати video-only delta без повтору завершеного збору;
- зберігати immutable source provenance та lineage `source -> timecode/frame -> asset`;
- зіставляти visible SKU/revision/components із current Passport і точними locators;
- витягувати повний кадр без crop/enhancement та одну завершену operation/cycle на clip;
- зберігати source resolution/FPS/color/audio настільки, наскільки це реально підтримує export;
- не виконувати upscale, interpolation, denoise, retouch, speed change, overlays або інші creative modifications;
- не перезаписувати наявні outputs;
- реєструвати partial errors окремо для кожного source;
- для кожного знайденого source окремо фіксувати `source_found`, `content_retrieval: FULL | PARTIAL | NONE`, перелік `saved_components`, user-facing status, зрозумілу причину неповноти та окремий machine reason code;
- не приховувати знайдене, але неотримане джерело загальним status collection;
- формувати schema-valid manifest і відтворювані hashes;
- передавати всі фактичні assets на незалежні Reviewer і Skeptic checks.
- для кожного asset фіксувати decision point, умови спостереження, видимий result/completion cue та яку невизначеність він зменшує;
- формувати `product_reference_candidate_pack` із multi-angle references та observed protected elements, не оголошуючи їх Product Truth до валідації;
- додавати reuse metadata: роль asset, use case, market/language/channel/surface, product area, operation phase, claim ID та evidence relationship;
- застосовувати media-specific evidence contract для video/audio, photos та comments, включно з permission і personal/sensitive-data flags;
- вести artifact lineage для original, derivative, diagnostic, master і working copy з version relation `replaces | parallel_snapshot | duplicate_of`;
- закривати кожне вхідне посилання disposition і не ставити `NO_MATCH` для HTML до перевірки raw text, embedded JSON та escaped fields;
- перед handoff обчислювати `SOURCE_COVERAGE_COMPLETE` і `PACKAGE_ADMISSIBLE_FOR_AUDIT`.
- після media review формувати `passport_media_delta.md` і передавати його через Координатора Собирателю Паспорта;
- не оголошувати end-to-end workflow завершеним до receipt `PASSPORT_DELTA_APPLIED`; до receipt використовувати `PASSPORT_UPDATE_PENDING`.

Для public TikTok post Image Collector використовує canonical post URL і current canonical `yt-dlp` extractor без browser cookies/login/session import. Extractor-generated ephemeral challenge cookie у межах public request допустимий, але його значення не копіюється, не повторно використовується й не виноситься до reports/Passport. Позитивний acquisition потребує physical master, SHA-256, ffprobe і full decode `PASS`; comments/captions gaps реєструються окремо й не анулюють отриманий master.

Точний executable workflow визначає [Collector instruction v1.7](../01_Agent_Instructions/Image_Collector_Agent_Instructions_v1.7.md). Цей requirements document не дублює його.

## Ролі та повноваження

- Image Collector створює candidates, manifest і handoff; максимальний media-статус — `READY_FOR_HUMAN_REVIEW`, а маршрутний статус після формування delta — `READY_FOR_PASSPORT_DELTA_APPLY`.
- Reviewer перевіряє кожний фактичний asset і metadata read-only.
- Skeptic перевіряє ті самі assets із презумпцією відхилення, але лише за evidence.
- До handoff pool входить тільки intersection `KEEP`; більш строгий verdict має пріоритет.
- Тільки людина встановлює `COLLECTION_READY`, змінює scope або дозволяє exceptional pilot mode.

Reviewer/Skeptic receipts є обов'язковими для `accepted` pool і позитивного media-статусу. Відсутність ролі або негативний verdict не блокують реєстрацію source records і evidence-bounded `passport_media_delta.md`; у такому разі media gate залишається незакритим, а Passport delta route продовжується окремо.

Reviewer і Skeptic не редагують media, manifest або instruction. Їх локальні правила є role-specific deltas до Collector instruction і manifest contract.

## Вихідний контракт

Machine source of truth: [Image Collector Manifest Schema v0.5](../02_Machine_Validation/image_collector_manifest_schema.v0.5.json).

Collection output включає:

- registered sources і coverage;
- `video_source_register.md`, Google Video/platform coverage і saturation record;
- `comments_corpus.jsonl` та `comments_summary.md` із customer signals і reason-coded gaps;
- still/video candidates, masters і quarantine;
- exact provenance, timecodes, hashes, Passport locators, quality/rights fields;
- target coverage і gaps;
- окремі Reviewer/Skeptic reports;
- conservative verdicts, manifest і handoff receipt;
- `passport_media_delta.md` з окремою таблицею всіх знайдених/опрацьованих джерел, де окремо видно факт знаходження, повноту отримання, збережені компоненти та причину неповноти, а також таблицею JBTD/способів із source IDs та точними locators;
- human acceptance record, якщо рішення вже прийнято.
- `product_reference_candidate_pack` зі статусом `REFERENCE_CANDIDATE | NEEDS_PASSPORT_VALIDATION | REFERENCE_LOCK_APPROVED`;
- decision evidence, reuse metadata, media evidence і lineage для кожного asset;
- `source_coverage_gate` та `package_admissibility` із перевіреними умовами.

Назви enums, required fields і conditional transitions визначаються тільки schema v0.5 та validator; specification й instructions не створюють паралельний machine contract.

## Acceptance tests

До `READY_FOR_HUMAN_REVIEW` потрібно:

- один exact SKU та current Passport binding;
- усі product files у canonical collection root;
- source/target/asset referential integrity;
- відсутність overwrite і artificial enhancement;
- complete-operation clips та truthful still naming;
- file existence/SHA checks;
- Reviewer/Skeptic reports для кожного asset;
- accepted pool тільки з intersection `KEEP`;
- schema/validator/test suite `PASS`;
- explicit gaps, limitations і rights boundary.
- основний query побудовано за `public_model_name`, Google Video і platform matrix завершено;
- кожне відео має comments corpus або reason-coded comments status.
- кожне опрацьоване джерело відображене в Passport delta, а кожен evidence-backed JBTD/спосіб має source ID і точний locator.
- для кожного source в Passport delta заповнено окремі поля: знайдено, отримано, збережено, причина неповноти; технічний code не є заміною пояснення.
- `passport_media_delta.md` передано Координатору, а workflow має receipt `PASSPORT_DELTA_APPLIED` або чесний незавершений стан `PASSPORT_UPDATE_PENDING`.
- кожний accepted asset має decision usefulness вище `LOW`, точний evidence relationship і повну lineage;
- усі links мають disposition, а HTML `NO_MATCH` підтверджений deep check;
- `SOURCE_COVERAGE_COMPLETE` і `PACKAGE_ADMISSIBLE_FOR_AUDIT=PASS` до позитивного handoff.

Quarantine, unavailable source, unknown rights або відсутність нових clips не блокують внесення до Паспорта реєстру джерел і evidence-bounded JBTD/use rows. Після `PASSPORT_DELTA_APPLIED` Аудитор і Верифікатор автоматично не запускаються.

Так само відсутній Reviewer/Skeptic receipt, `NOT_REVIEWED`, `REWORK`, `QUARANTINE` або `REJECT` блокують лише прийняття відповідного media asset і позитивний media-статус; вони не блокують перевірену source/JBTD delta до Паспорта.

`READY_FOR_MEDIA_RETEST` переходить до `PRODUCTION_READY` тільки після factual media walkthrough, одного non-live pilot, перевірки exports у фактичній версії DaVinci Resolve, human review і закриття defects. Саме перенесення до production package не змінює readiness.

## Межі доказовості

- Visual match не підтверджує claim, compatibility, rights або publication readiness.
- У `PILOT_REVIEW_ONLY` assets не можуть бути `accepted` або `COLLECTION_READY`.
- Machine schema/hash `PASS` не замінює перегляд media.
- Кількість assets не є метрикою якості без target coverage і review.

## Canonical dependencies

- [Context Assembly Contract](../../09_Shared_Contracts/CONTEXT_ASSEMBLY_CONTRACT.md), expected `active_v1.1`, profile `MEDIA_COLLECTION`;
- current SKU Passport/Product Truth projection;
- [Collector instruction](../01_Agent_Instructions/Image_Collector_Agent_Instructions_v1.7.md);
- [Reviewer instruction](../01_Agent_Instructions/Image_Collector_Reviewer_Agent_Instructions_v0.7.md);
- [Skeptic instruction](../01_Agent_Instructions/Image_Collector_Skeptic_Agent_Instructions_v0.7.md);
- [Manifest schema v0.5](../02_Machine_Validation/image_collector_manifest_schema.v0.5.json) і validator.
