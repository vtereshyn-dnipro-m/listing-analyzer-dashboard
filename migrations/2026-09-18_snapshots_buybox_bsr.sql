-- Buy Box и BSR — из сборщика, колонками, а не регулярками при отрисовке.
--
-- Оба поля лежат в raw каждого снапшота с июля, но не читались:
-- sold_by/merchant_id — кто держит Buy Box (767 пар наш магазин, 264 —
-- предложения нет вовсе, 4 — Amazon EU), product_information — ранг
-- строкой на языке страницы. Ранг разбирал Каталог регулярками при
-- каждой отрисовке и брал ПЕРВЫЙ подходящий ключ: у ES перед BSR стоит
-- «Rango de medición», у IT — «Composizione della batteria»; отсюда
-- разное покрытие по рынкам. Теперь разбирает ноутбук один раз,
-- парсер один на всех (services/bsr.py, тест на девять языков), в
-- колонках — уже число и категория.
--
-- buy_box_owner: own / amazon / other / none. none — на странице нет
-- предложения (sold_by отсутствует). Наш merchant id один на все
-- рынки (A4JU8NB3VJG0K), имя магазина по рынкам разное — поэтому
-- различаем по id. Сырой sold_by рядом, чтобы «other» был с именем.
--
-- bsr_rank — самый УЗКИЙ ранг (подкатегория), как и раньше на экране:
-- широкий у десятка товаров почти одинаков и ничего не различает.
-- Старые снапшоты остаются с NULL — экран для них разбирает raw тем же
-- парсером; заполнять историю не нужно, она дорисуется сама по кругу.
--
-- Вью listing_latest перечисляет колонки явно — дописываем четыре
-- в конец (CREATE OR REPLACE VIEW позволяет добавлять только в конец
-- и не меняя существующих).

BEGIN;

ALTER TABLE listing_data.listing_snapshots
    ADD COLUMN IF NOT EXISTS buy_box_owner  text,
    ADD COLUMN IF NOT EXISTS buy_box_seller text,
    ADD COLUMN IF NOT EXISTS bsr_rank       integer,
    ADD COLUMN IF NOT EXISTS bsr_category   text;

COMMENT ON COLUMN listing_data.listing_snapshots.buy_box_owner IS
    'Кто в Buy Box на момент снапшота: own | amazon | other | none (предложения нет)';
COMMENT ON COLUMN listing_data.listing_snapshots.buy_box_seller IS
    'Сырой sold_by со страницы; NULL, когда предложения нет';
COMMENT ON COLUMN listing_data.listing_snapshots.bsr_rank IS
    'Best Sellers Rank в самой узкой подкатегории; NULL — не найден или не разобран';
COMMENT ON COLUMN listing_data.listing_snapshots.bsr_category IS
    'Подкатегория ранга, как на странице (на языке рынка)';

-- Тело вью — из pg_get_viewdef живой базы (18.09), меняются только четыре
-- добавленные колонки в конце. Снимок в schema/notebook_tables.sql
-- совпадает с живым определением.
CREATE OR REPLACE VIEW listing_data.listing_latest AS
 SELECT DISTINCT ON (s.asin, s.marketplace) s.id, s.asin, s.marketplace,
        s.fetched_at, s.ok, s.title, s.list_price, s.display_price,
        s.b2b_price, s.in_stock, s.rating, s.review_count, s.bullet_points,
        s.raw,
        COALESCE(stable.has_aplus, false) AS has_aplus,
        s.buy_box_owner, s.buy_box_seller, s.bsr_rank, s.bsr_category
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

-- Проверка: четыре колонки на месте и во вью.
SELECT column_name FROM information_schema.columns
 WHERE table_schema = 'listing_data' AND table_name = 'listing_latest'
   AND column_name IN ('buy_box_owner', 'buy_box_seller', 'bsr_rank', 'bsr_category');

COMMIT;
