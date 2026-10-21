-- Роль пилота «Генератор текстов» в Listing Suite. 21.10.2026.
--
-- ВЫПОЛНЯЕТСЯ В БАЗЕ КАБИНЕТА, от роли Кабинета (она владеет app_users и
-- app_permissions), — владельцем, вручную. Агент Listing Suite к базе Кабинета
-- не подключается и этот файл не выполняет. Он лежит в отдельной папке
-- `migrations/kabinet/`, чтобы его не приняли за миграцию `listing_data`.
--
-- Решение владельца 21.10.2026: роль пилота видит ОДНУ страницу — «Генератор текстов
-- (пилот)». Сам генератор видят только эта роль и администратор Listing Suite.
-- Единственное действие роли — ls.textgen.accept — заводит следующий файл,
-- 2026-10-21_ls_textgen_accept.sql; здесь оно не закрывается.
--
-- Порядок: этот файл → 2026-10-21_ls_textgen_accept.sql. Роль этот файл НИКОМУ не
-- назначает: назначение — отдельным файлом 2026-10-21_ls_textgen_assign.sql, когда
-- подключат человека (решение владельца: «Роль пилота — позже Алексею»).
--
-- Что надо знать до применения:
--
-- 1. Экран «Доступ» роль знает (Кабинет, ПРОДУКТЫ["ls"]["roles"]), а подпись права
--    ls.textgen.accept — с PR Кабинета feat/ls-textgen-accept.
--
-- 2. В режиме раскатки (`reorder_params.ls_auth_enabled = 2`) права не действуют
--    вовсе — страницу видят все, как и все остальные страницы. Роль начинает
--    работать с режимом 1.
--
-- 3. Матрица из базы главнее матрицы в коде: действие, которого в таблице нет,
--    запрещено всем. Поэтому до этого файла генератор в режиме 1 не видит никто,
--    включая администратора.
BEGIN;

-- ── роль в списке допустимых ─────────────────────────────────────────────────
ALTER TABLE kabinet_data.app_users DROP CONSTRAINT IF EXISTS app_users_ls_role_check;
ALTER TABLE kabinet_data.app_users ADD CONSTRAINT app_users_ls_role_check
    CHECK (ls_role IS NULL
           OR ls_role = ANY (ARRAY['viewer','content_manager','approver','admin',
                                   'textgen_pilot']));

ALTER TABLE kabinet_data.app_permissions DROP CONSTRAINT IF EXISTS app_permissions_role_check;
ALTER TABLE kabinet_data.app_permissions ADD CONSTRAINT app_permissions_role_check
    CHECK (CASE WHEN action LIKE 'ls.%'
                THEN role = ANY (ARRAY['viewer','content_manager','approver','admin',
                                       'textgen_pilot'])
                ELSE role = ANY (ARRAY['viewer','country_manager','demand_planner','admin'])
           END);

-- ── страница генератора: администратор и роль пилота ─────────────────────────
INSERT INTO kabinet_data.app_permissions (action, role, allowed, updated_by)
SELECT 'ls.page.textgen', r.role, r.role IN ('admin','textgen_pilot'),
       'sql:ls_textgen_role_2026-10-21'
  FROM (VALUES ('viewer'), ('content_manager'), ('approver'), ('admin'),
               ('textgen_pilot')) AS r(role)
ON CONFLICT (action, role) DO NOTHING;

-- ── всё остальное роли пилота закрыто ────────────────────────────────────────
-- Явными строками «нельзя», а не отсутствием строки: на экране «Доступ» матрица
-- показывает, что решено, и пустая клетка читалась бы как «забыли».
INSERT INTO kabinet_data.app_permissions (action, role, allowed, updated_by)
SELECT a.action, 'textgen_pilot', false, 'sql:ls_textgen_role_2026-10-21'
  FROM (VALUES ('ls.admin'), ('ls.content.edit'), ('ls.amazon.push'),
               ('ls.method.edit'), ('ls.settings.edit'),
               ('ls.page.guide'), ('ls.page.dashboard'), ('ls.page.catalog'),
               ('ls.page.synthesis'), ('ls.page.photo'), ('ls.page.content'),
               ('ls.page.matrix'), ('ls.page.methodology'), ('ls.page.settings')
       ) AS a(action)
ON CONFLICT (action, role) DO NOTHING;

COMMIT;

-- Проверка: роль в обоих CHECK, страница — ровно admin и textgen_pilot.
SELECT role, allowed FROM kabinet_data.app_permissions
 WHERE action = 'ls.page.textgen' ORDER BY role;
