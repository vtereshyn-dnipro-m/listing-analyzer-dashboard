-- content_versions: три проверки после #153. 21.10.2026.
--
-- Применяется ПОСЛЕ 2026-10-21_content_versions.sql — можно тем же заходом,
-- подряд. Сама таблица не меняется: заменяется только тело триггерной функции.
-- Первый файл не правится намеренно — он смержен, и правка применённой миграции
-- запрещена правилом проекта.
--
-- Решение владельца 21.10.2026 — три необязательных пункта проверяющего #153,
-- «особенно сверку SKU паспорта с SKU текста»:
--   1. копия паспорта, на которую ссылается версия, — того же SKU: строка
--      passport_source_artifacts с другим sku_id означает текст, построенный по
--      чужому паспорту. Заодно сверяются id паспорта и SHA копии, если они в
--      строке регистрации записаны;
--   2. время шага не в будущем: created_at, accepted_at и sent_at не позже
--      «сейчас» с запасом в 5 минут на расхождение часов;
--   3. (в тесте) шапка tests/test_content_versions_sql.py говорит, что файлы
--      сверяются байт в байт.
--
-- Права не меняются: функция заменяется на месте, триггеры остаются прежними.

BEGIN;

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
             WHERE source_artifact_id = NEW.passport_artifact_id;
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

COMMIT;

-- Проверка: функция заменена (в теле есть сверка SKU копии паспорта), оба
-- триггера на месте.
SELECT position('копия паспорта % относится к SKU' IN prosrc) > 0 AS sku_check_in_place
  FROM pg_proc WHERE oid = 'listing_data.content_versions_guard()'::regprocedure;

SELECT tgname FROM pg_trigger
 WHERE tgrelid = 'listing_data.content_versions'::regclass AND NOT tgisinternal
 ORDER BY 1;
