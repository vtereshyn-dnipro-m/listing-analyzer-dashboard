# Image Collector manifest v0.2 → v0.3

## Призначення

Версія v0.3 робить машинно обов'язковими правила decision evidence, повторного використання, media-specific evidence, artifact lineage, reference candidates, source coverage та audit admissibility.

## Нові обов'язкові блоки

- top level: `product_reference_candidate_pack`, `source_coverage_gate`, `package_admissibility`;
- source: `source_found`, `content_retrieval`, `saved_components`, `disposition`, `html_deep_check`, `artifact_record`;
- asset: `decision_evidence`, `reuse_metadata`, `media_evidence`, `lineage`;
- target: optional `claim_id`.

## Стани та gates

- reference pack: `REFERENCE_CANDIDATE | NEEDS_PASSPORT_VALIDATION | REFERENCE_LOCK_APPROVED`;
- source coverage: `SOURCE_COVERAGE_COMPLETE | SOURCE_COVERAGE_INCOMPLETE`;
- package admissibility: `PASS | BLOCKED`;
- accepted asset не може мати `decision_usefulness=LOW`;
- `REFERENCE_LOCK_APPROVED` вимагає зовнішній approval receipt;
- HTML `NOT_RELEVANT` для зовнішнього джерела вимагає deep check;
- lineage asset має вести до artifact record пов'язаного source, а SHA lineage має збігатися з файлом.

## Міграція

Manifest v0.2 не оновлюється мовчки. Новий run створюється за v0.3. Історичний v0.2 залишається читабельним своїм schema/validator, але не проходить v0.3 без явного заповнення нових evidence blocks.

## Межі доказовості

`PACKAGE_ADMISSIBLE_FOR_AUDIT=PASS` підтверджує повноту й цілісність пакета, але не доводить claim, права на публікацію, Product Truth або майбутню ефективність creative.
