"""
services/analyze.py — AI-анализ пачкой поверх listing_latest.
Считает title_len/highlights_len (без AI) + опционально AI-грейд через Claude.

Запуск:
    python -m services.analyze --all --limit 3
    python -m services.analyze --all              # только новые снапшоты
    python -m services.analyze --all --no-ai       # без AI, только длины
    python -m services.analyze --all --force        # перегнать всё
"""

import argparse
import json
import logging

from config import ANTHROPIC_API_KEY, TITLE_LIMIT, HIGHLIGHTS_LIMIT
from services.db import get_conn, ensure_schema, fetch_all, db_configured

logger = logging.getLogger("listing_suite.analyze")

AI_PROMPT = """Ты аудитор Amazon-листингов. Тебе дают тайтл и буллеты товара.
Верни ТОЛЬКО JSON без пояснений:
{{
  "grade": "A"|"B"|"C"|"D",
  "must_keep_phrases": ["фраза1", "фраза2"]
}}
must_keep_phrases — 2-4 ключевые поисковые фразы из тайтла/буллетов, которые
нельзя терять при сокращении тайтла до {title_limit} символов (SQP-значимые термины).

Тайтл: {title}
Буллеты: {bullets}
"""


def _ai_grade(title: str, bullets: list[str]) -> dict:
    if not ANTHROPIC_API_KEY:
        return {"grade": None, "must_keep_phrases": []}

    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = AI_PROMPT.format(
        title_limit=TITLE_LIMIT, title=title or "", bullets="; ".join(bullets or [])
    )
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(text)
    except Exception as e:
        logger.warning("AI-анализ не удался: %s", e)
        return {"grade": None, "must_keep_phrases": []}


def run(sku_filter: str | None = None, limit: int | None = None, use_ai: bool = True, force: bool = False) -> int:
    ensure_schema()
    if not db_configured():
        logger.warning("DATABASE_URL не задан — analyze пропущен")
        return 0

    query = """
        SELECT l.asin, l.marketplace, l.title, l.bullet_points
        FROM listing_latest l
        JOIN product_matrix m ON m.asin = l.asin AND m.marketplace = l.marketplace
        WHERE l.ok = TRUE
    """
    params: list = []
    if sku_filter:
        query += " AND m.sku_group = %s"
        params.append(sku_filter)
    if not force:
        query += """
            AND NOT EXISTS (
                SELECT 1 FROM listing_analysis a
                WHERE a.asin = l.asin AND a.marketplace = l.marketplace
                  AND a.analyzed_at >= l.fetched_at
            )
        """

    rows = fetch_all(query, tuple(params))
    if limit:
        rows = rows[:limit]

    analyzed = 0
    with get_conn() as conn, conn.cursor() as cur:
        for row in rows:
            title = row["title"] or ""
            bullets = row["bullet_points"] or []
            highlights_text = " ".join(bullets)

            ai_result = _ai_grade(title, bullets) if use_ai else {"grade": None, "must_keep_phrases": []}

            cur.execute(
                """
                INSERT INTO listing_analysis
                    (asin, marketplace, title_len, title_over, highlights_len, ai_grade, must_keep_phrases, raw)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    row["asin"], row["marketplace"],
                    len(title), max(0, len(title) - TITLE_LIMIT),
                    len(highlights_text),
                    ai_result.get("grade"),
                    ai_result.get("must_keep_phrases", []),
                    json.dumps(ai_result),
                ),
            )
            analyzed += 1
            logger.info("analyzed %s (%s): title_len=%s grade=%s", row["asin"], row["marketplace"], len(title), ai_result.get("grade"))

    logger.info("analyze: %s листингов обработано", analyzed)
    return analyzed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--sku", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-ai", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not args.all and not args.sku:
        parser.error("укажи --all или --sku GS-98")

    run(sku_filter=args.sku, limit=args.limit, use_ai=not args.no_ai, force=args.force)
