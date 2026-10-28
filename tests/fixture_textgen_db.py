# -*- coding: utf-8 -*-
"""
tests/fixture_textgen_db.py — не тест, а подмены базы и тома для генератора текстов:
`DB` (соединение с транзакцией: откат при исключении), `Cur` (отвечает на те запросы,
что шлёт `services/textgen.py`, и падает на незнакомом) и `Store` (том паспортов).
Общие для `test_textgen_generate.py` и `test_textgen_page.py`: страница нажимает
«Сгенерировать» с НАСТОЯЩИМ `tg.generate` на тех же подменах (T-22), и подмены
не расходятся между двумя копиями.
"""
from __future__ import annotations

import copy as _copy
import re

from services import textgen as tg


class DB:
    def __init__(self):
        self.calls, self.content, self.log = [], [], []
        self.fail_content = False
        self.no_content_table = False
        self.stamp_cols = True          # миграция 2026-10-27_content_versions_stamp.sql применена
        self.decisions = []             # решения по конфликтам; None — миграции 2026-10-28 нет

    def cursor(self):
        return Cur(self)

    def __enter__(self):
        self.snap = _copy.deepcopy((self.calls, self.content))
        return self

    def __exit__(self, et, *a):
        if et is not None:
            self.calls, self.content = self.snap
        return False

    def close(self):
        self.closed = True


class Cur:
    def __init__(self, db):
        self.db, self.res = db, []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, p=()):
        db = self.db
        db.log.append(sql.split()[0] + " " + " ".join(sql.split()[1:3]))
        if "pg_advisory_xact_lock" in sql:
            self.res = [(None,)]
        elif sql.startswith("SELECT to_regclass('listing_data.passport_conflict_decisions')"):
            self.res = [(db.decisions is not None,)]
        elif "FROM passport_conflict_decisions" in sql:
            self.res = [tuple(d[k] for k in ("id", "conflict_id", "decision", "value", "decision_source",
                                             "decided_by", "decided_at"))
                        for d in (db.decisions or []) if (d["source_artifact_id"], d["artifact_sha256"]) == (p["a"], p["s"])]
        elif sql.startswith("SELECT to_regclass"):
            self.res = [(not db.no_content_table,)]
        elif "information_schema.columns" in sql:
            self.res = [(len(p[0]) if db.stamp_cols else 0,)]
        elif sql.startswith("SELECT count(*)"):
            today = [c for c in db.calls if not c.get("yesterday")]
            self.res = [(sum(1 for c in today if c["sku"] == p[0]),
                         sum(c["cost_usd"] for c in today if c["sku"] == p[1]),
                         sum(c["cost_usd"] for c in today))]
        elif sql.startswith("INSERT INTO textgen_calls"):
            row = dict(zip(("sku", "marketplace", "actor", "provider", "model", "cost_usd"), p),
                       id=len(db.calls) + 1, status="started")
            db.calls.append(row)
            self.res = [(row["id"],)]
        elif sql.startswith("UPDATE textgen_calls"):
            row = next(c for c in db.calls if c["id"] == p[-1])
            row.update(status=p[0], input_tokens=p[1], output_tokens=p[2], cost_usd=p[3], proposal_id=p[4],
                       error=p[5])
            self.res = []
        elif sql.startswith("SELECT COALESCE(max(version)"):
            vs = [c["version"] for c in db.content if (c["sku"], c["marketplace"], c["field"]) == tuple(p)]
            self.res = [(max(vs, default=0),)]
        elif sql.startswith("INSERT INTO content_versions"):
            if db.fail_content:
                raise RuntimeError("content_versions: триггер отказал")
            cols = re.search(r"\((.*?)\) VALUES", sql).group(1).replace(" ", "").split(",")
            if not db.stamp_cols and set(cols) & set(tg.STAMP_COLUMNS):
                # как база без миграции: «column … does not exist»
                raise RuntimeError("column prompt_sha256 of relation content_versions does not exist")
            vals = list(p[:11]) + ["model"] + list(p[11:])
            db.content.append(dict(zip(cols, vals)))
            self.res = []
        else:
            raise AssertionError(sql)

    def fetchone(self):
        return self.res[0] if self.res else None

    def fetchall(self):
        return list(self.res)


class Store:
    def __init__(self, data):
        self.data, self.reads = data, 0

    def get(self, loc):
        self.reads += 1
        return self.data
