-- Право «Принять / выгрузить контент генератора текстов» — ls.textgen.accept. 22.10.2026.
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
-- Код: действие появится в auth.py (_MATRIX) вместе с кнопками, отдельным PR.
-- Пока кода нет, строка в базе ни на что не влияет; пока строки нет, кнопка не
-- заработает ни у кого — действие, которого нет в матрице базы, запрещено всем.
BEGIN;

INSERT INTO kabinet_data.app_permissions (action, role, allowed, updated_by)
SELECT 'ls.textgen.accept', r.role, r.role IN ('admin', 'textgen_pilot'),
       'sql:ls_textgen_accept_2026-10-22'
  FROM (VALUES ('viewer'), ('content_manager'), ('approver'), ('admin'),
               ('textgen_pilot')) AS r(role)
ON CONFLICT (action, role) DO NOTHING;   -- уже выставленные руками галочки не трогаем

COMMIT;

-- Проверка: пять строк, разрешено ровно двум ролям.
SELECT role, allowed FROM kabinet_data.app_permissions
 WHERE action = 'ls.textgen.accept' ORDER BY role;
