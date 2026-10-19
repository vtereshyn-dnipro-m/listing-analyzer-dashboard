-- Сводки циклов автономной работы агента Listing Suite (19.10.2026, вариант Б, решение владельца).
--
-- Агент кладёт сводку строкой сюда, в СВОЮ базу; в тот же бот её отправляет задача Кабинета
-- «Kabinet - Agent Cycle Report», забирая неотправленное вторым источником. Агент Listing Suite
-- не касается ни базы Кабинета, ни секрета бота (docs/autonomy.md, «Канал записи сводки»).
-- Форма таблицы — та же, что у kabinet_data.agent_cycle_reports (kabinet-dashboard #328):
-- одна задача отправки читает обе одинаково.
--
-- Кто что может (меньше нельзя, больше не нужно):
--   claude_code_report   — роль агента ТОЛЬКО на вставку: колонки title/done/merged/waiting/problems
--                          и последовательность id. Ни чтения, ни других таблиц, ни sent_at.
--                          Её заводит владелец (пароль — секрет, в файл не пишется), строка
--                          подключения — в .mcp.json, сервер ls-cycle-report
--                          (mcp_servers/cycle_report.py). Нет роли — гранты пропускаются с NOTICE.
--   b1698364-…           — принципал задач Кабинета: чтение и отметка об отправке. Отдельным файлом
--                          2026-10-19_agent_cycle_reports_kabinet_grants.sql, применяется вместе
--                          с PR Кабинета.
--   583bf6d1-…           — приложение: таблица ему не нужна, права по умолчанию снимаются.
--
-- Применяет владелец схемы (v.tereshyn@dniprom.com) через Databricks, после мержа и после
-- того, как заведена роль claude_code_report.

BEGIN;

CREATE TABLE IF NOT EXISTS listing_data.agent_cycle_reports (
    id          bigserial PRIMARY KEY,
    created_at  timestamptz NOT NULL DEFAULT now(),
    title       text NOT NULL,             -- «Listing Suite · Цикл 19.10 14:00» — короткая шапка
    done        text,                      -- что сделано (строки через перевод строки)
    merged      text,                      -- что смержено САМ (уровень «сам») — номера PR и одна фраза
    waiting     text,                      -- что ждёт владельца: «мержи #N», ответ, секрет
    problems    text,                      -- что не получилось / красные проверки
    sent_at     timestamptz,               -- когда ушло в бот; NULL — ещё не отправлено (ставит задача Кабинета)
    send_error  text,                      -- последняя ошибка отправки (без токена и чата)
    attempts    int NOT NULL DEFAULT 0     -- неудачных отправок (ведёт задача Кабинета)
);
CREATE INDEX IF NOT EXISTS agent_cycle_reports_unsent_idx
    ON listing_data.agent_cycle_reports (id) WHERE sent_at IS NULL;
COMMENT ON TABLE listing_data.agent_cycle_reports IS
  'Сводки циклов автономной работы агента Listing Suite; отправляет в бот задача Kabinet - Agent Cycle Report.';

-- Права по умолчанию схемы дают приложению всё — ему эта таблица не нужна.
REVOKE ALL ON listing_data.agent_cycle_reports FROM "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
REVOKE ALL ON SEQUENCE listing_data.agent_cycle_reports_id_seq FROM "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";

-- Роль агента: только вставка пяти колонок. sent_at, send_error, attempts ей недоступны —
-- выдать сводку за отправленную агент не может.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'claude_code_report') THEN
        GRANT USAGE ON SCHEMA listing_data TO claude_code_report;
        GRANT INSERT (title, done, merged, waiting, problems)
            ON listing_data.agent_cycle_reports TO claude_code_report;
        GRANT USAGE ON SEQUENCE listing_data.agent_cycle_reports_id_seq TO claude_code_report;
    ELSE
        RAISE NOTICE 'роли claude_code_report нет — гранты агенту пропущены; завести роль и применить этот файл снова';
    END IF;
END $$;

COMMIT;

-- Проверка: таблица на месте, у роли агента — только вставка, у приложения — ничего.
SELECT to_regclass('listing_data.agent_cycle_reports') IS NOT NULL AS table_exists,
       (SELECT rolname FROM pg_roles WHERE rolname = 'claude_code_report') AS agent_role,
       CASE WHEN EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'claude_code_report')
            THEN has_table_privilege('claude_code_report', 'listing_data.agent_cycle_reports', 'SELECT') END AS agent_can_select,
       CASE WHEN EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'claude_code_report')
            THEN has_column_privilege('claude_code_report', 'listing_data.agent_cycle_reports', 'title', 'INSERT') END AS agent_can_insert_title,
       CASE WHEN EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'claude_code_report')
            THEN has_column_privilege('claude_code_report', 'listing_data.agent_cycle_reports', 'sent_at', 'INSERT') END AS agent_can_insert_sent_at,
       has_table_privilege('583bf6d1-6cd0-4a89-9c44-b387ec5c21cb', 'listing_data.agent_cycle_reports', 'SELECT') AS app_can_select;
-- Ожидается: true | claude_code_report | false | true | false | false
