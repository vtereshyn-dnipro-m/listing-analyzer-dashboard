"""Предпросмотр сводки цикла автономной работы Listing Suite — без записи.

Схема — docs/autonomy.md. ЗАПИСЬ идёт не отсюда, а инструментом `write_cycle_report` MCP-сервера
`ls-cycle-report` (mcp_servers/cycle_report.py): строку подключения держит процесс сервера, агент её не видит
(вариант Б, решение владельца 19.10.2026). Этот скрипт только собирает сводку тем же правилом и печатает её —
в базу не пишет и ни к чему не подключается:

    python3 scratchpad/cycle_report.py --title "Цикл 19.10 14:00" \
        --done "T-3: PR #140 открыт, проверка ок" --merged "#141 docs: факт про BSR" \
        --waiting "мержи #140; ответ Ярослава про product_root" --problems ""

Шапка получает приставку «Listing Suite · », чтобы в общем боте сводки двух продуктов не путались. Пустые поля в
сообщение не попадают.
"""
import argparse
import json
import sys

PREFIX = "Listing Suite · "
FIELDS = ("done", "merged", "waiting", "problems")


def row(a) -> dict:
    title = a.title if a.title.startswith(PREFIX) else PREFIX + a.title
    out = {"title": title}
    out.update({k: (getattr(a, k) or "").strip() or None for k in FIELDS})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    for k in FIELDS:
        ap.add_argument(f"--{k}", default="")
    ap.add_argument("--dry-run", action="store_true", help="то же, что без флага: скрипт только печатает, запись — write_cycle_report")
    a = ap.parse_args(argv)
    print(json.dumps(row(a), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
