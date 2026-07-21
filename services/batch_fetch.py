"""
services/batch_fetch.py — тянет живые снапшоты листингов через ScrapingDog
и складывает в listing_snapshots (append-only).

Запуск:
    python -m services.batch_fetch --all --limit 3
    python -m services.batch_fetch --sku GS-98
    python -m services.batch_fetch --all --competitors
"""

import argparse
import json
import logging
import time

import requests

from config import SCRAPINGDOG_API_KEY
from services.db import get_conn, ensure_schema, fetch_all, db_configured

logger = logging.getLogger("listing_suite.batch_fetch")

MARKETPLACE_TO_DOMAIN = {
    "US": "amazon.com", "DE": "amazon.de", "ES": "amazon.es", "FR": "amazon.fr",
    "IT": "amazon.it", "UK": "amazon.co.uk", "NL": "amazon.nl", "SE": "amazon.se",
    "PL": "amazon.pl",
}
MARKETPLACE_TO_COUNTRY = {
    "US": "us", "DE": "de", "ES": "es", "FR": "fr", "IT": "it",
    "UK": "gb", "NL": "nl", "SE": "se", "PL": "pl",
}

SCRAPINGDOG_URL = "https://api.scrapingdog.com/amazon/product"


def fetch_listing(asin: str, marketplace: str, max_retries: int = 3) -> dict:
    """Один запрос к ScrapingDog. Возвращает {'ok': bool, ...поля...}."""
    if not SCRAPINGDOG_API_KEY:
        return {"ok": False, "error": "SCRAPINGDOG_API_KEY не задан"}

    params = {
        "api_key": SCRAPINGDOG_API_KEY,
        "domain": MARKETPLACE_TO_DOMAIN.get(marketplace, "amazon.com"),
        "asin": asin,
        "country": MARKETPLACE_TO_COUNTRY.get(marketplace, "us"),
    }

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(SCRAPINGDOG_URL, params=params, timeout=30)
        except requests.RequestException as e:
            logger.warning("ASIN %s (%s): сетевая ошибка %s, попытка %s/%s", asin, marketplace, e, attempt, max_retries)
            time.sleep(2 * attempt)
            continue

        if resp.status_code == 429:
            wait = 2 ** attempt
            logger.warning("ASIN %s (%s): 429, жду %ss", asin, marketplace, wait)
            time.sleep(wait)
            continue

        if resp.status_code != 200:
            logger.warning("ASIN %s (%s): HTTP %s", asin, marketplace, resp.status_code)
            return {"ok": False, "error": f"HTTP {resp.status_code}", "raw": resp.text[:500]}

        data = resp.json()
        return _parse_scrapingdog_response(data)

    return {"ok": False, "error": "retries exhausted"}


def _parse_scrapingdog_response(data: dict) -> dict:
    """
    Приводит сырой ответ ScrapingDog к единому виду.
    ПРОВЕРЬ реальные ключи по своему тарифу/эндпоинту — ScrapingDog иногда
    меняет форму ответа между amazon/product и amazon/product-details.
    """
    availability = (data.get("availability_status") or data.get("availability") or "").lower()
    in_stock = "unavailable" not in availability and "out of stock" not in availability

    price_raw = data.get("price") or data.get("current_price")
    try:
        price = float(str(price_raw).replace(",", ".").replace("€", "").replace("$", "").strip())
    except (TypeError, ValueError):
        price = None

    return {
        "ok": True,
        "title": data.get("title"),
        "price": price,
        "in_stock": in_stock,
        "rating": data.get("rating") or data.get("total_rating"),
        "review_count": data.get("total_reviews") or data.get("review_count"),
        "bullet_points": data.get("feature_bullets") or data.get("about_this_item") or [],
        "raw": data,
    }


def run(sku_filter: str | None = None, limit: int | None = None, include_competitors: bool = False) -> int:
    ensure_schema()
    if not db_configured():
        logger.warning("DATABASE_URL не задан — batch_fetch пропущен")
        return 0

    query = "SELECT DISTINCT sku_group, asin, marketplace, is_competitor FROM product_matrix"
    conditions, params = [], []
    if not include_competitors:
        conditions.append("is_competitor = FALSE")
    if sku_filter:
        conditions.append("sku_group = %s")
        params.append(sku_filter)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    rows = fetch_all(query, tuple(params))
    if limit:
        rows = rows[:limit]

    fetched = 0
    with get_conn() as conn, conn.cursor() as cur:
        for row in rows:
            result = fetch_listing(row["asin"], row["marketplace"])
            cur.execute(
                """
                INSERT INTO listing_snapshots
                    (asin, marketplace, ok, title, price, in_stock, rating, review_count, bullet_points, raw)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    row["asin"], row["marketplace"], result.get("ok", False),
                    result.get("title"), result.get("price"), result.get("in_stock"),
                    result.get("rating"), result.get("review_count"),
                    result.get("bullet_points"), json.dumps(result.get("raw") or {}),
                ),
            )
            fetched += 1
            logger.info("fetched %s (%s): ok=%s", row["asin"], row["marketplace"], result.get("ok"))
            time.sleep(0.5)  # вежливая пауза между запросами

    logger.info("batch_fetch: %s снапшотов записано", fetched)
    return fetched


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--sku", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--competitors", action="store_true")
    args = parser.parse_args()

    if not args.all and not args.sku:
        parser.error("укажи --all или --sku GS-98")

    run(sku_filter=args.sku, limit=args.limit, include_competitors=args.competitors)
