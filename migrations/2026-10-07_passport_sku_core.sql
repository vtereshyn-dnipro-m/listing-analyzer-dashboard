-- «Контент → Паспорт SKU», v1: Реестр, Создание, Взаимодействие с Верификатором.
--
-- Нормативы — снимок канона AI Design Conveyor в canon/ (00A v2.13, 06E MVP-14,
-- Listing_Suite_Integration_Contract v1.2, AI_DESIGN_EXECUTION_GRAPH_CONTRACT
-- v2.6). Эти таблицы — хранилище Listing Suite для того, что канон требует
-- хранить, а не новая модель: статусы и ID взяты из канона дословно, и
-- CHECK держит их закрытым словарём. Чего в каноне нет, база не примет.
--
-- Инварианты, которые держит БАЗА, а не код (код можно обойти, базу — нет):
--   1. у точного SKU ровно один ACTIVE Паспорт (00A «Единственный продуктовый
--      документ», Integration Contract «рівно один ACTIVE canonical Passport») —
--      частичный уникальный индекс;
--   2. события запуска, квитанции, ответы и вердикты по ответам только
--      дописываются (00A: история неизменяема; ТЗ 11.6: «редактирование
--      отправленной версии запрещается») — триггер на UPDATE/DELETE;
--   3. повтор запроса с тем же idempotency key не создаёт второй записи
--      (Integration Contract «Concurrency та idempotency») — UNIQUE.
--
-- Права: права по умолчанию в listing_data дают принципалу приложения
-- (583bf6d1-…) полный доступ к новым таблицам — отдельный GRANT не нужен
-- (так же, как 2026-09-27_figma_renders.sql). Проверка — в конце файла.

BEGIN;

-- Канонический указатель и проекция для Реестра. Сам Паспорт — один файл на
-- томе (storage_path); здесь его версия, SHA, состояние и то, что Реестру
-- нужно показать без чтения файла.
CREATE TABLE IF NOT EXISTS listing_data.passport_objects (
    passport_id             text        PRIMARY KEY,
    lineage_id              text        NOT NULL,
    sku_id                  text        NOT NULL,   -- дословно: регистр, дефисы, ведущие нули
    product_version         text        NOT NULL,   -- версия/конфигурация товара, отдельно от SKU
    product_name            text,
    model                   text,
    status                  text        NOT NULL
        CHECK (status IN ('ACTIVE', 'ARCHIVED', 'STAGING', 'QUARANTINED')),
    state                   text        NOT NULL
        CHECK (state IN ('NOT_READY', 'BLOCKED', 'READY_WITH_LIMITATIONS', 'READY')),
    passport_version        text        NOT NULL,
    sha256                  text        NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    storage_path            text,                   -- рабочая копия на томе UC
    materials_url           text,                   -- папка материалов для человека (Drive)
    -- Одобренные ограничения READY_WITH_LIMITATIONS: [{id, text, affected_use}].
    limitations             jsonb       NOT NULL DEFAULT '[]'::jsonb,
    replaces_passport_id    text,
    replaced_by_passport_id text,
    last_event_type         text,                   -- тип последнего принятого события
    last_event_at           timestamptz,
    -- Системный read-back: SHA, прочитанный с тома последним. Не совпал с
    -- sha256 — «Данные устарели», изменяющие действия заперты (ТЗ 9.6.4).
    readback_sha256         text        CHECK (readback_sha256 IS NULL OR readback_sha256 ~ '^[a-f0-9]{64}$'),
    readback_at             timestamptz,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS passport_objects_one_active
    ON listing_data.passport_objects (sku_id) WHERE status = 'ACTIVE';
CREATE INDEX IF NOT EXISTS passport_objects_lineage ON listing_data.passport_objects (lineage_id);

-- Запуск графа AI Design. Таблицы движка — ai_runs, ai_run_events, ai_receipts —
-- общие, без префикса passport_: граф один (AI_DESIGN_EXECUTION_GRAPH_CONTRACT),
-- и запуск «Контента» начинается в нём же — ребро E140 выходит из
-- координатора Паспорта N020. Свои таблицы под каждую область означали бы два
-- движка, которые расходятся. Область запуска — колонка route; «Контент»
-- расширит её CHECK своей миграцией.
-- run_state — объект по ai_design_run_state.schema.json; колонки рядом — его
-- проекция для выборок («есть ли у SKU незавершённый запуск»).
CREATE TABLE IF NOT EXISTS listing_data.ai_runs (
    run_id            text        PRIMARY KEY,
    route             text        NOT NULL CHECK (route IN ('SKU_PASSPORT')),
    sku_id            text        NOT NULL,
    passport_id       text,
    requested_action  text        NOT NULL
        CHECK (requested_action IN ('INITIAL_CREATE', 'SUBMIT_SOURCE_EVIDENCE_DELTA', 'RECREATE_PASSPORT')),
    graph_version     text        NOT NULL,
    graph_sha256      text        NOT NULL CHECK (graph_sha256 ~ '^[a-f0-9]{64}$'),
    execution_mode    text        NOT NULL
        CHECK (execution_mode IN ('GRAPH_SHADOW_RUN', 'CONTROLLED_RUNTIME', 'PRODUCTION_RUNTIME')),
    -- Объединение «Стани Run State» контракта графа и enum схемы run_state:
    -- они расходятся (canon/REFERENCE_DRIFT.md, раздел 3), база принимает оба.
    lifecycle_state   text        NOT NULL
        CHECK (lifecycle_state IN ('RUN_CREATED', 'RUN_ACTIVE', 'WAITING_RECEIVER_ACCEPTANCE',
                                   'WAITING_HUMAN_DECISION', 'RUN_REWORK', 'RUN_BLOCKED',
                                   'RUN_FAILED', 'RUN_CANCELLED', 'RUN_COMPLETED')),
    terminal_status   text        NOT NULL DEFAULT 'NOT_TERMINAL'
        CHECK (terminal_status IN ('NOT_TERMINAL', 'COMPLETED', 'CANCELLED', 'FAILED_EXHAUSTED')),
    current_node_id   text        CHECK (current_node_id IS NULL OR current_node_id ~ '^N[0-9]{3}_[A-Z0-9_]+$'),
    run_state         jsonb       NOT NULL,
    created_by        text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ai_runs_open
    ON listing_data.ai_runs (sku_id) WHERE terminal_status = 'NOT_TERMINAL';

-- Переход графа: одно ребро — одна строка, с квитанцией и тем, сколько
-- бюджета он списал. Только дописывается.
CREATE TABLE IF NOT EXISTS listing_data.ai_run_events (
    run_id          text        NOT NULL REFERENCES listing_data.ai_runs (run_id),
    seq             integer     NOT NULL CHECK (seq > 0),
    edge_id         text        CHECK (edge_id IS NULL OR edge_id ~ '^E[0-9]{3}_[A-Z0-9_]+$'),
    from_node_id    text,
    to_node_id      text,
    receipt         jsonb       NOT NULL,
    receipt_sha256  text        NOT NULL CHECK (receipt_sha256 ~ '^[a-f0-9]{64}$'),
    budget_charge   jsonb       NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, seq)
);

-- Квитанции действий Listing Suite (listing_suite_passport_action_receipt) и
-- журнал идемпотентности: тот же ключ — та же квитанция, другой payload с тем
-- же ключом — IDEMPOTENCY_KEY_CONFLICT. Отсюда же read-only status lookup.
CREATE TABLE IF NOT EXISTS listing_data.ai_receipts (
    receipt_id        text        PRIMARY KEY,
    request_id        text        NOT NULL,
    idempotency_key   text        NOT NULL UNIQUE,
    request_sha256    text        NOT NULL CHECK (request_sha256 ~ '^[a-f0-9]{64}$'),
    requested_action  text        NOT NULL,
    sku_id            text        NOT NULL,
    operation_id      text,
    actor             text        NOT NULL,
    result            text        NOT NULL,
    receipt           jsonb       NOT NULL,
    receipt_sha256    text        NOT NULL CHECK (receipt_sha256 ~ '^[a-f0-9]{64}$'),
    created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ai_receipts_request ON listing_data.ai_receipts (request_id);
CREATE INDEX IF NOT EXISTS ai_receipts_sku ON listing_data.ai_receipts (sku_id, created_at DESC);

-- Зарегистрированные исходные материалы: копия в product_root/артефакты/ДАТА/,
-- SHA и результат доступа по каждому объекту (Integration Contract
-- «Вхідні дані та binding»). Регистрация — не факт Паспорта.
CREATE TABLE IF NOT EXISTS listing_data.passport_source_artifacts (
    source_artifact_id  text        PRIMARY KEY,
    sku_id              text        NOT NULL,
    passport_id         text,
    run_id              text,
    origin_locator      text        NOT NULL,       -- откуда пришёл: имя файла, URL, путь в Drive
    archived_locator    text,                       -- где лежит неизменная копия
    file_name           text,
    mime_type           text,
    bytes               bigint      CHECK (bytes IS NULL OR bytes >= 0),
    sha256              text        CHECK (sha256 IS NULL OR sha256 ~ '^[a-f0-9]{64}$'),
    access_result       text        NOT NULL,
    duplicate_of        text,
    lifecycle           text        NOT NULL DEFAULT 'ACTIVE' CHECK (lifecycle IN ('ACTIVE', 'OLD')),
    registered_by       text,
    recorded_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS passport_source_artifacts_sku ON listing_data.passport_source_artifacts (sku_id);

-- Вопросы Верификатора (06E). Статусы вопроса — 06E «Нормативная модель
-- статусов» плюс supersede/out-of-scope из ТЗ 11.5. Тип и состояние — разные
-- оси (ТЗ 11.3.2): «Решение конфликта» — тип, а не состояние.
CREATE TABLE IF NOT EXISTS listing_data.passport_questions (
    question_id         text        PRIMARY KEY CHECK (question_id ~ '^Q-[A-Za-z0-9._-]+-[0-9]{3,}$'),
    run_id              text,
    sku_id              text        NOT NULL,
    product_version     text,
    passport_id         text,
    question_type       text        NOT NULL CHECK (question_type IN ('ANSWER', 'DOCUMENT', 'CONFLICT')),
    status              text        NOT NULL
        CHECK (status IN ('OPEN', 'SENT', 'ANSWER_RECEIVED', 'RESOLVED', 'SUPERSEDED', 'OUT_OF_SCOPE')),
    -- «Блокирует Паспорт» — только при действующем BLK (ТЗ 11.3.2); код
    -- проверяет и это, но колонка block_id держит связь явной.
    impact              text        NOT NULL
        CHECK (impact IN ('BLOCKS_PASSPORT', 'REQUIRED_FOR_READINESS', 'NON_BLOCKING')),
    block_id            text,
    responsible_role    text,
    responsible_user    text,
    question_text       text        NOT NULL,
    reason_text         text,                       -- «Зачем это нужно»
    affected_object     text,                       -- затронутый факт, gap или conflict
    expected_answer     text,
    closure_criterion   text,
    evidence_required   boolean     NOT NULL DEFAULT false,
    due_at              timestamptz,
    gap_ids             jsonb       NOT NULL DEFAULT '[]'::jsonb,
    -- Для CONFLICT: текущее и новое значения с источниками и scope.
    conflict            jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS passport_questions_sku ON listing_data.passport_questions (sku_id, status);

-- Версии ответов: каждая отправка — новая неизменяемая строка (ТЗ 11.6).
CREATE TABLE IF NOT EXISTS listing_data.passport_answers (
    answer_id            text        PRIMARY KEY,
    question_id          text        NOT NULL REFERENCES listing_data.passport_questions (question_id),
    answer_version       integer     NOT NULL CHECK (answer_version > 0),
    supersedes_answer_id text,
    author               text        NOT NULL,
    answer_text          text,
    decision             text        CHECK (decision IS NULL OR decision IN
                                            ('KEEP_CURRENT', 'ACCEPT_NEW', 'KEEP_DISPUTED', 'NOT_APPLICABLE')),
    source_artifact_ids  jsonb       NOT NULL DEFAULT '[]'::jsonb,
    idempotency_key      text        NOT NULL UNIQUE,
    created_at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (question_id, answer_version)
);

-- Вердикт Верификатора по ответу (06E: Answer RECEIVED → VERIFIED | PARTIAL |
-- REJECTED). Отдельной таблицей, чтобы сам ответ оставался неизменным.
CREATE TABLE IF NOT EXISTS listing_data.passport_answer_verdicts (
    answer_id     text        NOT NULL REFERENCES listing_data.passport_answers (answer_id),
    seq           integer     NOT NULL CHECK (seq > 0),
    verdict       text        NOT NULL CHECK (verdict IN ('VERIFIED', 'PARTIAL', 'REJECTED')),
    reason        text,
    run_id        text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (answer_id, seq)
);

-- Блокеры BLK-<RUN>-<NNN>. BLOCKED показывается ТОЛЬКО при действующем
-- блокере с причиной, ответственным и условием возобновления (ТЗ 3.1, 9.6.3).
CREATE TABLE IF NOT EXISTS listing_data.passport_blocks (
    block_id           text        PRIMARY KEY CHECK (block_id ~ '^BLK-[A-Za-z0-9._-]+-[0-9]{3,}$'),
    run_id             text,
    sku_id             text        NOT NULL,
    passport_id        text,
    reason             text        NOT NULL,
    responsible_party  text        NOT NULL,
    responsible_role   text,
    responsible_user   text,
    resume_condition   text        NOT NULL,
    created_at         timestamptz NOT NULL DEFAULT now(),
    resolved_at        timestamptz,
    resolution         text
);
CREATE INDEX IF NOT EXISTS passport_blocks_active
    ON listing_data.passport_blocks (sku_id) WHERE resolved_at IS NULL;

-- Только дописывание: история запусков, квитанции, ответы и вердикты.
CREATE OR REPLACE FUNCTION listing_data.passport_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'listing_data.%: только дописывание — % запрещён (канон Паспорта SKU: история неизменяема)',
        TG_TABLE_NAME, TG_OP;
END;
$$;

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['ai_run_events', 'ai_receipts',
                             'passport_answers', 'passport_answer_verdicts'] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS %I ON listing_data.%I', t || '_append_only', t);
        EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON listing_data.%I
                        FOR EACH ROW EXECUTE FUNCTION listing_data.passport_append_only()',
                       t || '_append_only', t);
    END LOOP;
END $$;

COMMIT;

-- Проверка: девять таблиц на месте, приложение может писать, триггеры стоят.
SELECT t AS table_name,
       to_regclass('listing_data.' || t) IS NOT NULL AS exists,
       has_table_privilege('583bf6d1-6cd0-4a89-9c44-b387ec5c21cb', 'listing_data.' || t, 'INSERT') AS app_can_write
  FROM unnest(ARRAY['passport_objects', 'ai_runs', 'ai_run_events', 'ai_receipts',
                    'passport_source_artifacts', 'passport_questions', 'passport_answers',
                    'passport_answer_verdicts', 'passport_blocks']) AS t;

SELECT tgname FROM pg_trigger WHERE tgname LIKE '%_append_only'
   AND tgrelid::regclass::text ~ '(passport_|ai_)' ORDER BY 1;
