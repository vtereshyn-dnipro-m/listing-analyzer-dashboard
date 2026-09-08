-- Товар макета — один на файл, а не один на языковую страницу.
--
-- Первое чтение Figma показало, чем плох прежний ключ
-- (figma_file_key, figma_node_id): узел свой на КАЖДОЙ языковой
-- странице, поэтому один товар лёг в базу четырьмя строками —
-- Battery stapler CC-36 отдельно на UK/US, DE, IT, ES. На экране это
-- выглядело как четыре разных товара, а сводка «Все языки» показывала
-- ноль: ни одна из четырёх записей не имела всех языков, потому что
-- у каждой был ровно один.
--
-- Товар определяется парой (ASIN, тип секции): «Main Images» и
-- «A+ Premium Content» — разный контент одного товара, и держать их
-- вместе нельзя. Язык переезжает туда, где ему место — в слой
-- (figma_layers.lang), а страница и узел остаются справочными полями
-- со стороны ИСХОДНИКА.
--
-- Данные перед сменой ключа удаляются намеренно, все 17 строк. Это не
-- потеря работы: разбор принимал за секцию текстовый слой-подпись,
-- поэтому у каждого товара оказался ровно один «слой», а его текст —
-- имя самой секции. Восемь строк со статусом applied — тоже не
-- переводы: это те же имена секций, приехавшие с неанглийских
-- страниц. Настоящих переводов в таблице нет ни одного (проверено
-- 08.09.2026).

BEGIN;

DELETE FROM listing_data.figma_layers;
DELETE FROM listing_data.figma_products;

ALTER TABLE listing_data.figma_products
    DROP CONSTRAINT IF EXISTS figma_products_figma_file_key_figma_node_id_key;

-- страница и узел теперь описывают исходник, а не товар целиком
ALTER TABLE listing_data.figma_products
    ALTER COLUMN figma_node_id DROP NOT NULL;

ALTER TABLE listing_data.figma_products
    ADD CONSTRAINT figma_products_file_asin_type_key
    UNIQUE (figma_file_key, asin, section_type);

COMMIT;
