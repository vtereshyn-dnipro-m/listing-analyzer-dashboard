-- «Генератор текстов (пилот)»: хранилище сгенерированного контента. 21.10.2026.
--
-- Решения владельца 21.10.2026 (TASKS.md, T-20; docs/textgen.md):
--   - своя таблица, а не synthesis_changes. У synthesis_changes обязательный ASIN
--     (у нового товара его нет), одна строка на пару «тайтл + Highlights», нет
--     версий, автора и ссылки на паспорт; её же читает выгрузка flat file Синтеза
--     для Amazon, и принятый здесь текст не должен туда попасть;
--   - одна строка — одна ВЕРСИЯ одного поля: title, highlight, bullet_1…5,
--     description; ключ — точный SKU (99601000-B) и рынок, ASIN не обязателен;
--   - статусы: draft (черновик) → accepted (принято) → sent (выгружено и
--     передано Марко, отдельной кнопкой). Сверка с живым листингом — позже;
--   - ссылка на паспорт-источник: id, версия, SHA и строка регистрации копии
--     в passport_source_artifacts (копия docx — в томе UC,
--     <sku>/<passport_id>/v<версия>/).
--
-- Действующая версия поля — последняя по номеру среди accepted и sent. Статуса
-- «заменено» нет намеренно: владелец назвал три статуса, а «какая версия
-- действует» отвечает номер версии, а не отдельная метка.
--
-- Что держит БАЗА, а не код:
--   1. новая версия записывается только черновиком; текст, происхождение и id
--      версии потом не меняются — правка только новой версией;
--   2. статус идёт только вперёд — draft → accepted → sent — с непустым автором
--      и временем каждого шага, время не раньше предыдущего шага; записанные
--      автор и время не переписываются;
--   3. удаления нет — ни построчно, ни очисткой таблицы целиком;
--   4. номер версии у «SKU + рынок + поле» не повторяется, а повтор записи того
--      же прогона (proposal_id) у того же товара не создаёт второй строки.
--
-- Права: права по умолчанию в listing_data дают принципалу приложения
-- (583bf6d1-…) полный доступ к новым таблицам, отдельный GRANT не нужен — как в
-- 2026-10-07_passport_sku_core.sql. Проверка — в конце файла.
--
-- Применяет владелец через Databricks. Код, который пишет в таблицу, едет
-- отдельными PR (загрузка паспорта, кнопки «Принять» и «Выгрузить»).

BEGIN;

CREATE TABLE IF NOT EXISTS listing_data.content_versions (
    id                    bigserial   PRIMARY KEY,
    sku                   text        NOT NULL CHECK (sku <> '' AND sku = btrim(sku)),
    marketplace           text        NOT NULL CHECK (marketplace ~ '^[a-z]{2}(\.[a-z]{2})?$'),
    asin                  text        CHECK (asin IS NULL OR asin ~ '^B0[A-Z0-9]{8}$'),
    field                 text        NOT NULL CHECK (field IN (
                              'title', 'highlight',
                              'bullet_1', 'bullet_2', 'bullet_3', 'bullet_4', 'bullet_5',
                              'description')),
    text                  text        NOT NULL,
    text_len              integer     GENERATED ALWAYS AS (char_length(text)) STORED,
    version               integer     NOT NULL CHECK (version > 0),
    proposal_id           text        NOT NULL CHECK (btrim(proposal_id) <> ''),

    status                text        NOT NULL DEFAULT 'draft'
                                      CHECK (status IN ('draft', 'accepted', 'sent')),
    created_by            text        NOT NULL CHECK (btrim(created_by) <> ''),
    created_at            timestamptz NOT NULL DEFAULT now(),
    accepted_by           text        CHECK (accepted_by IS NULL OR btrim(accepted_by) <> ''),
    accepted_at           timestamptz,
    sent_by               text        CHECK (sent_by IS NULL OR btrim(sent_by) <> ''),
    sent_at               timestamptz,

    -- версия паспорта — строкой, как в passport_objects и в схеме канона
    passport_id           text        CHECK (passport_id IS NULL OR btrim(passport_id) <> ''),
    passport_version      text        CHECK (passport_version IS NULL OR btrim(passport_version) <> ''),
    passport_sha256       text        CHECK (passport_sha256 IS NULL OR passport_sha256 ~ '^[a-f0-9]{64}$'),
    passport_artifact_id  text        REFERENCES listing_data.passport_source_artifacts (source_artifact_id),

    origin                text        NOT NULL CHECK (origin IN ('model', 'manual', 'model_edited')),
    model                 text        CHECK (model IS NULL OR btrim(model) <> ''),
    skill_version         integer,
    checks                jsonb       NOT NULL DEFAULT '[]'::jsonb,

    -- шаг статуса записан вместе с автором и временем
    CONSTRAINT content_versions_status_steps CHECK (
        (status = 'draft'    AND accepted_at IS NULL     AND accepted_by IS NULL
                             AND sent_at IS NULL         AND sent_by IS NULL)
     OR (status = 'accepted' AND accepted_at IS NOT NULL AND accepted_by IS NOT NULL
                             AND sent_at IS NULL         AND sent_by IS NULL)
     OR (status = 'sent'     AND accepted_at IS NOT NULL AND accepted_by IS NOT NULL
                             AND sent_at IS NOT NULL     AND sent_by IS NOT NULL)),
    -- шаги — по порядку во времени
    CONSTRAINT content_versions_steps_in_order CHECK (
        (accepted_at IS NULL OR accepted_at >= created_at)
        AND (sent_at IS NULL OR sent_at >= accepted_at)),
    -- паспорт либо назван целиком, либо не назван вовсе (ручной ввод, новый товар);
    -- ссылка на копию паспорта — только вместе с самим паспортом
    CONSTRAINT content_versions_passport_whole CHECK (
        (passport_id IS NULL AND passport_version IS NULL AND passport_sha256 IS NULL
                             AND passport_artifact_id IS NULL)
     OR (passport_id IS NOT NULL AND passport_version IS NOT NULL AND passport_sha256 IS NOT NULL)),
    -- модель названа, если текст от неё
    CONSTRAINT content_versions_model_named CHECK (origin = 'manual' OR model IS NOT NULL)
);

CREATE UNIQUE INDEX IF NOT EXISTS content_versions_version
    ON listing_data.content_versions (sku, marketplace, field, version);
CREATE UNIQUE INDEX IF NOT EXISTS content_versions_proposal_field
    ON listing_data.content_versions (proposal_id, sku, marketplace, field);
CREATE INDEX IF NOT EXISTS content_versions_current
    ON listing_data.content_versions (sku, marketplace, field, version DESC)
    WHERE status IN ('accepted', 'sent');
CREATE INDEX IF NOT EXISTS content_versions_passport
    ON listing_data.content_versions (passport_id, passport_version);

-- Новая версия — только черновиком: статус и шаги появляются через UPDATE, где их
-- стережёт тот же триггер, — иначе «только вперёд» обходится вставкой сразу «sent».
-- Текст неизменяем, статус — только вперёд, удаления нет.
CREATE OR REPLACE FUNCTION listing_data.content_versions_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'draft' THEN
            RAISE EXCEPTION 'listing_data.content_versions: новая версия записывается только черновиком (draft), а не %', NEW.status;
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
    RETURN NEW;
END;
$$;

-- Очистка таблицы целиком строчный триггер не видит — для неё свой, на оператор.
CREATE OR REPLACE FUNCTION listing_data.content_versions_no_wipe() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'listing_data.content_versions: очистка таблицы запрещена — история версий неизменяема';
END;
$$;

DROP TRIGGER IF EXISTS content_versions_guard ON listing_data.content_versions;
CREATE TRIGGER content_versions_guard
    BEFORE INSERT OR UPDATE OR DELETE ON listing_data.content_versions
    FOR EACH ROW EXECUTE FUNCTION listing_data.content_versions_guard();

DROP TRIGGER IF EXISTS content_versions_no_wipe ON listing_data.content_versions;
CREATE TRIGGER content_versions_no_wipe
    BEFORE TRUNCATE ON listing_data.content_versions
    FOR EACH STATEMENT EXECUTE FUNCTION listing_data.content_versions_no_wipe();

COMMIT;

-- Проверка: таблица на месте, приложение может писать, оба триггера стоят.
SELECT to_regclass('listing_data.content_versions') IS NOT NULL AS exists,
       has_table_privilege('583bf6d1-6cd0-4a89-9c44-b387ec5c21cb',
                           'listing_data.content_versions', 'INSERT') AS app_can_insert,
       has_table_privilege('583bf6d1-6cd0-4a89-9c44-b387ec5c21cb',
                           'listing_data.content_versions', 'UPDATE') AS app_can_update;

SELECT tgname FROM pg_trigger
 WHERE tgrelid = 'listing_data.content_versions'::regclass AND NOT tgisinternal
 ORDER BY 1;
