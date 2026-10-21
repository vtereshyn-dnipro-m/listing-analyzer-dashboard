-- Журнал вызовов модели «Генератора текстов» и лимиты по нему. 21.10.2026.
--
-- Решение владельца 21.10.2026: «Сгенерировать» — право ls.textgen.accept; лимит —
-- 10 вызовов на товар в сутки, $1 на товар, $10 в сутки на весь пилот; при
-- превышении кнопка выключается с объяснением.
--
-- Лимит считается по базе, а не по сессии: вкладок и людей может быть несколько, а
-- `ai.usage_totals()` живёт в одной вкладке. Каждый вызов — строка: перед вызовом она
-- РЕЗЕРВИРУЕТ худшую цену (status = 'started', cost_usd — оценка сверху), после —
-- получает фактическую (ok / failed). Сумма считается и по незаконченным: зависший
-- вызов держит свою оценку, а не обнуляет лимит.
--
-- Строки не удаляются и задним числом не переписываются — иначе лимит обходится
-- чисткой журнала. Держит триггер: удаление и очистка таблицы запрещены, строка
-- меняется один раз — started → ok | failed, и только поля итога.
--
-- Применяется агентом по команде владельца «применяй 2026-10-21_textgen_calls.sql»
-- (AGENTS.md, «Автономия»). Без таблицы кнопка генерации выключена и называет
-- этот файл.
BEGIN;

CREATE TABLE IF NOT EXISTS listing_data.textgen_calls (
    id              bigserial     PRIMARY KEY,
    sku             text          NOT NULL CHECK (sku <> '' AND sku = btrim(sku)),
    marketplace     text          NOT NULL CHECK (marketplace ~ '^[a-z]{2}(\.[a-z]{2})?$'),
    actor           text          NOT NULL CHECK (btrim(actor) <> ''),
    provider        text          NOT NULL CHECK (btrim(provider) <> ''),
    model           text          NOT NULL CHECK (btrim(model) <> ''),
    status          text          NOT NULL DEFAULT 'started' CHECK (status IN ('started', 'ok', 'failed')),
    started_at      timestamptz   NOT NULL DEFAULT now(),
    finished_at     timestamptz,
    input_tokens    integer       CHECK (input_tokens IS NULL OR input_tokens >= 0),
    output_tokens   integer       CHECK (output_tokens IS NULL OR output_tokens >= 0),
    cost_usd        numeric(10,4) NOT NULL CHECK (cost_usd >= 0),
    proposal_id     text,
    error           text,
    CONSTRAINT textgen_calls_finish CHECK (
        (status = 'started' AND finished_at IS NULL)
     OR (status IN ('ok', 'failed') AND finished_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS textgen_calls_day ON listing_data.textgen_calls (started_at);
CREATE INDEX IF NOT EXISTS textgen_calls_sku_day ON listing_data.textgen_calls (sku, started_at);

CREATE OR REPLACE FUNCTION listing_data.textgen_calls_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'listing_data.textgen_calls: удаление запрещено — по журналу считаются лимиты';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'started' THEN
            RAISE EXCEPTION 'listing_data.textgen_calls: вызов записывается только как started, а не %', NEW.status;
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.status <> 'started' THEN
        RAISE EXCEPTION 'listing_data.textgen_calls: вызов % уже завершён (%) и не меняется', OLD.id, OLD.status;
    END IF;
    IF NEW.status NOT IN ('ok', 'failed') THEN
        RAISE EXCEPTION 'listing_data.textgen_calls: started → %: только ok или failed', NEW.status;
    END IF;
    IF (NEW.id, NEW.sku, NEW.marketplace, NEW.actor, NEW.provider, NEW.model, NEW.started_at)
       IS DISTINCT FROM (OLD.id, OLD.sku, OLD.marketplace, OLD.actor, OLD.provider, OLD.model, OLD.started_at) THEN
        RAISE EXCEPTION 'listing_data.textgen_calls: вызов % — меняются только поля итога', OLD.id;
    END IF;
    RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION listing_data.textgen_calls_no_wipe() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'listing_data.textgen_calls: очистка таблицы запрещена — по журналу считаются лимиты';
END $$;

DROP TRIGGER IF EXISTS textgen_calls_guard ON listing_data.textgen_calls;
CREATE TRIGGER textgen_calls_guard
    BEFORE INSERT OR UPDATE OR DELETE ON listing_data.textgen_calls
    FOR EACH ROW EXECUTE FUNCTION listing_data.textgen_calls_guard();

DROP TRIGGER IF EXISTS textgen_calls_no_wipe ON listing_data.textgen_calls;
CREATE TRIGGER textgen_calls_no_wipe
    BEFORE TRUNCATE ON listing_data.textgen_calls
    FOR EACH STATEMENT EXECUTE FUNCTION listing_data.textgen_calls_no_wipe();

COMMIT;

-- Проверка: таблица есть, приложение пишет и меняет, триггеры на месте.
SELECT to_regclass('listing_data.textgen_calls') IS NOT NULL AS exists,
       has_table_privilege('583bf6d1-6cd0-4a89-9c44-b387ec5c21cb', 'listing_data.textgen_calls', 'INSERT') AS app_can_insert,
       has_table_privilege('583bf6d1-6cd0-4a89-9c44-b387ec5c21cb', 'listing_data.textgen_calls', 'UPDATE') AS app_can_update,
       has_sequence_privilege('583bf6d1-6cd0-4a89-9c44-b387ec5c21cb', 'listing_data.textgen_calls_id_seq', 'USAGE') AS app_can_seq;

SELECT tgname FROM pg_trigger
 WHERE tgrelid = 'listing_data.textgen_calls'::regclass AND NOT tgisinternal
 ORDER BY 1;
