# Схема: снимок, а не источник истины

Истина в Databricks. Здесь — слепок живой базы, снятый вручную, чтобы
было с чем сверяться. Пункт 4 аудита 29.08 звучал так: «схему
ноутбучных таблиц проверить нечем, DDL живёт в Databricks, в
репозитории его нет». Теперь есть точка отсчёта.

| файл | что внутри |
|---|---|
| [objects.txt](objects.txt) | все объекты `listing_data` — имя и тип |
| [notebook_tables.sql](notebook_tables.sql) | DDL пяти ноутбучных таблиц и вью `listing_latest` |

Ни один из файлов НЕ применяется: `migrations/` — для изменений схемы,
`schema/` — для их фиксации постфактум.

## Зачем это, если сверять всё равно вручную

Одну проверку слепок делает сам, без базы:
[tests/test_schema_contract.py](../tests/test_schema_contract.py)
достаёт из SQL в коде имена таблиц и сверяет со списком. Код,
читающий несуществующий объект, падает на тесте, а не на человеке.

Так месяцами жил `policy_alerts`: страница «Методология» читала
таблицу, которой в базе нет, ловила исключение общим `except` и
говорила «Новых изменений нет — все источники соответствуют текущим
методологиям». Утверждение о политиках Amazon на пустом месте.

Допустимыми считаются объекты из `objects.txt` **плюс** таблицы,
создаваемые миграциями в `migrations/`. Поэтому свежая миграция не
роняет тест до обновления снимка — иначе трение заставило бы тест
отключить.

## Как обновить снимок

```sql
-- objects.txt
SELECT table_name,
       CASE table_type WHEN 'VIEW' THEN 'view' ELSE 'table' END
  FROM information_schema.tables
 WHERE table_schema = 'listing_data'
 ORDER BY table_name;

-- колонки для notebook_tables.sql
SELECT table_name, ordinal_position, column_name, data_type,
       is_nullable, column_default
  FROM information_schema.columns
 WHERE table_schema = 'listing_data'
 ORDER BY table_name, ordinal_position;

-- ключи и индексы
SELECT tablename, indexdef FROM pg_indexes
 WHERE schemaname = 'listing_data' ORDER BY tablename;

-- определение вью
SELECT pg_get_viewdef('listing_data.listing_latest'::regclass, true);
```

Снимок устаревает молча — это его главный недостаток, и лечится он
только повторным снятием. Дата снятия стоит в шапке каждого файла.

## Объекты, которых код не читает

В схеме есть восемь объектов, на которые в репозитории нет ни одной
ссылки. Они не мусор: семь из восьми наполняются, и, увидев их
впервые, легко построить неверную гипотезу — что и случилось с
`diagnosis_latest`.

| объект | строк на 08.09.2026 | что это |
|---|---|---|
| `suppressed_listings` | 6148 | подавленные листинги из Кабинета, свежесть 08.09; отдельно от `listing_issues` |
| `sqp_report_queue` | 1059 | очередь заказов отчётов SQP: `status`, `attempts`, `error_detail` |
| `analysis_latest` | 1005 | вью: последняя строка `listing_analysis` по паре |
| `discount_analysis` | 972 | вью: скидки и B2B-аномалии по ценам снапшота |
| `wound_down_candidates` | 129 | вью: кандидаты на вывод из ассортимента с `recommendation` |
| `diagnosis_latest` | 429 | вью: ПО ОДНОЙ строке на `sku_group` |
| `search_query_performance` | 0 | пустая, недельный SQP с разбивкой brand/total |
| `sku_economics` | 0 | пустая, выручка по `sku_group` |

**`diagnosis_latest` — не «диагноз без закрытых болей».** Название
обещает свежий срез, а вью отдаёт ПО ОДНОЙ строке на `sku_group`: 429
строк при 4382 открытых болях в `diagnosis` (08.09.2026). Переключение
Диагноза на неё выглядело бы как чистка данных, а на деле убрало бы
с экрана большую часть живых болей. Гипотеза была, проверена запросом
07.09 и отвергнута.
