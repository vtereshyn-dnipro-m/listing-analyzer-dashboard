#!/usr/bin/env python3
"""PreToolUse-хук: блокирует необратимые операции, на которые у агента есть права.

Раньше это было правилом в промпте («ничего не удаляй»), а права — были. Хук смотрит команду Bash,
запросы MCP-инструментов к базам и содержимое файлов .sql/.py, на которые команда ссылается
(SQL исполняется через run_sql.py <файл>, а вызовы Databricks API лежат в скриптах).

Блокируется (exit 2 — Claude Code не выполняет вызов и показывает причину):
  • DROP TABLE / SCHEMA / VIEW / DATABASE, TRUNCATE
  • DELETE FROM без WHERE (до ; или конца запроса)
  • удаление ноутбуков и джобов через API Databricks: workspace/delete, jobs/delete, w.workspace.delete, w.jobs.delete,
    dbutils.fs.rm, DROP TABLE в Spark SQL, а также удаление секретов/скоупов
Нужно удалить намеренно — человек делает это сам, в UI или из своей консоли.
"""
import json, os, re, sys

RULES = [
    (r"\bDROP\s+(TABLE|SCHEMA|VIEW|DATABASE|INDEX)\b", "DROP объекта базы"),
    (r"\bTRUNCATE\b", "TRUNCATE"),
    (r"/api/2\.[0-9]/workspace/delete\b", "удаление ноутбука или папки через Workspace API"),
    (r"/api/2\.[0-9]/jobs/delete\b", "удаление джобы через Jobs API"),
    (r"\bw\.workspace\.delete\(|\bworkspace\.delete\(", "удаление в workspace через SDK"),
    (r"\bw\.jobs\.delete\(|\bjobs\.delete\(", "удаление джобы через SDK"),
    (r"/api/2\.0/secrets/(delete|scopes/delete)\b|\bsecrets\.delete_(secret|scope)\(", "удаление секрета или скоупа"),
    (r"\bdbutils\.fs\.rm\(", "удаление файлов в DBFS/Volume"),
    (r"/api/2\.0/fs/(directories|files)/[^\s\"']+\"?\s*,\s*method\s*=\s*[\"']DELETE", "удаление файла на Volume через Files API"),
]

def delete_without_where(text: str):
    for m in re.finditer(r"\bDELETE\s+FROM\s+[\w.\"]+([^;]*)", text, re.I | re.S):
        tail = m.group(1)
        if not re.search(r"\bWHERE\b", tail, re.I):
            return "DELETE без WHERE: " + m.group(0)[:80].replace("\n", " ")
    return None

def gather(tool_name: str, tool_input: dict) -> str:
    parts = []
    if tool_name == "Bash":
        cmd = tool_input.get("command", "") or ""
        parts.append(cmd)
        # файлы, на которые ссылается команда (SQL для run_sql.py, скрипты с вызовами API)
        for path in re.findall(r"(?<![\w-])((?:/|\./|~/)?[\w./@~-]+\.(?:sql|py|sh))\b", cmd):
            p = os.path.expanduser(path)
            if not os.path.isabs(p):
                p = os.path.join(os.getcwd(), p)
            if "/.claude/hooks/" in p:      # сам хук содержит эти слова в правилах и справке
                continue
            if os.path.isfile(p) and os.path.getsize(p) < 2_000_000:
                try:
                    parts.append(open(p, encoding="utf-8", errors="replace").read())
                except OSError:
                    pass
    else:
        parts.append(json.dumps(tool_input, ensure_ascii=False))
    return "\n".join(parts)

def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool = payload.get("tool_name", ""); inp = payload.get("tool_input", {}) or {}
    if tool != "Bash" and "run_query" not in tool and "execute" not in tool.lower():
        return 0
    text = gather(tool, inp)
    hits = [why for pat, why in RULES if re.search(pat, text, re.I)]
    dw = delete_without_where(text)
    if dw:
        hits.append(dw)
    if hits:
        sys.stderr.write("⛔ Хук guard.py заблокировал вызов: " + "; ".join(hits) +
                         ". Необратимые операции агент не выполняет — это делает человек сам. "
                         "Если операция нужна, покажи её владельцу и попроси выполнить.\n")
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
