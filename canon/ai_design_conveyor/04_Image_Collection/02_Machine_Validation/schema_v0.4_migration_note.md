# Migration note: manifest v0.3 → v0.4

## Призначення

Версія v0.4 усуває можливість позитивного статусу на основі самодекларації без фізичних доказів.

## Обов'язкові зміни

- Додано `intake_evidence` з context receipt і human confirmation exact SKU.
- Додано `discovery_evidence` з файлами, SHA-256 і coverage rows для пошукових поверхонь; `LOCAL_ONLY` потребує окремого дозволу.
- `sku_passport.path_or_reference` та SHA-256 перевіряються проти фізичного файла.
- Для sources/assets потрібні `rights_evidence` і `allowed_downstream_use`; `production_input` дозволений лише з документованими правами.
- Reviewer і Skeptic надають окремі структуровані receipts, прив'язані до collection, asset IDs, file hashes і verdicts.
- Reference lock потребує структурованого схвалення агента Паспорта або process owner, прив'язаного до версії та SHA-256 Паспорта.
- Lineage relations мають посилатися на наявний artifact; `duplicate_of` і `replaces` проходять додаткові consistency checks.
- Додано dispositions для personal/sensitive data, overlays і third-party brands.
- `READY_FOR_HUMAN_REVIEW` залежить від `PASSED` review, повного source coverage, package admissibility і відсутності `NOT_REVIEWED`.
- Summary counts і target coverage перераховуються validator-ом із фактичних sources/assets.

## Сумісність

Manifest v0.3 залишається історичним і не змінюється. Нові collection створюються за schema v0.4 та instruction v1.1.
