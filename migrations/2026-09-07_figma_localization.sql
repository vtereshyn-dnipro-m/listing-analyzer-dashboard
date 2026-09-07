-- Локализация макетов Figma: тексты слоёв и их переводы.
--
-- Картинок здесь нет намеренно: оригиналы остаются в Figma, готовые
-- файлы в Google Drive. Копировать их в базу значит дублировать источник
-- правды и терять качество при пересохранении.
--
-- char_limit — сколько символов помещается в слой по его ширине
-- в макете. Это НЕ рекомендация, а предел: испанский и немецкий длиннее
-- английского примерно на пятую часть, и без предела текст уезжает
-- за границу слоя, а обнаруживается это при экспорте.

CREATE TABLE IF NOT EXISTS listing_data.figma_products (
    id              bigserial PRIMARY KEY,
    asin            text NOT NULL,
    sku             text,
    name            text,
    -- «Main Images» или «A+ Premium Content» — тип секции в Figma
    section_type    text,
    page_name       text,
    figma_file_key  text NOT NULL,
    -- id секции: имена фреймов вида «carousel 2.2» повторяются у разных
    -- товаров, поэтому связь только через секцию
    figma_node_id   text NOT NULL,
    layers_count    integer NOT NULL DEFAULT 0,
    synced_at       timestamptz,
    UNIQUE (figma_file_key, figma_node_id)
);

CREATE TABLE IF NOT EXISTS listing_data.figma_layers (
    id              bigserial PRIMARY KEY,
    product_id      bigint NOT NULL
                    REFERENCES listing_data.figma_products(id) ON DELETE CASCADE,
    layer_id        text NOT NULL,
    frame_name      text,
    lang            text NOT NULL,
    source_text     text NOT NULL,
    translated_text text,
    char_limit      integer,
    -- none | translated | approved | applied
    status          text NOT NULL DEFAULT 'none',
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (layer_id, lang)
);

CREATE INDEX IF NOT EXISTS figma_layers_product_lang_idx
    ON listing_data.figma_layers (product_id, lang);
