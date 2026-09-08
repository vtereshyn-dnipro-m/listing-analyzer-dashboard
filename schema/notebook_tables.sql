-- СНИМОК фактической схемы ноутбучных таблиц. Снят с живой базы
-- 08.09.2026 через information_schema.
--
-- ЭТО НЕ МИГРАЦИЯ. Применять этот файл не нужно и нельзя: таблицы уже
-- существуют, их заводят и наполняют ноутбуки Databricks, а не наш код.
-- Файл лежит в репозитории потому, что до сих пор их схему проверить
-- было нечем — DDL жил только в Databricks, и на этом попадались
-- дважды за неделю (`listing_changes`, алиасы `synthesis_drafts`).
--
-- Снимок устаревает молча. Он не заменяет проверку, он даёт точку
-- отсчёта: увидев расхождение, сравнивайте с базой, а не с памятью.

-- Экономика ASIN за 30 дней. Читает services/economics.py.
-- Свежесть на день снимка: 08.09.2026.
CREATE TABLE listing_data.asin_economics (
    id                bigserial PRIMARY KEY,
    asin              text NOT NULL,
    marketplace       text NOT NULL,
    sessions_30d      bigint,
    units_ordered_30d bigint,
    revenue_30d       numeric,
    conversion_rate   numeric,
    avg_price         numeric,
    buy_box_pct       numeric,
    shipping_template text,
    updated_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (asin, marketplace)
);

-- Зеркало каталога Amazon. Читают matrix_setup, services/flatfile.py.
-- Свежесть на день снимка: 08.09.2026.
CREATE TABLE listing_data.catalog_source (
    asin                text NOT NULL,
    marketplace         text NOT NULL,
    seller_sku          text,
    sku_group           text,
    fulfillment_channel text,
    snapshot_date       date,
    updated_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (asin, marketplace)
);

-- Атрибуты со стороны каталога Amazon. Читает services/attributes.py.
-- Свежесть на день снимка: 02.09.2026 — обновляется реже прочих.
CREATE TABLE listing_data.listing_attributes (
    asin                 text NOT NULL,
    marketplace          text NOT NULL,
    fetched_at           timestamptz NOT NULL DEFAULT now(),
    product_type         text,
    browse_node_id       text,
    browse_node_name     text,
    browse_path          text,
    attrs_total          integer,
    attrs_filled         integer,
    attrs_empty          text,
    has_generic_keyword  boolean,
    bullets_count        integer,
    has_description      boolean,
    raw                  jsonb,
    PRIMARY KEY (asin, marketplace)
);

-- Проблемы листинга из Кабинета. Читают services/issues.py, flatfile.py.
-- Свежесть на день снимка: 07.09.2026.
--
-- Ключ — (sku, marketplace, issue_code), то есть СТРОКА, а не листинг.
-- `is_buyable` и `asin_state` при этом дублируются во всех строках пары:
-- судить о блокирующей способности кода по агрегату нельзя, см. раздел
-- «Данные Amazon» в CLAUDE.md.
CREATE TABLE listing_data.listing_issues (
    sku               text NOT NULL,
    asin              text,
    marketplace       text NOT NULL,
    is_buyable        boolean NOT NULL DEFAULT false,
    is_discoverable   boolean NOT NULL DEFAULT false,
    issue_code        text NOT NULL,
    severity          text,
    message           text,
    attribute_names   text[],
    first_seen        timestamptz NOT NULL DEFAULT now(),
    last_seen         timestamptz NOT NULL DEFAULT now(),
    resolved_at       timestamptz,
    had_sales_before  boolean,
    suppression_cause text,
    stock_qty         integer,
    asin_state        text,
    PRIMARY KEY (sku, marketplace, issue_code)
);
CREATE INDEX idx_listing_issues_sku_mp ON listing_data.listing_issues
    (sku, marketplace) WHERE resolved_at IS NULL;

-- Brand Analytics Search Query Performance. Читают seo.py, search.py,
-- страница «Синтез». Свежесть на день снимка: 05.09.2026.
CREATE TABLE listing_data.sqp_reports (
    id                 bigserial PRIMARY KEY,
    asin               text NOT NULL,
    marketplace        text NOT NULL,
    reporting_date     date NOT NULL,
    search_query       text NOT NULL,
    search_query_score numeric,
    search_query_volume bigint,
    impressions_total  bigint,
    impressions_asin   bigint,
    impressions_share  numeric,
    clicks_total       bigint,
    clicks_asin        bigint,
    clicks_share       numeric,
    click_rate         numeric,
    cart_adds_total    bigint,
    cart_adds_asin     bigint,
    cart_adds_share    numeric,
    purchases_total    bigint,
    purchases_asin     bigint,
    purchases_share    numeric,
    price_median_total numeric,
    price_median_asin  numeric,
    loaded_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (asin, marketplace, reporting_date, search_query)
);
CREATE INDEX sqp_reports_query_idx ON listing_data.sqp_reports (search_query);

-- ------------------------------------------------------------------ вью
-- listing_latest — источник истины про A+ (см. CLAUDE.md, «Данные
-- Amazon», пункт 5). Признак стабилизируется по ТРЁМ последним удачным
-- снимкам: ScrapingDog врёт про `aplus` примерно на 15% запросов, а на
-- .it по отдельным товарам на половине. Определение снято с базы.
CREATE VIEW listing_data.listing_latest AS
 SELECT DISTINCT ON (s.asin, s.marketplace) s.id, s.asin, s.marketplace,
        s.fetched_at, s.ok, s.title, s.list_price, s.display_price,
        s.b2b_price, s.in_stock, s.rating, s.review_count, s.bullet_points,
        s.raw,
        COALESCE(stable.has_aplus, false) AS has_aplus
   FROM listing_data.listing_snapshots s
   LEFT JOIN LATERAL (
        SELECT bool_or(x.has_a) AS has_aplus
          FROM (SELECT COALESCE((sub.raw ->> 'aplus')::boolean, false)
                       OR jsonb_array_length(
                            COALESCE(sub.raw -> 'aplus_images', '[]'::jsonb)) > 0
                       AS has_a
                  FROM listing_data.listing_snapshots sub
                 WHERE sub.asin = s.asin AND sub.marketplace = s.marketplace
                   AND sub.ok = true
                 ORDER BY sub.fetched_at DESC
                 LIMIT 3) x) stable ON true
  ORDER BY s.asin, s.marketplace, s.fetched_at DESC;
