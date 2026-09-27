-- Рендеры макетов Figma хранятся НАВСЕГДА, а не сутки в памяти процесса.
--
-- Картинки — миниатюры в списке «Перевода» и превью слайдов в редакторе —
-- рендерит Figma по запросу /v1/images. У места View владельца токена
-- (design@) это 6 запросов в МЕСЯЦ на чтение файла и рендер вместе
-- (тип лимита «low», проверено 27.09: Retry-After 266304 с, ~74 ч до
-- сброса). Суточный кэш в памяти терялся при каждом ребуте Cloud и
-- рендерил заново то, что не менялось. Теперь отрендерили раз — легло
-- сюда, дальше показываем отсюда без запроса к Figma.
--
-- Перерисовывается узел, только когда изменился ОН САМ: node_hash —
-- отпечаток поддерева узла из документа, который и так читается при
-- «Перечитать из Figma» (services/figma.py::node_hash). Не lastModified
-- файла: он меняется от любой правки в файле и перерисовывал бы все
-- картинки разом.
--
-- Раньше в 2026-09-07_figma_localization.sql было записано «картинок
-- в базе нет намеренно — оригиналы в Figma». Это остаётся правдой для
-- ОРИГИНАЛОВ: здесь не исходники, а превью для экрана (0.25 и 0.5
-- масштаба), и хранить их дешевле, чем тратить на них месячную квоту.
--
-- Права: таблица создаётся владельцем схемы, а права по умолчанию в
-- listing_data уже дают принципалу приложения (583bf6d1-…) полный
-- доступ к новым таблицам — отдельный GRANT не нужен.

BEGIN;

CREATE TABLE IF NOT EXISTS listing_data.figma_renders (
    figma_file_key  text        NOT NULL,
    node_id         text        NOT NULL,
    -- 0.25 — миниатюра в списке, 0.5 — превью слайда в редакторе
    scale           real        NOT NULL,
    node_hash       text        NOT NULL,
    png             bytea       NOT NULL,
    bytes           integer     NOT NULL,
    rendered_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (figma_file_key, node_id, scale)
);

COMMENT ON TABLE listing_data.figma_renders IS
    'PNG-рендеры узлов Figma для экрана. Перерисовываются, только когда '
    'node_hash узла в figma_products.node_hashes не совпал с сохранённым.';

-- Отпечатки узлов на момент последнего чтения файла: {"1445:541": "9f…"}.
-- По ним ensure_renders решает, свежий ли сохранённый рендер.
ALTER TABLE listing_data.figma_products
    ADD COLUMN IF NOT EXISTS node_hashes jsonb NOT NULL DEFAULT '{}'::jsonb;

COMMIT;

-- Проверка: таблица и колонка на месте, права у приложения есть.
SELECT to_regclass('listing_data.figma_renders') AS renders_table,
       (SELECT count(*) FROM information_schema.columns
         WHERE table_schema = 'listing_data' AND table_name = 'figma_products'
           AND column_name = 'node_hashes') AS node_hashes_column,
       has_table_privilege('583bf6d1-6cd0-4a89-9c44-b387ec5c21cb',
                           'listing_data.figma_renders', 'INSERT') AS app_can_write;
