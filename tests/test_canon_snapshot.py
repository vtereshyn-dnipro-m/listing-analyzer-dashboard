# -*- coding: utf-8 -*-
"""
tests/test_canon_snapshot.py — снимок канона AI Design Conveyor не правится.

Решение владельца процесса AI Design: ИИ в каноне конвейера ничего не меняет
и не добавляет. Снимок в canon/ai_design_conveyor — копия байт в байт, и
правка, «пока никто не видит», выглядела бы так же, как оригинал. Поэтому
проверяется не наличие файлов, а их тождество манифесту:

1. каждый файл манифеста есть и его SHA-256 совпадает — правка ловится;
2. в снимке нет файлов вне манифеста — добавление ловится;
3. из нескольких версий одного документа в снимке только последняя, кроме
   родителей, на которых новая стоит по SHA (06F v1.3 ← v1.2 ← …);
4. ни одного пути из архивов (`_archive`, `99_Archive`, `_rollback`) и ни
   одного документа конфигурации FULL (05–05C);
5. всё, на что ссылаются узлы графа Паспорта (N010–N070, N250), есть в
   снимке — движку нечем было бы исполнять узел без своей инструкции;
6. отчёт о расхождениях REFERENCE_DRIFT.md совпадает с перегенерированным:
   производный отчёт, который отстал от снимка, хуже его отсутствия.

И что проверка не пустая: правка одного байта и лишний файл во временной
копии снимка обязаны ловиться.

Запуск (pytest не нужен):  python tests/test_canon_snapshot.py
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


CANON = ROOT / "canon"
SNAP = CANON / "ai_design_conveyor"
MANIFEST = json.loads((CANON / "MANIFEST.json").read_text(encoding="utf-8"))


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def problems(snap: pathlib.Path) -> list[str]:
    """Расхождения снимка с манифестом: то, что ловит правку и добавление."""
    out = []
    listed = {e["path"]: e for e in MANIFEST["files"]}
    for rel, e in listed.items():
        p = snap / rel
        if not p.is_file():
            out.append(f"нет файла {rel}")
        elif sha(p) != e["sha256"]:
            out.append(f"SHA не совпадает: {rel}")
    for p in snap.rglob("*"):
        if p.is_file():
            rel = p.relative_to(snap).as_posix()
            if rel not in listed:
                out.append(f"файл вне манифеста: {rel}")
    return out


# --- 1–2. тождество манифесту
found = problems(SNAP)
check(f"снимок тождественен манифесту ({len(MANIFEST['files'])} файлов; {found[:3]})", not found)

# --- мутации: правка байта и лишний файл ловятся
tmp = pathlib.Path(tempfile.mkdtemp(prefix="canon-test-"))
try:
    copy = tmp / "snap"
    shutil.copytree(SNAP, copy)
    target = copy / "02_SKU_Passport" / "00A_Контракт_передач_Паспорта_SKU.md"
    data = bytearray(target.read_bytes())
    data[100] ^= 1
    target.write_bytes(bytes(data))
    (copy / "02_SKU_Passport" / "свой_контракт.md").write_text("правило от ИИ", encoding="utf-8")
    got = problems(copy)
    check("правка одного байта в 00A ловится", any("SHA не совпадает" in g and "00A_" in g for g in got))
    check("добавленный в снимок файл ловится", any("свой_контракт.md" in g for g in got))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# --- 3. только последняя версия, кроме SHA-родителей
paths = [e["path"] for e in MANIFEST["files"]]
VERSION_RE = re.compile(r"^(.*?)[_.\- ]v(\d+(?:\.\d+)*)(\.[A-Za-z]+(?:\.json)?)$")
groups: dict = {}
for p in paths:
    m = VERSION_RE.match(os.path.basename(p))
    if m:
        groups.setdefault((os.path.dirname(p), m.group(1), m.group(3)), []).append(
            (tuple(int(x) for x in m.group(2).split(".")), p))
parents = set()
for p in paths:
    if p.endswith(".md"):
        text = (SNAP / p).read_text(encoding="utf-8", errors="ignore")
        parents.update(os.path.basename(x) for x in re.findall(r"Path:\s*`([^`]+)`", text))
stale = [p for vs in groups.values() for _v, p in sorted(vs)[:-1] if os.path.basename(p) not in parents]
check(f"старых версий без SHA-ссылки потомка нет ({stale})", not stale)
check("цепочка 06F: v1.3 и её родители v1.2, v1.1 на месте",
      {"02_SKU_Passport/06F_MVP_Negative_Fixtures_v1.3.md", "02_SKU_Passport/06F_MVP_Negative_Fixtures_v1.2.md",
       "02_SKU_Passport/06F_MVP_Negative_Fixtures_v1.1.md"} <= set(paths))

# --- 4. ни архивов, ни FULL
bad = [p for p in paths if any(x in p.split("/") for x in ("_archive", "99_Archive", "_rollback"))]
check(f"путей из архивов нет ({bad})", not bad)
full = [p for p in paths if re.match(r"^05[A-C]?_", os.path.basename(p))]
check(f"конфигурации FULL (05–05C) нет ({full})", not full)

# --- 5. ссылки узлов Паспорта разрешаются
nodes = json.loads((SNAP / "10_Runtime_Registry" / "AI_DESIGN_NODE_REGISTRY.json").read_text(encoding="utf-8"))
missing = []
for n in nodes["nodes"]:
    if n["node_id"][:4] in ("N010", "N020", "N030", "N040", "N050", "N060", "N070", "N250"):
        for k in ("input_schema_refs", "output_schema_refs", "canonical_instruction_refs"):
            for ref in n.get(k) or []:
                rel = ref.replace("AI Design Conveyor/", "")
                if not (SNAP / rel).is_file():
                    missing.append(f"{n['node_id']}: {rel}")
check(f"всё, на что ссылаются узлы Паспорта, есть в снимке ({missing[:3]})", not missing)

# --- 6. отчёт о расхождениях не отстал от снимка
import canon.check_references as cr  # noqa: E402

fresh = cr.report_text()
stored = (CANON / "REFERENCE_DRIFT.md").read_text(encoding="utf-8")
check("REFERENCE_DRIFT.md совпадает с перегенерированным (python canon/check_references.py)", fresh == stored)
check("отчёт называет известное расхождение: Integration Contract цитируется как v1.1 при файле v1.2",
      "`Listing_Suite_Integration_Contract.md` | 1.1 | 1.2" in fresh)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
