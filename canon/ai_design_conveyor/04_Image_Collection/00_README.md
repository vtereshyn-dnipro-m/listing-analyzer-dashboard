# Image Collector Agent — internet discovery and collection component v1.9

**Статус комплекта:** `READY_FOR_MEDIA_RETEST`  
**Дата:** 2026-10-02

## Назначение

Комплект реализует Image Collector для одного точного SKU. Головна функція агента — активний пошук фото, відео та медіасторінок продукту в інтернеті, реєстрація доступних і недоступних джерел, завантаження дозволених оригіналів для внутрішнього аналізу та формування простежуваної медіабібліотеки.

Компонент включено до загального production handoff Content TZ як додатковий on-demand елемент. Content TZ Agent або Координатор може створити `MEDIA_COLLECTION_REQUEST`, але робота починається тільки після підтвердження людиною exact SKU, scope, sources, rights boundary і product artifact root. Автономний постійний збір не дозволений.

Агент не создаёт новый контент. Локальні матеріали й URL з Паспорта є seed і corpus для дедуплікації; вони не обмежують internet discovery і не дозволяють завершити стандартний запуск лише локальною обробкою.

Перед выбором материалов агент обязательно открывает актуальный Паспорт SKU и сопоставляет с ним продукт, вариант, комплектацию, компоненты и свойства. Неуверенные и противоречащие паспорту материалы не принимаются автоматически.

## Ожидаемый результат

По одному SKU пользователь получает структурированную медиабиблиотеку: несколько сильных стоп-кадров по заданным характеристикам, claims, составу и свойствам; отдельные видеоклипы, каждый с одной полной операцией или циклом; master-файлы в максимально доступном качестве; карантин сомнительных материалов; manifest с источниками, таймкодами, именами, правами и результатами проверки. Media-итог агента — `READY_FOR_HUMAN_REVIEW`; после формирования `passport_media_delta.md` маршрут продолжается до receipt `PASSPORT_DELTA_APPLIED`. Только человек может подтвердить `COLLECTION_READY`.

## Состав: три агента и машинный контроль

- [Затверджена специфікація](00_Product_Requirements/Image_Collector_Agent_Specification_v1.7.md)
- [Collection Model Contract v1.0](00_Product_Requirements/Image_Collection_Collection_Model_Contract_v1.0.md) — `existing_media_snapshot`, collection purpose, typed media intake і discovery boundary
- [Passport Boundary Contract v1.0](00_Product_Requirements/Image_Collection_Passport_Boundary_Contract_v1.0.md) — media/document router і eligibility первинного збору
- [UI State and Human Action Contract v1.0](00_Product_Requirements/Image_Collection_UI_State_and_Human_Action_Contract_v1.0.md) — evidence-backed UI projection і typed human decisions
- [Listing Suite Binding and Result Contract v1.0](00_Product_Requirements/Image_Collection_Listing_Suite_Binding_and_Result_Contract_v1.0.md) — `START_MEDIA_COLLECTION`, idempotent start і user-facing result receipt
- [Implementation Handoff v1.0](00_Product_Requirements/Image_Collection_UI_Implementation_Handoff_v1.0.md) — матриця `IC-01–IC-10`, integration handlers, storage, error mapping і acceptance tests для програмістів
- [Єдина інструкція Image Collector](01_Agent_Instructions/Image_Collector_Agent_Instructions_v1.9.md) — purpose-specific discovery/intake, router, eligibility, UI binding/projection, human actions, керований public YouTube/TikTok download, resolution queues, decision evidence, reference candidates, reuse metadata, media evidence, lineage, DaVinci Resolve і Passport delta
- [Інструкція Reviewer Agent](01_Agent_Instructions/Image_Collector_Reviewer_Agent_Instructions_v0.7.md)
- [Інструкція Skeptic Agent](01_Agent_Instructions/Image_Collector_Skeptic_Agent_Instructions_v0.7.md)
- [JSON Schema manifest v0.5](02_Machine_Validation/image_collector_manifest_schema.v0.5.json)
- [Existing media snapshot schema](02_Machine_Validation/existing_media_snapshot.schema.json)
- [Media collection start request schema](02_Machine_Validation/media_collection_start_request.schema.json)
- [Media intake classification receipt schema](02_Machine_Validation/media_intake_classification_receipt.schema.json)
- [Initial collection eligibility receipt schema](02_Machine_Validation/image_collection_initial_eligibility_receipt.schema.json)
- [UI state receipt schema](02_Machine_Validation/image_collection_ui_state_receipt.schema.json)
- [User action request schema](02_Machine_Validation/image_collection_user_action_request.schema.json)
- [User action receipt schema](02_Machine_Validation/image_collection_user_action_receipt.schema.json)
- [Listing Suite start request schema](02_Machine_Validation/listing_suite_start_media_collection_request.schema.json)
- [Listing Suite start receipt schema](02_Machine_Validation/listing_suite_start_media_collection_receipt.schema.json)
- [UI result receipt schema](02_Machine_Validation/image_collection_ui_result_receipt.schema.json)
- [Migration note v0.4 → v0.5](02_Machine_Validation/schema_v0.5_migration_note.md)
- [Migration note v0.3 → v0.4](02_Machine_Validation/schema_v0.4_migration_note.md)
- [Migration note v0.2 → v0.3](02_Machine_Validation/schema_v0.3_migration_note.md)
- [Migration note v0.1 → v0.2](02_Machine_Validation/schema_v0.2_migration_note.md)
- [Валідний приклад manifest](02_Machine_Validation/sample_valid_manifest.v0.5.json)
- [Валідний приклад PILOT_REVIEW_ONLY manifest](02_Machine_Validation/sample_valid_pilot_review_manifest.v0.5.json)
- [Шаблон Access Resolution Queue](02_Machine_Validation/access_resolution_queue.template.md)
- [Шаблон Rights Clearance Queue](02_Machine_Validation/rights_clearance_queue.template.md)
- [Валидатор manifest contract](02_Machine_Validation/validate_manifest_contract.ps1)
- [Исполняемая тестовая матрица](02_Machine_Validation/test_manifest_contract.ps1)

## Статус готовности

UI alignment package має статус `CONTRACT_PACKAGE_COMPLETE`: `IC-01–IC-10` пов'язані з канонічними контрактами, schemas, fixtures і локальними tests. Це готовність до програмної реалізації, а не production admission.

Комплект v1.9 закриває `IC-09–IC-10`: кнопка Listing Suite має один binding `START_MEDIA_COLLECTION`, exact replay не створює другого run, а UI result показує source/asset counts, open actions, media gate та Passport delta status. `COMPLETED` можливий тільки після `PASSPORT_DELTA_APPLIED`.

Комплект v1.8 закриває `IC-07–IC-08`: Listing Suite отримує однозначний evidence-backed UI state, а дії людини мають exact target, manifest binding, stale-input та idempotency control. `COLLECTION_READY` можливий тільки через human receipt у `STANDARD`; publication authority і Passport mutation не надаються.

Комплект v1.7 закриває `IC-05–IC-06`: документні inputs маршрутизуються до Паспорта, mixed page чекає user intent, а первинний Image Collection стає доступним лише після read-back мінімального canonical Passport `NOT_READY`. Автоматичний запуск після створення Паспорта заборонений.

Комплект v1.6 закриває перший блок UI alignment `IC-01–IC-04`: перед запуском потрібен snapshot усієї наявної медиабази SKU; перший, додатковий, user-only і recovery-збір мають різні contracts; source input types закриті; додавання матеріалу не дозволяє internet discovery автоматично.

Комплект v1.5 додає перевірений public TikTok route: exact post URL → current `yt-dlp` extractor → native JS challenge та ephemeral extractor cookie без browser session → best pre-merged MP4 → metadata/thumbnail → ffprobe/full-decode → timecoded evidence → Passport delta. Signed CDN URLs і cookie values не повторно використовуються; comments/captions gaps відокремлені від успіху video acquisition.

Комплект v1.4 відновлює незалежність двох gates: Reviewer/Skeptic receipts обов'язкові для accepted media pool і позитивного media-статусу, але їх відсутність або негативний verdict не блокують реєстрацію source records та evidence-bounded `passport_media_delta.md`.

Комплект v1.3 матеріалізує `VIDEO_DOWNLOAD_DELTA`: canonical `yt-dlp` + FFmpeg/ffprobe preflight, public download без cookies/login, immutable master, SHA-256, ffprobe і full-decode gate, captions, timecoded frames, OCR/observations, privacy flags, independent Reviewer/Skeptic receipts і обов'язковий Passport delta handoff. Login/session/DRM/platform controls не обходяться; при них потрібен lawful owner/platform export.

Комплект v1.2 додає `access_resolution_queue` і `rights_clearance_queue`: session/login blockers, неповні comments corpus і невідомі права не приховуються, а передаються людині як конкретна дія. Закриття потребує receipt із SHA-256; повторний запуск виконується лише як delta для зазначених source IDs.

Комплект v1.1 закриває зауваження незалежного аудиту: фізично звіряє collection root, Passport, context/discovery/rights/review receipts та hashes; перевіряє повноту discovery surfaces, замкненість lineage, conditional media evidence, права для `production_input`, claim binding, summary/target coverage і складений gate `READY_FOR_HUMAN_REVIEW`. Manifest v0.4 і validator роблять ці правила обов'язковими.

Комплект v0.9 зберігає discovery rules v0.8 і додає обов'язкову прозорість отримання джерела. У Passport delta окремо видно: джерело знайдено, контент отримано повністю/частково/не отримано, що саме збережено та чому збір неповний. Machine reason code зберігається окремо й не підміняє людське пояснення.

Комплект v0.8 встановлює `public_model_name` головним пошуковим ключем, Google Video — першим обов'язковим маршрутом, а сторонні огляди, TikTok/Facebook/Instagram coverage та comments/replies — обов'язковою частиною discovery. SKU використовується тільки для внутрішнього binding і identity check. Portable downloader має version/self-test preflight і `VIDEO_DOWNLOAD_DELTA` recovery без повтору завершеного збору. `passport_media_delta.md` є обов'язковим handoff до Координатора і Собирателя Паспорта; до receipt `PASSPORT_DELTA_APPLIED` загальний workflow має `PASSPORT_UPDATE_PENDING`. Після внесення delta Аудитор і Верифікатор без прямого запиту не запускаються. Статус `READY_FOR_MEDIA_RETEST` не означає `PRODUCTION_READY`, який допускається тільки після:

1. сценарного walkthrough всех тестов на фактических медиа;
2. пробного задания на одном non-live SKU;
3. проверки фактических экспортов установленной версией DaVinci Resolve;
4. human review результатов и закрытия найденных отклонений.

Пилотные материалы предыдущего запуска полностью удалены по прямой команде владельца 2026-09-14. Устойчивые выводы пилота встроены в действующую инструкцию. Следующее тестирование начинается как новый run.

## Владелец и полномочия

Людина створює запит безпосередньо або підтверджує `MEDIA_COLLECTION_REQUEST` від Content TZ/Координатора; тільки людина змінює scope і підтверджує `COLLECTION_READY`. Агент може завершити автоматичну роботу тільки статусом `READY_FOR_HUMAN_REVIEW`.

## Розміщення продуктових артефактів

Усі input copies, source records, extracted stills/clips, masters, quarantine, review reports, manifest і handoff receipt зберігаються тільки в:

`<product_root>/артефакти/<YYYY-MM-DD>/image_collector/<collection_id>/`

Оригінал, який уже зареєстрований у product artifact inventory, не переміщується і не дублюється без потреби; manifest посилається на його exact path/SHA. Product-specific файли поза `product_root` заборонені. Shared tools залишаються у цьому production package.
