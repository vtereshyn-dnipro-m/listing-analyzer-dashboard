# Decision receipt LS-CFG-005 — canonical authority matrix

Версія: 1.0  
Дата: 04.10.2026  
Статус: `CONTRACT_READY_BINDING_REQUIRED`

## Рішення

Затверджено сім канонічних ролей, їхні action permissions, окрему SKU-scope перевірку, fail-closed для unmapped identity та заборону довіряти `actor_authority` від UI. `PASSPORT_ADMIN` явно має право подавати evidence delta.

Реальні IdP issuer, group IDs, claim names і membership не затверджені та не вигадуються. До їхнього внесення profile має `binding_status=BINDING_REQUIRED`, а всі mutation та archive-access evaluations завершуються `AUTHORITY_PROFILE_NOT_ACTIVE`.

## Підтвердження

- Власник canonical matrix: `PROJECT_OWNER`.
- Погодження: пряма команда користувача від 04.10.2026 — «хорошо. делай».
- Канонічний контракт: `Listing_Suite_Authority_Mapping_Contract.md`.
- Production-candidate profile: `Listing_Suite_Authority_Profile_v1.0.json`.

## Умова закриття LS-CFG-005

Security/identity owner додає перевірені bindings, profile переходить у `BOUND`, проходять authority integration tests, а deployment manifest посилається на exact profile version/SHA. Лише після цього `LS-CFG-005` може стати `CLOSED`.

## Межі доказовості

Receipt затверджує модель доступу, але не підтверджує реальну IdP інтеграцію, directory membership або production activation.
