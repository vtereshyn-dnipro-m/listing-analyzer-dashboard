-- listing_data.flatfile_templates — эталоны шаблонов Amazon flat file
--
-- Зачем таблица. Amazon принимает не произвольную таблицу, а свой файл:
-- вкладка «Plantilla», строки 1–6 служебные (в первой — settings с
-- templateIdentifier и датой генерации, в пятой — машинные имена атрибутов),
-- данные с 7-й. Взять эти строки неоткуда, кроме как из настоящего шаблона,
-- поэтому человек загружает Category Listings Report из Seller Central один
-- раз, а приложение хранит эталон и дописывает в его копию свои строки.
--
-- Почему не в репозитории: шаблон Amazon перевыпускает (в строке 1 живут
-- templateIdentifier и timestamp), обновлять его должен товаровед, а не
-- разработчик коммитом. Плюс он свой на каждый маркетплейс — язык подписей
-- и marketplace_id в именах атрибутов разные.
--
-- Почему строк на маркетплейс несколько. Типов товара у бренда 60, а один
-- шаблон покрывает 30: отчёт делится на файлы без пересечений
-- (ABRASIVE_WHEELS…LEVEL и MACHINE_LUBRICANT…WRENCH). Строка с DRILL,
-- положенная во второй файл, не пройдёт валидацию, поэтому каждый файл
-- отчёта — своя строка, а слотом служит имя файла.
--
-- template_bytes — тот же .xlsm, но со СРЕЗАННЫМИ строками данных: чужие
-- 456 строк в нашу выгрузку попасть не должны. Разбор при загрузке сохраняет
-- в JSON то, что мы из файла узнали: номера нужных колонок, покрываемые типы
-- товара, карту ASIN → SKU → product_type и оформление ячеек строки данных.
--
-- Применяет Databricks. Приложение схему не создаёт и не меняет.

CREATE TABLE IF NOT EXISTS listing_data.flatfile_templates (
    id             BIGSERIAL PRIMARY KEY,
    marketplace    TEXT NOT NULL,
    slot           TEXT NOT NULL,      -- имя файла-источника без расширения
    file_name      TEXT NOT NULL,
    sheet_path     TEXT NOT NULL,      -- xl/worksheets/sheetN.xml вкладки Plantilla
    columns        JSONB NOT NULL,     -- машинное имя атрибута -> номер колонки
    item_name_attr TEXT NOT NULL,      -- item_name[marketplace_id=…][language_tag=…]
    partial_label  TEXT NOT NULL,      -- подпись частичного обновления на языке шаблона
    product_types  JSONB NOT NULL,     -- типы товара, которые шаблон принимает
    sku_map        JSONB,              -- asin -> [{sku, product_type, status}]
    styles         JSONB,              -- буква колонки -> id стиля ячейки
    rows_seen      INTEGER NOT NULL DEFAULT 0,
    template_bytes BYTEA NOT NULL,     -- эталон: строки 1–6, данные вырезаны
    uploaded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (marketplace, slot)
);

-- выгрузка всегда идёт по маркетплейсу целиком: берём все его шаблоны
CREATE INDEX IF NOT EXISTS idx_flatfile_templates_mp
    ON listing_data.flatfile_templates (marketplace, slot);
