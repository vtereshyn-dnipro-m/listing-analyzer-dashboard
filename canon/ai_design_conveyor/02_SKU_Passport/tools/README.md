# Проверка пакета Паспорта SKU

Версия: 1.1  
Дата: 24.09.2026

Оба скрипта работают только на чтение, используют Node.js без сторонних библиотек и выводят JSON в stdout. Они не создают продуктовых документов, не выдают `ACCEPTED` receipt и не оценивают истинность фактов.

`passport_package_check.js` проверяет пакет Собирателя перед передачей Аудитору и повторно на входе Аудитора и Верификатора. Версия 1.1 читает Markdown как UTF-8, а DOCX — из `word/document.xml`; вспомогательная матрица `passport_section_matrix__*` не считается вторым Паспортом.

Инструменты не являются нормативным источником blocker code. Ошибка исполнения, неподдерживаемый формат либо только manifest/parent/checksum mismatch выводятся как diagnostics и требуют прямого read-back, но не меняют маршрут и не создают `REJECTED`. Блокировать может лишь содержательное условие из закрытого словаря 00A/инструкции агента, подтверждённое уполномоченным получателем.

Для строк preflight checker строит реестр `PF-*` из действующих 00A, 02, 02A, 02C и 03. Непрошедший зарегистрированный содержательный код остаётся finding; неизвестный код выводится как `UNREGISTERED_PREFLIGHT_CODE` в diagnostics и не влияет на итоговый статус. Поле `package_admissible_for_audit` в manifest является заявлением отправителя, а не самостоятельным доказательством; отрицательное значение требует проверки зарегистрированных gates получателем и само по себе не блокирует.

`handoff_integrity_check.js` выполняет необязательную диагностическую проверку межфайловой согласованности: наличие handoff/preflight/binding, parent SHA, audit scope, revision и `PF-STATE-RECONCILIATION`. Его `FAIL` по техническим manifest/parent linkage не является основанием блокировать содержательный handoff; он не ремонтирует пакет и не выдаёт receipt.

`handoff_metadata_consistency_check.js` выполняется до seal. Он получает текущий единственный файл Паспорта и live-контракт 00A, вычисляет их путь/SHA/версию и сравнивает эти значения в manifest, handoff, preflight и binding. Он также запрещает ссылки на старые имена `Паспорт_SKU__...__vN.md` и hard-coded `requested_action`.

`handoff_integrity_check.js` допускает ровно один именованный `package_seal_binding__*.md` в каталоге ревизии. Старый общий `package_seal_binding.md` и дубликаты binding дают `FAIL`; исторические binding остаются только в своих старых ревизиях.

Если Паспорт содержит `extension_field`, скрипт также проверяет наличие минимальных метаданных `extension_id`, `source_label`, `value`, `scope`, `source_artifact_id`, `locator`, `status` и `extension_reason`. Само наличие дополнительного поля не является ошибкой; ошибкой является его потеря, приблизительное маппирование или неполная provenance.

При наличии предыдущего manifest проверка может сравнить `base_package_id` и `base_package_sha256`; отсутствие или несовпадение этих полей носит диагностический характер:

```powershell
node .\tools\handoff_integrity_check.js --product-root 'C:\путь\к\товару' --run-dir 'C:\путь\к\товару\COLLECTOR-RUN-...' --manifest 'C:\путь\к\товару\...\revision-NNN\package_manifest.md' --base-manifest 'C:\путь\к\товару\...\предыдущий\revision-MMM\package_manifest.md'
```

`--run-dir` — корень RUN для трассировки; route-файлы читаются из каталога ревизии, в котором находится `--manifest`.
Для первого полного RUN без предыдущего пакета обязательно передавай `--base-manifest none`. В этом случае manifest обязан явно содержать `base_package_id: none` и `base_package_sha256: none` либо пустое значение. Подставлять текущий manifest как собственного родителя запрещено.

Запуск:

```powershell
node .\tools\passport_package_check.js --product-root 'C:\путь\к\товару' --run-dir 'C:\путь\к\товару\COLLECTOR-RUN-...' --passport 'C:\путь\к\товару\Паспорт_SKU__21680000__v1.md' --profile-approval 'C:\путь\к\товару\службові\CATEGORY_PROFILE_APPROVAL.json' --stage auditor
```

Для `--stage verifier` добавь `--audit-report` с путём к отчёту Аудитора. Отчёт должен содержать `handoff_scope=<фактически проверенный scope>`, `handoff_verdict=READY_FOR_VERIFIER`, `input_receipt=ACCEPTED`, `collector_package_sha256=<SHA-256 package manifest>`.

Проверки: принадлежность путей папке товара; наличие единого Паспорта и его состояния; пять файлов 02C; SHA и размер payload по package manifest; паспортный hash и версия контракта; результаты PF, включая `PF-STATE-RECONCILIATION`; старый запрос профиля после его утверждения; отсутствие дополнительного паспортного документа в run; для Верификатора — полный аудиторский допуск и привязка к текущему manifest.

Собиратель запускает скрипт после seal и до handoff. Ошибка требует новой неизменяемой ревизии пакета; уже запечатанные файлы не редактируются. Аудитор и Верификатор запускают его повторно на полученном пакете. Если профиль утверждён, путь к его локальной записи передаётся через `--profile-approval`.

`PASS` означает только прохождение перечисленных механических проверок. Агент-получатель самостоятельно проверяет смысл, полноту схемы, применимость доказательств и создаёт receipt по 00A. `FAIL` или ошибка запуска запрещают положительный handoff. Старые пакеты до 00A ожидаемо дают FAIL и сохраняются без переписывания. Скрипт не проверяет всю семантику 02C, полноту архива источников, права на медиа или Product Truth.

Для одного SKU должен существовать один физический файл Паспорта. Проверка snapshot/hash не разрешает создавать `Паспорт...v2` или `v3`: изменения записываются в тот же файл, а предыдущие byte snapshots сохраняются только через sealed manifests и Change Events.

Перед handoff Собиратель может запустить три read-only диагностики: `passport_package_check.js`, `handoff_metadata_consistency_check.js` и `handoff_integrity_check.js`. `FAIL` по manifest, parent linkage, seal или checksum фиксируется как диагностическое расхождение и не запрещает содержательный handoff. Блокирующими остаются только отсутствие/повреждение исходного продуктового артефакта, неверный SKU/scope или невозможность установить provenance по 00A. После seal повторная проверка выполняется только на копии чтения; исходные архивные файлы не исправляются.

## Ответы и необходимость нового вопроса

`response_coverage_check.js` запускает MVP Верификатор на том же immutable возвращённом источнике и своём `response_coverage.json`:

```powershell
node .\tools\response_coverage_check.js --product-root 'C:\путь\к\товару' --coverage 'C:\путь\к\товару\response_coverage.json' --returned-source 'C:\путь\к\товару\артефакти\YYYY-MM-DD\returned.docx' --mode intake
node .\tools\response_coverage_check.js --product-root 'C:\путь\к\товару' --coverage 'C:\путь\к\товару\response_coverage.json' --returned-source 'C:\путь\к\товару\артефакти\YYYY-MM-DD\returned.docx' --mode outbound
```

`intake` проверяет 1:1 строки Q ID, обязательные поля 06E, счётчики, SHA исходного файла и отсутствие нового вопроса с `same_intent_repeat=true`. `outbound` дополнительно требует по каждому follow-up поля необходимости 06E: `blocked_deliverable_or_gate`, `mandatory_basis`, `internal_resolution_checked=true`, `bounded_draft_possible` как boolean, `external_request_necessary=true`, `decision_reason`. Это проверка наличия и согласованности записи; агент самостоятельно оценивает убедительность основания и содержание новой формы. После любого редактирования outbound формы действуют её отдельные смысловые и визуальные gates 06E.


