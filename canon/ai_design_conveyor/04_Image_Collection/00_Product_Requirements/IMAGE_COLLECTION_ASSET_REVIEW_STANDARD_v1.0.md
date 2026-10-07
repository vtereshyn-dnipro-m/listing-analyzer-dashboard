# Стандарт перевірки media assets Image Collection v1.0

## Призначення

Стандарт забезпечує однаковий, evidence-bound результат Reviewer і Skeptic для кожного фактично перевіреного asset. Role-specific спосіб аналізу не змінює критерії, reason codes, verdict mapping або формат receipt.

## Область застосування

Стандарт застосовується до still і video assets Image Collector перед формуванням accepted media pool. Він не підтверджує Product Truth, права на публікацію або готовність колекції до production.

## Вхідні дані

- exact SKU, product version і Passport binding;
- collection ID та manifest binding;
- фактичний asset із path і SHA-256;
- source, lineage, target/use-case та requested downstream uses;
- metadata, rights/privacy flags і media-specific evidence;
- Context Assembly receipt для `MEDIA_COLLECTION`.

## Обов'язкові критерії

Кожний asset отримує рівно один запис для кожного `criterion_id`:

1. `ASSET_OPENED_AND_INSPECTED`;
2. `FILE_IDENTITY_AND_INTEGRITY`;
3. `SKU_AND_VERSION_MATCH`;
4. `PROVENANCE_AND_LINEAGE`;
5. `METADATA_ACCURACY`;
6. `TARGET_AND_USE_CASE_FIT`;
7. `EVIDENCE_RELATIONSHIP`;
8. `TECHNICAL_QUALITY`;
9. `PRIVACY_AND_PERSONAL_DATA`;
10. `THIRD_PARTY_MARKS`;
11. `RIGHTS_AND_DOWNSTREAM_USE`;
12. `REVIEW_PACKAGE_COMPLETENESS`.

`NOT_APPLICABLE` дозволений лише з поясненням. `NOT_VERIFIED` не дорівнює `PASS`.

## Формат результату критерію

Кожен criterion result містить:

- `applicability`;
- `result = PASS | FAIL | NOT_VERIFIED | NOT_APPLICABLE`;
- контрольований `reason_code`;
- observed fact і точні evidence refs;
- impact;
- `remediability`;
- remediation owner;
- одну дозволену action;
- умову повторної перевірки.

Вільний текст доповнює, але не замінює ці поля.

## Детерміноване визначення verdict

Порядок застосовується зверху вниз:

1. `NOT_REVIEWED`, якщо asset не відкрито повністю, SHA-256 не збігається або review coverage неповне.
2. `REJECT`, якщо є `FAIL + NOT_FIXABLE` для заявленого use або asset суперечить exact SKU/task.
3. `QUARANTINE`, якщо є `NOT_VERIFIED` чи `FAIL`, що потребує зовнішнього рішення щодо identity, Product Truth, rights або applicability.
4. `REWORK`, якщо кожен blocking `FAIL` має `FIXABLE_BY_COLLECTOR`, точного owner, allowed action і recheck condition.
5. `KEEP`, лише якщо всі applicable criteria мають `PASS`, а решта обґрунтовано `NOT_APPLICABLE`.

Reviewer/Skeptic не можуть обрати м'якший verdict, ніж випливає з criteria results.

## Downstream-use verdicts

Один загальний verdict не розширює права використання. Для кожного asset окремо фіксуються:

- `analysis`;
- `internal_reference`;
- `production_input`;
- `publication`.

Значення: `ALLOWED | LIMITED | BLOCKED | NOT_REQUESTED`. `publication=ALLOWED` цим стандартом не видається: потрібен окремий release/rights authority.

## Ролі та відповідальність

- Reviewer застосовує критерії як compliance review.
- Skeptic незалежно шукає доказову причину блокування, але використовує ті самі критерії та schema.
- Collector не створює receipts цих ролей і не змінює їхні verdicts.
- Aggregator не переоцінює evidence; він перевіряє bindings і детерміновано об'єднує результати.

## Acceptance tests

- обидві ролі використовують standard version `1.0`;
- asset sets і SHA-256 збігаються;
- присутні всі 12 унікальних criterion IDs;
- кожний негативний result має reason, evidence, impact і route fields;
- verdict відповідає mapping;
- publication authority не створюється;
- accepted pool містить лише assets із `KEEP` обох агентів для потрібного use.

## Блокери

- asset не відкрито фактично;
- відсутній criterion або дубль criterion ID;
- verdict не випливає з criteria results;
- Reviewer і Skeptic перевіряли різні bytes;
- негативний result не має evidence або remediation/escalation owner;
- довільний reason/status поза schema.

## Межі доказовості

Стандарт уніфікує перевірку та її результат. Він не доводить достовірність Product Truth, не надає права на публікацію і не усуває дефекти asset автоматично.
