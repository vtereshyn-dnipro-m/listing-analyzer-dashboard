"""Сводка цикла автономной работы Listing Suite — для того же бота, что у Кабинета.

Схема — docs/autonomy.md. КАНАЛ ЗАПИСИ ЕЩЁ НЕ ВЫБРАН (TASKS.md, T-1): роль Кабинета на запись из его `.mcp.json`
владелец брать запретил (19.10.2026), а свою роль или таблицу заводит он сам. Поэтому скрипт пока только СОБИРАЕТ
сводку и печатает её — в базу не пишет и ни к чему не подключается:

    python3 scratchpad/cycle_report.py --title "Цикл 19.10 14:00" \
        --done "T-3: PR #140 открыт, проверка ок" --merged "#141 docs: факт про BSR (по «мержи #141»)" \
        --waiting "мержи #140; ответ Ярослава про product_root" --problems ""

`--merged` — смерженное за цикл; мерж только по «мержи #N» владельца (24.10.2026), сам агент не мержит
ничего. Шапка получает приставку «Listing Suite · », чтобы в общем боте сводки двух продуктов не путались. Пустые поля в
сообщение не попадают. Агент кладёт напечатанное в ответ владельцу. Когда канал выберут, запись добавится сюда
отдельным PR («ждёт меня»).
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
    ap.add_argument("--dry-run", action="store_true", help="то же, что без флага: канал записи не выбран")
    a = ap.parse_args(argv)
    print(json.dumps(row(a), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
