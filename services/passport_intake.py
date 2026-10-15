# -*- coding: utf-8 -*-
"""
services/passport_intake.py — приём исходных материалов для Паспорта SKU.

Норматив — `Listing_Suite_Source_Intake_Policy.md` v1.0 и утверждённый профиль
`Listing_Suite_Source_Intake_Profile_v1.0.json` (LS-CFG-001/002: 15 расширений,
100 файлов, 500 МиБ на файл, 5 ГиБ на снимок, 30 минут видео, глубина 5).
Результат — квитанция приёма по `listing_suite_source_intake_receipt.schema.json`.
Регистрация материала — не факт Паспорта: это только «что принято и где лежит».

Порядок проверок — из политики, и он важен: файл вне выбранного корня или
через ссылку отвергается ДО чтения содержимого; тип проверяется и по
расширению, и по самим байтам (несовпадение — `TYPE_MISMATCH`, а не тихий
приём); пределы на объект — у объекта, пределы на снимок (число файлов и
общий объём) — у всего снимка разом, `REJECTED_POLICY`.

Куда кладётся копия, модуль не решает: это `ArtifactStore` с двумя методами,
`put` и `get`. Где живёт `product_root` — решение владельца процесса, его ещё
нет; пока есть только хранилище в памяти для тестов. Квитанцию с `ACCEPTED`
без копии и повторного чтения выдать нельзя — так требует схема
(`archived_locator` и SHA обязательны), и так требует политика: сбой копии,
хэша или повторного чтения — не `ACCEPTED`.

ZIP. По решению владельца Listing Suite (07.10.2026) материалы можно загрузить
архивом. Канон архив как источник запрещает — `.zip` не в списке расширений,
и это заперто граничным случаем `ARCHIVE-NOT-ALLOWED`. Поэтому архив здесь —
не источник, а выбранная папка: он разворачивается, каждый файл внутри
проверяется как обычный, а сам архив нигде не регистрируется. Архив внутри
архива — `TYPE_NOT_ALLOWED`, как в каноне.
"""
from __future__ import annotations

import hashlib
import io
import json
import pathlib
import posixpath
import re
import struct
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone

CANON = pathlib.Path(__file__).resolve().parent.parent / "canon" / "ai_design_conveyor" / "02_SKU_Passport"
PROFILE_FILE = CANON / "Listing_Suite_Source_Intake_Profile_v1.0.json"
PROFILE_SCHEMA = CANON / "listing_suite_source_intake_profile.schema.json"
RECEIPT_SCHEMA = CANON / "listing_suite_source_intake_receipt.schema.json"

NOT_CONFIGURED = "INTAKE_POLICY_NOT_CONFIGURED"

# Причины из политики — закрытый словарь, своих нет.
REASONS = ("TYPE_NOT_ALLOWED", "TYPE_MISMATCH", "FILE_TOO_LARGE", "TOTAL_SIZE_EXCEEDED",
           "FILE_COUNT_EXCEEDED", "VIDEO_TOO_LONG", "RECURSION_DEPTH_EXCEEDED", "PATH_OUTSIDE_SELECTION",
           "LINK_TRAVERSAL_BLOCKED", "READ_FAILED", "ARCHIVE_COPY_FAILED", "HASH_FAILED", "READBACK_FAILED")
ACCESS = ("ACCEPTED", "ACCESS_DENIED", "UNAVAILABLE", "UNSUPPORTED", "DUPLICATE_EXACT")

# Расширение → ожидаемый тип. Пары из профиля: каждому из 15 расширений
# соответствует свой тип из списка разрешённых.
EXT_MIME = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv", ".txt": "text/plain", ".md": "text/markdown",
    ".json": "application/json", ".html": "text/html",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
    ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
}
VIDEO = {"video/mp4", "video/quicktime", "video/webm"}


# ---------------------------------------------------------------- профиль
def profile_sha(profile: dict) -> str:
    """SHA профиля так, как его считает канон: компактный UTF-8 JSON в порядке
    полей файла, без самого `policy_sha256`. Проверено на всех четырёх
    профилях канона — сортировка ключей даёт другой хэш."""
    body = {k: v for k, v in profile.items() if k != "policy_sha256"}
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def load_profile(path: pathlib.Path = PROFILE_FILE) -> tuple[dict | None, str | None]:
    """Действующий профиль приёма или причина, почему его нет.

    Пустой, нулевой или неподписанный предел, несовпадение схемы или SHA —
    `INTAKE_POLICY_NOT_CONFIGURED`: приём не начинается вовсе (политика,
    «Обов'язковий deployment profile»)."""
    import jsonschema
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
        schema = json.loads(PROFILE_SCHEMA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, NOT_CONFIGURED
    if list(jsonschema.Draft202012Validator(schema).iter_errors(profile)):
        return None, NOT_CONFIGURED
    if profile_sha(profile) != profile.get("policy_sha256"):
        return None, NOT_CONFIGURED
    for k in ("max_file_count", "max_single_file_bytes", "max_total_bytes",
              "max_video_duration_seconds", "max_recursion_depth"):
        if not isinstance(profile.get(k), int) or profile[k] <= 0:
            return None, NOT_CONFIGURED
    return profile, None


# ---------------------------------------------------------------- тип по байтам
def sniff(data: bytes, ext: str) -> str:
    """Тип по содержимому. Расширение только выбирает, каким из текстовых
    типов считать текст: csv и txt по байтам неотличимы."""
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm" if b"webm" in data[:64] else "video/x-matroska"
    if data[4:8] == b"ftyp":
        return "video/quicktime" if data[8:12] == b"qt  " else "video/mp4"
    if data.startswith(b"PK\x03\x04"):
        try:
            names = set(zipfile.ZipFile(io.BytesIO(data)).namelist())
        except zipfile.BadZipFile:
            return "application/octet-stream"
        if "[Content_Types].xml" in names and "word/document.xml" in names:
            return EXT_MIME[".docx"]
        if "[Content_Types].xml" in names and "xl/workbook.xml" in names:
            return EXT_MIME[".xlsx"]
        return "application/zip"
    if b"\x00" in data[:4096]:
        return "application/octet-stream"
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return "application/octet-stream"
    if ext == ".json":
        try:
            json.loads(text)
            return "application/json"
        except ValueError:
            return "text/plain"
    head = text[:2048].lower()
    if ext == ".html":
        return "text/html" if ("<html" in head or "<!doctype html" in head) else "text/plain"
    return {".csv": "text/csv", ".md": "text/markdown"}.get(ext, "text/plain")


def video_seconds(data: bytes, mime: str) -> float | None:
    """Длительность видео из заголовка без сторонних программ; None — не
    удалось прочитать. MP4/MOV — атом `mvhd`, WebM — элементы EBML
    `Duration` и `TimecodeScale`."""
    try:
        if mime in ("video/mp4", "video/quicktime"):
            i = data.find(b"mvhd")
            if i < 0:
                return None
            ver = data[i + 4]
            if ver == 1:
                scale, dur = struct.unpack(">IQ", data[i + 24:i + 36])
            else:
                scale, dur = struct.unpack(">II", data[i + 16:i + 24])
            return dur / scale if scale else None
        if mime == "video/webm":
            scale = 1_000_000
            j = data.find(b"\x2a\xd7\xb1")
            if j >= 0:
                n = data[j + 3] & 0x0F if data[j + 3] & 0x80 == 0 else data[j + 3] & 0x7F
                scale = int.from_bytes(data[j + 4:j + 4 + n], "big") or scale
            k = data.find(b"\x44\x89")
            if k < 0:
                return None
            size = data[k + 2] & 0x7F
            raw = data[k + 3:k + 3 + size]
            dur = struct.unpack(">d" if size == 8 else ">f", raw)[0]
            return dur * scale / 1e9
    except (IndexError, struct.error):
        return None
    return None


# ---------------------------------------------------------------- кандидаты
@dataclass
class Candidate:
    """Объект выбранного набора до проверки: где лежал, на какой глубине и,
    если до чтения дошло, его байты. `blocked` — причина отказа, выясненная
    ещё до чтения (выход за корень, ссылка): содержимое тогда не читается."""
    locator: str
    name: str
    depth: int = 0
    data: bytes | None = None
    declared_size: int | None = None
    blocked: str | None = None
    unreadable: bool = False


UPLOAD_ROOT = "browser-upload"


def from_uploads(files: list[tuple[str, bytes]], max_single: int, root: str = UPLOAD_ROOT) -> list[Candidate]:
    """Загруженные файлы под корнем выбора `root`. ZIP — выбранная папка:
    разворачивается, сам не регистрируется (см. docstring модуля)."""
    out: list[Candidate] = []
    for name, data in files:
        if name.lower().endswith(".zip"):
            out.extend(expand_zip(name, data, max_single, root))
        else:
            out.append(Candidate(locator=f"{root}/{name}", name=name, data=data, declared_size=len(data)))
    return out


def expand_zip(zip_name: str, data: bytes, max_single: int, root: str = UPLOAD_ROOT) -> list[Candidate]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        infos = zf.infolist()
    except zipfile.BadZipFile:
        return [Candidate(locator=f"{root}/{zip_name}", name=zip_name, unreadable=True)]
    out = []
    for info in infos:
        if info.is_dir():
            continue
        raw = info.filename.replace("\\", "/")
        loc = f"{root}/{zip_name}!/{raw}"
        norm = posixpath.normpath(raw)
        mode = (info.external_attr >> 16) & 0o170000
        name = posixpath.basename(norm)
        if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw) or norm == ".." or norm.startswith("../"):
            out.append(Candidate(locator=loc, name=name, blocked="PATH_OUTSIDE_SELECTION"))
            continue
        if mode == 0o120000:
            out.append(Candidate(locator=loc, name=name, blocked="LINK_TRAVERSAL_BLOCKED"))
            continue
        depth = norm.count("/")
        c = Candidate(locator=loc, name=name, depth=depth, declared_size=info.file_size)
        if info.file_size <= max_single:
            # Сверх предела не читаем вовсе: объявленный размер уже говорит
            # «слишком большой», а распаковка бомбы съела бы память процесса.
            try:
                c.data = zf.read(info)
            except Exception:
                c.unreadable = True
        out.append(c)
    return out


# ---------------------------------------------------------------- проверка
# Предел профиля по измерению граничной матрицы канона
# (`listing_suite_source_intake_boundary_cases.schema.json`).
LIMITS = {
    "file_count": ("max_file_count", "FILE_COUNT_EXCEEDED"),
    "single_file_bytes": ("max_single_file_bytes", "FILE_TOO_LARGE"),
    "total_bytes": ("max_total_bytes", "TOTAL_SIZE_EXCEEDED"),
    "video_duration_seconds": ("max_video_duration_seconds", "VIDEO_TOO_LONG"),
    "recursion_depth": ("max_recursion_depth", "RECURSION_DEPTH_EXCEEDED"),
}


def limit_reason(dimension: str, value, profile: dict) -> str | None:
    """Причина отказа по одному измерению или None. Ровно предел — можно,
    предел + 1 — нельзя (граничные случаи `*-AT-LIMIT` и `*-OVER-LIMIT`)."""
    if dimension == "extension":
        ext = str(value).lower()
        ok = ext in {e.lower() for e in profile["allowed_extensions"]} and EXT_MIME.get(ext) in set(
            profile["allowed_mime_types"])
        return None if ok else "TYPE_NOT_ALLOWED"
    key, reason = LIMITS[dimension]
    return reason if value > profile[key] else None


@dataclass
class Result:
    source_artifact_id: str
    original_locator: str
    name: str
    detected_mime_type: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    access_result: str = "ACCEPTED"
    reason_code: str | None = None
    duplicate_of: str | None = None
    archived_locator: str | None = None
    data: bytes | None = field(default=None, repr=False)

    def reject(self, access: str, reason: str) -> "Result":
        self.access_result, self.reason_code, self.data = access, reason, None
        return self


def evaluate(cands: list[Candidate], profile: dict, known: dict[str, str] | None = None) -> tuple[list[Result], str | None]:
    """Пооб'єктна проверка до копии. Вторым значением — отказ всего снимка
    (`FILE_COUNT_EXCEEDED` или `TOTAL_SIZE_EXCEEDED`), он же REJECTED_POLICY.

    `known` — SHA уже зарегистрированных материалов этого SKU → их ID:
    точный повтор — `DUPLICATE_EXACT` с `duplicate_of`, новой редакции нет."""
    known = dict(known or {})
    results: list[Result] = []
    for i, c in enumerate(cands, 1):
        r = Result(source_artifact_id=f"SRC-{i:03d}", original_locator=c.locator, name=c.name)
        results.append(r)
        if c.blocked:
            r.reject("ACCESS_DENIED", c.blocked)
            continue
        if c.unreadable:
            r.reject("UNAVAILABLE", "READ_FAILED")
            continue
        r.size_bytes = c.declared_size if c.data is None else len(c.data)
        ext = posixpath.splitext(c.name.lower())[1]
        why = (limit_reason("recursion_depth", c.depth, profile) or limit_reason("extension", ext, profile)
               or (limit_reason("single_file_bytes", r.size_bytes, profile) if r.size_bytes is not None else None))
        if why:
            r.reject("UNSUPPORTED", why)
            continue
        if c.data is None:
            r.reject("UNAVAILABLE", "READ_FAILED")
            continue
        r.detected_mime_type = sniff(c.data, ext)
        if r.detected_mime_type != EXT_MIME[ext]:
            r.reject("UNSUPPORTED", "TYPE_MISMATCH")
            continue
        if r.detected_mime_type in VIDEO:
            secs = video_seconds(c.data, r.detected_mime_type)
            if secs is None:
                # Длительность не прочитана — проверить предел нечем, а
                # пропустить непроверенное значит молча нарушить политику.
                r.reject("UNAVAILABLE", "READ_FAILED")
                continue
            if limit_reason("video_duration_seconds", secs, profile):
                r.reject("UNSUPPORTED", "VIDEO_TOO_LONG")
                continue
        try:
            r.sha256 = hashlib.sha256(c.data).hexdigest()
        except Exception:
            r.reject("UNAVAILABLE", "HASH_FAILED")
            continue
        r.data = c.data
        if r.sha256 in known:
            r.access_result, r.duplicate_of, r.data = "DUPLICATE_EXACT", known[r.sha256], None
        else:
            known[r.sha256] = r.source_artifact_id

    snapshot = (limit_reason("file_count", len(results), profile)
                or limit_reason("total_bytes", sum(r.size_bytes or 0 for r in results), profile))
    return results, snapshot


# ---------------------------------------------------------------- копия
class ArtifactStore:
    """Куда ложится неизменная копия материала. Реализация под `product_root`
    появится, когда владелец процесса скажет, где он живёт; пока — память."""

    def put(self, path: str, data: bytes) -> str:
        raise NotImplementedError

    def get(self, locator: str) -> bytes:
        raise NotImplementedError


class MemoryStore(ArtifactStore):
    def __init__(self):
        self.files: dict[str, bytes] = {}

    def put(self, path: str, data: bytes) -> str:
        self.files[path] = bytes(data)
        return path

    def get(self, locator: str) -> bytes:
        return self.files[locator]


def archive(results: list[Result], store: ArtifactStore, sku_id: str, day: str) -> list[Result]:
    """Копия каждого принятого объекта в `<sku>/артефакти/<день>/`, затем
    повторное чтение и сверка SHA. Любой сбой — не `ACCEPTED` (политика, п. 7)."""
    taken: set[str] = set()
    for r in results:
        if r.access_result != "ACCEPTED":
            continue
        stem, ext = posixpath.splitext(r.name)
        path, n = f"{sku_id}/артефакти/{day}/{r.name}", 1
        while path in taken:
            n += 1
            path = f"{sku_id}/артефакти/{day}/{stem} ({n}){ext}"
        taken.add(path)
        try:
            loc = store.put(path, r.data)
        except Exception:
            r.reject("UNAVAILABLE", "ARCHIVE_COPY_FAILED")
            continue
        try:
            back = store.get(loc)
        except Exception:
            r.reject("UNAVAILABLE", "READBACK_FAILED")
            continue
        if hashlib.sha256(back).hexdigest() != r.sha256:
            r.reject("UNAVAILABLE", "READBACK_FAILED")
            continue
        r.archived_locator, r.data = loc, None
    return results


# ---------------------------------------------------------------- квитанция
def receipt(results: list[Result], profile: dict, snapshot_reason: str | None, *, actor_id: str,
            sku_id: str, selection_root: str, now: datetime | None = None) -> dict:
    """Квитанция приёма. Статус: отказ снимка — REJECTED_POLICY; ни одного
    принятого — NO_ACCEPTED_OBJECTS (запрос не создаётся); часть отклонена —
    PARTIAL_REQUIRES_CONFIRMATION (продолжить можно только явным согласием);
    иначе READY_TO_SUBMIT."""
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    accepted = sum(r.access_result == "ACCEPTED" for r in results) if not snapshot_reason else 0
    dup = sum(r.access_result == "DUPLICATE_EXACT" for r in results) if not snapshot_reason else 0
    rejected = len(results) - accepted - dup
    if snapshot_reason:
        status = "REJECTED_POLICY"
    elif accepted == 0:
        status = "NO_ACCEPTED_OBJECTS"
    elif rejected:
        status = "PARTIAL_REQUIRES_CONFIRMATION"
    else:
        status = "READY_TO_SUBMIT"
    objects = []
    for r in results:
        o = {"source_artifact_id": r.source_artifact_id, "original_locator": r.original_locator,
             "archived_locator": r.archived_locator, "detected_mime_type": r.detected_mime_type,
             "size_bytes": r.size_bytes, "sha256": r.sha256, "access_result": r.access_result,
             "reason_code": r.reason_code, "duplicate_of": r.duplicate_of}
        if snapshot_reason:
            o.update(access_result="UNSUPPORTED", reason_code=snapshot_reason, archived_locator=None)
        objects.append(o)
    digest = hashlib.sha256(json.dumps([sku_id, selection_root, [(o["original_locator"], o["sha256"])
                                                                 for o in objects]],
                                       ensure_ascii=False).encode()).hexdigest()[:20].upper()
    return {
        "schema_version": "1.0",
        "intake_receipt_id": f"LS-INTAKE-RECEIPT-{digest}",
        "snapshot_id": f"LS-SNAPSHOT-{digest}",
        "actor_id": actor_id, "sku_id": sku_id, "selection_root": selection_root,
        "policy": {k: profile[k] for k in ("policy_id", "policy_version", "policy_sha256")},
        "frozen_at": now.isoformat().replace("+00:00", "Z"),
        "object_count": len(objects), "accepted_source_count": accepted,
        "rejected_source_count": rejected, "duplicate_count": dup,
        "submission_status": status, "objects": objects,
    }


def receipt_problems(rec: dict) -> list[str]:
    """Целостность квитанции приёма до запроса (контрактные отказы фикстур
    `contract_reject_intake_*`): счётчики сходятся с объектами, принятые
    лежат под выбранным корнем."""
    out = []
    objs = rec.get("objects") or []
    acc = sum(o["access_result"] == "ACCEPTED" for o in objs)
    dup = sum(o["access_result"] == "DUPLICATE_EXACT" for o in objs)
    if (rec.get("object_count") != len(objs) or rec.get("accepted_source_count") != acc
            or rec.get("duplicate_count") != dup
            or rec.get("rejected_source_count") != len(objs) - acc - dup):
        out.append("COUNT_MISMATCH")
    root = (rec.get("selection_root") or "").replace("\\", "/").rstrip("/") + "/"
    for o in objs:
        if o["access_result"] in ("ACCEPTED", "DUPLICATE_EXACT"):
            loc = o["original_locator"].replace("\\", "/")
            if not loc.startswith(root) or "/../" in loc:
                out.append("PATH_OUTSIDE_SELECTION")
                break
    return out
