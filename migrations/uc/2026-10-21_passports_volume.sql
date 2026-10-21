-- Том Unity Catalog для копий паспортов SKU (docx). 21.10.2026.
--
-- Решение владельца 21.10.2026: копия паспорта, по которой написан текст
-- «Генератора текстов», лежит в томе UC — в НАШЕЙ схеме dnipro_m.listing_data,
-- а не в dnipro_m.dnipro_m. Путь внутри тома:
--   <sku>/<passport_id>/v<версия>/<passport_id>_v<версия>.docx
-- Пишет services/passport_copies.py (кнопка на странице генератора), копия не
-- перезаписывается, регистрация — строка listing_data.passport_source_artifacts.
--
-- Это НЕ миграция listing_data (Lakebase/Postgres), а SQL Unity Catalog:
-- выполняется в SQL-редакторе Databricks (или в ноутбуке) владельцем схемы.
-- scratchpad/apply_migration.py этот файл не применяет — он не прямо в migrations/.
--
-- Сейчас на каталоге dnipro_m у группы `account users` стоят ALL_PRIVILEGES и
-- MANAGE (проверено 21.10.2026), поэтому том без грантов ниже уже был бы открыт
-- приложению — и всем в аккаунте. Гранты ниже делают доступ приложения явным и
-- не зависящим от этой широкой выдачи; сужать её — отдельное решение владельца
-- каталога.

CREATE VOLUME IF NOT EXISTS dnipro_m.listing_data.passports
  COMMENT 'Listing Suite: копии паспортов SKU (docx), <sku>/<passport_id>/v<версия>/. Не перезаписываются; регистрация — listing_data.passport_source_artifacts. Решение владельца 21.10.2026.';

-- Приложение Listing Suite (kabinet-dashboard-sp): пишет копию и читает её обратно
-- для сверки SHA. WRITE VOLUME разрешает и удаление, но в коде удаления нет:
-- копия неизменна по решению владельца.
GRANT USE CATALOG ON CATALOG dnipro_m TO `583bf6d1-6cd0-4a89-9c44-b387ec5c21cb`;
GRANT USE SCHEMA ON SCHEMA dnipro_m.listing_data TO `583bf6d1-6cd0-4a89-9c44-b387ec5c21cb`;
GRANT READ VOLUME, WRITE VOLUME ON VOLUME dnipro_m.listing_data.passports
  TO `583bf6d1-6cd0-4a89-9c44-b387ec5c21cb`;

-- По желанию владельца: агенту (claude-uc-ro) — только чтение, чтобы сверять копии.
-- GRANT USE SCHEMA ON SCHEMA dnipro_m.listing_data TO `b1698364-6ec5-4240-8cd6-e06dd6e60856`;
-- GRANT READ VOLUME ON VOLUME dnipro_m.listing_data.passports TO `b1698364-6ec5-4240-8cd6-e06dd6e60856`;

-- Проверка:
DESCRIBE VOLUME dnipro_m.listing_data.passports;
SHOW GRANTS ON VOLUME dnipro_m.listing_data.passports;
