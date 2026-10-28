"""Решения верификатора по конфликтам копии паспорта docx (решение владельца 28.10.2026).

Конфликт копии закрывается решением: выбранная сторона (A или B) или своё
значение, и ПРОВЕРЯЕМЫЙ источник решения — чьи слова и где («чат 21.10,
Ярослав»). Решение пишется в `passport_conflict_decisions` новой строкой, копия
паспорта не меняется. Действует последнее решение по конфликту этой копии; новая
копия (v3) приходит со своими конфликтами, и решения по v2 к ней не относятся.

Право записи — `ls.textgen.accept` (администратор и пилот), проверяет страница в
момент нажатия. Отдельное право `ls.passport.decide` — когда привяжется
канонический профиль полномочий (решение владельца 28.10.2026).

Генератор берёт решения из той же таблицы (`services/textgen.generate`) и
перестаёт вырезать решённое: `passport_facts.apply_decisions`.
"""
from __future__ import annotations

import re

from services import passport_facts as pf

TABLE = "passport_conflict_decisions"
MIGRATION = "2026-10-28_passport_conflict_decisions.sql"
MIN_SOURCE = 5          # «чат» без даты и автора — не проверяемый источник
_COLS = ("id", "conflict_id", "decision", "value", "decision_source", "decided_by", "decided_at")
_SELECT = ("SELECT id, conflict_id, decision, value, decision_source, decided_by, decided_at"
           " FROM passport_conflict_decisions WHERE source_artifact_id = %(a)s AND artifact_sha256 = %(s)s"
           " ORDER BY id")


def _last(rows) -> dict:
    """Последнее решение по каждому конфликту: строки идут по id."""
    out = {}
    for r in rows:
        d = dict(zip(_COLS, r)) if not isinstance(r, dict) else dict(r)
        out[d["conflict_id"]] = d
    return out


def load(artifact_id: str, sha: str) -> tuple[dict, str | None, bool]:
    """(решения по id конфликта, причина сбоя, нет миграции) — для экрана."""
    from services.db import safe_read, table_exists
    exists = table_exists(f"listing_data.{TABLE}")
    if exists is False:
        return {}, None, True
    df, err = safe_read(_SELECT, {"a": artifact_id, "s": sha})
    if err:
        return {}, err, False
    return _last(df.to_dict("records")), None, False


def read_with(cur, artifact_id: str, sha: str) -> dict:
    """То же через курсор генерации, до платного вызова. Нет таблицы — решений нет."""
    cur.execute(f"SELECT to_regclass('listing_data.{TABLE}') IS NOT NULL")
    if not cur.fetchone()[0]:
        return {}
    cur.execute(_SELECT, {"a": artifact_id, "s": sha})
    return _last(cur.fetchall())


def check(facts: pf.Facts, conflict_id: str, decision: str, value: str, source: str) -> str | None:
    """Причина отказа (код для i18n `pp.dec.err.<код>`) или None."""
    ids = {c.get("id") for c in facts.conflicts}
    if conflict_id not in ids:
        return "NO_CONFLICT"
    if decision not in pf.DECISIONS:
        return "BAD_DECISION"
    if decision == "VALUE" and not (value or "").strip():
        return "NO_VALUE"
    if len(re.sub(r"\s+", " ", source or "").strip()) < MIN_SOURCE:
        return "NO_SOURCE"
    return None


def record(conn, *, copy: dict, sku: str, passport_id: str, conflict_id: str, decision: str,
           value: str, source: str, actor: str) -> int:
    """Новая строка решения; id. Совпадение копии, SKU и SHA проверяет и триггер."""
    with conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO passport_conflict_decisions (source_artifact_id, artifact_sha256, sku_id, passport_id,"
            " conflict_id, decision, value, decision_source, decided_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " RETURNING id",
            (copy["source_artifact_id"], copy["sha256"], sku, passport_id, conflict_id, decision,
             (value or "").strip() or None, re.sub(r"\s+", " ", source).strip(), actor))
        return int(cur.fetchone()[0])
