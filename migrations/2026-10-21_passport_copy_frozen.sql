-- Копия паспорта, на которую ссылается текст, не меняется. 21.10.2026.
--
-- Решение владельца 21.10.2026: «копию паспорта, на которую ссылается текст, —
-- запретить менять (триггер), новый паспорт = новая версия». Новая версия
-- паспорта — это новая строка passport_source_artifacts (новый файл, новый SHA),
-- а не правка старой.
--
-- Применяется ПОСЛЕДНИМ, после 2026-10-21_content_versions.sql и
-- 2026-10-21_content_versions_checks.sql. Два изменения:
--
--   1. триггер passport_copy_frozen на passport_source_artifacts: у строки, на
--      которую ссылается хоть одна версия content_versions, не меняется ничего,
--      кроме одного шага lifecycle ACTIVE → OLD (копию сменила новая версия
--      паспорта; обратно — нет). SKU, id паспорта, SHA, файл, duplicate_of и
--      прочее — нет. Удаление такой строки и так держит внешний ключ
--      content_versions → passport_source_artifacts;
--   2. та же триггерная функция content_versions_guard, что в
--      2026-10-21_content_versions_checks.sql, с одной добавкой: строка копии
--      читается FOR SHARE. Без блокировки параллельная правка копии проскакивала
--      между сверкой и записью версии (проверка #154): теперь правка ждёт конца
--      вставки и видит ссылку, а вставка ждёт конца правки и видит новый SKU.
--
-- ПОРЯДОК ВАЖЕН: два предыдущих файла заменяют ту же функцию своим телом. После
-- любого их повторного прогона — прогнать этот файл снова; проверочные запросы
-- в конце показывают, что блокировка и триггер на месте.

BEGIN;

-- Предусловие: таблица версий уже есть. Без неё триггер ниже встал бы на
-- таблицу копий и ронял бы каждый её UPDATE.
DO $$
BEGIN
    IF to_regclass('listing_data.content_versions') IS NULL THEN
        RAISE EXCEPTION 'сначала 2026-10-21_content_versions.sql и 2026-10-21_content_versions_checks.sql';
    END IF;
END $$;

-- Поиск версий, ссылающихся на копию, — для триггера ниже.
CREATE INDEX IF NOT EXISTS content_versions_passport_artifact
    ON listing_data.content_versions (passport_artifact_id)
    WHERE passport_artifact_id IS NOT NULL;

CREATE OR REPLACE FUNCTION listing_data.content_versions_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    copy_sku     text;
    copy_pass    text;
    copy_sha     text;
    found_copy   boolean;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'draft' THEN
            RAISE EXCEPTION 'listing_data.content_versions: новая версия записывается только черновиком (draft), а не %', NEW.status;
        END IF;
        IF NEW.created_at > now() + interval '5 minutes' THEN
            RAISE EXCEPTION 'listing_data.content_versions: время создания % в будущем', NEW.created_at;
        END IF;
        IF NEW.passport_artifact_id IS NOT NULL THEN
            SELECT sku_id, passport_id, sha256, true INTO copy_sku, copy_pass, copy_sha, found_copy
              FROM listing_data.passport_source_artifacts
             WHERE source_artifact_id = NEW.passport_artifact_id
               FOR SHARE;
            IF found_copy AND copy_sku IS DISTINCT FROM NEW.sku THEN
                RAISE EXCEPTION 'listing_data.content_versions: копия паспорта % относится к SKU %, а текст — к SKU %', NEW.passport_artifact_id, copy_sku, NEW.sku;
            END IF;
            IF found_copy AND copy_pass IS NOT NULL AND copy_pass IS DISTINCT FROM NEW.passport_id THEN
                RAISE EXCEPTION 'listing_data.content_versions: копия паспорта % — это паспорт %, а текст ссылается на %', NEW.passport_artifact_id, copy_pass, NEW.passport_id;
            END IF;
            IF found_copy AND copy_sha IS NOT NULL AND copy_sha IS DISTINCT FROM NEW.passport_sha256 THEN
                RAISE EXCEPTION 'listing_data.content_versions: SHA копии паспорта % не совпадает с SHA, на который ссылается текст', NEW.passport_artifact_id;
            END IF;
        END IF;
        RETURN NEW;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'listing_data.content_versions: удаление запрещено — история версий неизменяема';
    END IF;
    IF (NEW.id, NEW.sku, NEW.marketplace, NEW.asin, NEW.field, NEW.text, NEW.version,
        NEW.proposal_id, NEW.created_by, NEW.created_at, NEW.passport_id,
        NEW.passport_version, NEW.passport_sha256, NEW.passport_artifact_id, NEW.origin,
        NEW.model, NEW.skill_version, NEW.checks)
       IS DISTINCT FROM
       (OLD.id, OLD.sku, OLD.marketplace, OLD.asin, OLD.field, OLD.text, OLD.version,
        OLD.proposal_id, OLD.created_by, OLD.created_at, OLD.passport_id,
        OLD.passport_version, OLD.passport_sha256, OLD.passport_artifact_id, OLD.origin,
        OLD.model, OLD.skill_version, OLD.checks) THEN
        RAISE EXCEPTION 'listing_data.content_versions: версия % неизменяема — правка текста и происхождения только новой версией', OLD.id;
    END IF;
    IF OLD.status = NEW.status THEN
        IF (NEW.accepted_by, NEW.accepted_at, NEW.sent_by, NEW.sent_at)
           IS DISTINCT FROM (OLD.accepted_by, OLD.accepted_at, OLD.sent_by, OLD.sent_at) THEN
            RAISE EXCEPTION 'listing_data.content_versions: версия % — автор и время шага «%» уже записаны и не переписываются', OLD.id, OLD.status;
        END IF;
        RETURN NEW;
    END IF;
    IF NOT ((OLD.status = 'draft'    AND NEW.status = 'accepted')
         OR (OLD.status = 'accepted' AND NEW.status = 'sent')) THEN
        RAISE EXCEPTION 'listing_data.content_versions: статус % → % не разрешён — только draft → accepted → sent', OLD.status, NEW.status;
    END IF;
    IF OLD.status = 'accepted'
       AND (NEW.accepted_by, NEW.accepted_at) IS DISTINCT FROM (OLD.accepted_by, OLD.accepted_at) THEN
        RAISE EXCEPTION 'listing_data.content_versions: при выгрузке приёмка не переписывается';
    END IF;
    IF NEW.status = 'accepted' AND NEW.accepted_at > now() + interval '5 minutes' THEN
        RAISE EXCEPTION 'listing_data.content_versions: время приёмки % в будущем', NEW.accepted_at;
    END IF;
    IF NEW.status = 'sent' AND NEW.sent_at > now() + interval '5 minutes' THEN
        RAISE EXCEPTION 'listing_data.content_versions: время выгрузки % в будущем', NEW.sent_at;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION listing_data.passport_copy_frozen() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM listing_data.content_versions
                WHERE passport_artifact_id = OLD.source_artifact_id)
       AND ((NEW.source_artifact_id, NEW.sku_id, NEW.passport_id, NEW.run_id,
             NEW.origin_locator, NEW.archived_locator, NEW.file_name, NEW.mime_type,
             NEW.bytes, NEW.sha256, NEW.access_result, NEW.duplicate_of,
             NEW.registered_by, NEW.recorded_at)
            IS DISTINCT FROM
            (OLD.source_artifact_id, OLD.sku_id, OLD.passport_id, OLD.run_id,
             OLD.origin_locator, OLD.archived_locator, OLD.file_name, OLD.mime_type,
             OLD.bytes, OLD.sha256, OLD.access_result, OLD.duplicate_of,
             OLD.registered_by, OLD.recorded_at)
            OR (NEW.lifecycle IS DISTINCT FROM OLD.lifecycle
                AND NOT (OLD.lifecycle = 'ACTIVE' AND NEW.lifecycle = 'OLD'))) THEN
        RAISE EXCEPTION 'listing_data.passport_source_artifacts: копия % — источник текста в content_versions и не меняется (можно только пометить OLD); новый паспорт — новая строка', OLD.source_artifact_id;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS passport_copy_frozen ON listing_data.passport_source_artifacts;
CREATE TRIGGER passport_copy_frozen
    BEFORE UPDATE ON listing_data.passport_source_artifacts
    FOR EACH ROW EXECUTE FUNCTION listing_data.passport_copy_frozen();

COMMIT;

-- Проверка: блокировка копии в функции версий и триггер на копиях на месте.
SELECT position('FOR SHARE' IN prosrc) > 0 AS copy_locked,
       position('копия паспорта % относится к SKU' IN prosrc) > 0 AS sku_check_in_place
  FROM pg_proc WHERE oid = 'listing_data.content_versions_guard()'::regprocedure;

SELECT tgname FROM pg_trigger
 WHERE tgrelid = 'listing_data.passport_source_artifacts'::regclass AND NOT tgisinternal
 ORDER BY 1;
