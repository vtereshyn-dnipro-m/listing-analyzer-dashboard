-- Решения верификатора по конфликтам копии паспорта docx (решение владельца 28.10.2026).
--
-- «Таблица решений: конфликт, выбранная сторона или значение, источник решения,
-- автор, время, копия и её SHA. Генератор сразу перестаёт вырезать закрытое и
-- берёт решённую сторону; копия v2 не меняется; v3 потом перекрывает. В таблицу —
-- только решения с проверяемым источником (слова Ярослава, например чат 21.10)».
-- Право записи — ls.textgen.accept (администратор и пилот); проверяет страница.
--
-- Решение привязано к КОПИИ (source_artifact_id и её SHA), а не к SKU: новая
-- копия (v3) приходит со своими конфликтами, и решения по v2 к ней не относятся.
-- Действует последнее решение по конфликту копии (наибольший id); прежние
-- остаются историей. Строки не меняются и не удаляются — держит триггер.
--
-- Применяется агентом только по команде владельца «применяй
-- 2026-10-28_passport_conflict_decisions.sql» (AGENTS.md, «Автономия»). Без
-- таблицы раздел Паспорта показывает конфликты, но кнопка решения выключена и
-- называет этот файл; генератор работает по-старому.

BEGIN;

CREATE TABLE IF NOT EXISTS listing_data.passport_conflict_decisions (
    id                  bigserial   PRIMARY KEY,
    source_artifact_id  text        NOT NULL REFERENCES listing_data.passport_source_artifacts (source_artifact_id),
    artifact_sha256     text        NOT NULL CHECK (artifact_sha256 ~ '^[a-f0-9]{64}$'),
    sku_id              text        NOT NULL CHECK (sku_id <> '' AND sku_id = btrim(sku_id)),
    passport_id         text        NOT NULL CHECK (btrim(passport_id) <> ''),
    conflict_id         text        NOT NULL CHECK (conflict_id ~ '^CONFLICT-[A-Za-z0-9._-]+$'),
    decision            text        NOT NULL CHECK (decision IN ('SIDE_A', 'SIDE_B', 'VALUE')),
    value               text,
    decision_source     text        NOT NULL CHECK (char_length(btrim(decision_source)) >= 5),
    decided_by          text        NOT NULL CHECK (btrim(decided_by) <> ''),
    decided_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT passport_conflict_decisions_value CHECK (
        decision <> 'VALUE' OR (value IS NOT NULL AND btrim(value) <> ''))
);
CREATE INDEX IF NOT EXISTS passport_conflict_decisions_copy
    ON listing_data.passport_conflict_decisions (source_artifact_id, conflict_id, id);

CREATE OR REPLACE FUNCTION listing_data.passport_conflict_decisions_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    copy_sku    text;
    copy_pass   text;
    copy_sha    text;
    copy_life   text;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'listing_data.passport_conflict_decisions: решение % не меняется и не удаляется — новое решение пишется новой строкой', OLD.id;
    END IF;
    SELECT sku_id, passport_id, sha256, lifecycle INTO copy_sku, copy_pass, copy_sha, copy_life
      FROM listing_data.passport_source_artifacts
     WHERE source_artifact_id = NEW.source_artifact_id
       FOR SHARE;
    IF copy_life IS DISTINCT FROM 'ACTIVE' THEN
        RAISE EXCEPTION 'listing_data.passport_conflict_decisions: копия % не действующая (%), решение по ней не записывается', NEW.source_artifact_id, copy_life;
    END IF;
    IF copy_sku IS DISTINCT FROM NEW.sku_id OR copy_pass IS DISTINCT FROM NEW.passport_id
       OR copy_sha IS DISTINCT FROM NEW.artifact_sha256 THEN
        RAISE EXCEPTION 'listing_data.passport_conflict_decisions: SKU, паспорт или SHA не совпадают с копией %', NEW.source_artifact_id;
    END IF;
    IF NEW.decided_at > now() + interval '5 minutes' THEN
        RAISE EXCEPTION 'listing_data.passport_conflict_decisions: время решения % в будущем', NEW.decided_at;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION listing_data.passport_conflict_decisions_no_wipe() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'listing_data.passport_conflict_decisions: очистка таблицы запрещена — это история решений';
END;
$$;

DROP TRIGGER IF EXISTS passport_conflict_decisions_guard ON listing_data.passport_conflict_decisions;
CREATE TRIGGER passport_conflict_decisions_guard
    BEFORE INSERT OR UPDATE OR DELETE ON listing_data.passport_conflict_decisions
    FOR EACH ROW EXECUTE FUNCTION listing_data.passport_conflict_decisions_guard();

DROP TRIGGER IF EXISTS passport_conflict_decisions_no_wipe ON listing_data.passport_conflict_decisions;
CREATE TRIGGER passport_conflict_decisions_no_wipe
    BEFORE TRUNCATE ON listing_data.passport_conflict_decisions
    FOR EACH STATEMENT EXECUTE FUNCTION listing_data.passport_conflict_decisions_no_wipe();

COMMIT;

-- Проверка: таблица есть, приложение пишет, триггеры на месте, таблица пуста.
SELECT to_regclass('listing_data.passport_conflict_decisions') IS NOT NULL AS exists,
       has_table_privilege('583bf6d1-6cd0-4a89-9c44-b387ec5c21cb', 'listing_data.passport_conflict_decisions', 'INSERT') AS app_can_insert,
       has_sequence_privilege('583bf6d1-6cd0-4a89-9c44-b387ec5c21cb', 'listing_data.passport_conflict_decisions_id_seq', 'USAGE') AS app_can_seq,
       (SELECT count(*) FROM listing_data.passport_conflict_decisions) AS rows;

SELECT tgname FROM pg_trigger
 WHERE tgrelid = 'listing_data.passport_conflict_decisions'::regclass AND NOT tgisinternal
 ORDER BY 1;
