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
4. Скрипт предпросмотра сводки помечает шапку продуктом и не подключается
   к базе: роль Кабинета из его `.mcp.json` брать запрещено (19.10.2026).
5. Запись сводки (вариант Б) — ровно одна и узкая: MCP-сервер
   `ls-cycle-report` с одним инструментом и одним зашитым INSERT в
   `listing_data.agent_cycle_reports`, строка подключения только из своего
   окружения. Роль агента в миграции — вставка пяти колонок без `sent_at`;
   задаче Кабинета — чтение и отметка отправки, без правки текста. Сервер
   чтения `lakebase-listing` записи не получил.

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
code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
code = re.sub(r'(?s)^""".*?"""', "", code)  # докстринг описывает запрет и сам содержит слова
sql = re.findall(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE)\b", code)
check(f"предпросмотр не пишет — SQL в скрипте нет ({sql})", not sql)
check("к базе не подключается (psycopg2, connect)", not re.search(r"psycopg2|\.connect\(", code))
# Владелец 19.10.2026: роль Кабинета из его .mcp.json не брать. Проверка видит именно
# эту форму чтения учётных данных, а не только секреты Streamlit.
for needle in (".mcp.json", "LAKEBASE_DSN", "KABINET_ROOT", "kabinet-dashboard", "mcpServers"):
    check(f"чужих учётных данных не читает: нет «{needle}»", needle not in code)
check("секретов приложения не читает (st.secrets, cfg, secrets.toml)",
      not re.search(r"st\.secrets|\bcfg\(|secrets\.toml|dbutils\.secrets|os\.environ", code))
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

# ================================================== 5. запись сводки (Б)
print("5. запись сводки: сервер ls-cycle-report и права в миграциях")
srv = (ROOT / "mcp_servers" / "cycle_report.py").read_text(encoding="utf-8")
srv_code = re.sub(r'(?s)^#.*?"""(.*?)"""', "", srv, count=1)  # шапка uv и докстринг
stmts = re.findall(r"\b(INSERT|UPDATE|DELETE|ALTER|CREATE|GRANT|SELECT|COPY)\b", srv_code)
check(f"в сервере ровно один SQL — INSERT ({stmts})", stmts == ["INSERT"])
check("INSERT — в listing_data.agent_cycle_reports, пять колонок, без sent_at",
      re.search(r"INSERT INTO listing_data\.agent_cycle_reports \(title, done, merged, waiting, problems\)", srv_code)
      is not None and "sent_at" not in srv_code)
check("без RETURNING: роли агента чтение не выдано", "RETURNING" not in srv_code.upper())
check("инструмент ровно один", srv_code.count("@mcp.tool()") == 1)
check("SQL от агента не принимается: execute только с зашитым запросом",
      re.findall(r"cur\.execute\((\w+)", srv_code) == ["INSERT_SQL"])
for needle in (".mcp.json", "KABINET_ROOT", "kabinet-dashboard", "mcpServers", "st.secrets"):
    check(f"сервер не читает чужих учётных данных: нет «{needle}»", needle not in srv_code)
check("строка подключения — только из своего окружения (LAKEBASE_DSN)",
      re.findall(r"os\.environ(?:\.get)?\(?\[?[\"'](\w+)", srv_code) == ["LAKEBASE_DSN"])
# Поведение инструмента — на подменах: fastmcp (его нет в requirements, сервер ставится через uv)
# и psycopg2.connect. Сеть и база не трогаются.
import os  # noqa: E402
import types  # noqa: E402

CALLS = []


class _Cur:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        CALLS.append(("execute", sql, params))


class _Con:
    def __enter__(self):
        return self

    def __exit__(self, et, *a):
        CALLS.append(("commit" if et is None else "rollback",))
        return False

    def cursor(self):
        return _Cur()

    def close(self):
        CALLS.append(("close",))


_fm = types.ModuleType("fastmcp")
_fm.FastMCP = type("FastMCP", (), {"__init__": lambda self, name: None,
                                    "tool": lambda self: (lambda f: f), "run": lambda self: None})
_saved_fm = sys.modules.get("fastmcp")
sys.modules["fastmcp"] = _fm
import psycopg2  # noqa: E402

_real_connect = psycopg2.connect
psycopg2.connect = lambda dsn, **kw: CALLS.append(("connect", dsn)) or _Con()
_saved_dsn = os.environ.pop("LAKEBASE_DSN", None)
try:
    spec = importlib.util.spec_from_file_location("cycle_report_srv", ROOT / "mcp_servers" / "cycle_report.py")
    srv_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(srv_mod)
    r = srv_mod.write_cycle_report("Цикл 19.10", done="T-3 готово")
    check("без LAKEBASE_DSN — отказ словами и ни одного подключения", r.get("ok") is False and not CALLS)
    os.environ["LAKEBASE_DSN"] = "postgresql://fake"
    r = srv_mod.write_cycle_report("Цикл 19.10", done="T-3 готово", waiting="  ")
    ex = [c for c in CALLS if c[0] == "execute"]
    check("одна вставка, коммит и закрытие соединения",
          len(ex) == 1 and ("commit",) in CALLS and ("close",) in CALLS and r.get("ok") is True)
    check("шапка с приставкой продукта, пустое поле — NULL",
          ex and ex[0][2] == ("Listing Suite · Цикл 19.10", "T-3 готово", None, None, None))
    check("подключение — со строкой из окружения сервера", ("connect", "postgresql://fake") in CALLS)
    check("пустая шапка — отказ, без записи", srv_mod.write_cycle_report("  ").get("ok") is False and len(
        [c for c in CALLS if c[0] == "execute"]) == 1)
    long = srv_mod.row("x" * 500, done="y" * 9000)
    check("длинное обрезается по пределам сообщения", len(long[0]) == srv_mod.TITLE_MAX and len(long[1]) == srv_mod.FIELD_MAX)

    # Пароль не уходит агенту через текст ошибки. libpq цитирует куски строки подключения
    # («invalid percent-encoded token: "<пароль>"») — найдено проверяющим PR #140.
    PW = "Fake%zzPass123"
    os.environ["LAKEBASE_DSN"] = f"postgresql://claude_code_report:{PW}@localhost:1/db"

    def _bad_connect(dsn, **kw):
        raise psycopg2.ProgrammingError(f'invalid dsn: invalid percent-encoded token: "{PW}"')

    psycopg2.connect = _bad_connect
    r = srv_mod.write_cycle_report("Цикл")
    check(f"сбой подключения — без текста драйвера и без пароля ({r.get('error', '')[:60]})",
          r.get("ok") is False and PW not in str(r) and "zzPass" not in str(r) and "ProgrammingError" in str(r))

    class _BadCur(_Cur):
        def execute(self, sql, params=None):
            raise psycopg2.Error(f"permission denied; dsn {os.environ['LAKEBASE_DSN']}")

    class _BadCon(_Con):
        def cursor(self):
            return _BadCur()

    psycopg2.connect = lambda dsn, **kw: _BadCon()
    r = srv_mod.write_cycle_report("Цикл")
    check("сбой запроса — текст есть, пароль вырезан",
          r.get("ok") is False and "permission denied" in r.get("error", "") and PW not in str(r) and "zzPass" not in str(r))
    kv = srv_mod.secret_parts("host=h user=u password=Abc%41def dbname=d")
    check("пароль находится и в форме key=value, и раскодированным", "Abc%41def" in kv and "AbcAdef" in kv)
finally:
    psycopg2.connect = _real_connect
    os.environ.pop("LAKEBASE_DSN", None)
    if _saved_dsn is not None:
        os.environ["LAKEBASE_DSN"] = _saved_dsn
    if _saved_fm is None:
        sys.modules.pop("fastmcp", None)
    else:
        sys.modules["fastmcp"] = _saved_fm

ro = (ROOT / "mcp_servers" / "lakebase_pg.py").read_text(encoding="utf-8")
check("сервер чтения lakebase-listing остался только на чтение",
      "readonly=True" in ro and "insert" in ro and "write_cycle_report" not in ro)

mig = (ROOT / "migrations" / "2026-10-19_agent_cycle_reports.sql").read_text(encoding="utf-8")
mig_code = "\n".join(l.split("--")[0] for l in mig.splitlines())
cols = re.search(r"CREATE TABLE IF NOT EXISTS listing_data\.agent_cycle_reports \((.*?)\n\);", mig_code, re.S)
names = [c.strip().split()[0] for c in re.split(r",\s*\n", cols.group(1)) if c.strip()] if cols else []
check(f"таблица той же формы, что у Кабинета ({names})",
      names == ["id", "created_at", "title", "done", "merged", "waiting", "problems", "sent_at", "send_error", "attempts"])
# Права сверяются НА РАВЕНСТВО со всем набором GRANT/REVOKE файла, а не поиском запрещённых слов:
# лишний грант любой формы (вся таблица, другая таблица, членство в роли, имя в кавычках) должен
# валить тест. Так их нашёл проверяющий PR #140: шесть мутаций из семи прошли слова-запреты.
APP, KAB = "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856"


def acl(sql_text: str) -> set:
    code = "\n".join(l.split("--")[0] for l in sql_text.splitlines())
    stmts = re.findall(r"\b(?:GRANT|REVOKE)\b[^;]*;", code)
    return {" ".join(s.replace('"', "").rstrip(";").split()) for s in stmts}


T, SEQ = "listing_data.agent_cycle_reports", "listing_data.agent_cycle_reports_id_seq"
want_mig = {f"REVOKE ALL ON {T} FROM {APP}",
            f"REVOKE ALL ON SEQUENCE {SEQ} FROM {APP}",
            "GRANT USAGE ON SCHEMA listing_data TO claude_code_report",
            f"GRANT INSERT (title, done, merged, waiting, problems) ON {T} TO claude_code_report",
            f"GRANT USAGE ON SEQUENCE {SEQ} TO claude_code_report"}
got_mig = acl(mig)
check(f"права в миграции — ровно ожидаемые (лишние: {sorted(got_mig - want_mig)}, нет: {sorted(want_mig - got_mig)})",
      got_mig == want_mig)
check("нет ALTER DEFAULT PRIVILEGES и смены владельца", not re.search(r"(?i)ALTER\s+(DEFAULT|TABLE[^;]*OWNER)", mig_code))
kg = (ROOT / "migrations" / "2026-10-19_agent_cycle_reports_kabinet_grants.sql").read_text(encoding="utf-8")
want_kg = {f"GRANT USAGE ON SCHEMA listing_data TO {KAB}",
           f"GRANT SELECT ON {T} TO {KAB}",
           f"GRANT UPDATE (sent_at, send_error, attempts) ON {T} TO {KAB}"}
got_kg = acl(kg)
check(f"права задачи Кабинета — ровно ожидаемые (лишние: {sorted(got_kg - want_kg)}, нет: {sorted(want_kg - got_kg)})",
      got_kg == want_kg)
check("файл прав Кабинета помечен «применять вместе с PR Кабинета»", "НЕ ПРИМЕНЯТЬ ОТДЕЛЬНО" in kg)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
