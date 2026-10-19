-- Права задачи Кабинета «Kabinet - Agent Cycle Report» на сводки Listing Suite (19.10.2026).
--
-- ПОДГОТОВЛЕНО, НЕ ПРИМЕНЯТЬ ОТДЕЛЬНО: применяется вместе с PR Кабинета, который учит задачу
-- забирать неотправленное из listing_data.agent_cycle_reports вторым источником (решение
-- владельца 19.10.2026). Без того PR права никому не нужны, а сами по себе ничего не ломают.
-- Порядок: 2026-10-19_agent_cycle_reports.sql (таблица) → этот файл → выкладка задачи Кабинета.
--
-- Принципал задач Кабинета — b1698364-6ec5-4240-8cd6-e06dd6e60856. Роль в базе Listing Suite
-- у него уже есть (проверено 19.10.2026 чтением pg_roles), USAGE на схему — тоже; SELECT на
-- новые таблицы схема выдаёт ему по умолчанию, здесь он повторён явно, чтобы файл не зависел
-- от прав по умолчанию.
--
-- Что задаче нужно и не больше:
--   SELECT                          — найти неотправленное (WHERE sent_at IS NULL AND attempts < N);
--   UPDATE (sent_at, send_error, attempts) — отметить отправку или ошибку.
-- Править текст сводки, вставлять и удалять строки задача не может.

BEGIN;

GRANT USAGE ON SCHEMA listing_data TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT ON listing_data.agent_cycle_reports TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT UPDATE (sent_at, send_error, attempts)
    ON listing_data.agent_cycle_reports TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";

COMMIT;

-- Проверка: чтение и отметка есть, правки текста нет.
SELECT has_table_privilege('b1698364-6ec5-4240-8cd6-e06dd6e60856', 'listing_data.agent_cycle_reports', 'SELECT') AS can_select,
       has_column_privilege('b1698364-6ec5-4240-8cd6-e06dd6e60856', 'listing_data.agent_cycle_reports', 'sent_at', 'UPDATE') AS can_mark_sent,
       has_column_privilege('b1698364-6ec5-4240-8cd6-e06dd6e60856', 'listing_data.agent_cycle_reports', 'title', 'UPDATE') AS can_edit_title,
       has_table_privilege('b1698364-6ec5-4240-8cd6-e06dd6e60856', 'listing_data.agent_cycle_reports', 'INSERT') AS can_insert;
-- Ожидается: true | true | false | false
