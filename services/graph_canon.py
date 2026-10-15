# -*- coding: utf-8 -*-
"""
services/graph_canon.py — реестры графа AI Design из снимка канона.

Ядро движка (реестры → проверки рёбер → маршрутизатор → бюджет → запись
перехода) — перенос эталонных скриптов канона из
`canon/ai_design_conveyor/10_Runtime_Registry/*.ps1` на Python. Скрипты лежат
в снимке рядом с контрактами: сверять перенос надо с ними, а не с памятью.

Этот модуль только читает. Он отвечает на три вопроса:

- **Какие файлы канона действуют.** Каждый файл сверяется с
  `canon/MANIFEST.json` по SHA перед разбором. Правка байта в снимке — отказ
  загрузки, а не тихо другой граф: движок, который идёт по исправленному
  реестру, выглядит работающим и ведёт не туда.
- **Как хэшируется состояние.** Эталон хэширует ФАЙЛ, который написал
  PowerShell. У нас состояние живёт в `ai_runs.run_state` (jsonb), файла нет,
  поэтому хэш берётся от канонической сериализации: ключи по алфавиту, без
  пробелов, UTF-8 без экранирования. jsonb ключи переставляет — значит
  порядок из файла всё равно не сохранился бы, и хэш «как в файле» был бы
  невоспроизводим после чтения из базы.
- **Валидно ли по схеме канона.** Схемы — из снимка, без правок, кроме
  одной оговорённой: `product_root` в схеме run_state требует путь диска
  Windows (`^[A-Za-z]:\\.+`). Наш корень — том UC, где он будет, ещё не
  решено; это расхождение названо в `canon/REFERENCE_DRIFT.md` и ушло
  владельцу. Ослабление стоит здесь одной строкой и проверяется тестом.

Провайдеров модели и файлового хранилища здесь нет и быть не должно.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANON = ROOT / "canon"
SNAPSHOT = CANON / "ai_design_conveyor"
REG = "10_Runtime_Registry/"

NODE_REGISTRY = REG + "AI_DESIGN_NODE_REGISTRY.json"
EDGE_REGISTRY = REG + "AI_DESIGN_CORE_EDGE_REGISTRY.json"
PROVIDER_REGISTRY = REG + "AI_DESIGN_GATE_FACT_PROVIDER_REGISTRY.json"
TERMINATION_POLICY = REG + "AI_DESIGN_REWORK_TERMINATION_POLICY.json"
GRAPH_CONTRACT = REG + "AI_DESIGN_EXECUTION_GRAPH_CONTRACT.md"
GOVERNANCE_MAPPING = REG + "AI_DESIGN_GOVERNANCE_ROUTE_MAPPING.json"

SCHEMAS = {
    "run_state": REG + "ai_design_run_state.schema.json",
    "gate_input": REG + "ai_design_gate_input.schema.json",
    "gate_evaluation": REG + "ai_design_gate_evaluation.schema.json",
    "evidence_bundle": REG + "ai_design_gate_evidence_bundle.schema.json",
    "router_decision": REG + "ai_design_router_decision.schema.json",
    "budget_request": REG + "ai_design_termination_budget_request.schema.json",
    "budget_receipt": REG + "ai_design_termination_budget_receipt.schema.json",
    "ledger": REG + "ai_design_rework_budget_ledger.schema.json",
    "transition_receipt": REG + "ai_design_transition_receipt.schema.json",
}

# Узел, на который ведёт ребро с платным вызовом провайдера. Эталон
# (New-AIDesignGateInputs, Invoke-AIDesignGateEvaluation) держит его именем:
# для такого ребра полномочие обязано быть PASS, NOT_REQUIRED запрещено.
PROVIDER_EXECUTION_NODE = "N190_AI_CREATOR_PROVIDER_EXECUTION"


class CanonError(RuntimeError):
    """Снимок канона не совпал с манифестом или не читается."""


def canonical_bytes(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def sha256_json(obj) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def manifest() -> dict:
    data = json.loads((CANON / "MANIFEST.json").read_text(encoding="utf-8"))
    return {f["path"]: f["sha256"] for f in data["files"]}


def read_bytes(rel: str) -> tuple[bytes, str]:
    """Файл снимка и его SHA — только если он совпал с манифестом."""
    want = manifest().get(rel)
    if want is None:
        raise CanonError(f"{rel}: нет в MANIFEST.json — файл вне снимка канона")
    path = SNAPSHOT / rel
    try:
        raw = path.read_bytes()
    except OSError as e:
        raise CanonError(f"{rel}: не читается — {e}") from e
    got = hashlib.sha256(raw).hexdigest()
    if got != want:
        raise CanonError(f"{rel}: SHA {got[:12]}… не совпал с манифестом {want[:12]}… — снимок правили")
    return raw, got


def read_json(rel: str) -> tuple[dict, str]:
    raw, sha = read_bytes(rel)
    return json.loads(raw.decode("utf-8")), sha


def header_version(text: str) -> str:
    m = re.search(r"(?:Версия|Версія|Version)\s*:\s*`?([0-9][0-9A-Za-z.\-]*)`?", text)
    if not m:
        raise CanonError("в контракте графа не найдена строка версии")
    return m.group(1)


@dataclass(frozen=True)
class Pin:
    path: str
    version: str
    sha256: str

    def as_dict(self) -> dict:
        return {"path": "AI Design Conveyor/" + self.path, "version": self.version, "sha256": self.sha256}


@dataclass
class Graph:
    """Действующий граф: реестры, политика бюджета и их SHA."""
    nodes: dict
    edges: dict
    providers: dict
    policy: dict
    graph_version: str
    provider_graph_version: str
    pins: dict = field(default_factory=dict)

    def outgoing(self, node_ids) -> list[dict]:
        active = set(node_ids)
        return sorted((e for e in self.edges.values() if e["source_node_id"] in active),
                      key=lambda e: e["edge_id"])

    def pinned_graph(self) -> dict:
        p = self.pins
        return {"graph_version": self.graph_version,
                "graph_contract": p["graph_contract"].as_dict(),
                "node_registry": p["node_registry"].as_dict(),
                "edge_registry": p["edge_registry"].as_dict(),
                "governance_mapping": p["governance_mapping"].as_dict()}

    @property
    def sha256(self) -> str:
        """Отпечаток графа целиком — для `ai_runs.graph_sha256`."""
        return sha256_json({k: v.sha256 for k, v in sorted(self.pins.items())})


@lru_cache(maxsize=1)
def load_graph() -> Graph:
    nodes, node_sha = read_json(NODE_REGISTRY)
    edges, edge_sha = read_json(EDGE_REGISTRY)
    providers, prov_sha = read_json(PROVIDER_REGISTRY)
    policy, pol_sha = read_json(TERMINATION_POLICY)
    contract_raw, contract_sha = read_bytes(GRAPH_CONTRACT)
    gov, gov_sha = read_json(GOVERNANCE_MAPPING)
    contract_version = header_version(contract_raw.decode("utf-8"))
    edge_map = {e["edge_id"]: e for e in edges["edges"]}
    node_map = {n["node_id"]: n for n in nodes["nodes"]}
    # Ребро на незарегистрированный узел — не граф, а опечатка; не грузим.
    for e in edge_map.values():
        for k in ("source_node_id", "target_node_id"):
            if e[k] not in node_map:
                raise CanonError(f"{e['edge_id']}: {k} {e[k]} нет в реестре узлов")
    pins = {
        "graph_contract": Pin(GRAPH_CONTRACT, contract_version, contract_sha),
        "node_registry": Pin(NODE_REGISTRY, nodes["registry_version"], node_sha),
        "edge_registry": Pin(EDGE_REGISTRY, edges["registry_version"], edge_sha),
        "governance_mapping": Pin(GOVERNANCE_MAPPING, gov["mapping_version"], gov_sha),
        "provider_registry": Pin(PROVIDER_REGISTRY, providers["registry_id"], prov_sha),
        "termination_policy": Pin(TERMINATION_POLICY, policy["policy_version"], pol_sha),
    }
    return Graph(nodes=node_map, edges=edge_map,
                 providers={p["fact_id"]: p for p in providers["providers"]},
                 policy=policy,
                 # Версия — из ФАЙЛА контракта, а не из ссылок: эталон
                 # (New-AIDesignControlledRunState) зашивает 2.5 при файле 2.6.
                 graph_version=f"AI-DESIGN-GRAPH-{contract_version}",
                 provider_graph_version=providers["graph_version"],
                 pins=pins)


# ---------------------------------------------------------------- схемы ---

@lru_cache(maxsize=1)
def _schema_registry():
    from referencing import Registry, Resource
    resources = []
    for rel in SCHEMAS.values():
        doc, _ = read_json(rel)
        res = Resource.from_contents(doc)
        name = rel.rsplit("/", 1)[1]
        resources.append((name, res))
        if "$id" in doc:
            resources.append((doc["$id"], res))
    return Registry().with_resources(resources)


def _relaxed_run_state(doc: dict) -> dict:
    """Единственная оговорённая поправка схемы: путь диска Windows в
    `product_root` (см. докстринг модуля). Остальное — как в каноне."""
    doc = copy.deepcopy(doc)
    doc["$defs"]["productIdentity"]["properties"]["product_root"].pop("pattern", None)
    return doc


@lru_cache(maxsize=None)
def _validator(kind: str):
    from jsonschema import Draft202012Validator
    doc, _ = read_json(SCHEMAS[kind])
    if kind == "run_state":
        doc = _relaxed_run_state(doc)
    return Draft202012Validator(doc, registry=_schema_registry(),
                                format_checker=Draft202012Validator.FORMAT_CHECKER)


def schema_errors(kind: str, obj) -> list[str]:
    return [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
            for e in _validator(kind).iter_errors(obj)]


def require_valid(kind: str, obj) -> None:
    errs = schema_errors(kind, obj)
    if errs:
        raise SchemaViolation(kind, errs)


class SchemaViolation(ValueError):
    def __init__(self, kind: str, errors: list[str]):
        self.kind, self.errors = kind, errors
        super().__init__(f"{kind}: " + "; ".join(errors[:5]))
