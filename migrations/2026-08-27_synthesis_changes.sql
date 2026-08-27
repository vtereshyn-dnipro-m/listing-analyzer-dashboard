-- Таблица принятых правок Синтеза.
--
-- Зачем отдельная: listing_data.listing_changes — универсальная таблица
-- «поле — было — стало» (id, sku_group, asin, marketplace, changed_at,
-- field, before_value, after_value, exported_at), в неё пишут другие
-- процессы. Правка Синтеза несёт свой набор фактов — две части сплита,
-- их длины, Coverage, версию методологии, модель, выброшенные фразы —
-- и складывать это в универсальную таблицу значило бы либо ломать её,
-- либо размазывать одну правку по девяти строкам «поле-значение».
--
-- change_type задан на вырост: сейчас пишется только title_split,
-- дальше bullets, description, aplus — области уже есть в synthesis_skill.
-- Поэтому и колонки названы нейтрально (before_text/after_text), а не
-- before_title: для правки буллетов «title» было бы враньём.
--
-- Применять в Databricks. Приложение схему не меняет (правило CLAUDE.md).

CREATE TABLE IF NOT EXISTS listing_data.synthesis_changes (
    id              BIGSERIAL   PRIMARY KEY,
    sku_group       TEXT,                      -- как в listing_changes; код пока не пишет
    asin            TEXT        NOT NULL,
    marketplace     TEXT        NOT NULL,
    change_type     TEXT        NOT NULL DEFAULT 'title_split',
    before_text     TEXT,                      -- исходный тайтл
    before_len      INTEGER,
    after_text      TEXT,                      -- принятый title
    after_len       INTEGER,
    after_extra     TEXT,                      -- Item Highlights (вторая часть сплита)
    after_extra_len INTEGER,
    dropped         TEXT,                      -- выброшенные фразы, через «; »
    coverage_score  NUMERIC(5,2),              -- доля сохранённого поискового веса
    skill_version   INTEGER,                   -- версия методологии из synthesis_skill
    model           TEXT,
    status          TEXT        NOT NULL DEFAULT 'accepted',
    accepted_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    exported_at     TIMESTAMPTZ                -- когда ушло в flat file; код пока не пишет
);

-- Чтения идут как DISTINCT ON (asin, marketplace) ... ORDER BY accepted_at DESC
-- (load_accepted, worklog): индекс покрывает и выборку, и сортировку.
CREATE INDEX IF NOT EXISTS idx_synthesis_changes_pair_time
    ON listing_data.synthesis_changes (asin, marketplace, accepted_at DESC);

-- Выгрузка flat file фильтрует принятые правки нужного типа по маркетплейсу.
CREATE INDEX IF NOT EXISTS idx_synthesis_changes_export
    ON listing_data.synthesis_changes (change_type, marketplace, accepted_at DESC)
    WHERE status = 'accepted';
