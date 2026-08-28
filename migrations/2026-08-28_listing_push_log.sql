-- listing_data.listing_push_log — журнал отправок тайтла в Amazon по SP-API
--
-- Зачем таблица. Это единственная операция приложения, которая пишет в живые
-- листинги клиента. След обязан оставаться от КАЖДОЙ попытки, а не только от
-- удачной: отказ Amazon приходит с причиной, и без записи эта причина живёт
-- ровно до перезагрузки страницы. Поэтому строка пишется и при ok = TRUE,
-- и при отказе — с текстом issues и текстом ошибки.
--
-- Чем отличается от synthesis_changes. Там — что человек ПРИНЯЛ, здесь — что
-- ушло в Amazon и чем ответил Amazon. Правку могут принять и не отправить,
-- отправка может отбиться и быть повторённой: это разные события, и держать
-- их в одной таблице значит потерять и то, и другое.
--
-- submission_id — идентификатор заявки от Amazon. По нему потом сверяют
-- судьбу правки: PATCH возвращает ACCEPTED сразу, но каталог обновляется
-- асинхронно, и «принято» не равно «применено».
--
-- ok вынесен отдельным полем от status намеренно: status — сырой ответ
-- Amazon (ACCEPTED / INVALID / HTTP 429), а ok — наш вывод. Судить об успехе
-- по строке статуса в запросах не придётся.
--
-- Применяет Databricks. Приложение схему не создаёт и не меняет.

CREATE TABLE IF NOT EXISTS listing_data.listing_push_log (
    id            BIGSERIAL PRIMARY KEY,
    asin          TEXT NOT NULL,
    sku           TEXT NOT NULL,        -- продавцовый SKU: FBM, без суффикса -FBA
    marketplace   TEXT NOT NULL,
    before_text   TEXT,                 -- тайтл до отправки
    after_text    TEXT NOT NULL,        -- что отправили
    after_extra   TEXT,                 -- Item Highlights, если уходили вместе с тайтлом
    submission_id TEXT,                 -- идентификатор заявки Amazon
    status        TEXT NOT NULL DEFAULT '',   -- сырой ответ: ACCEPTED / INVALID / HTTP 429
    ok            BOOLEAN NOT NULL DEFAULT FALSE,
    issues        TEXT,                 -- причины отказа от Amazon, одной строкой
    error         TEXT,                 -- наша ошибка: сеть, токен, лимит длины
    pushed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- защита от повтора спрашивает «когда этот товар отправляли удачно в последний раз»
CREATE INDEX IF NOT EXISTS idx_listing_push_log_pair_time
    ON listing_data.listing_push_log (asin, marketplace, pushed_at DESC);

-- разбор отказов: показать всё неудачное по рынку за период
CREATE INDEX IF NOT EXISTS idx_listing_push_log_failed
    ON listing_data.listing_push_log (marketplace, pushed_at DESC)
    WHERE ok IS FALSE;
