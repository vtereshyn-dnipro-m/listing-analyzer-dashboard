# Політика приймання джерел Listing Suite

Версія: 1.0  
Дата: 04.10.2026  
Статус: `PROFILE_APPROVED_FOR_IMPLEMENTATION`; production activation заборонена до integration-test PASS

## Призначення

Визначити fail-closed правила реєстрації окремих файлів і `SELECT_FOLDER_SNAPSHOT` до формування action request. Політика не визначає Product Truth і не запускає агента.

## Область застосування

Політика застосовується до локальних матеріалів, які поточний користувач явно вибрав для exact SKU. URL intake, cloud subscription, background folder watch і автоматичний web research не входять до v1.

Machine-readable deployment profile відповідає `listing_suite_source_intake_profile.schema.json`, а результат snapshot — `listing_suite_source_intake_receipt.schema.json`.

## Обов'язковий deployment profile

До ввімкнення feature flag адміністратор задає й підписує:

```yaml
policy_id:
policy_version:
effective_at:
allowed_extensions: []
allowed_mime_types: []
max_file_count:
max_single_file_bytes:
max_total_bytes:
max_video_duration_seconds:
max_recursion_depth:
archive_root_pattern: product_root/артефакти/YYYY-MM-DD/
hash_algorithm: SHA-256
configured_by:
approved_by:
policy_sha256:
```

Порожнє, нульове, від'ємне або непідписане required value дає `INTAKE_POLICY_NOT_CONFIGURED`. Intake не починається. Цей документ навмисно не встановлює довільних числових лімітів замість власника продукту та інфраструктури.

Затверджений production-candidate profile: `Listing_Suite_Source_Intake_Profile_v1.0.json`. `policy_sha256` обчислюється з UTF-8 canonical compact JSON у стабільному порядку properties без самого поля `policy_sha256`.

## Правила виконання

1. Перевірити path containment у явно вибраній папці.
2. Не переходити через symlink, shortcut, junction або mount/reparse point.
3. Не розширювати filesystem permissions і не запускати intake від іншого actor.
4. Зафіксувати frozen inventory до копіювання.
5. Перевірити extension і detected MIME; невідповідність дає `TYPE_MISMATCH`.
6. Перевірити count, single-file size, total size, video duration і recursion depth за active profile.
7. Кожний прийнятий object скопіювати до archive root, обчислити SHA-256 і виконати read-back.
8. Exact duplicate зберегти як `DUPLICATE_EXACT` із `duplicate_of`; не створювати нову редакцію змісту.
9. Недоступний або відхилений object не включати до agent scope.
10. Якщо accepted object count дорівнює нулю, action request не створювати.

## Пооб'єктні результати

Schema-compatible access results: `ACCEPTED | ACCESS_DENIED | UNAVAILABLE | UNSUPPORTED | DUPLICATE_EXACT`.

Детальна причина зберігається в intake receipt, а не підміняє access result. Дозволені reason codes: `TYPE_NOT_ALLOWED`, `TYPE_MISMATCH`, `FILE_TOO_LARGE`, `TOTAL_SIZE_EXCEEDED`, `FILE_COUNT_EXCEEDED`, `VIDEO_TOO_LONG`, `RECURSION_DEPTH_EXCEEDED`, `PATH_OUTSIDE_SELECTION`, `LINK_TRAVERSAL_BLOCKED`, `READ_FAILED`, `ARCHIVE_COPY_FAILED`, `HASH_FAILED`, `READBACK_FAILED`.

## Partial intake

Partial intake дозволено, якщо прийнято хоча б один object. UI до відправлення показує accepted/rejected/duplicate counts і пооб'єктні причини. Користувач явно продовжує з прийнятим subset; склад inventory після цього заморожується.

## Acceptance tests

- Відсутній deployment profile → `INTAKE_POLICY_NOT_CONFIGURED`, нуль копій і нуль action requests.
- Файл поза selection root або через link → відхилено без читання target.
- Limit boundary перевірений для рівно limit і limit + 1.
- MIME/extension mismatch не приймається мовчки.
- Archive copy/hash/read-back failure не створює `ACCEPTED`.
- Partial intake містить повну пооб'єктну звітність.
- Zero accepted objects не запускають конвеєр.

## Межі доказовості

Політика визначає required configuration і поведінку при відмові. Вона не затверджує конкретні limits або file types; їх має надати deployment profile окремого програмного проєкту.
