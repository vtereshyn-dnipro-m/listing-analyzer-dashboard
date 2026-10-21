"""Копии паспорта SKU (docx) в томе UC и их регистрация (решение владельца 21.10.2026).

Паспорт — исходник «Генератора текстов»: текст ссылается на копию, по которой
он написан (`content_versions.passport_artifact_id`). Поэтому копия:

- лежит в томе `dnipro_m.listing_data.passports` по пути
  `<sku>/<passport_id>/v<версия>/<passport_id>_v<версия>.docx`. Drive пока не
  заводим;
- неизменна. Тот же путь второй раз не пишется: тот же файл — повтор без записи,
  другой файл — отказ. Строку регистрации держит триггер `passport_copy_frozen`;
- регистрируется строкой `passport_source_artifacts`: SHA файла, размер, кто
  загрузил. Новая версия паспорта — новая строка, прежняя копия того же
  паспорта уходит в OLD (единственный шаг, который триггер разрешает).

SKU, id паспорта и версия берутся из ШАПКИ файла (таблица «Параметр / Значення»
канонической формы), а не вводятся руками: опечатка в ручном поле положила бы
паспорт одного товара в папку другого.

Страница зовёт `read_header()` для показа и `register()` по кнопке; права
проверяет страница, в момент нажатия.
"""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from services.passport_intake import ArtifactStore

VOLUME = "dnipro_m.listing_data.passports"
ROOT = "/Volumes/dnipro_m/listing_data/passports"
MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MAX_BYTES = 25 * 1024 * 1024          # паспорт — текст и таблицы, не фото
MAX_XML_BYTES = 50 * 1024 * 1024      # распакованный document.xml: защита от «бомбы»

HEADER_KEYS = ("passport_id", "passport_version", "sku_id", "state", "run_id", "updated_at")
REQUIRED = ("passport_id", "passport_version", "sku_id")
# Имена идут в путь тома: только то, что не может выйти из своей папки.
SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
VERSION_IN_PATH = re.compile(r"/v(\d+)/[^/]+$")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class CopyError(Exception):
    """Отказ с кодом: страница показывает `tg.pp.err.<code>`."""

    def __init__(self, code: str, detail: str = "", active: tuple[str, ...] = ()):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code, self.detail, self.active = code, detail, active


@dataclass
class Outcome:
    status: str                       # REGISTERED | DUPLICATE
    artifact_id: str
    locator: str
    header: dict
    superseded: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ шапка
def _cell_text(tc) -> str:
    return "".join(x.text or "" for x in tc.iter(W + "t")).strip()


def read_header(data: bytes) -> dict:
    """Поля шапки паспорта. Отказ — CopyError: не docx, нет шапки, нет поля,
    поле не годится для пути."""
    if len(data) > MAX_BYTES:
        raise CopyError("TOO_LARGE", str(len(data)))
    if not data.startswith(b"PK\x03\x04"):
        raise CopyError("NOT_DOCX")
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        info = z.getinfo("word/document.xml")
    except (zipfile.BadZipFile, KeyError):
        raise CopyError("NOT_DOCX") from None
    if info.file_size > MAX_XML_BYTES:
        raise CopyError("TOO_LARGE", "document.xml")
    try:
        root = ET.fromstring(z.read(info))
    except ET.ParseError:
        raise CopyError("NOT_DOCX") from None
    for tbl in root.iter(W + "tbl"):
        found = {}
        for tr in tbl.iter(W + "tr"):
            cells = [_cell_text(tc) for tc in tr.findall(W + "tc")]
            if len(cells) == 2 and cells[0] in HEADER_KEYS:
                found[cells[0]] = cells[1]
        if "passport_id" in found:
            break
    else:
        raise CopyError("NO_HEADER")
    for k in REQUIRED:
        if not found.get(k):
            raise CopyError("MISSING_FIELD", k)
    for k in ("passport_id", "sku_id"):
        if not SAFE.fullmatch(found[k]):
            raise CopyError("BAD_FIELD", f"{k}={found[k]}")
    if not re.fullmatch(r"[1-9][0-9]{0,5}", found["passport_version"]):
        raise CopyError("BAD_FIELD", f"passport_version={found['passport_version']}")
    return found


def copy_path(h: dict) -> str:
    pid, v = h["passport_id"], h["passport_version"]
    return f"{h['sku_id']}/{pid}/v{v}/{pid}_v{v}.docx"


def artifact_id(h: dict) -> str:
    return f"DOCX-{h['passport_id']}-v{h['passport_version']}"


def version_of(locator: str) -> int | None:
    m = VERSION_IN_PATH.search(locator or "")
    return int(m.group(1)) if m else None


# ------------------------------------------------------------------ том
class VolumeStore(ArtifactStore):
    """Том UC через Files API. Тот же путь второй раз не пишется."""

    def __init__(self, workspace, root: str = ROOT):
        self.w, self.root = workspace, root.rstrip("/")

    def _full(self, path: str) -> str:
        return path if path.startswith(self.root + "/") else f"{self.root}/{path}"

    def put(self, path: str, data: bytes) -> str:
        from databricks.sdk.errors import NotFound
        full = self._full(path)
        try:
            have = self.get(full)
        except NotFound:
            have = None
        if have is not None:
            if hashlib.sha256(have).digest() == hashlib.sha256(data).digest():
                return full          # копия уже там: прошлая загрузка не дошла до базы
            raise CopyError("COPY_EXISTS_DIFFERENT", full)
        self.w.files.upload(full, io.BytesIO(data), overwrite=False)
        return full

    def get(self, locator: str) -> bytes:
        return self.w.files.download(self._full(locator)).contents.read()


def volume_store() -> VolumeStore | None:
    """Том по секретам приложения; None — нет секции [databricks] (локально).
    Сбой создания клиента — CopyError, а не трейсбек страницы."""
    from services import collector
    try:
        w = collector.client()
    except Exception as e:  # noqa: BLE001
        raise CopyError("STORE_UNAVAILABLE", f"{type(e).__name__}: {str(e)[:160]}") from None
    return VolumeStore(w) if w is not None else None


# ------------------------------------------------------------- регистрация
def register(data: bytes, origin_name: str, *, actor: str, store: ArtifactStore, conn,
             replace: tuple[str, ...] = ()) -> Outcome:
    """Копия в том, повторное чтение, строка регистрации — одной транзакцией базы
    под блокировкой SKU. Сбой тома — откат, в базе ничего. Сбой базы после
    записи файла — файл остаётся, повторная загрузка того же файла его узнаёт.

    Один SKU — один действующий паспорт (решение владельца 21.10.2026). Если у SKU
    уже действует паспорт с другим id, без `replace` — отказ OTHER_PASSPORT_ACTIVE,
    в `active` — id действующих КОПИЙ (`DOCX-<паспорт>-v<версия>`, с версией): страница
    спрашивает «заменить?». `replace` — ровно тот набор, что человек видел; разошёлся
    хоть на одну копию (успели загрузить третий паспорт или новую версию) — снова
    вопрос, а не молчаливая замена. После замены прежние копии SKU — в OLD (архив)."""
    h = read_header(data)
    sha = hashlib.sha256(data).hexdigest()
    sku, pid, ver = h["sku_id"], h["passport_id"], int(h["passport_version"])
    aid = artifact_id(h)
    # Таблица общая с приёмом материалов Паспорта (этап 3): все запросы — только по
    # копиям docx в этом томе, чужие строки не трогаются и за дубль не считаются.
    mine = " AND mime_type = %s AND archived_locator LIKE %s"
    scope = (MIME, ROOT + "/%")
    with conn, conn.cursor() as cur:
        # Две блокировки: SKU (версии одного товара) и id паспорта (один id —
        # один товар). Порядок всегда один, взаимной блокировки нет.
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("passport_copy:" + sku,))
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("passport_copy_id:" + pid,))
        cur.execute("SELECT source_artifact_id, archived_locator FROM passport_source_artifacts"
                    " WHERE sku_id = %s AND sha256 = %s" + mine + " ORDER BY recorded_at LIMIT 1",
                    (sku, sha) + scope)
        dup = cur.fetchone()
        if dup:
            return Outcome("DUPLICATE", dup[0], dup[1], h)
        # Тот же id паспорта у другого SKU — до записи в том: иначе копия легла бы
        # в папку товара, а строка упала бы на первичном ключе (проверка #161).
        cur.execute("SELECT sku_id FROM passport_source_artifacts WHERE passport_id = %s"
                    " AND sku_id <> %s" + mine + " LIMIT 1", (pid, sku) + scope)
        other = cur.fetchone()
        if other:
            raise CopyError("PASSPORT_OTHER_SKU", f"{pid} → {other[0]}")
        cur.execute("SELECT source_artifact_id FROM passport_source_artifacts WHERE sku_id = %s"
                    " AND passport_id <> %s AND lifecycle = 'ACTIVE'" + mine, (sku, pid) + scope)
        active = tuple(sorted(r[0] for r in cur.fetchall()))
        if active and active != tuple(sorted(replace)):
            raise CopyError("OTHER_PASSPORT_ACTIVE", ", ".join(active), active)
        cur.execute("SELECT source_artifact_id, archived_locator FROM passport_source_artifacts"
                    " WHERE sku_id = %s AND passport_id = %s" + mine, (sku, pid) + scope)
        known = [(r[0], version_of(r[1])) for r in cur.fetchall()]
        if any(v == ver for _, v in known) or any(a == aid for a, _ in known):
            raise CopyError("VERSION_TAKEN", f"{pid} v{ver}")
        newest = max((v for _, v in known if v is not None), default=0)
        if newest > ver:
            raise CopyError("VERSION_OLDER", f"v{ver} < v{newest}")
        try:
            loc = store.put(copy_path(h), data)
            back = store.get(loc)
        except CopyError:
            raise
        except Exception as e:  # noqa: BLE001 — причина уходит на экран
            raise CopyError("STORE_UNAVAILABLE", f"{type(e).__name__}: {str(e)[:160]}") from None
        if hashlib.sha256(back).hexdigest() != sha:
            raise CopyError("READBACK_FAILED", loc)
        cur.execute(
            "INSERT INTO passport_source_artifacts (source_artifact_id, sku_id, passport_id, run_id,"
            " origin_locator, archived_locator, file_name, mime_type, bytes, sha256, access_result,"
            " lifecycle, registered_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ACCEPTED',"
            " 'ACTIVE', %s)",
            (aid, sku, pid, h.get("run_id") or None, origin_name or None, loc, loc.rsplit("/", 1)[-1],
             MIME, len(data), sha, actor))
        # В архив — все прежние действующие копии SKU: того же паспорта (старая
        # версия) и, при замене, подтверждённого другого.
        cur.execute("UPDATE passport_source_artifacts SET lifecycle = 'OLD'"
                    " WHERE sku_id = %s AND lifecycle = 'ACTIVE'"
                    " AND source_artifact_id <> %s" + mine + " RETURNING source_artifact_id",
                    (sku, aid) + scope)
        old = [r[0] for r in cur.fetchall()]
    return Outcome("REGISTERED", aid, loc, h, old)


def copies(sku: str):
    """Зарегистрированные копии паспорта SKU: (df, причина), как `safe_read`."""
    from services.db import safe_read
    return safe_read(
        "SELECT source_artifact_id, passport_id, archived_locator, sha256, bytes, lifecycle,"
        " registered_by, recorded_at FROM passport_source_artifacts"
        " WHERE sku_id = %(s)s AND mime_type = %(m)s ORDER BY recorded_at DESC", {"s": sku, "m": MIME})
