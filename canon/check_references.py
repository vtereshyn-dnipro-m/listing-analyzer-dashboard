# -*- coding: utf-8 -*-
"""
canon/check_references.py — где документы канона ссылаются на версию или SHA
соседа, которые расходятся с самим файлом в снимке.

Канон мы не правим (решение владельца процесса), поэтому расхождение не
чинится, а называется: отчёт `REFERENCE_DRIFT.md` уходит владельцу одним
списком. По правилу договорённости 07.10 код берёт ФАЙЛ, а не версию из
ссылки. Отчёт — производный от снимка; `tests/test_canon_snapshot.py`
требует, чтобы он совпадал с перегенерированным, иначе он устареет молча.

Ловится три формы ссылки:
- «`имя.md` v2.10» и «[текст](имя.md) v2.10» — версия рядом со ссылкой;
- строка таблицы «| `имя.md` | 2.10 | `SHA` |» — снимок зависимостей;
- «Path: `имя` … SHA-256: `…`» — родитель по SHA.

Запуск:  python canon/check_references.py
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, "ai_design_conveyor")
REPORT = os.path.join(HERE, "REFERENCE_DRIFT.md")

NAME = r"[\w.\-+А-Яа-яЁёІіЇїЄєҐґ]+\.(?:md|json)"
NEAR_VERSION = re.compile(
    r"(?:`(" + NAME + r")`|\[[^\]]*\]\(([^)]+\.(?:md|json))\))"   # имя в кавычках или ссылка
    r"[^\n`|]{0,40}?\bv\s?(\d+(?:\.\d+)*)\b")                       # …v2.10 рядом
TABLE_ROW = re.compile(r"^\|\s*`(" + NAME + r")`\s*\|\s*`?v?(\d+(?:\.\d+)*)`?\s*\|\s*`([0-9A-Fa-f]{64})`")
PARENT = re.compile(r"Path:\s*`([^`]+)`.*?SHA-256:\s*`([0-9A-Fa-f]{64})`", re.S)


def load_manifest() -> dict:
    with open(os.path.join(HERE, "MANIFEST.json"), encoding="utf-8") as f:
        return {os.path.basename(e["path"]): e for e in json.load(f)["files"]}


def norm_version(v: str | None) -> str | None:
    if not v:
        return None
    m = re.search(r"(\d+(?:\.\d+)*)$", v)
    return m.group(1) if m else v


def scan() -> list[dict]:
    files = load_manifest()
    found: list[dict] = []
    seen = set()
    for name, entry in sorted(files.items()):
        if not name.endswith(".md"):
            continue
        text = open(os.path.join(SNAP, entry["path"]), encoding="utf-8", errors="ignore").read()
        for m in NEAR_VERSION.finditer(text):
            target = os.path.basename(urllib.parse.unquote(m.group(1) or m.group(2) or ""))
            _add(found, seen, entry["path"], target, files, m.group(3), None)
        for line in text.splitlines():
            m = TABLE_ROW.match(line.strip())
            if m:
                _add(found, seen, entry["path"], m.group(1), files, m.group(2), m.group(3))
        for m in PARENT.finditer(text):
            _add(found, seen, entry["path"], os.path.basename(m.group(1)), files, None, m.group(2))
    return found


def _add(found, seen, source, target, files, version, sha):
    t = files.get(target)
    if not t or target == os.path.basename(source):
        return
    actual_v = norm_version(t.get("version"))
    v_bad = version is not None and actual_v is not None and version != actual_v
    s_bad = sha is not None and sha.lower() != t["sha256"]
    if not (v_bad or s_bad):
        return
    key = (source, target, version, sha)
    if key in seen:
        return
    seen.add(key)
    found.append({"source": source, "target": t["path"], "cited_version": version,
                  "actual_version": actual_v, "sha_mismatch": s_bad})


def registry_gaps() -> list[tuple[str, str, int, int]]:
    """Поля, которые контракт графа объявляет обязательными для узла и ребра
    (блоки yaml «Обязательный контракт Node/Edge Registry»), против реестров.
    Движок графа читает именно реестр, поэтому пропуск здесь — это решение,
    которое движку принять не из чего."""
    reg = os.path.join(SNAP, "10_Runtime_Registry")
    contract = open(os.path.join(reg, "AI_DESIGN_EXECUTION_GRAPH_CONTRACT.md"), encoding="utf-8").read()
    out = []
    for title, file, key in (("Node Registry", "AI_DESIGN_NODE_REGISTRY.json", "nodes"),
                             ("Edge Registry", "AI_DESIGN_CORE_EDGE_REGISTRY.json", "edges")):
        block = contract.split("## Обязательный контракт " + title)[1].split("```")[1]
        required = [ln.split(":")[0].strip() for ln in block.splitlines() if ":" in ln]
        items = json.load(open(os.path.join(reg, file), encoding="utf-8"))[key]
        for field in required:
            missing = sum(1 for it in items if field not in it)
            if missing:
                out.append((file, field, missing, len(items)))
    return out


def run_state_gaps() -> list[str]:
    """Схема состояния запуска против контракта графа: что в ней не сходится
    с тем, где и как исполняется движок Listing Suite."""
    reg = os.path.join(SNAP, "10_Runtime_Registry")
    contract = open(os.path.join(reg, "AI_DESIGN_EXECUTION_GRAPH_CONTRACT.md"), encoding="utf-8").read()
    schema = json.load(open(os.path.join(reg, "ai_design_run_state.schema.json"), encoding="utf-8"))
    out = []
    section = contract.split("## Стани Run State")[1].split("\n## ")[0]
    declared = re.findall(r"^- `([A-Z_]+)`", section, re.M)
    enum = schema["properties"]["lifecycle_state"]["enum"]
    absent = [s for s in declared if s not in enum]
    if absent:
        out.append("`ai_design_run_state.schema.json` → `lifecycle_state` не допускает состояний, "
                   "которые контракт графа («Стани Run State») объявляет: "
                   + ", ".join(f"`{s}`" for s in absent) + ".")
    root_pattern = schema["$defs"]["productIdentity"]["properties"]["product_root"].get("pattern", "")
    if re.match(r"\^\[A-Za-z\]:", root_pattern):
        out.append("`ai_design_run_state.schema.json` → `product_root` требует путь с буквой диска Windows "
                   f"(`{root_pattern}`); путь тома Unity Catalog (`/Volumes/…`) под него не подходит.")
    return out


GUARD_ATOM = re.compile(
    r"^[a-z][a-z0-9_]*\s*(?:==\s*(?:true|false|-?[0-9]+(?:\.[0-9]+)?|[A-Z][A-Z0-9_]*)"
    r"|>\s*-?[0-9]+(?:\.[0-9]+)?|\s+IN\s+\[[A-Z0-9_, ]+\]|\s+IN\s+[a-z][a-z0-9_]*)$")


def engine_gaps() -> list[str]:
    """Эталонные скрипты движка против своих контрактов и друг друга —
    то, что видно по файлам, без запуска."""
    reg = os.path.join(SNAP, "10_Runtime_Registry")
    rd = lambda n: open(os.path.join(reg, n), encoding="utf-8").read()  # noqa: E731
    out = []
    contract_v = re.search(r"Версия:\s*`([0-9.]+)`", rd("AI_DESIGN_EXECUTION_GRAPH_CONTRACT.md")).group(1)
    want = f"AI-DESIGN-GRAPH-{contract_v}"
    pinned = {"AI_DESIGN_GATE_FACT_PROVIDER_REGISTRY.json": json.loads(rd("AI_DESIGN_GATE_FACT_PROVIDER_REGISTRY.json"))["graph_version"],
              "AI_DESIGN_E2E_SHADOW_SCENARIOS.json": json.loads(rd("AI_DESIGN_E2E_SHADOW_SCENARIOS.json"))["graph_version"]}
    # Скрипт присваивает версию дважды (1.8, затем 2.5) — действует последнее.
    m = re.findall(r"graph_version='(AI-DESIGN-GRAPH-[0-9.]+)'", rd("New-AIDesignControlledRunState.ps1"))
    if m:
        pinned["New-AIDesignControlledRunState.ps1"] = m[-1]
    off = {k: v for k, v in pinned.items() if v != want}
    if off:
        out.append(f"Контракт графа — версия `{contract_v}`, а версия графа `{want}` не совпадает в: "
                   + ", ".join(f"`{k}` (`{v}`)" for k, v in off.items())
                   + ". Факт `graph_version_compatible` сравнивает с реестром поставщиков и поэтому "
                     "ложен для запуска, закреплённого по контракту, — ребро E310 закрыто.")
    edges = json.loads(rd("AI_DESIGN_CORE_EDGE_REGISTRY.json"))["edges"]
    bad = [(e["edge_id"], a.strip()) for e in edges for a in re.split(r"\s+AND\s+", e["guard_expression"])
           if not GUARD_ATOM.match(a.strip())]
    if bad:
        out.append("Условия вне грамматики `Invoke-AIDesignGateEvaluation.ps1` (эталон бросает "
                   "исключение, ребро не вычисляется): " + "; ".join(f"`{e}`: `{a}`" for e, a in bad) + ".")
    providers = json.loads(rd("AI_DESIGN_GATE_FACT_PROVIDER_REGISTRY.json"))["providers"]
    derived = [p["fact_id"] for p in providers if p["provider_kind"] == "RUN_STATE_DERIVATION"]
    closed = set(re.findall(r"'([a-z_]+)'\{", rd("New-AIDesignGateInputs.ps1")))
    used = {f for e in edges for f in re.findall(r"\b([a-z][a-z0-9_]*)\b", e["guard_expression"])}
    open_ = sorted(f for f in derived if f not in closed and f in used)
    out.append(f"Фактов вида `RUN_STATE_DERIVATION` в реестре поставщиков {len(derived)}, закрытых функций "
               f"в `New-AIDesignGateInputs.ps1` — {len(closed & set(derived))}. Без функции и потому всегда "
               f"UNRESOLVED ({len(open_)}): " + ", ".join(f"`{f}`" for f in open_) + ".")
    writer = rd("Invoke-AIDesignStateTransition.ps1")
    if "Resolve-AIDesignTerminationBudget" not in writer:
        out.append("`Invoke-AIDesignStateTransition.ps1` не вызывает `Resolve-AIDesignTerminationBudget.ps1`, "
                   "хотя `AI_DESIGN_STATE_TRANSITION_WRITER_CONTRACT.md` (правила 13–16) требует квитанцию "
                   "бюджета до записи. Обратные рёбра в эталоне ничем не ограничены.")
    if re.search(r"available_edge_ids\s*=.*-notin @\(\$next\.edge_state\.applied_edge_ids\)", writer):
        out.append("`Invoke-AIDesignStateTransition.ps1` исключает применённые рёбра из доступных, а правило 8 "
                   "контракта записи делает доступными все исходящие рёбра активных узлов. По эталону ребро "
                   "переделки срабатывает один раз за запуск, и бюджет «3 переделки на ассет» недостижим.")
    classes = sorted({e["edge_class"] for e in edges})
    events = json.loads(rd("ai_design_termination_budget_request.schema.json"))["properties"]["event_class"]["enum"]
    if not any("edge_class" in open(os.path.join(dp, f), encoding="utf-8", errors="ignore").read()
               and "event_class" in open(os.path.join(dp, f), encoding="utf-8", errors="ignore").read()
               for dp, _, fs in os.walk(SNAP) for f in fs if f.endswith((".md", ".json"))):
        out.append("Сопоставление класса ребра (" + ", ".join(f"`{c}`" for c in classes) + ") классу события "
                   "бюджета (" + ", ".join(f"`{c}`" for c in events) + ") в каноне не задано.")
    schema = json.loads(rd("ai_design_run_state.schema.json"))
    if "pinned_product_truth" in schema["required"] and \
            "sha256" in schema["$defs"]["pinnedArtifact"]["required"]:
        out.append("`ai_design_run_state.schema.json` требует `pinned_product_truth` с путём, версией и SHA "
                   "существующего Паспорта — запуск первичного создания (Паспорта ещё нет) схемой не представим.")
    return out


def render(rows: list[dict], gaps: list[tuple[str, str, int, int]], state: list[str],
           engine: list[str] = ()) -> str:
    out = ["# Расхождения в каноне AI Design Conveyor", "",
           "Производный отчёт `canon/check_references.py` по снимку `canon/MANIFEST.json`.",
           "Канон не правится; код берёт ФАЙЛ из снимка, а не версию из ссылки.", "",
           "## 1. Ссылки на версию или SHA соседа", "",
           f"Всего: {len(rows)}.", "",
           "| Где ссылка | На что | Указано | В файле | SHA |", "|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| `{r['source']}` | `{os.path.basename(r['target'])}` | "
                   f"{r['cited_version'] or '—'} | {r['actual_version'] or '—'} | "
                   f"{'не совпадает' if r['sha_mismatch'] else '—'} |")
    out += ["", "## 2. Реестры графа против `AI_DESIGN_EXECUTION_GRAPH_CONTRACT.md`", "",
            "Поле объявлено в контракте обязательным, в реестре его нет.", ""]
    if gaps:
        out += ["| Реестр | Поле | Нет у | Всего |", "|---|---|---|---|"]
        out += [f"| `{f}` | `{fld}` | {m} | {n} |" for f, fld, m, n in gaps]
    else:
        out.append("Расхождений нет.")
    out += ["", "## 3. Схема состояния запуска", ""]
    out += [f"- {s}" for s in state] if state else ["Расхождений нет."]
    out += ["", "## 4. Эталонные скрипты движка против контрактов", "",
            "Движок Listing Suite (`services/graph_*.py`) следует контракту там, где скрипт с ним расходится.", ""]
    out += [f"- {s}" for s in engine] if engine else ["Расхождений нет."]
    return "\n".join(out) + "\n"


def report_text() -> str:
    return render(scan(), registry_gaps(), run_state_gaps(), engine_gaps())


if __name__ == "__main__":
    text = report_text()
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"→ {REPORT}")
