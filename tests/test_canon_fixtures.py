# -*- coding: utf-8 -*-
"""
tests/test_canon_fixtures.py — фикстуры Listing Suite из канона против его
JSON-схем.

Набор `02_SKU_Passport/fixtures/listing_suite` (v2.0) — исполнимый образец
контракта: каждому файлу манифест фикстур назначает схему и ожидаемый исход.
Здесь проверяется схемная половина — то, что схема пропускает валидное и
отвергает невалидное ДО создания запуска. Контрактная половина
(`contract_expected`: устаревший снимок, выход пути за выбранную папку,
расхождение счёта…) — это preflight, и он появится вместе с действиями на
этапах 3–5; для неё здесь запирается одно, но важное правило README набора:
`contract_reject_*` ОБЯЗАНЫ проходить схему. Переделать контрактный отказ в
схемный ради простоты адаптера — запрещённая подмена: тогда отказ случился
бы раньше проверки состояния, и проверка состояния осталась бы непроверенной.

И что проверка не пустая: валидный запрос без обязательного поля и запрос с
ролью, которой нет в закрытом словаре, обязаны отвергаться.

Запуск (pytest не нужен):  python tests/test_canon_fixtures.py
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys

import jsonschema

ROOT = pathlib.Path(__file__).resolve().parent.parent
PASSPORT = ROOT / "canon" / "ai_design_conveyor" / "02_SKU_Passport"
FIX = PASSPORT / "fixtures" / "listing_suite"

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


def load(p: pathlib.Path):
    return json.loads(p.read_text(encoding="utf-8"))


def verdict(schema: dict, doc) -> tuple[str, list[str]]:
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)
    errs = list(cls(schema, format_checker=cls.FORMAT_CHECKER).iter_errors(doc))
    return ("PASS" if not errs else "FAIL"), [e.message[:120] for e in errs[:2]]


manifest = load(FIX / "fixture_manifest.json")
cases = manifest["cases"]
check(f"набор фикстур v2.0 и в нём есть случаи ({len(cases)})",
      manifest.get("version") == "2.0" and len(cases) > 40)

listed = {c["file"] for c in cases}
on_disk = {p.name for p in FIX.glob("*.json") if p.name != "fixture_manifest.json"}
check(f"каждый файл фикстуры описан в манифесте и наоборот ({sorted(on_disk ^ listed)})", on_disk == listed)

wrong = []
for c in cases:
    got, why = verdict(load(PASSPORT / c["schema"]), load(FIX / c["file"]))
    if got != c["schema_expected"]:
        wrong.append(f"{c['file']}: ждали {c['schema_expected']}, вышло {got} {why}")
check(f"все {len(cases)} случаев дают ожидаемый схемный исход ({wrong[:3]})", not wrong)

contract = [c for c in cases if c["file"].startswith("contract_reject_")]
check(f"contract_reject_* проходят схему — отказ за preflight, не за схемой ({len(contract)})",
      contract and all(c["schema_expected"] == "PASS" for c in contract))
check("invalid_schema_* ожидают отказ схемы",
      all(c["schema_expected"] == "FAIL" for c in cases if c["file"].startswith("invalid_schema_")))

# --- мутации: схема действительно смотрит на запрос
req_schema = load(PASSPORT / "listing_suite_passport_action_request.schema.json")
good = load(FIX / "valid_delta_request.json")
no_key = copy.deepcopy(good)
no_key.pop("idempotency_key")
check("валидный запрос без idempotency_key отвергается", verdict(req_schema, no_key)[0] == "FAIL")
fake_role = copy.deepcopy(good)
fake_role["actor_authority"] = "SUPER_ADMIN"
check("роль вне закрытого словаря отвергается", verdict(req_schema, fake_role)[0] == "FAIL")
extra = copy.deepcopy(good)
extra["agent"] = "COLLECTOR"
check("лишнее поле (выбор агента из UI) отвергается: additionalProperties=false",
      verdict(req_schema, extra)[0] == "FAIL")

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
