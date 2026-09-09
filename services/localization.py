# -*- coding: utf-8 -*-
"""
services/localization.py — переводы текстовых слоёв макетов Figma.

Дизайнер рисует карточку по-английски, а продаётся она в Испании,
Германии, Италии и Франции. Перевод сам по себе умеет любой плагин;
здесь он нужен вместе с тремя вещами, которых плагин не даёт.

ДЛИНА. Испанский и немецкий длиннее английского примерно на пятую часть,
а слой в макете фиксированной ширины. Плагин вставит текст, и он уедет
за границу слоя или обрежется — обнаружится это при экспорте, когда
работа уже сделана. Поэтому длина считается ДО вставки, и каждая строка
знает свой предел.

УЧЁТ. Плагин работает внутри одного файла и не отвечает на первый же
вопрос: сколько товаров вообще без перевода.

ПАМЯТЬ. Переводы лежат в базе, поэтому один и тот же термин на разных
карточках переводится одинаково, а не заново каждый раз.

Картинок здесь нет и не будет: оригиналы остаются в Figma, готовые файлы
в Drive. В базе только текст и ссылки.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from services import figma, translate
from services.db import get_conn, get_engine, safe_read

# Порядок языков на экране: источник первым, дальше рынки.
SOURCE_LANG = "en"
TARGET_LANGS = ("de", "es", "it", "fr")
ALL_LANGS = (SOURCE_LANG,) + TARGET_LANGS

# Статусы слоя. Перевод живёт дольше одного захода: модель предложила,
# человек поправил, дизайнер применил — и это разные состояния.
ST_NONE, ST_TRANSLATED, ST_APPROVED, ST_APPLIED = (
    "none", "translated", "approved", "applied")

# Запас в лимите не делаем: предел — это ширина слоя, а не рекомендация.
# Зато отмечаем «впритык», когда занято больше девяти десятых: такой
# текст ещё влезет, но любая правка выведет его за край.
TIGHT = 0.9


def fits(text: str | None, limit) -> tuple[int, int | None, str]:
    """(длина, предел, состояние) для одной строки перевода.

    Состояние: `over` — не влезает, `tight` — впритык, `ok` — с запасом,
    `unknown` — предел неизвестен (слой ещё не прочитан из Figma).

    Предел приходит из макета и может отсутствовать. Отсутствие предела
    и предел, равный нулю, — разные вещи: первое значит «не знаем»,
    второе «места нет». Поэтому проверяется через pd.isna, а не через
    истинность: ноль в Python ложный, и слой с нулевой шириной молча
    считался бы неизвестным.
    """
    s = "" if text is None else str(text)
    n = len(s)
    try:
        lim = None if limit is None or pd.isna(limit) else int(limit)
    except (TypeError, ValueError):
        lim = None
    if lim is None:
        return n, None, "unknown"
    if n > lim:
        return n, lim, "over"
    if lim > 0 and n / lim >= TIGHT:
        return n, lim, "tight"
    return n, lim, "ok"


def over_rows(df: pd.DataFrame) -> int:
    """Сколько строк не влезает в макет. Именно это число выносится
    под таблицу: дизайнеру нужно знать не «есть ли проблема», а сколько
    строк править."""
    if df is None or df.empty:
        return 0
    return sum(1 for _, r in df.iterrows()
               if fits(r.get("translated_text"), r.get("char_limit"))[2] == "over")


def product_state(langs_done: set) -> str:
    """Состояние товара по набору готовых языков: all / partial / none."""
    have = {lg for lg in TARGET_LANGS if lg in langs_done}
    if len(have) == len(TARGET_LANGS):
        return "all"
    return "partial" if have else "none"


def summarize(products: pd.DataFrame) -> dict:
    """Четыре числа для шапки: всего, все языки, частично, только англ."""
    if products is None or products.empty:
        return {"total": 0, "all": 0, "partial": 0, "none": 0}
    counts = {"all": 0, "partial": 0, "none": 0}
    for _, r in products.iterrows():
        counts[product_state(set(r.get("langs_done") or ()))] += 1
    return {"total": len(products), **counts}


# Суточный кеш. Figma отвечает 429 и просит ждать сотни секунд на каждую
# попытку, а структура файла меняется редко — раз в сутки достаточно.
# Метка последнего чтения живёт в самих данных (synced_at), а не в кеше
# процесса: процесс на Streamlit Cloud перезапускается, и кеш в памяти
# заставил бы читать Figma заново после каждого перезапуска.
SYNC_EVERY_HOURS = 24


def sync_age_hours(products: pd.DataFrame) -> float | None:
    """Сколько часов назад читали Figma. None — не читали никогда."""
    if products is None or products.empty or "synced_at" not in products:
        return None
    ts = pd.to_datetime(products["synced_at"], errors="coerce", utc=True).max()
    if pd.isna(ts):
        return None
    now = pd.Timestamp.now(tz="UTC")
    return max(0.0, (now - ts).total_seconds() / 3600.0)


def needs_sync(products: pd.DataFrame) -> bool:
    age = sync_age_hours(products)
    return age is None or age >= SYNC_EVERY_HOURS


# ---------------------------------------------------------------- запись

def save_parsed(parsed: dict) -> tuple[int, int, str | None]:
    """Разобранный документ → таблицы. (товаров, слоёв, ошибка).

    Английские секции дают исходный текст и ПРЕДЕЛ символов, секции
    языковых страниц — уже существующие переводы.

    Ключ товара — (файл, ASIN, тип секции), а не узел Figma: узел свой
    на каждой языковой странице, и по нему один товар ложился в базу
    четырьмя строками с одним языком в каждой. Язык принадлежит слою,
    поэтому и берётся со слоя.
    """
    products = parsed.get("products") or []
    if not products:
        return 0, 0, None
    n_p = n_l = 0
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            for p in products:
                cur.execute(
                    """
                    INSERT INTO figma_products
                        (asin, sku, name, section_type, page_name,
                         figma_file_key, figma_node_id, layers_count, synced_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s, now())
                    ON CONFLICT (figma_file_key, asin, section_type) DO UPDATE
                        SET name = EXCLUDED.name,
                            sku = EXCLUDED.sku,
                            page_name = EXCLUDED.page_name,
                            figma_node_id = EXCLUDED.figma_node_id,
                            layers_count = EXCLUDED.layers_count,
                            synced_at = now()
                    RETURNING id
                    """,
                    (p["asin"], p.get("sku"), p.get("name"),
                     p.get("section_type"), p.get("page_name"),
                     p.get("file_key") or "", p["figma_node_id"],
                     len(p.get("layers") or [])))
                pid = cur.fetchone()[0]
                n_p += 1
                for lr in p.get("layers") or []:
                    # текст со страницы-языка — это перевод, с английской —
                    # исходник; предел символов берётся у обоих, потому
                    # что ширина слоя своя на каждой странице
                    lang = lr.get("lang") or p.get("lang")
                    is_source = lang == SOURCE_LANG
                    cur.execute(
                        """
                        INSERT INTO figma_layers
                            (product_id, layer_id, slot, frame_name, lang,
                             source_text, translated_text, char_limit,
                             status, updated_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
                        ON CONFLICT (product_id, slot, lang) DO UPDATE
                            SET source_text = EXCLUDED.source_text,
                                char_limit = EXCLUDED.char_limit,
                                frame_name = EXCLUDED.frame_name,
                                layer_id = EXCLUDED.layer_id,
                                updated_at = now()
                        """,
                        (pid, lr["layer_id"], lr.get("slot"),
                         lr.get("frame_name"),
                         lang, lr["source_text"],
                         None if is_source else lr["source_text"],
                         lr.get("char_limit"),
                         ST_NONE if is_source else ST_APPLIED))
                    n_l += 1
        conn.close()
        return n_p, n_l, None
    except Exception as e:
        return n_p, n_l, f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------- чтение

@st.cache_data(ttl=120)
def load_products() -> tuple[pd.DataFrame, str | None]:
    """Товары макетов и языки, по которым перевод уже есть.

    Возвращает причину сбоя отдельно: пустая таблица здесь означает
    «в Figma ничего не прочитано», и показывать её вместо недоступной
    базы значит утверждать то, чего мы не знаем.
    """
    try:
        df = pd.read_sql(
            """
            SELECT p.id, p.asin, p.sku, p.name, p.section_type,
                   p.page_name, p.figma_file_key, p.figma_node_id,
                   p.layers_count, p.synced_at,
                   COALESCE(array_agg(DISTINCT l.lang)
                            FILTER (WHERE l.translated_text IS NOT NULL
                                      AND l.translated_text <> ''), '{}') AS langs_done
            FROM figma_products p
            LEFT JOIN figma_layers l ON l.product_id = p.id
            GROUP BY p.id
            ORDER BY p.name
            """, get_engine())
        if not df.empty:
            df["langs_done"] = df["langs_done"].map(
                lambda v: set(v) if v is not None else set())
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"{type(e).__name__}: {e}"


def save_translation(product_id: int, slot: str, lang: str,
                     text: str) -> str | None:
    """Правка человека. Возвращает причину сбоя или None.

    Строки языка может НЕ БЫТЬ: перевод чаще всего делается туда, где
    страницы в макете ещё нет. Поэтому вставка с обновлением, а не
    UPDATE: голый UPDATE молча ничего не менял бы, и правка исчезала
    вместе с вкладкой.

    Исходник и `layer_id` берутся у английской строки того же места:
    первое — чтобы строка осталась осмысленной без макета, второе —
    чтобы плагин знал, откуда копировать слой.

    `edited_after_model` считается СРАВНЕНИЕМ с тем, что предложила
    модель, а не фактом открытия поля: иначе доля правок — мера того,
    где автоматика возможна, — врала бы в обе стороны.
    """
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO figma_layers
                    (product_id, layer_id, slot, frame_name, lang,
                     source_text, translated_text, char_limit, status,
                     updated_at)
                SELECT s.product_id, s.layer_id, s.slot, s.frame_name,
                       %(lang)s, s.source_text,
                       NULLIF(%(text)s, ''),
                       s.char_limit,
                       CASE WHEN %(text)s = '' THEN %(none)s ELSE %(done)s END,
                       now()
                  FROM figma_layers s
                 WHERE s.product_id = %(pid)s AND s.slot = %(slot)s
                   AND s.lang = %(src)s
                ON CONFLICT (product_id, slot, lang) DO UPDATE
                    SET translated_text = NULLIF(%(text)s, ''),
                        status = CASE WHEN %(text)s = '' THEN %(none)s
                                      ELSE %(done)s END,
                        edited_after_model = (
                            figma_layers.model_text IS NOT NULL
                            AND figma_layers.model_text <> %(text)s),
                        updated_at = now()
                """,
                {"text": (text or "").strip(), "pid": product_id,
                 "slot": slot, "lang": lang, "src": SOURCE_LANG,
                 "none": ST_NONE, "done": ST_TRANSLATED})
        conn.close()
        return None
    except Exception as e:
        return f"{type(e).__name__}: {e}"


def save_model_translation(product_id: int, lang: str, model: str,
                           texts: dict) -> tuple[int, str | None]:
    """Ответ модели по слоям: (сколько записано, причина сбоя).

    Пишется и перевод, и то, ЧТО предложила модель. Второе — не дубль:
    как только человек поправит строку, `translated_text` разойдётся
    с `model_text`, и разница покажет, где автоматика справляется,
    а где нет. Правка человека при этом не затирается: переводом
    от модели перезаписывается только строка, которую он не трогал.
    """
    if not texts:
        return 0, None
    n = 0
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            for slot, text in texts.items():
                # вставка с обновлением по той же причине, что и в правке
                # человека: строки языка может не быть вовсе
                cur.execute(
                    """
                    INSERT INTO figma_layers
                        (product_id, layer_id, slot, frame_name, lang,
                         source_text, translated_text, model_text, model,
                         char_limit, status, translated_at, updated_at)
                    SELECT s.product_id, s.layer_id, s.slot, s.frame_name,
                           %(lang)s, s.source_text, %(text)s, %(text)s,
                           %(model)s, s.char_limit, %(done)s, now(), now()
                      FROM figma_layers s
                     WHERE s.product_id = %(pid)s AND s.slot = %(slot)s
                       AND s.lang = %(src)s
                    ON CONFLICT (product_id, slot, lang) DO UPDATE
                        SET translated_text = %(text)s,
                            model_text = %(text)s,
                            model = %(model)s,
                            translated_at = now(),
                            status = %(done)s,
                            updated_at = now()
                        WHERE figma_layers.edited_after_model = FALSE
                    """,
                    {"text": text, "model": model, "pid": product_id,
                     "slot": slot, "lang": lang, "src": SOURCE_LANG,
                     "done": ST_TRANSLATED})
                n += cur.rowcount or 0
        conn.close()
        return n, None
    except Exception as e:
        return n, f"{type(e).__name__}: {e}"


@st.cache_data(ttl=120)
def load_prompt() -> tuple[str, int, str | None]:
    """Промпт перевода из `synthesis_skill`: (текст, версия, причина).

    Версия 0 и пустой текст означают «своего промпта ещё нет» —
    страница покажет текст по умолчанию и прямо скажет, что он
    не сохранён. Молчаливой подстановки, как было с методологией
    тайтлов, здесь не происходит: человек видит ровно то, что уйдёт
    модели, ещё до нажатия кнопки.
    """
    df, err = safe_read(
        """
        SELECT skill_text, version FROM synthesis_skill
         WHERE scope = %(scope)s AND is_active = TRUE
         ORDER BY version DESC LIMIT 1
        """, params={"scope": translate.SCOPE})
    if err:
        return "", 0, err
    if df.empty:
        return "", 0, None
    row = df.iloc[0]
    return str(row["skill_text"] or ""), int(row["version"] or 0), None


def save_prompt(text: str) -> str | None:
    """Новая версия промпта. Правки без коммитов, откат — на «Методологии»."""
    # версия читается своим запросом, а не через кэшированный load_prompt:
    # кэш может отдать значение до чужой правки, и версии столкнутся
    df, err = safe_read(
        "SELECT COALESCE(MAX(version), 0) AS v FROM synthesis_skill "
        "WHERE scope = %(scope)s", params={"scope": translate.SCOPE})
    if err:
        return err
    ver = int(df.iloc[0]["v"]) if not df.empty else 0
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE synthesis_skill SET is_active = FALSE "
                "WHERE scope = %s AND is_active = TRUE", (translate.SCOPE,))
            cur.execute(
                """
                INSERT INTO synthesis_skill
                    (version, marketplace, scope, skill_text, is_active)
                VALUES (%s, 'all', %s, %s, TRUE)
                """, (ver + 1, translate.SCOPE, (text or "").strip()))
        conn.close()
        load_prompt.clear()
        return None
    except Exception as e:
        return f"{type(e).__name__}: {e}"


@st.cache_data(ttl=120)
def glossary(lang: str, limit: int = 60) -> tuple[pd.DataFrame, str | None]:
    """Готовые пары «английский → перевод» как образец стиля.

    Заводить их руками не нужно: если строка есть и на UK/US, и на DE,
    это уже готовая пара — их связывает `slot`, место слоя в макете.
    Пары идут в промпт, чтобы модель попадала в словарь дизайнера,
    а не изобретала свой на каждой карточке.

    Строки, совпадающие с исходником, ОСТАВЛЕНЫ намеренно: «1,500 mAh»
    и коды моделей не переводятся, и модель должна видеть, что их
    трогать не надо, — это половина смысла образца.
    """
    return safe_read(
        """
        SELECT src.source_text AS en,
               dst.translated_text AS tr,
               dst.char_limit AS char_limit
        FROM figma_layers dst
        JOIN figma_layers src
          ON src.product_id = dst.product_id
         AND src.slot = dst.slot
         AND src.lang = %(src)s
        WHERE dst.lang = %(dst)s
          AND dst.translated_text IS NOT NULL
          AND dst.translated_text <> ''
        ORDER BY length(src.source_text) DESC
        LIMIT %(lim)s
        """,
        params={"src": SOURCE_LANG, "dst": lang, "lim": int(limit)})


@st.cache_data(ttl=figma.IMAGE_TTL, show_spinner=False)
def preview_png(node_id: str, scale: float = figma.IMAGE_SCALE
                ) -> tuple[bytes | None, str | None]:
    """Картинка макета байтами: (png, причина отказа).

    Кэшируется КАРТИНКА, а не ссылка, и на сутки. Ссылку Figma держит
    около часа: кэш ссылки на сутки означал бы битые картинки через
    час — ссылка протухла, а мы её всё ещё раздаём. Байты не протухают,
    а макет меняется раз в недели.

    Ключ кэша — узел и масштаб, поэтому переключение языка в таблице
    картинку заново не просит: превью показывает английский макет,
    по нему и видно роль строки.
    """
    return figma.node_png(node_id, scale=scale)


@st.cache_data(ttl=60)
def load_layers(product_id: int, lang: str) -> tuple[pd.DataFrame, str | None]:
    """Строки товара на выбранном языке — то, что правит дизайнер.

    Основа — АНГЛИЙСКИЕ строки, перевод подтягивается к ним по `slot`.
    Не наоборот: строки языка существуют только там, где дизайнер уже
    нарисовал эту страницу в макете, а переводить надо как раз туда,
    где её нет. Прежний запрос читал `WHERE lang = <язык>` и на
    непереведённом языке отдавал пусто — экран говорил «текстовых
    слоёв нет» у товара, где их 33, и работать было нельзя.

    Предел символов берётся у языковой строки, когда она есть: ширина
    слоя своя на каждой странице. Когда её нет, берётся английский —
    он и есть ближайшая правда о макете.
    """
    try:
        df = pd.read_sql(
            """
            SELECT COALESCE(d.id, s.id)                AS id,
                   COALESCE(d.layer_id, s.layer_id)    AS layer_id,
                   s.layer_id                          AS source_layer_id,
                   s.slot                              AS slot,
                   COALESCE(d.frame_name, s.frame_name) AS frame_name,
                   s.source_text                       AS source_text,
                   d.translated_text                   AS translated_text,
                   COALESCE(d.char_limit, s.char_limit) AS char_limit,
                   COALESCE(d.status, %(none)s)        AS status,
                   COALESCE(d.edited_after_model, FALSE) AS edited_after_model,
                   d.model                             AS model,
                   d.updated_at                        AS updated_at
            FROM figma_layers s
            LEFT JOIN figma_layers d
                   ON d.product_id = s.product_id
                  AND d.slot = s.slot
                  AND d.lang = %(lang)s
            WHERE s.product_id = %(pid)s AND s.lang = %(src)s
            ORDER BY s.frame_name, s.id
            """, get_engine(),
            params={"pid": int(product_id), "lang": lang,
                    "src": SOURCE_LANG, "none": ST_NONE})
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------- демо
# Пока Figma не прочитана, показывать пустой экран бессмысленно: по нему
# не понять, как устроена работа. Поэтому есть демонстрационный набор —
# но он ОБЪЯВЛЯЕТСЯ на экране плашкой. Молчаливое демо, неотличимое от
# настоящих данных, — худшее из возможных: по нему принимают решения.

DEMO_PRODUCT = {
    "id": -1, "asin": "B0G4S9SJ3M", "sku": "54225000",
    "name": "Battery stapler Dnipro-M CC-36",
    "section_type": "Main Images", "page_name": "UK/US",
    "figma_file_key": "demo", "figma_node_id": "demo:0",
    "layers_count": 6, "synced_at": None,
}

# Тексты взяты короткими и длинными нарочно: на них видно и запас,
# и превышение — ради чего колонка длины и заведена.
DEMO_LAYERS = [
    ("PT01:title", "USB-C Charging", 18,
     {"es": "Carga USB-C", "de": "USB-C-Aufladung"}),
    ("PT01:sub", "Charge indicator", 22,
     {"es": "Indicador de carga", "de": "Ladeanzeige"}),
    ("PT02:body", "Charges from power banks and car adapters", 34,
     {"es": "Se carga desde power banks y adaptadores de coche",
      "de": "Lädt über Powerbanks und Kfz-Adapter"}),
    ("PT02:badge", "20V", 6, {"es": "20 V", "de": "20 V"}),
    ("PT03:title", "Brushless motor", 20,
     {"es": "Motor sin escobillas", "de": "Bürstenloser Motor"}),
    ("PT03:sub", "Two-year warranty", 24,
     {"es": "Garantía de dos años", "de": "Zwei Jahre Garantie"}),
]


def demo_products() -> pd.DataFrame:
    rows = [dict(DEMO_PRODUCT, langs_done={"es"}),
            dict(DEMO_PRODUCT, id=-2, asin="B0GTRY26HB", sku="99601000",
                 name="Leaf blower Dnipro-M SBA-36", layers_count=4,
                 langs_done=set()),
            dict(DEMO_PRODUCT, id=-3, asin="B0DFWVNRWB", sku="41324000",
                 name="Screwdriver set Dnipro-M CSD-36X", layers_count=5,
                 langs_done={"es", "de", "it", "fr"})]
    return pd.DataFrame(rows)


def demo_layers(product_id: int, lang: str) -> pd.DataFrame:
    rows = []
    for i, (lid, src, lim, tr) in enumerate(DEMO_LAYERS, 1):
        rows.append({
            "id": -i, "layer_id": lid, "frame_name": lid.split(":")[0],
            "source_text": src, "char_limit": lim,
            "translated_text": tr.get(lang) if product_id == -1 else None,
            "status": ST_TRANSLATED if tr.get(lang) and product_id == -1
            else ST_NONE, "updated_at": None,
        })
    return pd.DataFrame(rows)
