# -*- coding: utf-8 -*-
"""
canon/build_snapshot.py — снимок канона «AI Design Conveyor» для Паспорта SKU.

Канон конвейера ведёт владелец процесса AI Design (Ярослав), и его решение
записано прямо: ИИ в каноне ничего не меняет и не добавляет. Поэтому здесь
только КОПИЯ байт в байт и манифест с SHA-256. Правка снимка руками ловится
`tests/test_canon_snapshot.py`; обновление — только новым прогоном этого
скрипта по новому архиву от владельца.

Что входит: нормативные документы контура Паспорта (02_SKU_Passport), узлы и
рёбра графа исполнения, которые к нему относятся (10_Runtime_Registry), реестр
требований площадок и всё, на что эти документы ссылаются. Что НЕ входит:

- архивы (`_archive`, `99_Archive`, `_rollback`) — runtime authority у них нет;
- более старые версии, у которых есть новая (`…_v1.0` при `…_v1.1`), КРОМЕ
  родителей, на которые новая версия ссылается по SHA (06F: v1.3 наследует
  v1.2, та — v1.1 «byte-addressed»; без родителя набор не исполним);
- 05–05C — историческая конфигурация FULL, Координатор v2.9 сам исключает её
  из рабочего маршрута (`verifier_mode=MVP`, только 06–06E);
- эскизы PNG (раскладка, а не контракт) и docx-копия ТЗ v1.0 — тот же
  документ лежит рядом в markdown;
- отчёты рецензента (`.audit-review`) и Amazon_Catalog_Triage — не нормы.

Запуск:  python canon/build_snapshot.py "<путь к AI Design Conveyor.zip>"
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.parse
import zipfile
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "ai_design_conveyor")
MANIFEST = os.path.join(HERE, "MANIFEST.json")
ROOT_NAME = "AI Design Conveyor"

# Узлы графа, которые исполняет Listing Suite в v1 (Паспорт без Image
# Collection). Их ссылки на схемы и инструкции входят в снимок.
PASSPORT_NODES = ("N010", "N020", "N030", "N040", "N050", "N060", "N070", "N250")

# Контракты движка графа: на них ссылается контракт исполнения словами, без
# markdown-ссылки, поэтому замыкание по ссылкам их не находит.
EXTRA = [
    "10_Runtime_Registry/AI_DESIGN_REWORK_BUDGET_AND_TERMINATION_CONTRACT.md",
    "10_Runtime_Registry/AI_DESIGN_REWORK_TERMINATION_POLICY.json",
    "10_Runtime_Registry/AI_DESIGN_DECISION_GRAPH_ANALYSIS.md",
    "10_Runtime_Registry/AI_DESIGN_DECISION_GRAPH_ANALYSIS.json",
    "10_Runtime_Registry/AI_DESIGN_GRAPH_ANALYSIS_POLICY.json",
    "10_Runtime_Registry/AI_DESIGN_RUN_STATE.md",
    # run_state.schema требует pin `governance_mapping` наравне с реестрами.
    "10_Runtime_Registry/AI_DESIGN_GOVERNANCE_ROUTE_MAPPING.json",
    "10_Runtime_Registry/AI_DESIGN_GOVERNANCE_ROUTE_MAPPING.md",
    "10_Runtime_Registry/AI_DESIGN_STATE_TRANSITION_WRITER_CONTRACT.md",
    "10_Runtime_Registry/AI_DESIGN_ROUTER_DECISION_CONTRACT.md",
    "10_Runtime_Registry/AI_DESIGN_EXECUTION_LEASE_AND_IDEMPOTENCY_CONTRACT.md",
    "10_Runtime_Registry/AI_DESIGN_APPROVED_PASSPORT_DELTA_AND_WRITEBACK_CONTRACT.md",
    "10_Runtime_Registry/AI_DESIGN_PASSPORT_AUDIT_RECEIPT_CONTRACT.md",
    "03_Content_TZ/05_Routing/marketplace_requirements_registry.json",
    # Движок графа (ядро Listing Suite, 15.10.2026): реестр поставщиков
    # фактов, контракты и схемы входа проверок, решения маршрутизатора,
    # бюджета и квитанции перехода, сценарии теневого прогона — и эталонные
    # скрипты, с которых движок перенесён (для сверки, не для запуска).
    "10_Runtime_Registry/AI_DESIGN_GATE_FACT_PROVIDER_REGISTRY.json",
    "10_Runtime_Registry/AI_DESIGN_GATE_FACT_RESOLVER_CONTRACT.md",
    "10_Runtime_Registry/AI_DESIGN_SHADOW_RUN_CONTRACT.md",
    "10_Runtime_Registry/AI_DESIGN_E2E_SHADOW_SCENARIOS.json",
    "10_Runtime_Registry/ai_design_gate_input.schema.json",
    "10_Runtime_Registry/ai_design_gate_evaluation.schema.json",
    "10_Runtime_Registry/ai_design_gate_evidence_bundle.schema.json",
    "10_Runtime_Registry/ai_design_gate_fact_provider_registry.schema.json",
    "10_Runtime_Registry/ai_design_gate_input_build_manifest.schema.json",
    "10_Runtime_Registry/ai_design_router_decision.schema.json",
    "10_Runtime_Registry/ai_design_termination_budget_request.schema.json",
    "10_Runtime_Registry/ai_design_termination_budget_receipt.schema.json",
    "10_Runtime_Registry/ai_design_rework_budget_ledger.schema.json",
    "10_Runtime_Registry/ai_design_transition_receipt.schema.json",
    "10_Runtime_Registry/ai_design_shadow_run_report.schema.json",
    "10_Runtime_Registry/New-AIDesignControlledRunState.ps1",
    "10_Runtime_Registry/New-AIDesignGateInputs.ps1",
    "10_Runtime_Registry/Invoke-AIDesignGateEvaluation.ps1",
    "10_Runtime_Registry/New-AIDesignRouterDecision.ps1",
    "10_Runtime_Registry/Resolve-AIDesignTerminationBudget.ps1",
    "10_Runtime_Registry/Invoke-AIDesignStateTransition.ps1",
    "10_Runtime_Registry/Invoke-AIDesignShadowRun.ps1",
]

SKIP_DIRS = ("_archive", "99_Archive", "_rollback", "__pycache__", ".audit-review",
             "Amazon_Catalog_Triage", "Передача программисту", "Listing_Suite_UI")
# Историческая конфигурация FULL — см. docstring.
SKIP_FILE = re.compile(r"^05[A-C]?_")
VERSION_RE = re.compile(r"^(.*?)[_.\- ]v(\d+(?:\.\d+)*)(\.[A-Za-z]+(?:\.json)?)$")
LINK_RE = re.compile(r"\]\(([^)]+?\.(?:md|json))\)")
PARENT_PATH_RE = re.compile(r"Path:\s*`([^`]+)`")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def header_version(path: str) -> str | None:
    """Версия из шапки документа: «Версия: 2.13», «Версія: 1.2», «version»."""
    try:
        if path.endswith(".json"):
            data = json.load(open(path, encoding="utf-8"))
            if isinstance(data, dict):
                for k in ("registry_version", "version", "schema_version", "catalog_version"):
                    if isinstance(data.get(k), (str, int, float)):
                        return str(data[k])
            return None
        if not path.endswith(".md"):
            return None
        head = open(path, encoding="utf-8", errors="ignore").read(1500)
    except (OSError, ValueError):
        return None
    m = re.search(r"(?:Версия|Версія|Version)(?: шаблона| набору)?\s*:\s*`?([0-9A-Za-z][0-9A-Za-z.\-]*)`?",
                  head)
    return m.group(1) if m else None


def build(zip_path: str) -> dict:
    tmp = tempfile.mkdtemp(prefix="canon-")
    try:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmp)
        root = os.path.join(tmp, ROOT_NAME)

        def live(rel: str) -> bool:
            parts = rel.split(os.sep)
            return not any(p in SKIP_DIRS for p in parts) and not SKIP_FILE.match(parts[-1])

        files = set()
        for r, _ds, fs in os.walk(root):
            for f in fs:
                rel = os.path.relpath(os.path.join(r, f), root)
                if live(rel) and not f.endswith(".png"):
                    files.add(rel)

        # Самая новая версия в группе «имя_vX»; старые — только как родитель.
        groups: dict = {}
        for rel in files:
            m = VERSION_RE.match(os.path.basename(rel))
            if m:
                key = (os.path.dirname(rel), m.group(1), m.group(3))
                groups.setdefault(key, []).append((tuple(int(x) for x in m.group(2).split(".")), rel))
        superseded = set()
        for vs in groups.values():
            vs.sort()
            superseded.update(rel for _v, rel in vs[:-1])

        seeds = [f for f in files if f.startswith("02_SKU_Passport" + os.sep)]
        nodes = json.load(open(os.path.join(root, "10_Runtime_Registry/AI_DESIGN_NODE_REGISTRY.json"),
                               encoding="utf-8"))["nodes"]
        seeds += ["10_Runtime_Registry/AI_DESIGN_NODE_REGISTRY.json",
                  "10_Runtime_Registry/AI_DESIGN_CORE_EDGE_REGISTRY.json",
                  "10_Runtime_Registry/AI_DESIGN_EXECUTION_GRAPH_CONTRACT.md"]
        for n in nodes:
            if n["node_id"][:4] in PASSPORT_NODES:
                for k in ("input_schema_refs", "output_schema_refs", "canonical_instruction_refs"):
                    for ref in n.get(k) or []:
                        seeds.append(os.path.normpath(ref.replace(ROOT_NAME + "/", "")))
        seeds += EXTRA

        selected: set = set()
        queue = [os.path.normpath(s) for s in seeds]
        while queue:
            rel = queue.pop()
            if rel in selected or rel not in files:
                continue
            if rel in superseded and not _is_parent(rel, selected, root):
                continue
            selected.add(rel)
            if rel.endswith(".md"):
                text = open(os.path.join(root, rel), encoding="utf-8", errors="ignore").read()
                targets = [urllib.parse.unquote(m) for m in LINK_RE.findall(text)]
                targets += PARENT_PATH_RE.findall(text)
                for t in targets:
                    p = os.path.normpath(os.path.join(os.path.dirname(rel), t))
                    if p in files and p not in selected:
                        queue.append(p)
        # Родители, найденные после потомка: второй проход.
        for rel in sorted(superseded):
            if rel not in selected and _is_parent(rel, selected, root):
                selected.add(rel)

        if os.path.isdir(OUT):
            shutil.rmtree(OUT)
        entries = []
        for rel in sorted(selected):
            src = os.path.join(root, rel)
            dst = os.path.join(OUT, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
            entries.append({"path": rel.replace(os.sep, "/"), "sha256": sha256(dst),
                            "bytes": os.path.getsize(dst), "version": header_version(dst)})
        manifest = {
            "snapshot_of": ROOT_NAME,
            "source_archive": os.path.basename(zip_path),
            "source_archive_sha256": sha256(zip_path),
            "built_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "rule": "byte copy, never edited; newest version only, except SHA-addressed parents",
            "files": entries,
        }
        with open(MANIFEST, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
            f.write("\n")
        return manifest
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _is_parent(rel: str, selected: set, root: str) -> bool:
    """Старая версия нужна, если выбранный документ ссылается на неё как на
    родителя по SHA (строка «Path: `…`» в блоке «Parent fixture artifact»)."""
    name = os.path.basename(rel)
    for s in selected:
        if not s.endswith(".md"):
            continue
        text = open(os.path.join(root, s), encoding="utf-8", errors="ignore").read()
        if any(os.path.basename(p) == name for p in PARENT_PATH_RE.findall(text)):
            return True
    return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    m = build(sys.argv[1])
    print(f"{len(m['files'])} файлов, {sum(e['bytes'] for e in m['files'])} байт → {OUT}")
