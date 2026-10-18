# -*- coding: utf-8 -*-
"""
tests/test_autonomy.py — схема автономной работы (AGENTS.md, «Автономия»).

Схема держится на тексте: очереди, правилах и инструкции проверяющему. Текст
ломается тихо — задача без уровня, правило, выпавшее из раздела при правке,
проверяющий, которому дали право править. Поэтому заперто:

1. У каждой задачи `TASKS.md` уровень из трёх и критерий готовности, и
   критерий — не «PR открыт».
2. Особые правила Listing Suite стоят в своих уровнях: канон Ярослава,
   отправка в Amazon, вызовы моделей и траты — «никогда сам»; миграции SQL
   и ребут Streamlit Cloud — «ждёт меня».
3. Проверяющий — отдельный агент без права правки, с теми же границами в
   своём списке.
4. Скрипт сводки пишет ровно одну строку в таблицу Кабинета, помечает
   шапку продуктом и не трогает секретов приложения.

Запуск (pytest не нужен):  python tests/test_autonomy.py
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


LEVELS = {"сам", "ждёт меня", "никогда сам"}

# ================================================================ 1. TASKS
print("1. очередь TASKS.md")
tasks_text = (ROOT / "TASKS.md").read_text(encoding="utf-8")
body = tasks_text.split("## В работе", 1)[1]
entries = re.split(r"(?m)^### ", body)[1:]
check(f"в очереди есть задачи ({len(entries)})", len(entries) > 0)
ids = []
for e in entries:
    head = e.splitlines()[0]
    m = re.match(r"(T-\d+)\.", head)
    tid = m.group(1) if m else head[:20]
    ids.append(tid)
    lvl = re.search(r"(?m)^- Уровень:\s*(.+?)\s*$", e)
    crit = re.search(r"(?ms)^- Критерий готовности:\s*(.+?)(?=^- |\Z)", e)
    check(f"{tid}: номер в шапке", bool(m))
    check(f"{tid}: уровень из трёх ({lvl.group(1) if lvl else '—'})", bool(lvl) and lvl.group(1) in LEVELS)
    ctext = " ".join(crit.group(1).split()) if crit else ""
    check(f"{tid}: критерий готовности есть и это не «PR открыт»",
          len(ctext) > 30 and not re.fullmatch(r"(?i)pr открыт\.?", ctext))
    check(f"{tid}: статус есть", bool(re.search(r"(?m)^- Статус:\s*\S", e)))
check("номера задач не повторяются", len(ids) == len(set(ids)))

# ======================================================= 2. раздел AGENTS
print("2. раздел «Автономия» в AGENTS.md")
agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
sec = agents.split("## Автономия", 1)[1].split("\n## ", 1)[0] if "## Автономия" in agents else ""
check("раздел есть и стоит до правил проекта", sec and agents.index("## Автономия") < agents.index("## Правила проекта"))
self_part = sec.split("**Сам**", 1)[1].split("**Ждёт меня**", 1)[0] if "**Сам**" in sec else ""
wait_part = sec.split("**Ждёт меня**", 1)[1].split("**Никогда сам**", 1)[0] if "**Ждёт меня**" in sec else ""
never_part = sec.split("**Никогда сам**", 1)[1].split("**Цикл.**", 1)[0] if "**Никогда сам**" in sec else ""
low = lambda s: " ".join(s.lower().split())  # noqa: E731
for what, words in (("канон Ярослава — только чтение", ("канон ярослава", "только чтение")),
                    ("отправка в Amazon", ("отправка в amazon",)),
                    ("вызовы моделей и траты", ("вызовы моделей", "тратит деньги")),
                    ("секреты", ("секретов",)),
                    ("сообщения людям", ("сообщения людям",))):
    check(f"«никогда сам»: {what}", all(w in low(never_part) for w in words))
for what, words in (("миграции SQL", ("миграции sql",)), ("ребут Streamlit Cloud", ("ребут streamlit cloud",)),
                    ("правка проверяющего и хуков", (".claude/agents/", "хуки"))):
    check(f"«ждёт меня»: {what}", all(w in low(wait_part) for w in words))
for leak in ("канон", "amazon", "модел", "миграц", "ребут"):
    check(f"«сам» не разрешает ничего про «{leak}»", leak not in low(self_part))
check("размер AGENTS.md — под порогом 150 тыс. символов (иначе — в docs/)", len(agents) <= 150_000)
check("схема описана в docs/autonomy.md", (ROOT / "docs" / "autonomy.md").is_file())

# ======================================================= 3. проверяющий
print("3. агент-проверяющий")
rv_path = ROOT / ".claude" / "agents" / "pr-reviewer.md"
rv = rv_path.read_text(encoding="utf-8") if rv_path.is_file() else ""
fm = re.match(r"(?s)^---\n(.*?)\n---\n", rv)
meta = dict(line.split(":", 1) for line in fm.group(1).splitlines() if ":" in line) if fm else {}
tools = {t.strip() for t in meta.get("tools", "").split(",")}
check("проверяющий есть, имя pr-reviewer", meta.get("name", "").strip() == "pr-reviewer")
check(f"инструменты только на чтение ({sorted(tools)})", tools and not tools & {"Edit", "Write", "NotebookEdit", "Agent"})
check("не правит, не мержит, не зовёт модели", all(w in rv for w in ("не правишь", "не мержишь", "не зовёшь модели")))
for what, needle in (("канон", "canon/ai_design_conveyor/"), ("отправка в Amazon", "services/spapi.py"),
                     ("вызовы моделей", "services/ai.py"), ("весь набор тестов", "tests/test_*.py"),
                     ("вердикт первой строкой", "Проверка: ок")):
    check(f"в списке проверяющего: {what}", needle in rv)

# ===================================================== 4. скрипт сводки
print("4. скрипт сводки цикла")
cr_path = ROOT / "scratchpad" / "cycle_report.py"
src = cr_path.read_text(encoding="utf-8")
sql = re.findall(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE)\b", src)
check(f"пишет ровно одну строку: одна вставка и больше ничего ({sql})", sql == ["INSERT"])
check("пишет в таблицу Кабинета", "kabinet_data.agent_cycle_reports" in src)
check("секретов приложения не читает (st.secrets, cfg, secrets.toml)",
      not re.search(r"st\.secrets|\bcfg\(|secrets\.toml|dbutils\.secrets", src))
check("строку подключения не печатает", not re.search(r"print\([^)]*dsn", src, re.I))
spec = importlib.util.spec_from_file_location("cycle_report", cr_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = mod.main(["--title", "Цикл 19.10", "--done", "T-3 готово", "--waiting", "  ", "--dry-run"])
out = json.loads(buf.getvalue())
check("шапка помечена продуктом", rc == 0 and out["title"] == "Listing Suite · Цикл 19.10")
check("пустое поле не уходит в сообщение", out["waiting"] is None and out["done"] == "T-3 готово")
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    mod.main(["--title", "Listing Suite · X", "--dry-run"])
check("приставка не удваивается", json.loads(buf.getvalue())["title"] == "Listing Suite · X")

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
