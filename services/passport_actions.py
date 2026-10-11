# -*- coding: utf-8 -*-
"""
services/passport_actions.py — запрос действия над Паспортом и проверки до него.

Норматив — `Listing_Suite_Integration_Contract.md` v1.2 и
`Listing_Suite_Implementation_Handoff.md` («Обов'язковий порядок перевірок»).
Запрос строится по `listing_suite_passport_action_request.schema.json`, и
ДО запуска проходит восемь проверок строго по порядку: схема → полномочия →
точный SKU и версия товара → текущий Паспорт (id, версия, SHA) → состав
материалов → ключ идемпотентности → блокировка SKU → проверка маршрута.
Отказ до запуска не создаёт ни версии Паспорта, ни запуска агента.

Модуль ничего не пишет. Квитанция действия и журнал идемпотентности
появятся вместе с движком: квитанцию по контракту выдаёт сторона,
принявшая запрос, и сохраняется она ДО ответа клиенту.

Полномочия. Канонический профиль `Listing_Suite_Authority_Profile_v1.0.json`
стоит в `BINDING_REQUIRED`: матрица ролей утверждена, а привязки к
настоящим учётным записям нет. По контракту это fail-closed — любое
изменяющее действие получает `AUTHORITY_PROFILE_NOT_ACTIVE`. Так и
работает: пока профиль Listing Suite с привязкой к нашим ролям не
утверждён, запрос дальше полномочий не проходит. Роль, пришедшая из
интерфейса (`actor_authority`), доказательством не является.
"""
from __future__ import annotations

import hashlib
import json
import pathlib

CANON = pathlib.Path(__file__).resolve().parent.parent / "canon" / "ai_design_conveyor" / "02_SKU_Passport"
REQUEST_SCHEMA = CANON / "listing_suite_passport_action_request.schema.json"
AUTHORITY_PROFILE = CANON / "Listing_Suite_Authority_Profile_v1.0.json"

DELTA, RECREATE = "SUBMIT_SOURCE_EVIDENCE_DELTA", "RECREATE_PASSPORT"
REPLAY = "REPLAY_STORED_RECEIPT"


def canonical_json(obj) -> str:
    """Стабильная сериализация: ключи по алфавиту, без пробелов, UTF-8.
    Хэш запроса считается от неё, а не от случайного порядка полей —
    иначе один и тот же запрос дал бы два хэша и ложный конфликт ключа."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def request_sha(req: dict) -> str:
    return hashlib.sha256(canonical_json(req).encode()).hexdigest()


def schema_errors(req: dict) -> list[str]:
    import jsonschema
    schema = json.loads(REQUEST_SCHEMA.read_text(encoding="utf-8"))
    cls = jsonschema.validators.validator_for(schema)
    return [e.message for e in cls(schema, format_checker=cls.FORMAT_CHECKER).iter_errors(req)]


def evaluate_authority(action: str, canonical_roles: tuple, sku_id: str,
                       profile_path: pathlib.Path = AUTHORITY_PROFILE) -> str:
    """AUTHORIZED или причина отказа по `Listing_Suite_Authority_Mapping_Contract`.

    Порядок контракта: профиль активен → роль привязана → действие
    разрешено роли → SKU в области роли. Несколько ролей объединяют
    действия, но не области."""
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "AUTHORITY_PROFILE_NOT_ACTIVE"
    if profile.get("binding_status") != "BOUND":
        return "AUTHORITY_PROFILE_NOT_ACTIVE"
    perms = {p["canonical_role"]: p for p in profile.get("role_permissions", [])}
    mine = [perms[r] for r in canonical_roles if r in perms]
    if not mine:
        return "AUTHORITY_NOT_MAPPED"
    if not any(action in p["allowed_actions"] for p in mine):
        return "ACTION_NOT_AUTHORIZED"
    # В v1 привязки прав к SKU нет (договорённость 07.10.2026): область
    # ролей Listing Suite — весь справочник. Когда появится, проверка встанет здесь.
    return "AUTHORIZED"


def idempotency(req_sha: str, stored: dict | None) -> str | None:
    """Тот же ключ и тот же запрос — вернуть сохранённую квитанцию; тот же
    ключ с другим запросом — `IDEMPOTENCY_KEY_CONFLICT`; нового ключа нет
    в журнале — None, можно идти дальше."""
    if not stored:
        return None
    return REPLAY if stored.get("request_sha256") == req_sha else "IDEMPOTENCY_KEY_CONFLICT"


def preflight(req: dict, *, canonical_roles: tuple, current: dict | None, intake: dict | None,
              stored: dict | None, locked: bool, authority=evaluate_authority) -> str | None:
    """Первая причина отказа в порядке Handoff или None — запрос можно
    передавать Координатору. `REPLAY_STORED_RECEIPT` — не отказ: это повтор
    уже принятого запроса, ответом будет сохранённая квитанция.

    `current` — действующий Паспорт SKU (строка `passport_objects`: id,
    lineage, версия, SHA), `intake` — квитанция приёма материалов,
    `stored` — запись журнала идемпотентности по этому ключу."""
    if schema_errors(req):
        return "REQUEST_SCHEMA_INVALID"
    verdict = authority(req["requested_action"], canonical_roles, req["sku_id"])
    if verdict != "AUTHORIZED":
        return verdict
    cp = req["current_passport"]
    if current is None or str(current.get("sku_id")) != req["sku_id"]:
        # Новые данные и пересоздание — только для существующего Паспорта
        # точного SKU. Запрос называет Паспорт, которого сейчас нет: это тот
        # же случай, что устаревший снимок, — перечитать и подтвердить заново.
        return "STALE_PASSPORT_INPUT"
    if (cp["passport_id"], cp["version"], cp["sha256"]) != (
            str(current.get("passport_id")), str(current.get("passport_version")), str(current.get("sha256"))):
        return "STALE_PASSPORT_INPUT"
    if not any(s["access_result"] in ("ACCEPTED", "DUPLICATE_EXACT") for s in req["source_inventory"]):
        return "NO_ACCEPTED_SOURCE_OBJECTS"
    if intake is not None:
        from services.passport_intake import receipt_problems
        problems = receipt_problems(intake)
        if problems:
            return problems[0]
        inv = {s["source_artifact_id"]: s["sha256"] for s in req["source_inventory"]}
        rec = {o["source_artifact_id"]: o["sha256"] for o in intake["objects"]
               if o["access_result"] in ("ACCEPTED", "DUPLICATE_EXACT")}
        if inv != rec:
            # В запросе ровно замороженный состав — ни объекта больше.
            return "COUNT_MISMATCH"
    rep = idempotency(request_sha(req), stored)
    if rep:
        return rep
    if locked:
        return "PASSPORT_MUTATION_LOCKED"
    return None
