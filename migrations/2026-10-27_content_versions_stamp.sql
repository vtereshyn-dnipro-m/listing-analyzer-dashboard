-- Штамп версии на черновике генератора (решение владельца 27.10.2026).
--
-- «Вместе с черновиком записывать версию методологии, промпта и модели — чтобы
-- после обновления правил было понятно, почему старый текст отличается от
-- нового». Модель (`model`) и номер методологии (`skill_version`) уже пишутся.
-- Здесь — две колонки:
--   · prompt_sha256 — sha256 ровно того, что ушло в модель: методология
--     (system) и запрос с фактами паспорта (`services/textgen.prompt_sha256`);
--   · rules_version — коммит кода правил (полный sha git), по которому
--     черновик проверен и записан.
-- Обе пустые у старых строк: их не знали, когда те писались. Код пишет их, только
-- когда колонки есть, и без миграции работает по-старому, называя этот файл.
--
-- Колонки входят в список неизменяемых: штамп — это происхождение, правится
-- только новой версией, как текст. Поэтому функция версий заменяется — тело
-- дословно из 2026-10-21_passport_copy_frozen.sql (с блокировкой FOR SHARE),
-- плюс две колонки в сравнении NEW/OLD. Триггер не пересоздаётся: он уже
-- вызывает эту функцию.
--
-- ПОРЯДОК ВАЖЕН: 2026-10-21_content_versions*.sql и
-- 2026-10-21_passport_copy_frozen.sql заменяют ту же функцию своим телом. После
-- их повторного прогона — прогнать этот файл снова.
--
-- Применяется агентом только по команде владельца «применяй
-- 2026-10-27_content_versions_stamp.sql» (AGENTS.md, «Автономия»).

BEGIN;

-- Предусловие: таблица версий уже есть.
DO $$
BEGIN
    IF to_regclass('listing_data.content_versions') IS NULL THEN
        RAISE EXCEPTION 'сначала 2026-10-21_content_versions.sql, 2026-10-21_content_versions_checks.sql и 2026-10-21_passport_copy_frozen.sql';
    END IF;
END $$;

ALTER TABLE listing_data.content_versions
    ADD COLUMN IF NOT EXISTS prompt_sha256 text
        CHECK (prompt_sha256 IS NULL OR prompt_sha256 ~ '^[a-f0-9]{64}$'),
    ADD COLUMN IF NOT EXISTS rules_version text
        CHECK (rules_version IS NULL OR rules_version ~ '^[a-f0-9]{40}$');

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
        NEW.model, NEW.skill_version, NEW.checks, NEW.prompt_sha256, NEW.rules_version)
       IS DISTINCT FROM
       (OLD.id, OLD.sku, OLD.marketplace, OLD.asin, OLD.field, OLD.text, OLD.version,
        OLD.proposal_id, OLD.created_by, OLD.created_at, OLD.passport_id,
        OLD.passport_version, OLD.passport_sha256, OLD.passport_artifact_id, OLD.origin,
        OLD.model, OLD.skill_version, OLD.checks, OLD.prompt_sha256, OLD.rules_version) THEN
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

-- Проверка: обе колонки есть, функция версий их замораживает и по-прежнему
-- блокирует копию паспорта, триггеры на месте.
SELECT column_name, data_type FROM information_schema.columns
 WHERE table_schema = 'listing_data' AND table_name = 'content_versions'
   AND column_name IN ('prompt_sha256', 'rules_version')
 ORDER BY 1;

SELECT position('NEW.prompt_sha256, NEW.rules_version' IN prosrc) > 0 AS stamp_frozen,
       position('FOR SHARE' IN prosrc) > 0 AS copy_locked
  FROM pg_proc WHERE oid = 'listing_data.content_versions_guard()'::regprocedure;

SELECT tgname FROM pg_trigger
 WHERE tgrelid = 'listing_data.content_versions'::regclass AND NOT tgisinternal
 ORDER BY 1;
