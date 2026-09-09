-- Место слоя в макете: то, чем строки разных языков связываются между собой.
--
-- Разведка 08.09 показала, что структура макета на UK/US и DE совпадает
-- точно: те же имена фреймов (`B0G4S9SJ3M.PT01`) и те же пути в дереве.
-- Английское «Battery Capacity» и немецкое «Batteriekapazität» лежат
-- в узлах с РАЗНЫМИ id, но на одном и том же месте — `PT01#0.1.2`.
--
-- Без этого поля связать их нечем: id узла свой на каждой языковой
-- странице, а текст на то и перевод, что не совпадает. Отсюда и брались
-- «переводы», равные исходнику: слой языковой страницы записывался
-- сам по себе, а не как пара к английскому.
--
-- Ключ слоя становится (товар, место, язык). `layer_id` остаётся —
-- он понадобится плагину, который будет писать перевод обратно в Figma:
-- туда нужен именно id узла.

BEGIN;

ALTER TABLE listing_data.figma_layers
    ADD COLUMN IF NOT EXISTS slot text;

ALTER TABLE listing_data.figma_layers
    DROP CONSTRAINT IF EXISTS figma_layers_layer_id_lang_key;

-- Старые строки ключа не имеют и новому ограничению противоречить не
-- могут только пустыми: чтения до 08.09 клали в базу имена секций
-- вместо текста слоёв, ценности в них нет (проверено — переводов ноль).
DELETE FROM listing_data.figma_layers WHERE slot IS NULL;

ALTER TABLE listing_data.figma_layers
    ADD CONSTRAINT figma_layers_product_slot_lang_key
    UNIQUE (product_id, slot, lang);

COMMIT;
