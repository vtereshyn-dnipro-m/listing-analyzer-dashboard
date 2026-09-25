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
import json

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


def product_state(langs_done: set, cov: dict | None = None) -> str:
    """Состояние товара: all / partial / none.

    «Только английский» — это когда переводов НЕТ ВОВСЕ. Раньше сюда
    попадал и товар с 97 переведёнными строками из 107: язык считался
    готовым только при нуле пробелов, а готовых языков не осталось —
    и список называл английскими три воздуходувки, где Мария перевела
    все слайды (проверено 25.09: `Main Images` 30 из 30 на ES и IT,
    дыры только в новых модулях A+). Ярлык отвечал на вопрос «есть ли
    язык, доделанный до конца», а читался как «есть ли перевод».

    Поэтому состояний по-прежнему три, но граница другая: «все языки» —
    ноль пробелов (как было), «только англ.» — ноль переведённых строк,
    остальное — «частично», и сколько именно, говорит чип покрытия.
    """
    have = {lg for lg in TARGET_LANGS if lg in langs_done}
    if len(have) == len(TARGET_LANGS):
        return "all"
    if cov:
        done = sum(int((cov.get(lg) or {}).get("done", 0)) for lg in TARGET_LANGS)
        return "partial" if done else "none"
    return "partial" if have else "none"


def row_state(r) -> str:
    """Состояние строки списка — по покрытию, а не по одному набору."""
    return product_state(set(r.get("langs_done") or ()), r.get("lang_cov") or {})


def summarize(products: pd.DataFrame) -> dict:
    """Четыре числа для шапки: всего, все языки, частично, только англ."""
    if products is None or products.empty:
        return {"total": 0, "all": 0, "partial": 0, "none": 0}
    counts = {"all": 0, "partial": 0, "none": 0}
    for _, r in products.iterrows():
        counts[row_state(r)] += 1
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
                         figma_file_key, figma_node_id, lang_nodes,
                         layers_count, synced_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s, now())
                    ON CONFLICT (figma_file_key, asin, section_type) DO UPDATE
                        SET name = EXCLUDED.name,
                            sku = EXCLUDED.sku,
                            page_name = EXCLUDED.page_name,
                            figma_node_id = EXCLUDED.figma_node_id,
                            lang_nodes = EXCLUDED.lang_nodes,
                            layers_count = EXCLUDED.layers_count,
                            synced_at = now()
                    RETURNING id
                    """,
                    (p["asin"], p.get("sku"), p.get("name"),
                     p.get("section_type"), p.get("page_name"),
                     p.get("file_key") or "", p["figma_node_id"],
                     json.dumps(p.get("lang_nodes") or {}),
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
                   p.lang_nodes, p.layers_count, p.synced_at
            FROM figma_products p
            ORDER BY p.name
            """, get_engine())
        cov = lang_coverage()
        # «Готов» — язык, где НЕ ОСТАЛОСЬ непереведённых строк. Раньше
        # готовым считался язык с хотя бы одной переведённой строкой:
        # одна строка, переведённая кнопкой ↻, красила язык в готовый
        # у товара с тридцатью непереведёнными (B0GTW2CTWZ: DE 1 из 30),
        # и список говорил «все языки готовы» там, где не сделано
        # ничего. Пятый случай за неделю, когда правда лежала в базе,
        # а экран показывал другое.
        df["lang_cov"] = df["id"].map(lambda i: cov.get(int(i), {}))
        df["lang_gaps"] = df["lang_cov"].map(
            lambda c: {lg: v["total"] - v["done"] for lg, v in c.items()})
        df["langs_done"] = df["lang_gaps"].map(
            lambda g: {lg for lg in TARGET_LANGS if not g.get(lg, 0)})
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"{type(e).__name__}: {e}"


def _coverage(product_id: int | None = None) -> pd.DataFrame:
    """Английские строки и языки, на которых у каждой есть перевод.

    Одна строка на слот: `product_id, slot, source_text, char_limit,
    have` — список языков с непустым переводом того же слота. Служебные
    строки (числа, коды моделей) отсеяны: их не переводят ни модель,
    ни дизайнер, и язык с ними в счёте никогда не стал бы готовым.
    """
    where = "s.lang = %(src)s"
    params: dict = {"src": SOURCE_LANG}
    if product_id is not None:
        where += " AND s.product_id = %(pid)s"
        params["pid"] = int(product_id)
    df = pd.read_sql(
        f"""
        SELECT s.product_id, s.slot, s.source_text, s.char_limit,
               COALESCE(array_agg(d.lang)
                        FILTER (WHERE d.translated_text IS NOT NULL
                                  AND d.translated_text <> ''), '{{}}') AS have
        FROM figma_layers s
        LEFT JOIN figma_layers d
               ON d.product_id = s.product_id
              AND d.slot = s.slot
              AND d.lang <> %(src)s
        WHERE {where}
        GROUP BY s.product_id, s.slot, s.source_text, s.char_limit
        ORDER BY s.product_id, s.slot
        """, get_engine(), params=params)
    if df.empty:
        return df
    df["have"] = df["have"].map(lambda v: set(v) if v is not None else set())
    return df[~df["source_text"].map(translate.is_boilerplate)]


@st.cache_data(ttl=120)
def export_rows(product_ids: tuple) -> tuple[pd.DataFrame, str | None]:
    """Готовые переводы нескольких товаров для плагина, одним запросом.

    `(asin, lang, layer_id, slot, translated_text)` — только непустые
    переводы, только целевые языки. Ключ кэша — кортеж id, поэтому
    вызывать с ОТСОРТИРОВАННЫМ кортежем: иначе одна и та же выборка
    в другом порядке станет отдельным запросом.
    """
    if not product_ids:
        return pd.DataFrame(), None
    try:
        df = pd.read_sql(
            """
            SELECT p.asin, l.lang, l.layer_id, l.slot, l.translated_text
            FROM figma_layers l
            JOIN figma_products p ON p.id = l.product_id
            WHERE l.product_id = ANY(%(ids)s)
              AND l.lang <> %(src)s
              AND l.translated_text IS NOT NULL AND l.translated_text <> ''
            ORDER BY p.asin, l.lang, l.slot
            """, get_engine(),
            params={"ids": [int(i) for i in product_ids], "src": SOURCE_LANG})
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"{type(e).__name__}: {e}"


def export_payload(file_key: str | None, rows) -> dict:
    """JSON для плагина на НЕСКОЛЬКО товаров и языков.

    Форма `{"file_key", "items": [{"asin", "lang", "layers": [...]}]}`
    — та же единица, что в выгрузке одного товара, только списком.
    Плагин принимает обе: одиночную и с `items`.

    Единственная сборка этой формы: её зовут и кнопка в списке
    (с DataFrame), и HTTP-маршрут для плагина (со списком словарей,
    без pandas). Две копии сборщика разошлись бы на первом же поле.
    """
    if rows is None:
        recs: list = []
    elif isinstance(rows, pd.DataFrame):
        recs = rows.to_dict("records") if not rows.empty else []
    else:
        recs = list(rows)
    items: dict = {}
    for r in sorted(recs, key=lambda r: (str(r["asin"]), str(r["lang"]), str(r["slot"]))):
        key = (str(r["asin"]), str(r["lang"]))
        it = items.setdefault(key, {"asin": key[0], "lang": key[1], "layers": []})
        it["layers"].append({"layer_id": str(r["layer_id"]), "slot": str(r["slot"]),
                             "text": str(r["translated_text"])})
    return {"file_key": file_key, "items": list(items.values())}

@st.cache_data(ttl=120)
def lang_coverage() -> dict:
    """{product_id: {lang: {done, total, main, aplus}}} по всем товарам.

    Один запрос на весь список, а не четыре на товар: в списке
    двадцать товаров, и ходить в базу по восемьдесят раз ради чипов —
    это и медленно, и не нужно.

    `main` и `aplus` — пары (переведено, всего) по типу места. Разнести
    их обязательно: слайды карточки у трёх воздуходувок переведены
    целиком, а дыры — в модулях A+, и «ES 97/107» без этой разбивки
    отправляет дизайнера искать пропущенное по всей карточке.
    """
    cov = _coverage()
    out: dict = {}
    for _, r in cov.iterrows():
        per = out.setdefault(int(r["product_id"]),
                             {lg: {"done": 0, "total": 0,
                                   "main": [0, 0], "aplus": [0, 0]}
                              for lg in TARGET_LANGS})
        kind = "aplus" if aplus_part(slide_of(r["slot"])) else "main"
        for lg in TARGET_LANGS:
            c = per[lg]
            c["total"] += 1
            c[kind][1] += 1
            if lg in r["have"]:
                c["done"] += 1
                c[kind][0] += 1
    return out


def lang_gaps() -> dict:
    """{product_id: {lang: сколько строк ещё без перевода}} — то, по чему
    считаются кнопки и планы перевода."""
    return {pid: {lg: c["total"] - c["done"] for lg, c in per.items()}
            for pid, per in lang_coverage().items()}


def missing_plan(product_id: int) -> tuple[dict, str | None]:
    """{lang: [строки без перевода]} — то, что переводит «всё, чего нет».

    Строки на каждый язык СВОИ: у DE может не хватать тридцати, у FR
    одной. Общий список на все языки заставил бы модель переводить
    заново и то, что уже есть. Предел символов берётся английский —
    языковой строки по определению нет.
    """
    try:
        cov = _coverage(product_id)
    except Exception as e:
        return {}, f"{type(e).__name__}: {e}"
    plan: dict = {}
    for _, r in cov.iterrows():
        row = {"slot": r["slot"], "source_text": r["source_text"],
               "char_limit": r["char_limit"]}
        for lg in TARGET_LANGS:
            if lg not in r["have"]:
                plan.setdefault(lg, []).append(row)
    return plan, None


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


APLUS_PART = "A+"


def norm_part(part: str) -> str:
    """«pt01» → «PT01», но «A+d05» остаётся: d/m — вариант модуля."""
    part = str(part or "")
    return part if part.startswith(APLUS_PART) else part.upper()


def slide_of(slot: str) -> str:
    """Имя слайда из места слоя: «B0G4S9SJ3M.PT01#3» → «PT01».

    Текст живёт в слайдах, а не в главном фото: у стаплера девять
    слайдов и на каждом свой текст. Группировка по слайду — это то,
    как карточку видит дизайнер. Модуль A+ — тоже «слайд»:
    «B0G4S9SJ3M.A+d05#1.0» → «A+d05» (позиционное имя, см. figma.py).
    """
    head = str(slot or "").split("#", 1)[0]
    return norm_part(head.rsplit(".", 1)[-1]) if "." in head else ""


def slide_order(name: str) -> tuple:
    """Порядок слайдов на экране: фото, слайды, A+ десктоп, A+ мобайл.

    Алфавит поставил бы «A+…» раньше «MAIN» — модули впереди карточки,
    а дизайнер видит их внизу, под слайдами.
    """
    name = str(name or "")
    if name == "MAIN":
        return (0, name)
    if not name.startswith(APLUS_PART):
        return (1, name)
    var = name[len(APLUS_PART):len(APLUS_PART) + 1]
    return (2 if var == "d" else 3 if var == "m" else 4, name)


def aplus_part(name: str) -> tuple[str, int | None] | None:
    """«A+d05» → («d», 5), «A+m12» → («m», 12); не A+ — None.

    Иная ширина («A+x200001») — («x», None): номер от ширины
    не отделить, и на экране такой модуль зовётся по имени фрейма.
    """
    name = str(name or "")
    if not name.startswith(APLUS_PART):
        return None
    tail = name[len(APLUS_PART):]
    if tail[:1] in ("d", "m") and tail[1:].isdigit():
        return (tail[:1], int(tail[1:]))
    return ("x", None)


def lang_nodes_of(row) -> dict:
    """Узлы слайдов по языкам, в каком бы виде ни пришли из jsonb.

    Формат: {"en": {"MAIN": "1445:541", "PT01": …}, "de": {…}}.
    Понимается и прежний плоский вид ({"de": "1482:33161"}) — база
    могла быть прочитана до появления слайдов, и падать из-за этого
    экран не должен.
    """
    nodes = row.get("lang_nodes")
    if isinstance(nodes, str):
        try:
            nodes = json.loads(nodes or "{}")
        except ValueError:
            return {}
    if not isinstance(nodes, dict):
        return {}
    out = {}
    for lang, val in nodes.items():
        out[lang] = val if isinstance(val, dict) else {"MAIN": str(val)}
    return out


def preview_node(row, lang: str, part: str = "MAIN") -> tuple[str, str]:
    """(узел для рендера, язык этого макета).

    Часть товаров дизайнер уже перевёл в самой Figma, и для них есть
    НАСТОЯЩИЙ макет на языке — с переведённым текстом прямо на
    картинке. Показывать вместо него английский значит прятать
    готовую работу.

    Английский остаётся запасным: языковых макетов одиннадцать
    на двадцать один товар, и там, где своего нет, английский —
    единственный способ увидеть роль строки. Но подпись обязана
    сказать, ЧТО показано: иначе «немецкая карточка» и «английская,
    потому что немецкой нет» выглядят одинаково.
    """
    nodes = lang_nodes_of(row)
    part = norm_part(part or "MAIN")
    own = (nodes.get(lang) or {}).get(part)
    if own:
        return str(own), lang
    src = (nodes.get(SOURCE_LANG) or {}).get(part)
    if src:
        return str(src), SOURCE_LANG
    # у товара, прочитанного до появления слайдов, есть только .MAIN
    fallback = ("" if pd.isna(row.get("figma_node_id"))
                else str(row.get("figma_node_id") or ""))
    return (fallback, SOURCE_LANG) if part == "MAIN" else ("", SOURCE_LANG)


@st.cache_data(ttl=figma.IMAGE_TTL, show_spinner=False)
def _png_cached(node_id: str, scale: float) -> bytes:
    """Только УДАЧНЫЙ рендер. Отказ уходит исключением и не кэшируется.

    Кэш здесь суточный, и запомнить в нём отказ значит держать пустую
    картинку сутки: так вчерашний 403 по истёкшему токену пережил
    замену токена — код и права были уже в порядке, а экран показывал
    прошлое. `st.cache_data` запоминает только то, что функция ВЕРНУЛА,
    поэтому отказ обязан быть исключением.
    """
    png, err = figma.node_png(node_id, scale=scale)
    if err or not png:
        raise RuntimeError(err or "рендер не пришёл")
    return png


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
    try:
        return _png_cached(node_id, scale), None
    except Exception as e:
        # отказ наружу, но НЕ в кэш: иначе он переживёт починку причины
        return None, str(e)


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
    # Форма та же, что у настоящих данных: `lang_gaps` — сколько строк
    # без перевода на каждый язык, `langs_done` — языки, где их ноль.
    def gaps(**n):
        return {lg: n.get(lg, 0) for lg in TARGET_LANGS}
    rows = [dict(DEMO_PRODUCT, lang_gaps=gaps(de=4, it=4, fr=4),
                 langs_done={"es"}),
            dict(DEMO_PRODUCT, id=-2, asin="B0GTRY26HB", sku="99601000",
                 name="Leaf blower Dnipro-M SBA-36", layers_count=4,
                 lang_gaps=gaps(de=3, es=3, it=3, fr=3), langs_done=set()),
            dict(DEMO_PRODUCT, id=-3, asin="B0DFWVNRWB", sku="41324000",
                 name="Screwdriver set Dnipro-M CSD-36X", layers_count=5,
                 lang_gaps=gaps(), langs_done={"es", "de", "it", "fr"})]
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
