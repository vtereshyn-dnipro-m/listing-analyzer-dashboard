-- След модели в слое: что она предложила и правил ли это человек.
--
-- Вопрос, на который это ответит через месяц: где перевод можно
-- отдать автоматике, а где нельзя. Ответ нужен фактами, а не
-- ощущением, поэтому хранится не флаг «человек нажал правку»,
-- а САМ текст модели: правка определяется сравнением, и её величину
-- потом видно — поправили запятую или переписали строку целиком.
--
-- `model` — чем переводили. Без него сравнение поколений моделей
-- невозможно: доля правок упадёт, и будет непонятно, модель стала
-- лучше или дизайнер устал править.
--
-- Флаг `edited_after_model` вычисляется при сохранении (текст человека
-- не равен тексту модели), но хранится отдельно: сравнивать строки
-- в каждом запросе отчёта дорого, а главное — текст модели со временем
-- может быть перезаписан повторным переводом, и тогда факт правки
-- восстановить будет уже нечем.

BEGIN;

ALTER TABLE listing_data.figma_layers
    ADD COLUMN IF NOT EXISTS model_text text;

ALTER TABLE listing_data.figma_layers
    ADD COLUMN IF NOT EXISTS model text;

ALTER TABLE listing_data.figma_layers
    ADD COLUMN IF NOT EXISTS translated_at timestamptz;

ALTER TABLE listing_data.figma_layers
    ADD COLUMN IF NOT EXISTS edited_after_model boolean NOT NULL DEFAULT false;

COMMIT;
