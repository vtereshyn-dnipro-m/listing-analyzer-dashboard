# -*- coding: utf-8 -*-
"""
services/plugin_api.py — HTTP-маршрут, по которому плагин Figma
забирает готовые переводы сам, без файла.

    GET /figma/translations?asins=B0G4S9SJ3M,B0DG2Y9MSS&langs=de,es
    Authorization: Bearer <FIGMA_PLUGIN_TOKEN>

Ответ — ровно та же форма, что у кнопки «Выгрузить для Figma»:
`{"file_key": …, "items": [{"asin", "lang", "layers": [...]}]}`.
Плагин не знает, откуда пришёл JSON — из файла или по сети, — и
дальше идёт одним путём. Оба параметра необязательны: без них
отдаётся всё переведённое.

ТОКЕН ОБЯЗАТЕЛЕН, И БЕЗ НЕГО МАРШРУТА НЕТ. Не «маршрут есть, но
отвечает 401», а маршрут не монтируется вовсе: приложение без
секрета FIGMA_PLUGIN_TOKEN не открывает наружу ничего. Сравнение
токена — за постоянное время (`hmac.compare_digest`), чтобы длину
и префикс нельзя было подобрать по времени ответа.

Плагин Figma ходит из iframe на домене Figma, поэтому нужны CORS:
`Access-Control-Allow-Origin: *` безопасен — доступ решает токен
в заголовке, а не происхождение запроса. Заголовок `Authorization`
заставляет браузер слать предварительный OPTIONS — он тоже здесь.

База читается в потоке (`run_in_threadpool`): обработчик асинхронный,
а psycopg2 блокирующий, и запрос в цикле событий подвесил бы всё
приложение на время чтения. Streamlit-кэши не трогаются намеренно:
здесь нет контекста скрипта, и `st.cache_data` на этом шумел бы
предупреждением на каждый вызов. Прямой `get_conn()` — и всё.

Отказ называется вслух и JSON'ом: плагин читает `error` и показывает
человеку, а не HTML-страницу ошибки, в которой он ничего не разберёт.
"""
from __future__ import annotations

import hmac
import json

from services.db import cfg, get_conn

TOKEN_SECRET = "FIGMA_PLUGIN_TOKEN"
PATH = "/figma/translations"
SOURCE_LANG = "en"

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Access-Control-Max-Age": "600",
}


def _csv(value: str | None) -> list[str] | None:
    """«a, B ,c» → ["a","B","c"]; пусто → None (значит «без фильтра»)."""
    items = [x.strip() for x in str(value or "").split(",") if x.strip()]
    return items or None


def authorized(header: str | None, token: str | None) -> bool:
    """`Authorization: Bearer <token>` совпадает с секретом."""
    if not token or not header:
        return False
    scheme, _, given = str(header).partition(" ")
    if scheme.lower() != "bearer" or not given.strip():
        return False
    return hmac.compare_digest(given.strip(), str(token))


def fetch_rows(asins: list[str] | None, langs: list[str] | None) -> list[dict]:
    """Переводы из базы: asin, lang, layer_id, slot, translated_text, file_key.

    Приведение `::text[]` обязательно: psycopg2 отдаёт None как NULL,
    а `ANY(NULL)` без типа Postgres не понимает.
    """
    sql = """
        SELECT p.asin, l.lang, l.layer_id, l.slot, l.translated_text,
               p.figma_file_key
        FROM figma_layers l
        JOIN figma_products p ON p.id = l.product_id
        WHERE l.lang <> %(src)s
          AND l.translated_text IS NOT NULL AND l.translated_text <> ''
          AND (%(asins)s::text[] IS NULL OR p.asin = ANY(%(asins)s::text[]))
          AND (%(langs)s::text[] IS NULL OR l.lang = ANY(%(langs)s::text[]))
        ORDER BY p.asin, l.lang, l.slot
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, {"src": SOURCE_LANG, "asins": asins, "langs": langs})
            return [dict(asin=r[0], lang=r[1], layer_id=r[2], slot=r[3],
                         translated_text=r[4], file_key=r[5])
                    for r in cur.fetchall()]
    finally:
        conn.close()


def payload(rows: list[dict]) -> dict:
    """Строки → форма выгрузки. Сборщик общий с кнопкой в списке."""
    from services.localization import export_payload
    file_key = next((r.get("file_key") for r in rows if r.get("file_key")), None)
    return export_payload(file_key, rows)


def _json(status: int, body: dict):
    from starlette.responses import Response
    return Response(json.dumps(body, ensure_ascii=False), status_code=status,
                    media_type="application/json; charset=utf-8", headers=CORS)


async def translations(request):
    """Обработчик GET /figma/translations."""
    from starlette.concurrency import run_in_threadpool

    if request.method == "OPTIONS":
        from starlette.responses import Response
        return Response(status_code=204, headers=CORS)

    if not authorized(request.headers.get("authorization"), cfg(TOKEN_SECRET)):
        return _json(401, {"error": "Нет доступа: нужен заголовок "
                                    "Authorization: Bearer <токен плагина>."})
    asins = _csv(request.query_params.get("asins"))
    langs = _csv(request.query_params.get("langs"))
    try:
        rows = await run_in_threadpool(fetch_rows, asins, langs)
    except Exception as e:                        # noqa: BLE001 — причина уходит плагину
        return _json(500, {"error": f"Не удалось прочитать переводы: "
                                    f"{type(e).__name__}: {e}"})
    return _json(200, payload(rows))


def routes() -> list:
    """Маршруты для st.App. Пусто, если токен не задан, — наружу ничего."""
    if not cfg(TOKEN_SECRET):
        return []
    from starlette.routing import Route
    return [Route(PATH, translations, methods=["GET", "OPTIONS"])]
