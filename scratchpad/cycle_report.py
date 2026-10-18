"""Положить сводку цикла автономной работы Listing Suite в kabinet_data.agent_cycle_reports.

В бот её отправит задача Кабинета `Kabinet - Agent Cycle Report` — тот же бот, что у Кабинета; секрет бота агент
не трогает. Схема — docs/autonomy.md. Работает после мержа kabinet-dashboard #328 и применения его SQL.

    python3 scratchpad/cycle_report.py --title "Цикл 19.10 14:00" \
        --done "T-3: PR #137 открыт, проверка ок" --merged "#138 docs: факт про BSR" \
        --waiting "мержи #137; ответ Ярослава про product_root" --problems ""

Шапка получает приставку «Listing Suite · », чтобы в общем боте сводки двух продуктов не путались. Пустые поля в
сообщение не попадают. `--dry-run` печатает, что уйдёт, и ничего не пишет.

Пишет ОДНУ строку и ничего больше — под ролью Кабинета из `.mcp.json` (сервер `lakebase-kabinet`): сначала из
`.mcp.json` этого репозитория, иначе из репозитория Кабинета рядом (`KABINET_ROOT`, по умолчанию
`../kabinet-dashboard`). Своей роли на запись в базу Кабинета у Listing Suite нет. Строку подключения скрипт
не печатает.
"""
import argparse
import json
import os
import sys

PREFIX = "Listing Suite · "
FIELDS = ("done", "merged", "waiting", "problems")
SERVER = "lakebase-kabinet"


def dsn() -> str:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    kabinet = os.environ.get("KABINET_ROOT") or os.path.join(os.path.dirname(root), "kabinet-dashboard")
    for base in (root, kabinet):
        path = os.path.join(base, ".mcp.json")
        try:
            servers = json.load(open(path, encoding="utf-8"))["mcpServers"]
        except (OSError, ValueError, KeyError):
            continue
        if SERVER in servers:
            return servers[SERVER]["env"]["LAKEBASE_DSN"]
    sys.exit(f"нет сервера {SERVER} ни в .mcp.json этого репозитория, ни в {kabinet}/.mcp.json — "
             "сводку записать нечем (KABINET_ROOT — путь к репозиторию Кабинета)")


def row(a) -> tuple:
    title = a.title if a.title.startswith(PREFIX) else PREFIX + a.title
    return (title, *[(getattr(a, k) or "").strip() or None for k in FIELDS])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    for k in FIELDS:
        ap.add_argument(f"--{k}", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    values = row(a)
    if a.dry_run:
        print(json.dumps(dict(zip(("title",) + FIELDS, values)), ensure_ascii=False, indent=1))
        return 0
    import psycopg2
    with psycopg2.connect(dsn()) as c, c.cursor() as cur:
        cur.execute("""INSERT INTO kabinet_data.agent_cycle_reports (title, done, merged, waiting, problems)
                       VALUES (%s, %s, %s, %s, %s) RETURNING id""", values)
        print("сводка записана, id", cur.fetchone()[0], "— уйдёт в бот в течение 15 минут")
    return 0


if __name__ == "__main__":
    sys.exit(main())
