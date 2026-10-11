# Decision receipt `LS-CFG-001/002`

Дата: 04.10.2026  
Рішення: `APPROVED`  
Owner/approver: `PROJECT_OWNER`  
Джерело затвердження: пряма команда користувача в робочому чаті `согласен. заполняем`.

## Затверджені значення

- Extensions: `.pdf`, `.docx`, `.xlsx`, `.csv`, `.txt`, `.md`, `.json`, `.html`, `.jpg`, `.jpeg`, `.png`, `.webp`, `.mp4`, `.mov`, `.webm`.
- Archives `.zip/.rar/.7z`, executables і macro-enabled formats не входять до allowlist.
- Maximum files: `100`.
- Maximum single file: `524288000` bytes (`500 MiB`).
- Maximum snapshot total: `5368709120` bytes (`5 GiB`).
- Maximum video duration: `1800` seconds.
- Maximum recursion depth: `5`.
- Partial intake потребує явного підтвердження користувача.
- Zero accepted objects не створює action request.

## Застосування

Canonical profile: `Listing_Suite_Source_Intake_Profile_v1.0.json`. Значення є production candidate, але не вмикають feature flag. Activation можлива лише після boundary та integration-test receipts.

## Межі доказовості

Receipt підтверджує product/policy decision, а не фактичну реалізацію обмежень у Listing Suite.
