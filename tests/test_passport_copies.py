# -*- coding: utf-8 -*-
"""
tests/test_passport_copies.py — копия паспорта SKU в томе UC и её регистрация
(`services/passport_copies.py`, решение владельца 21.10.2026). Без сети и базы:
том и соединение подменены, docx собирается в тесте (настоящий паспорт в
публичный репозиторий не кладём).

Что заперто:
  · SKU, id паспорта и версия — из шапки файла; файл не docx, нет шапки, нет
    поля, поле с «/» или «..» — отказ с кодом, а не путь в чужую папку;
  · путь `<sku>/<passport_id>/v<версия>/<passport_id>_v<версия>.docx`;
  · копия неизменна: тот же файл второй раз — повтор без записи, другой файл
    на ту же версию — отказ, по тому же пути в томе — отказ без перезаписи;
  · новая версия переводит прежнюю копию в OLD, старая версия после новой —
    отказ;
  · сбой тома или повторного чтения — в базе ничего; сбой базы после записи
    файла — повтор того же файла его узнаёт;
  · запись под блокировкой SKU.

Запуск (pytest не нужен):  python tests/test_passport_copies.py
"""
from __future__ import annotations

import copy
import hashlib
import io
import pathlib
import re
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from databricks.sdk.errors import NotFound  # noqa: E402

from services import passport_copies as pc  # noqa: E402
from services.passport_intake import MemoryStore  # noqa: E402

FAILS: list[str] = []


def check(name: str, cond) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


def refused(fn, code: str) -> bool:
    try:
        fn()
    except pc.CopyError as e:
        return e.code == code
    except Exception:  # noqa: BLE001 — чужое исключение = не тот отказ, а не падение теста
        return False
    return False


# ------------------------------------------------------------------ docx
def docx(rows, *, extra_table_first=False, body_extra="") -> bytes:
    def tbl(rs):
        return "<w:tbl>" + "".join(
            "<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t>{c}</w:t></w:r></w:p></w:tc>" for c in r) + "</w:tr>"
            for r in rs) + "</w:tbl>"
    body = (tbl([("Поле", "Значення", "Статус")]) if extra_table_first else "") + tbl(rows) + body_extra
    xml = ('<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
           f'wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>')
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", xml)
    return b.getvalue()


def header(ver="2", sku="99601000-B", pid="PASS-99601000-B-001", state="NOT_READY", drop=()):
    rows = [("Параметр", "Значення"), ("passport_id", pid), ("passport_version", ver), ("state", state),
            ("sku_id", sku), ("run_id", "RUN-99601000-B-001")]
    return [r for r in rows if r[0] not in drop]


V2 = docx(header("2"))
V2b = docx(header("2"), body_extra="<w:p><w:r><w:t>правка</w:t></w:r></w:p>")
V3 = docx(header("3"))
V1 = docx(header("1"))

# ------------------------------------------------------------------ шапка
h = pc.read_header(V2)
check("шапка: SKU, id, версия, состояние, run_id",
      (h["sku_id"], h["passport_id"], h["passport_version"], h["state"], h["run_id"])
      == ("99601000-B", "PASS-99601000-B-001", "2", "NOT_READY", "RUN-99601000-B-001"))
check("шапка находится и во второй таблице", pc.read_header(docx(header(), extra_table_first=True))["sku_id"] == "99601000-B")
check("путь копии", pc.copy_path(h) == "99601000-B/PASS-99601000-B-001/v2/PASS-99601000-B-001_v2.docx")
check("версия из пути", pc.version_of(pc.ROOT + "/" + pc.copy_path(h)) == 2 and pc.version_of("x.docx") is None)
check("не zip — NOT_DOCX", refused(lambda: pc.read_header(b"%PDF-1.7 ..."), "NOT_DOCX"))
_z = io.BytesIO()
with zipfile.ZipFile(_z, "w") as z:
    z.writestr("a.txt", "x")
check("zip без document.xml — NOT_DOCX", refused(lambda: pc.read_header(_z.getvalue()), "NOT_DOCX"))
check("нет шапки — NO_HEADER", refused(lambda: pc.read_header(docx([("a", "b")])), "NO_HEADER"))
check("нет версии — MISSING_FIELD", refused(lambda: pc.read_header(docx(header(drop=("passport_version",)))), "MISSING_FIELD"))
check("нет SKU — MISSING_FIELD", refused(lambda: pc.read_header(docx(header(drop=("sku_id",)))), "MISSING_FIELD"))
for bad in ("../99601000-B", "99601000/B", "", ".hidden"):
    check(f"SKU «{bad}» в путь не идёт", refused(lambda b=bad: pc.read_header(docx(header(sku=b))),
                                                 "MISSING_FIELD" if not bad else "BAD_FIELD"))
check("id паспорта с «/» в путь не идёт", refused(lambda: pc.read_header(docx(header(pid="PASS/../x"))), "BAD_FIELD"))
for bad in ("0", "2a", "-1", "v2", "1.5"):
    check(f"версия «{bad}» — BAD_FIELD", refused(lambda b=bad: pc.read_header(docx(header(ver=b))), "BAD_FIELD"))
check("слишком большой файл — TOO_LARGE", refused(lambda: pc.read_header(b"PK\x03\x04" + b"0" * (pc.MAX_BYTES + 1)), "TOO_LARGE"))


# ------------------------------------------------------------- подмена базы
class FakeDB:
    """Ровно те запросы, что шлёт register(); транзакция — копия таблицы."""

    def __init__(self):
        self.rows: list[dict] = []
        self.log: list[str] = []
        self.locks: list[str] = []
        self.fail_insert = False

    def cursor(self):
        return FakeCursor(self)

    def __enter__(self):
        self._snap = copy.deepcopy(self.rows)
        return self

    def __exit__(self, et, ev, tb):
        if et is not None:
            self.rows = self._snap
        return False


class FakeCursor:
    def __init__(self, db):
        self.db, self.res = db, []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, p=()):
        db = self.db
        db.log.append(sql.split()[0] + " " + sql.split()[1])
        # Фильтр «только копии docx в томе» читается из самого запроса: нет его —
        # чужие строки приёма попадают в выборку, как попали бы в базе.
        def scoped(r, tail):
            if "mime_type = %s AND archived_locator LIKE %s" not in sql:
                return True
            mime, like = tail
            return r.get("mime_type") == mime and (r.get("archived_locator") or "").startswith(like[:-1])
        if "pg_advisory_xact_lock" in sql:
            db.locks.append(p[0])
            self.res = [(None,)]
        elif sql.startswith("SELECT") and "sha256 = %s" in sql:
            self.res = [(r["source_artifact_id"], r["archived_locator"]) for r in db.rows
                        if r["sku_id"] == p[0] and r["sha256"] == p[1] and scoped(r, p[2:])][:1]
        elif sql.startswith("SELECT source_artifact_id FROM") and "passport_id <> %s" in sql:
            # Значение lifecycle — из запроса: без фильтра «ACTIVE» сюда попали бы архивные.
            want = re.search(r"lifecycle = '(\w+)'", sql)
            self.res = sorted({(r["source_artifact_id"],) for r in db.rows
                               if r["sku_id"] == p[0] and r["passport_id"] != p[1] and scoped(r, p[2:])
                               and (want is None or r["lifecycle"] == want.group(1))})
        elif sql.startswith("SELECT sku_id"):
            self.res = [(r["sku_id"],) for r in db.rows
                        if r["passport_id"] == p[0] and r["sku_id"] != p[1] and scoped(r, p[2:])][:1]
        elif sql.startswith("SELECT") and "passport_id = %s" in sql:
            self.res = [(r["source_artifact_id"], r["archived_locator"]) for r in db.rows
                        if r["sku_id"] == p[0] and r["passport_id"] == p[1] and scoped(r, p[2:])]
        elif sql.startswith("INSERT"):
            if db.fail_insert:
                raise RuntimeError("connection reset")
            cols = sql.split("(", 1)[1].split(")", 1)[0].replace(" ", "").split(",")
            row = dict(zip(cols[:10], p[:10]))
            row.update(access_result="ACCEPTED", lifecycle="ACTIVE", registered_by=p[10])
            assert len(cols) == 13 and len(p) == 11, (cols, p)
            if any(r["source_artifact_id"] == row["source_artifact_id"] for r in db.rows):
                raise RuntimeError("duplicate key")
            db.rows.append(row)
            self.res = []
        elif sql.startswith("UPDATE"):
            # Значения lifecycle берутся из самого запроса: SET и WHERE.
            new, old = re.findall(r"lifecycle = '(\w+)'", sql)
            out = []
            for r in db.rows:
                # Фильтр по паспорту — только если он есть в самом запросе.
                by_pid = "passport_id = %s" in sql
                pp = list(p)
                pid = pp.pop(1) if by_pid else None
                if r["sku_id"] == pp[0] and (pid is None or r["passport_id"] == pid) and r["lifecycle"] == old \
                        and r["source_artifact_id"] != pp[1] and scoped(r, pp[2:]):
                    r["lifecycle"] = new
                    out.append((r["source_artifact_id"],))
            self.res = out
        else:
            raise AssertionError(sql)

    def fetchone(self):
        return self.res[0] if self.res else None

    def fetchall(self):
        return list(self.res)


class CountingStore(MemoryStore):
    """Том в памяти с локаторами, как у настоящего: под корнем тома."""

    def __init__(self):
        super().__init__()
        self.puts = 0
        self.fail_put = self.corrupt = False

    def put(self, path, data):
        self.puts += 1
        if self.fail_put:
            raise OSError("volume is read-only")
        return super().put(pc.ROOT + "/" + path, data)

    def get(self, locator):
        b = super().get(locator)
        return b + b"x" if self.corrupt else b


db, store = FakeDB(), CountingStore()
# Чужая строка той же таблицы — материал приёма Паспорта (этап 3): тот же SKU и
# паспорт, тот же SHA, ACTIVE. Её нельзя ни принять за дубль, ни увести в OLD.
FOREIGN = {"source_artifact_id": "SRC-photo-1", "sku_id": "99601000-B", "passport_id": "PASS-99601000-B-001",
           "run_id": None, "origin_locator": "photo.jpg", "archived_locator": "99601000-B/артефакти/2026-10-21/photo.jpg",
           "file_name": "photo.jpg", "mime_type": "image/jpeg", "bytes": 1, "sha256": hashlib.sha256(V2).hexdigest(),
           "access_result": "ACCEPTED", "lifecycle": "ACTIVE", "registered_by": "intake"}
db.rows.append(dict(FOREIGN))
reg = lambda data, s=None: pc.register(data, "Паспорт.docx", actor="v.tereshyn@dniprom.com",  # noqa: E731
                                        store=s or store, conn=db)

r = reg(V2)
row = db.rows[1] if len(db.rows) > 1 else {}
check("первая загрузка — REGISTERED (строка приёма с тем же SHA — не дубль), копия по пути",
      r.status == "REGISTERED" and r.locator == pc.ROOT + "/" + pc.copy_path(h) and store.files.get(r.locator) == V2)
check("строка: id, SKU, паспорт, run_id, SHA, размер, тип, автор, ACTIVE",
      row.get("source_artifact_id") == "DOCX-PASS-99601000-B-001-v2" and row.get("sku_id") == "99601000-B"
      and row.get("passport_id") == "PASS-99601000-B-001" and row.get("run_id") == "RUN-99601000-B-001"
      and row.get("sha256") == hashlib.sha256(V2).hexdigest() and row.get("bytes") == len(V2)
      and row.get("mime_type") == pc.MIME and row.get("registered_by") == "v.tereshyn@dniprom.com"
      and row.get("lifecycle") == "ACTIVE" and row.get("access_result") == "ACCEPTED"
      and row.get("origin_locator") == "Паспорт.docx")
check("запись под блокировками SKU и id паспорта, первыми запросами",
      db.log[0].startswith("SELECT pg_advisory_xact_lock") and db.log[1].startswith("SELECT pg_advisory_xact_lock")
      and db.locks[:2] == ["passport_copy:99601000-B", "passport_copy_id:PASS-99601000-B-001"])

puts = store.puts
r = reg(V2)
check("тот же файл — DUPLICATE, без второй строки и без записи в том",
      r.status == "DUPLICATE" and len(db.rows) == 2 and store.puts == puts)
check("другой файл на ту же версию — VERSION_TAKEN, ничего не записано",
      refused(lambda: reg(V2b), "VERSION_TAKEN") and len(db.rows) == 2 and store.puts == puts)
OTHER = docx(header("2", sku="99601000-B-4"))
check("тот же id паспорта у другого SKU — PASSPORT_OTHER_SKU до записи в том",
      refused(lambda: reg(OTHER), "PASSPORT_OTHER_SKU") and len(db.rows) == 2 and store.puts == puts)

r = reg(V3)
check("новая версия — REGISTERED, прежняя копия в OLD",
      r.status == "REGISTERED" and r.superseded == ["DOCX-PASS-99601000-B-001-v2"]
      and [x["lifecycle"] for x in db.rows] == ["ACTIVE", "OLD", "ACTIVE"])
check("строка приёма не тронута", db.rows[0] == FOREIGN)
check("старая версия после новой — VERSION_OLDER", refused(lambda: reg(V1), "VERSION_OLDER") and len(db.rows) == 3)

# Один SKU — один действующий паспорт (решение владельца 21.10.2026): другой id у
# того же SKU — вопрос «заменить?», ответ — те же id; прежние копии — в архив.
P2 = docx(header("1", pid="PASS-99601000-B-002"))
puts = store.puts


def asked(fn, want):
    try:
        fn()
    except pc.CopyError as e:
        return e.code == "OTHER_PASSPORT_ACTIVE" and e.active == want
    except Exception:  # noqa: BLE001
        return False
    return False


check("другой паспорт у SKU — вопрос «заменить?» с действующим id, ничего не записано",
      asked(lambda: reg(P2), ("DOCX-PASS-99601000-B-001-v3",)) and len(db.rows) == 3 and store.puts == puts)
check("ответ про прежнюю версию той же копии — снова вопрос, а не молчаливая замена",
      asked(lambda: pc.register(P2, "p2.docx", actor="a", store=store, conn=db, replace=("DOCX-PASS-99601000-B-001-v2",)),
            ("DOCX-PASS-99601000-B-001-v3",)) and len(db.rows) == 3)
r = pc.register(P2, "p2.docx", actor="a", store=store, conn=db, replace=("DOCX-PASS-99601000-B-001-v3",))
check("подтверждённая замена — REGISTERED, прежний паспорт в архиве, действует один",
      r.status == "REGISTERED" and r.superseded == ["DOCX-PASS-99601000-B-001-v3"]
      and [x["lifecycle"] for x in db.rows if x["mime_type"] == pc.MIME] == ["OLD", "OLD", "ACTIVE"])
check("строка приёма и после замены не тронута", db.rows[0] == FOREIGN)

# Два действующих паспорта (так было бы до этого правила или после сбоя): ответ
# про один не архивирует второй — вопрос заново; набор шире действующего — тоже.
db5, s5 = FakeDB(), CountingStore()
for pid_, ver_ in (("PASS-A", "1"), ("PASS-B", "1")):
    d_ = docx(header(ver_, pid=pid_))
    s5.put(pc.copy_path(pc.read_header(d_)), d_)
    db5.rows.append({"source_artifact_id": f"DOCX-{pid_}-v{ver_}", "sku_id": "99601000-B", "passport_id": pid_,
                     "archived_locator": pc.ROOT + "/" + pc.copy_path(pc.read_header(d_)), "mime_type": pc.MIME,
                     "sha256": hashlib.sha256(d_).hexdigest(), "lifecycle": "ACTIVE"})
NEWP = docx(header("1", pid="PASS-C"))
both = ("DOCX-PASS-A-v1", "DOCX-PASS-B-v1")
r5 = lambda rep: pc.register(NEWP, "c.docx", actor="a", store=s5, conn=db5, replace=rep)  # noqa: E731
check("два действующих: вопрос называет обе копии", asked(lambda: r5(()), both))
check("ответ про одну из двух — вопрос заново, ничего не в архиве",
      asked(lambda: r5(("DOCX-PASS-A-v1",)), both) and all(x["lifecycle"] == "ACTIVE" for x in db5.rows))
check("набор шире действующего — вопрос заново",
      asked(lambda: r5(both + ("DOCX-PASS-Z-v9",)), both) and len(db5.rows) == 2)
check("подтверждены обе — обе в архиве, действует одна новая",
      r5(both).status == "REGISTERED"
      and sorted(x["lifecycle"] for x in db5.rows) == ["ACTIVE", "OLD", "OLD"])
try:
    _st = reg(docx(header("2", pid="PASS-99601000-B-002"))).status
except pc.CopyError as e:
    _st = e.code
check("архивный паспорт вопроса не вызывает: новая версия действующего — без вопроса", _st == "REGISTERED")

# сбои тома: в базе ничего
db2, s2 = FakeDB(), CountingStore()
s2.fail_put = True
check("том не принял — STORE_UNAVAILABLE, строк нет",
      refused(lambda: pc.register(V2, "p.docx", actor="a", store=s2, conn=db2),
              "STORE_UNAVAILABLE") and db2.rows == [])
s2.fail_put, s2.corrupt = False, True
check("повторное чтение не сошлось — READBACK_FAILED, строк нет",
      refused(lambda: pc.register(V2, "p.docx", actor="a", store=s2, conn=db2), "READBACK_FAILED") and db2.rows == [])


# ---------------------------------------------------------------- том UC
class FakeFiles:
    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.uploads: list[tuple[str, bool]] = []

    def upload(self, path, contents, *, overwrite=None):
        self.uploads.append((path, overwrite))
        if path in self.files and not overwrite:
            raise RuntimeError("AlreadyExists")
        self.files[path] = contents.read()

    def download(self, path):
        if path not in self.files:
            raise NotFound("not found")
        return type("R", (), {"contents": io.BytesIO(self.files[path])})()


class FakeWorkspace:
    def __init__(self):
        self.files = FakeFiles()


ws = FakeWorkspace()
vs = pc.VolumeStore(ws)
loc = vs.put("99601000-B/P/v2/P_v2.docx", b"abc")
check("том: путь под корнем, загрузка без перезаписи",
      loc == pc.ROOT + "/99601000-B/P/v2/P_v2.docx" and ws.files.uploads == [(loc, False)])
check("том: повторное чтение по локатору", vs.get(loc) == b"abc")
check("том: тот же файл по тому же пути — без второй загрузки",
      vs.put("99601000-B/P/v2/P_v2.docx", b"abc") == loc and len(ws.files.uploads) == 1)
check("том: другой файл по тому же пути — COPY_EXISTS_DIFFERENT, файл цел",
      refused(lambda: vs.put("99601000-B/P/v2/P_v2.docx", b"xyz"), "COPY_EXISTS_DIFFERENT")
      and ws.files.files[loc] == b"abc")

# сбой базы после записи файла: повтор того же файла узнаёт копию
db3, ws3 = FakeDB(), FakeWorkspace()
vs3 = pc.VolumeStore(ws3)
db3.fail_insert = True
try:
    pc.register(V2, "p.docx", actor="a", store=vs3, conn=db3)
    crashed = False
except RuntimeError:
    crashed = True
check("сбой базы после записи: исключение, строк нет, файл в томе",
      crashed and db3.rows == [] and len(ws3.files.files) == 1)
db3.fail_insert = False
r = pc.register(V2, "p.docx", actor="a", store=vs3, conn=db3)
check("повтор того же файла после сбоя базы — REGISTERED без второй загрузки",
      r.status == "REGISTERED" and len(db3.rows) == 1 and len(ws3.files.uploads) == 1)

# ---------------------------------------------------------- статика страницы
# Загрузка — один блок для генератора и раздела «Паспорт SKU» (решение владельца
# 28.10.2026): components/passport_upload.py, его зовут обе страницы.
SRC = (ROOT / "components" / "passport_upload.py").read_text(encoding="utf-8")
check("обе страницы зовут один блок загрузки",
      'passport_upload.render("tg-pp", say)' in (ROOT / "pages" / "textgen.py").read_text(encoding="utf-8")
      and 'passport_upload.render("pp-up"' in (ROOT / "components" / "passport_area.py").read_text(encoding="utf-8"))
check("блок: кнопка выключена без права и право проверяется в момент нажатия",
      'disabled=not may' in SRC and 'may = auth.can("ls.textgen.accept")' in SRC
      and SRC.index('auth.require("ls.textgen.accept"') < SRC.index("pc.register("))
check("блок: SKU и версия не вводятся руками — только из шапки", "text_input" not in SRC)
check("блок: соединение закрывается", "conn.close()" in SRC.split("pc.register(", 1)[1])
ok_branch = SRC.split("else:\n            if res.status == \"DUPLICATE\":", 1)[-1].split("finally:", 1)[0]
check("блок: после сохранения Реестр перечитывается сразу (проверка #176)", "load_registry.clear()" in ok_branch)
check("блок: на странице выбранного товара чужой паспорт не сохраняется (lock_sku)",
      "may = auth.can(\"ls.textgen.accept\") and not (lock_sku and other)" in SRC
      and 'passport_upload.render("pp-up", sku_hint=r["sku"], lock_sku=True)'
      in (ROOT / "components" / "passport_area.py").read_text(encoding="utf-8"))

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
