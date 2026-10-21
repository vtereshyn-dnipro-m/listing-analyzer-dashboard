-- Роль пилота «Генератор текстов» в Listing Suite. 21.10.2026.
--
-- ВЫПОЛНЯЕТСЯ В БАЗЕ КАБИНЕТА, от роли Кабинета (она владеет app_users и
-- app_permissions), — владельцем, вручную. Агент Listing Suite к базе Кабинета
-- не подключается и этот файл не выполняет. Он лежит в отдельной папке
-- `migrations/kabinet/`, чтобы его не приняли за миграцию `listing_data`.
--
-- Решение владельца 21.10.2026: Ярослав — не администратор. Ему нужна роль, которая
-- видит ОДНУ страницу — «Генератор текстов (пилот)» — и ни одного действия. Сам
-- генератор видят только эта роль и администратор Listing Suite.
--
-- Что надо знать до применения:
--
-- 1. Экран «Доступ» роль пока НЕ знает. Список ролей Listing Suite зашит в
--    `access_screen.py` (ПРОДУКТЫ["ls"]["roles"]), а этот файл — выкладка из
--    репозитория Кабинета, правится только там. До правки источника строку Ярослава
--    на экране «Доступ» НЕ редактировать: выпадашка роли не знает textgen_pilot.
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

-- ── роль Ярославу ────────────────────────────────────────────────────────────
-- Почта — подставить перед выполнением. Пока стоит заготовка, блок отказывается
-- выполняться и откатывает всю транзакцию. Строки в app_users нет — блок тоже
-- отказывается: пусть Ярослав один раз войдёт с рабочей почты (с 13.10.2026 вход
-- заводит карточку «Просмотр» сам), и файл выполняется после этого. Заводить
-- карточку здесь значило бы молча решать и про доступ в Кабинет.
-- Кабинетную роль (`role`) блок не трогает.
DO $$
DECLARE
    почта text := 'ПОДСТАВИТЬ_ПОЧТУ_ЯРОСЛАВА';
    n int;
BEGIN
    IF почта = 'ПОДСТАВИТЬ_ПОЧТУ_ЯРОСЛАВА' THEN
        RAISE EXCEPTION 'Почта Ярослава не подставлена — роль никому не назначена';
    END IF;
    UPDATE kabinet_data.app_users SET ls_role = 'textgen_pilot'
     WHERE lower(email) = lower(почта);
    GET DIAGNOSTICS n = ROW_COUNT;
    IF n <> 1 THEN
        RAISE EXCEPTION 'Строк с почтой %: % (нужна ровно одна)', почта, n;
    END IF;
END $$;

COMMIT;
