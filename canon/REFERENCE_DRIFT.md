# Расхождения в каноне AI Design Conveyor

Производный отчёт `canon/check_references.py` по снимку `canon/MANIFEST.json`.
Канон не правится; код берёт ФАЙЛ из снимка, а не версию из ссылки.

## 1. Ссылки на версию или SHA соседа

Всего: 20.

| Где ссылка | На что | Указано | В файле | SHA |
|---|---|---|---|---|
| `02_SKU_Passport/00A_Контракт_передач_Паспорта_SKU.md` | `Listing_Suite_Integration_Contract.md` | 1.1 | 1.2 | — |
| `02_SKU_Passport/02B_Шаблон_запуска_агента_собирателя.md` | `00A_Контракт_передач_Паспорта_SKU.md` | 2.10 | 2.13 | — |
| `02_SKU_Passport/02_Агент_собиратель_Паспорта_SKU.md` | `00A_Контракт_передач_Паспорта_SKU.md` | 2.10 | 2.13 | — |
| `02_SKU_Passport/03_Агент_аудитор_качества_Паспорта_SKU.md` | `00A_Контракт_передач_Паспорта_SKU.md` | 2.10 | 2.13 | — |
| `02_SKU_Passport/06D_MVP_Сценарии_приёмки.md` | `06F_MVP_Negative_Fixtures_v1.3.md` | 1.2 | 1.3 | — |
| `02_SKU_Passport/06E_MVP_Реестр_вопросов_и_ответов.md` | `00A_Контракт_передач_Паспорта_SKU.md` | 2.10 | 2.13 | — |
| `02_SKU_Passport/06F_MVP_Negative_Fixtures.md` | `00A_Контракт_передач_Паспорта_SKU.md` | 2.6 | 2.13 | не совпадает |
| `02_SKU_Passport/06F_MVP_Negative_Fixtures_v1.1.md` | `00A_Контракт_передач_Паспорта_SKU.md` | 2.6 | 2.13 | не совпадает |
| `02_SKU_Passport/06F_MVP_Negative_Fixtures_v1.1.md` | `02C_Контракт_выхода_агента_собирателя.md` | 18 | 23 | не совпадает |
| `02_SKU_Passport/06F_MVP_Negative_Fixtures_v1.2.md` | `00A_Контракт_передач_Паспорта_SKU.md` | 2.7 | 2.13 | не совпадает |
| `02_SKU_Passport/06F_MVP_Negative_Fixtures_v1.2.md` | `02C_Контракт_выхода_агента_собирателя.md` | 19 | 23 | не совпадает |
| `02_SKU_Passport/06F_MVP_Negative_Fixtures_v1.3.md` | `00A_Контракт_передач_Паспорта_SKU.md` | 2.10 | 2.13 | не совпадает |
| `02_SKU_Passport/06F_MVP_Negative_Fixtures_v1.3.md` | `02C_Контракт_выхода_агента_собирателя.md` | 20 | 23 | не совпадает |
| `02_SKU_Passport/06_MVP_Агент_верификатор_интервьюер.md` | `00A_Контракт_передач_Паспорта_SKU.md` | 2.10 | 2.13 | — |
| `02_SKU_Passport/Listing_Suite_Developer_Delivery_Package.md` | `Listing_Suite_Integration_Contract.md` | 1.0 | 1.2 | — |
| `02_SKU_Passport/Listing_Suite_Developer_Delivery_Package.md` | `Listing_Suite_UI_Message_Mapping.md` | 1.0 | 1.1 | — |
| `02_SKU_Passport/Listing_Suite_Implementation_Handoff.md` | `Listing_Suite_Integration_Contract.md` | 1.1 | 1.2 | — |
| `02_SKU_Passport/Listing_Suite_Implementation_Handoff.md` | `00_Агент_координатор_конвейера_Паспорта_SKU.md` | 2.7 | 2.9 | — |
| `02_SKU_Passport/Listing_Suite_Implementation_Handoff.md` | `Listing_Suite_UI_Message_Mapping.md` | 1.0 | 1.1 | — |
| `02_SKU_Passport/Listing_Suite_ТЗ_Контент_Паспорт_SKU.md` | `Listing_Suite_Integration_Contract.md` | 1.1 | 1.2 | — |

## 2. Реестры графа против `AI_DESIGN_EXECUTION_GRAPH_CONTRACT.md`

Поле объявлено в контракте обязательным, в реестре его нет.

| Реестр | Поле | Нет у | Всего |
|---|---|---|---|
| `AI_DESIGN_CORE_EDGE_REGISTRY.json` | `action_proposal_schema` | 87 | 87 |
| `AI_DESIGN_CORE_EDGE_REGISTRY.json` | `consequence_tier` | 87 | 87 |
| `AI_DESIGN_CORE_EDGE_REGISTRY.json` | `policy_decision_receipt` | 87 | 87 |
| `AI_DESIGN_CORE_EDGE_REGISTRY.json` | `authority_binding` | 87 | 87 |
| `AI_DESIGN_CORE_EDGE_REGISTRY.json` | `canonical_action_digest_expression` | 87 | 87 |
| `AI_DESIGN_CORE_EDGE_REGISTRY.json` | `execution_broker` | 87 | 87 |
| `AI_DESIGN_CORE_EDGE_REGISTRY.json` | `effect_verification_contract` | 87 | 87 |

## 3. Схема состояния запуска

- `ai_design_run_state.schema.json` → `lifecycle_state` не допускает состояний, которые контракт графа («Стани Run State») объявляет: `RUN_CREATED`, `RUN_FAILED`, `RUN_CANCELLED`.
- `ai_design_run_state.schema.json` → `product_root` требует путь с буквой диска Windows (`^[A-Za-z]:\\.+`); путь тома Unity Catalog (`/Volumes/…`) под него не подходит.
