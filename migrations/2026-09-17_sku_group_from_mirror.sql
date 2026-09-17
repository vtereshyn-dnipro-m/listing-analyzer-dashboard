-- SKU вместо ASIN в product_matrix.sku_group.
--
-- Парсер ввода при голом ASIN писал `sku or asin`: ASIN попадал в колонку
-- SKU и в Каталоге/выгрузке читался как «sku B0G4S9SJ3M». Таких строк две,
-- обе июльские; настоящий SKU у обеих есть в зеркале каталога. Парсер
-- исправлен, вставка теперь берёт SKU из зеркала сама. Это — данные.
--
-- Запрос общий, а не по двум строкам: если ASIN-в-SKU появится снова,
-- его закроет тот же файл. Идемпотентен.

BEGIN;

UPDATE listing_data.product_matrix m
   SET sku_group = c.sku_group
  FROM listing_data.catalog_source c
 WHERE c.asin = m.asin AND c.marketplace = m.marketplace
   AND m.sku_group = m.asin
   AND c.sku_group IS NOT NULL AND c.sku_group <> '';

-- Проверка: должно вернуть 0 строк.
SELECT asin, marketplace FROM listing_data.product_matrix WHERE sku_group = asin;

COMMIT;
