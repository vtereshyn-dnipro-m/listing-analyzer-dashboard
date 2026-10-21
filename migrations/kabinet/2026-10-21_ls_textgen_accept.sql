-- Право «Принять / выгрузить контент генератора текстов» — ls.textgen.accept. 21.10.2026.
--
-- ВЫПОЛНЯЕТСЯ В БАЗЕ КАБИНЕТА, от роли Кабинета (она владеет app_permissions), —
-- владельцем, вручную. Агент Listing Suite к базе Кабинета не подключается и этот
-- файл не выполняет.
--
-- Решение владельца 21.10.2026: кнопки «Принять» и «Выгрузить» на странице
-- «Генератор текстов (пилот)» — у администратора (Ярослав — администратор) и у
-- роли пилота textgen_pilot (для Алексея). Остальным ролям — нет. Применяется,
-- когда подключат Алексея.
--
-- Порядок: сначала 2026-10-21_ls_textgen_role.sql — без него CHECK
-- app_permissions_role_check не знает роль textgen_pilot, и этот файл откатится
-- целиком.
--
-- Когда применять: ВМЕСТЕ с PR кнопок «Принять» и «Выгрузить» — тогда действие
-- появится в auth.py (_MATRIX). Правило AGENTS.md: новое действие ls.* живёт в
-- коде и в app_permissions одновременно. Применённый раньше файл ничего не
-- сломает (действия нет в коде — кнопок нет), но сверка Кабинета
-- scratchpad/smoke_ls_auth.py покраснеет дважды: «лишнее действие
-- ls.textgen.accept», пока его нет в auth.py, и «пилоту разрешено ровно
-- {ls.page.textgen}», пока эту проверку не поправят в Кабинете. Правка сверки —
-- в репозитории Кабинета, тем же заходом, что и кнопки.
--
-- Пока строки нет, кнопка не заработает ни у кого — действие, которого нет в
-- матрице базы, запрещено всем.
BEGIN;

INSERT INTO kabinet_data.app_permissions (action, role, allowed, updated_by)
SELECT 'ls.textgen.accept', r.role, r.role IN ('admin', 'textgen_pilot'),
       'sql:ls_textgen_accept_2026-10-21'
  FROM (VALUES ('viewer'), ('content_manager'), ('approver'), ('admin'),
               ('textgen_pilot')) AS r(role)
ON CONFLICT (action, role) DO NOTHING;   -- уже выставленные руками галочки не трогаем

COMMIT;

-- Проверка: пять строк, разрешено ровно двум ролям.
SELECT role, allowed FROM kabinet_data.app_permissions
 WHERE action = 'ls.textgen.accept' ORDER BY role;
