# -*- coding: utf-8 -*-
"""
tests/test_passport_intake.py — приём материалов Паспорта и проверки до запроса.

Норматив — политика приёма Listing Suite v1.0, утверждённый профиль
(LS-CFG-001/002), Integration Contract v1.2 и порядок проверок Handoff.
Каждая проверка здесь — про то, что ломается тихо:

1. Профиль подписан: SHA считается так же, как его считает канон; правка
   предела — `INTAKE_POLICY_NOT_CONFIGURED`, и приём не начинается.
2. Граничная матрица канона (13 случаев) исполняется против кода:
   ровно предел — можно, предел + 1 — нельзя; `.zip` как источник — нельзя.
3. Тип проверяется по БАЙТАМ: PDF под именем .png — `TYPE_MISMATCH`.
4. ZIP — выбранная папка: выход за корень и ссылки отвергаются без чтения,
   архив в архиве — `TYPE_NOT_ALLOWED`, глубина 6 — отказ.
5. Длительность видео читается из заголовка; не прочиталась — не принято.
6. Точный повтор — `DUPLICATE_EXACT` с `duplicate_of`, а не новая редакция.
7. `ACCEPTED` только после копии, хэша и повторного чтения; сбой любого —
   не `ACCEPTED`. Квитанция проходит схему канона.
8. Отказ снимка (число файлов, общий объём) — `REJECTED_POLICY` целиком;
   ноль принятых — запроса нет; часть отклонена — нужно согласие.
9. Контрактные фикстуры канона: выход пути за корень и несходящиеся
   счётчики ловятся до запроса; устаревший снимок Паспорта —
   `STALE_PASSPORT_INPUT`.
10. Порядок проверок Handoff: схема раньше полномочий, полномочия раньше
    всего остального; канонический профиль полномочий не привязан —
    `AUTHORITY_PROFILE_NOT_ACTIVE`, дальше запрос не идёт.
11. Идемпотентность: тот же ключ и запрос — повтор квитанции, тот же ключ
    с другим запросом — конфликт.

Запуск (pytest не нужен):  python tests/test_passport_intake.py
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import pathlib
import struct
import sys
import tempfile
import zipfile

import jsonschema

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import services.passport_actions as pa                     # noqa: E402
import services.passport_intake as pi                      # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


CANON = pi.CANON
FIX = CANON / "fixtures" / "listing_suite"


def load(p):
    return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))


# ================================================================ 1. профиль
profile, why = pi.load_profile()
check(f"профиль канона загружен и подписан ({why})", profile is not None and why is None)
check("SHA профиля считается как в каноне", pi.profile_sha(load(pi.PROFILE_FILE)) == load(pi.PROFILE_FILE)["policy_sha256"])
with tempfile.TemporaryDirectory() as d:
    bad = load(pi.PROFILE_FILE)
    bad["max_file_count"] = 1000                 # правка без новой подписи
    p = pathlib.Path(d) / "p.json"
    p.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    check("правка предела без подписи → INTAKE_POLICY_NOT_CONFIGURED", pi.load_profile(p) == (None, pi.NOT_CONFIGURED))
    bad = load(pi.PROFILE_FILE)
    bad["max_video_duration_seconds"] = 0
    bad["policy_sha256"] = pi.profile_sha(bad)   # подписан, но предел нулевой
    p.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    check("нулевой предел даже с подписью → INTAKE_POLICY_NOT_CONFIGURED", pi.load_profile(p)[1] == pi.NOT_CONFIGURED)
    p.write_text("{", encoding="utf-8")
    check("нечитаемый профиль → INTAKE_POLICY_NOT_CONFIGURED", pi.load_profile(p)[1] == pi.NOT_CONFIGURED)

# ================================================================ 2. граничная матрица канона
matrix = load(FIX / "valid_intake_boundary_cases.json")
check("матрица для того же профиля, что загружен",
      (matrix["policy_id"], matrix["policy_version"]) == (profile["policy_id"], profile["policy_version"]))
wrong = []
for case in matrix["cases"]:
    dim, val, want = case["dimension"], case["value"], case["expected"]
    if dim in pi.LIMITS or dim == "extension":
        got = pi.limit_reason(dim, val, profile)
        ok = (got is None) if want == "ACCEPT" else (got == case["reason_code"])
    elif dim == "partial_confirmation":
        res = [pi.Result("SRC-001", "r/a.txt", "a.txt", sha256="a" * 64, archived_locator="x"),
               pi.Result("SRC-002", "r/b.exe", "b.exe").reject("UNSUPPORTED", "TYPE_NOT_ALLOWED")]
        ok = pi.receipt(res, profile, None, actor_id="u", sku_id="S", selection_root="r")["submission_status"] \
            == "PARTIAL_REQUIRES_CONFIRMATION"
    elif dim == "accepted_count":
        res = [pi.Result("SRC-001", "r/b.exe", "b.exe").reject("UNSUPPORTED", "TYPE_NOT_ALLOWED")]
        ok = pi.receipt(res, profile, None, actor_id="u", sku_id="S", selection_root="r")["submission_status"] \
            == "NO_ACCEPTED_OBJECTS"
    else:
        ok = False
    if not ok:
        wrong.append(case["case_id"])
check(f"все {len(matrix['cases'])} граничных случаев канона исполняются кодом ({wrong})", not wrong)

# число файлов и общий объём — отказ всего снимка, а не части
small = {**profile, "max_file_count": 3, "max_total_bytes": 30}
files = [(f"f{i}.txt", f"text {i}".encode()) for i in range(4)]
res, snap = pi.evaluate(pi.from_uploads(files, profile["max_single_file_bytes"]), small)
rec = pi.receipt(res, small, snap, actor_id="u", sku_id="S", selection_root=pi.UPLOAD_ROOT)
check("4 файла при пределе 3 — REJECTED_POLICY целиком, принятых ноль",
      snap == "FILE_COUNT_EXCEEDED" and rec["submission_status"] == "REJECTED_POLICY"
      and rec["accepted_source_count"] == 0)
res, snap = pi.evaluate(pi.from_uploads(files[:3], profile["max_single_file_bytes"]), small)
check("3 файла при пределе 3 — снимок принят", snap is None)
res, snap = pi.evaluate(pi.from_uploads([("big.txt", b"x" * 31)], 10 ** 6), small)
check("объём 31 при пределе 30 — TOTAL_SIZE_EXCEEDED", snap == "TOTAL_SIZE_EXCEEDED")

# ================================================================ 3. тип по байтам
PDF = b"%PDF-1.7\n" + b"0" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


def one(name, data, prof=profile, known=None):
    r, _ = pi.evaluate(pi.from_uploads([(name, data)], prof["max_single_file_bytes"]), prof, known)
    return r[0]


check("PDF принимается", one("manual.pdf", PDF).access_result == "ACCEPTED")
check("PDF под именем .png → TYPE_MISMATCH", one("photo.png", PDF).reason_code == "TYPE_MISMATCH")
check("бинарник под именем .pdf → TYPE_MISMATCH", one("manual.pdf", b"MZ\x90\x00\x03" + b"\x00" * 50).reason_code == "TYPE_MISMATCH")
check(".exe → TYPE_NOT_ALLOWED", one("setup.exe", b"MZ").reason_code == "TYPE_NOT_ALLOWED")
check("битый JSON под .json → TYPE_MISMATCH", one("d.json", b"{oops").reason_code == "TYPE_MISMATCH")


def office(kind: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml" if kind == "docx" else "xl/workbook.xml", "<x/>")
    return buf.getvalue()


check("DOCX узнаётся по содержимому", one("spec.docx", office("docx")).access_result == "ACCEPTED")
check("XLSX под именем .docx → TYPE_MISMATCH", one("spec.docx", office("xlsx")).reason_code == "TYPE_MISMATCH")

# ================================================================ 4. ZIP как выбранная папка
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    z.writestr("docs/manual.pdf", PDF)
    z.writestr("../evil.pdf", PDF)
    z.writestr("a/b/c/d/e/f/deep.pdf", PDF)          # глубина 6
    z.writestr("a/b/c/d/e/ok.pdf", PDF + b"1")        # глубина 5
    z.writestr("inner.zip", b"PK\x03\x04")
    link = zipfile.ZipInfo("docs/link.pdf")
    link.external_attr = (0o120777 << 16)
    z.writestr(link, "/etc/passwd")
res, snap = pi.evaluate(pi.from_uploads([("pack.zip", buf.getvalue())], profile["max_single_file_bytes"]), profile)
by = {r.original_locator.split("!/")[1]: r for r in res}
check("файлы внутри архива проверяются по одному", by["docs/manual.pdf"].access_result == "ACCEPTED")
check("сам архив источником не стал (нет объекта pack.zip)", all("!/" in r.original_locator for r in res))
check("«../» в архиве → PATH_OUTSIDE_SELECTION", by["../evil.pdf"].reason_code == "PATH_OUTSIDE_SELECTION")
check("ссылка в архиве → LINK_TRAVERSAL_BLOCKED, содержимое не читалось",
      by["docs/link.pdf"].reason_code == "LINK_TRAVERSAL_BLOCKED" and by["docs/link.pdf"].sha256 is None)
check("глубина 6 → RECURSION_DEPTH_EXCEEDED, глубина 5 принята",
      by["a/b/c/d/e/f/deep.pdf"].reason_code == "RECURSION_DEPTH_EXCEEDED"
      and by["a/b/c/d/e/ok.pdf"].access_result == "ACCEPTED")
check("архив в архиве → TYPE_NOT_ALLOWED", by["inner.zip"].reason_code == "TYPE_NOT_ALLOWED")
check("битый архив — READ_FAILED, а не пустой набор",
      [r.reason_code for r in pi.evaluate(pi.from_uploads([("x.zip", b"not a zip")], 10 ** 6), profile)[0]] == ["READ_FAILED"])


# ================================================================ 5. длительность видео
def mp4(seconds: int, scale: int = 1000) -> bytes:
    ftyp = struct.pack(">I", 16) + b"ftypisom" + b"\x00\x00\x02\x00"
    mvhd = b"mvhd" + b"\x00\x00\x00\x00" + b"\x00" * 8 + struct.pack(">II", scale, seconds * scale)
    return ftyp + struct.pack(">I", len(mvhd) + 4) + mvhd + b"\x00" * 64


def webm(seconds: float) -> bytes:
    return (b"\x1a\x45\xdf\xa3\x9f\x42\x82\x84webm" + b"\x00" * 8
            + b"\x2a\xd7\xb1\x83" + (1_000_000).to_bytes(3, "big")
            + b"\x44\x89\x88" + struct.pack(">d", seconds * 1000))


check("MP4 30:00 принят", one("v.mp4", mp4(1800)).access_result == "ACCEPTED")
check("MP4 30:01 → VIDEO_TOO_LONG", one("v.mp4", mp4(1801)).reason_code == "VIDEO_TOO_LONG")
check("WebM 30:00 принят, 30:01 нет",
      one("v.webm", webm(1800)).access_result == "ACCEPTED" and one("v.webm", webm(1801)).reason_code == "VIDEO_TOO_LONG")
check("длительность не прочиталась → не принято (READ_FAILED)",
      one("v.mp4", b"\x00\x00\x00\x10ftypisom" + b"\x00" * 32).reason_code == "READ_FAILED")

# ================================================================ 6. дубликаты
res, _ = pi.evaluate(pi.from_uploads([("a.pdf", PDF), ("copy.pdf", PDF)], 10 ** 6), profile)
check("повтор внутри набора → DUPLICATE_EXACT на первый",
      res[1].access_result == "DUPLICATE_EXACT" and res[1].duplicate_of == res[0].source_artifact_id)
r = one("again.pdf", PDF, known={hashlib.sha256(PDF).hexdigest(): "SRC-REG-7"})
check("повтор уже зарегистрированного → DUPLICATE_EXACT с его ID",
      r.access_result == "DUPLICATE_EXACT" and r.duplicate_of == "SRC-REG-7")

# ================================================================ 7. копия, хэш, повторное чтение
rschema = load(pi.RECEIPT_SCHEMA)
val = jsonschema.Draft202012Validator(rschema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER)
store = pi.MemoryStore()
res, snap = pi.evaluate(pi.from_uploads([("manual.pdf", PDF), ("photo.png", PDF), ("copy.pdf", PDF)], 10 ** 6), profile)
pi.archive(res, store, "21680000", "2026-10-11")
rec = pi.receipt(res, profile, snap, actor_id="v.tereshyn@dniprom.com", sku_id="21680000",
                 selection_root=pi.UPLOAD_ROOT)
check(f"квитанция проходит схему канона ({[e.message for e in val.iter_errors(rec)][:1]})",
      not list(val.iter_errors(rec)))
check("принятый лежит в <sku>/артефакти/<день>/",
      rec["objects"][0]["archived_locator"] == "21680000/артефакти/2026-10-11/manual.pdf")
check("счётчики: 1 принят, 1 отклонён, 1 повтор; нужна явная доводка",
      (rec["accepted_source_count"], rec["rejected_source_count"], rec["duplicate_count"], rec["submission_status"])
      == (1, 1, 1, "PARTIAL_REQUIRES_CONFIRMATION"))
check("собственная квитанция чиста для проверки перед запросом", pi.receipt_problems(rec) == [])


class BrokenStore(pi.MemoryStore):
    def __init__(self, mode):
        super().__init__()
        self.mode = mode

    def put(self, path, data):
        if self.mode == "put":
            raise OSError("диск недоступен")
        return super().put(path, data)

    def get(self, locator):
        return b"other" if self.mode == "readback" else super().get(locator)


for mode, reason in (("put", "ARCHIVE_COPY_FAILED"), ("readback", "READBACK_FAILED")):
    res, _ = pi.evaluate(pi.from_uploads([("manual.pdf", PDF)], 10 ** 6), profile)
    pi.archive(res, BrokenStore(mode), "S", "2026-10-11")
    rec = pi.receipt(res, profile, None, actor_id="u", sku_id="S", selection_root=pi.UPLOAD_ROOT)
    check(f"сбой {mode} → {reason}, не ACCEPTED, запроса нет",
          res[0].reason_code == reason and rec["submission_status"] == "NO_ACCEPTED_OBJECTS"
          and not list(val.iter_errors(rec)))

# ================================================================ 9. контрактные фикстуры канона
check("фикстура: путь вне выбранной папки → PATH_OUTSIDE_SELECTION",
      pi.receipt_problems(load(FIX / "contract_reject_intake_path_escape.json")) == ["PATH_OUTSIDE_SELECTION"])
check("фикстура: счётчики не сходятся с объектами → COUNT_MISMATCH",
      "COUNT_MISMATCH" in pi.receipt_problems(load(FIX / "contract_reject_intake_count_mismatch.json")))
check("фикстура: частичный приём канона чист", pi.receipt_problems(load(FIX / "valid_partial_intake_receipt.json")) == [])

# ================================================================ 10–11. проверки до запроса
ok = lambda *a: "AUTHORIZED"                                    # noqa: E731
good = load(FIX / "valid_delta_request.json")
cur = {"sku_id": good["sku_id"], "passport_id": good["current_passport"]["passport_id"],
       "passport_version": good["current_passport"]["version"], "sha256": good["current_passport"]["sha256"]}
args = dict(canonical_roles=("DATA_CONTRIBUTOR",), current=cur, intake=None, stored=None, locked=False)
check("валидный запрос при полномочиях проходит все проверки", pa.preflight(good, authority=ok, **args) is None)
check("канонический профиль полномочий не привязан → AUTHORITY_PROFILE_NOT_ACTIVE",
      pa.preflight(good, **args) == "AUTHORITY_PROFILE_NOT_ACTIVE")
broken = copy.deepcopy(good)
broken.pop("idempotency_key")
check("схема проверяется раньше полномочий", pa.preflight(broken, **args) == "REQUEST_SCHEMA_INVALID")
stale = load(FIX / "contract_reject_stale_snapshot.json")
cur_stale = {**cur, "sku_id": stale["sku_id"], "passport_id": stale["current_passport"]["passport_id"],
             "passport_version": "7", "sha256": "a" * 64}
check("фикстура: устаревший снимок Паспорта → STALE_PASSPORT_INPUT",
      pa.preflight(stale, authority=ok, **{**args, "current": cur_stale}) == "STALE_PASSPORT_INPUT")
check("Паспорта у SKU нет → STALE_PASSPORT_INPUT, а не запуск",
      pa.preflight(good, authority=ok, **{**args, "current": None}) == "STALE_PASSPORT_INPUT")
none_acc = copy.deepcopy(good)
for s in none_acc["source_inventory"]:
    s["access_result"] = "UNSUPPORTED"
check("в составе ни одного принятого → NO_ACCEPTED_SOURCE_OBJECTS",
      pa.preflight(none_acc, authority=ok, **args) == "NO_ACCEPTED_SOURCE_OBJECTS")
sha = pa.request_sha(good)
check("тот же ключ и тот же запрос → повтор сохранённой квитанции",
      pa.preflight(good, authority=ok, **{**args, "stored": {"request_sha256": sha}}) == pa.REPLAY)
check("тот же ключ с другим запросом → IDEMPOTENCY_KEY_CONFLICT",
      pa.preflight(good, authority=ok, **{**args, "stored": {"request_sha256": "0" * 64}}) == "IDEMPOTENCY_KEY_CONFLICT")
check("SKU занят другой операцией → PASSPORT_MUTATION_LOCKED",
      pa.preflight(good, authority=ok, **{**args, "locked": True}) == "PASSPORT_MUTATION_LOCKED")
reordered = dict(reversed(list(good.items())))
check("хэш запроса не зависит от порядка полей", pa.request_sha(reordered) == sha)

# полномочия по контракту на привязанном профиле
with tempfile.TemporaryDirectory() as d:
    bound = load(FIX / "valid_authority_profile_bound.json")
    p = pathlib.Path(d) / "a.json"
    p.write_text(json.dumps(bound), encoding="utf-8")
    ev = lambda action, roles: pa.evaluate_authority(action, roles, "S", profile_path=p)   # noqa: E731
    check("роль без привязки → AUTHORITY_NOT_MAPPED", ev(pa.DELTA, ("SOMEONE",)) == "AUTHORITY_NOT_MAPPED")
    check("DATA_CONTRIBUTOR на пересоздание → ACTION_NOT_AUTHORIZED",
          ev(pa.RECREATE, ("DATA_CONTRIBUTOR",)) == "ACTION_NOT_AUTHORIZED")
    check("PASSPORT_ADMIN на новые данные → AUTHORIZED", ev(pa.DELTA, ("PASSPORT_ADMIN",)) == "AUTHORIZED")
    check("PRODUCT_OWNER пересоздание не получает", ev(pa.RECREATE, ("PRODUCT_OWNER",)) == "ACTION_NOT_AUTHORIZED")

src = (ROOT / "services" / "passport_intake.py").read_text(encoding="utf-8") + \
      (ROOT / "services" / "passport_actions.py").read_text(encoding="utf-8")
check("приём и проверки ничего не пишут в базу",
      not any(w in src for w in ("INSERT INTO", "UPDATE ", "DELETE FROM", "get_conn")))

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
