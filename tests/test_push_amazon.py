# -*- coding: utf-8 -*-
"""
tests/test_push_amazon.py — отправка в Amazon пишет в живые листинги клиента.

Здесь важнее не «работает ли отправка», а «не срабатывает ли она сама».
Ошибка в эту сторону необратима: тайтл уже в чужом каталоге, откатывать
его придётся руками через Seller Central. Поэтому первая и главная группа
проверок — что без явного подтверждения ни одного запроса не уходит.

Дальше — правила, каждое из которых уже стоило бы отказа Amazon или, хуже,
удачной записи не туда:

  · marketplace_id берётся из загруженного шаблона Seller Central, а не
    из таблицы в коде: угаданный идентификатор рынка означает запись
    в чужую страну;
  · тайтл сверх лимита не отправляется вовсе, а Item Highlights уходят
    только вместе с укладывающимся тайтлом — политика Amazon с 27.07.2026;
  · SKU — FBM без суффикса -FBA, как в flat file;
  · журнал пишется и при успехе, и при отказе.

Запуск (pytest не нужен):  python tests/test_push_amazon.py
"""
from __future__ import annotations

import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import services.db                                     # noqa: E402
services.db.get_conn = lambda: type(
    "C", (), {"close": lambda self: None})()
pd.read_sql = lambda *a, **k: pd.DataFrame()

import requests                                        # noqa: E402
import services.spapi as sp                            # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


MP_ID = "A1RKKUPIHCS9HS"
TPL = {"item_name_attr":
       f"item_name[marketplace_id={MP_ID}][language_tag=es_ES]#1.value"}
SENT: list[dict] = []


class _Resp:
    def __init__(self, payload, code=200):
        self.status_code, self._p = code, payload
        self.text = str(payload)

    def json(self):
        return self._p


def arm(payload, code=200):
    """Подменяем сеть и запоминаем, что реально ушло."""
    SENT.clear()
    sp.st = type("S", (), {"session_state": {"spapi.token": {
        "token": "tok", "until": 9e18}}})()
    sp.cfg = lambda name, default=None: {
        "SP_API_SELLER_ID": "A2SELLER", "SP_API_CLIENT_ID": "c",
        "SP_API_CLIENT_SECRET": "s", "SP_API_REFRESH_TOKEN": "r",
    }.get(name, default)

    def patch(url, params=None, headers=None, data=None, timeout=None):
        SENT.append({"url": url, "params": params, "headers": headers,
                     "data": data})
        return _Resp(payload, code)

    requests.patch = patch


# --- marketplace_id: только из шаблона
check("marketplace_id и язык взяты из шаблона",
      sp.marketplace_meta([TPL]) == (MP_ID, "es_ES"))
check("без шаблона идентификатор не выдумывается",
      sp.marketplace_meta([]) is None
      and sp.marketplace_meta([{"item_name_attr": "item_name#1.value"}]) is None)
check("регион по маркетплейсу", sp.host_for("es").endswith("-eu.amazon.com")
      and sp.host_for("com").endswith("-na.amazon.com"))
check("неизвестный маркетплейс не получает хост", sp.host_for("zz") is None)

# --- политика Amazon 27.07.2026
patches, skipped = sp.build_patches("Título corto", "Highlights", MP_ID,
                                    "es_ES", 75, 125)
check("тайтл в лимите — один патч на item_name",
      len(patches) == 2 and patches[0]["path"] == "/attributes/item_name")
check("Item Highlights уходят как title_differentiation",
      patches[1]["path"] == "/attributes/title_differentiation")
check("операция именно replace",
      all(p["op"] == "replace" for p in patches))
check("в значении есть marketplace_id и language_tag",
      patches[0]["value"][0]["marketplace_id"] == MP_ID
      and patches[0]["value"][0]["language_tag"] == "es_ES")

over, skipped = sp.build_patches("x" * 80, "Highlights", MP_ID, "es_ES", 75, 125)
check("тайтл сверх лимита не отправляется вовсе", over == [])
check("причина отказа названа числом",
      any("80" in s and "75" in s for s in skipped))
check("вместе с длинным тайтлом Highlights тоже не уходят",
      not any(p.get("path", "").endswith("title_differentiation")
              for p in over))

long_hl, skipped_hl = sp.build_patches("Título", "y" * 200, MP_ID, "es_ES",
                                       75, 125)
check("длинные Highlights пропущены, а тайтл отправлен",
      len(long_hl) == 1 and skipped_hl)

# --- сам запрос
arm({"sku": "17586000", "status": "ACCEPTED", "submissionId": "sub-1"})
res = sp.push_title("17586000", "es", "ABRASIVE_WHEELS", "Título nuevo",
                    "Highlights", MP_ID, "es_ES", 75, 125)
check("запрос ушёл ровно один", len(SENT) == 1)
req = SENT[0] if SENT else {}
check("метод бьёт по listings/2021-08-01 и SKU",
      "/listings/2021-08-01/items/A2SELLER/17586000" in req.get("url", ""))
check("marketplaceIds в параметрах",
      (req.get("params") or {}).get("marketplaceIds") == MP_ID)
check("токен в заголовке", "x-amz-access-token" in (req.get("headers") or {}))
body = (req.get("data") or b"").decode("utf-8")
check("productType в теле", '"productType": "ABRASIVE_WHEELS"' in body)
check("ответ разобран как принятый",
      res["ok"] and res["submission_id"] == "sub-1")

# --- отказ Amazon доходит с причиной
arm({"sku": "17586000", "status": "INVALID", "submissionId": "sub-2",
     "issues": [{"code": "4000001", "message": "Title too long",
                 "severity": "ERROR"}]})
bad = sp.push_title("17586000", "es", "ABRASIVE_WHEELS", "Título", "",
                    MP_ID, "es_ES", 75, 125)
check("отказ не выдаётся за успех", not bad["ok"])
check("причина от Amazon видна целиком",
      "Title too long" in bad["error"] and "4000001" in bad["error"])

arm({"errors": [{"message": "Access denied"}]}, code=403)
denied = sp.push_title("17586000", "es", "ABRASIVE_WHEELS", "Título", "",
                       MP_ID, "es_ES", 75, 125)
check("HTTP-ошибка названа кодом и телом",
      not denied["ok"] and "403" in denied["error"]
      and "Access denied" in denied["error"])

# --- журнал пишется и при успехе, и при отказе
LOGGED: list[tuple] = []


class _Cur:
    def execute(self, sql, params=None):
        LOGGED.append((str(sql), params))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Conn:
    def cursor(self):
        return _Cur()

    def commit(self):
        pass

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


sp.get_conn = lambda: _Conn()
sp.log_push("B0AAA", "17586000", "es", "было", "стало", "hl",
            {"ok": True, "status": "ACCEPTED", "submission_id": "sub-1",
             "sent_highlights": True})
sp.log_push("B0AAA", "17586000", "es", "было", "стало", "hl",
            {"ok": False, "status": "INVALID", "error": "Title too long",
             "issues": [{"code": "1", "message": "bad"}]})
check("в журнал легли обе попытки", len(LOGGED) == 2)
check("успех записан с submissionId",
      LOGGED[0][1][6] == "sub-1" and LOGGED[0][1][8] is True)
check("отказ записан с причиной",
      LOGGED[1][1][8] is False and "Title too long" in str(LOGGED[1][1][10]))
check("Highlights в журнале только когда реально уходили",
      LOGGED[0][1][5] == "hl" and LOGGED[1][1][5] is None)

# --- секреты
sp.cfg = lambda name, default=None: None
check("без секретов отправка объявляется ненастроенной",
      not sp.configured() and len(sp.missing_secrets()) == 4)

# =========================== страница: без подтверждения не шлём
CALLS: list = []
import types                                            # noqa: E402


def load_page():
    src = open(ROOT / "pages/synthesis.py", encoding="utf-8").read()
    mod = types.ModuleType("syn")
    mod.__dict__["__name__"] = "syn"
    exec(compile(src[:src.index("with tab_queue:")], "syn", "exec"),
         mod.__dict__)
    return mod


syn = load_page()
syn.push_title = lambda *a, **k: CALLS.append(a) or {
    "ok": True, "status": "ACCEPTED", "submission_id": "s", "issues": [],
    "skipped": [], "sent_highlights": False}
syn.log_push = lambda *a, **k: None
syn.load_pushes = lambda: {}

ROW = {"sku": "17586000", "marketplace": "es", "asin": "B0AAA",
       "product_type": "ABRASIVE_WHEELS", "title": "Título nuevo",
       "before": "Título viejo largo", "highlights": "", "tpl": TPL}

# рисуем блок подтверждения, ничего не нажимая: кнопки-заглушки не нажаты
syn.st = type("S", (), {
    "session_state": {}, "markdown": staticmethod(lambda *a, **k: None),
    "container": staticmethod(lambda **k: _Ctx()),
    "selectbox": staticmethod(lambda label, opts, **k: sorted(opts)[0]),
    "caption": staticmethod(lambda *a, **k: None),
    "error": staticmethod(lambda *a, **k: None),
    "warning": staticmethod(lambda *a, **k: None),
    "checkbox": staticmethod(lambda *a, **k: True),
    "columns": staticmethod(lambda spec: [_Col(), _Col(), _Col()]),
    "button": staticmethod(lambda *a, **k: False),
    "rerun": staticmethod(lambda: None),
    "cache_data": type("C", (), {"clear": staticmethod(lambda: None)}),
})()


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Col:
    def button(self, *a, **k):
        return False


syn.render_push_confirm([ROW])
check("отрисовка подтверждения НИЧЕГО не отправляет", not CALLS)

# --- то же самое на живой странице: нажатие кнопки панели не отправляет
import services.flatfile as ff                          # noqa: E402
import services.flatfile_template as ft                 # noqa: E402

FULL_TPL = dict(TPL, slot="0_TEST", file_name="0_TEST.xlsm",
                product_types=["ABRASIVE_WHEELS"], sku_map={}, styles={},
                columns={}, partial_label="p", sheet_path="x",
                template_bytes=b"", rows_seen=0)
ff.templates_for = lambda mp: [FULL_TPL] if mp == "es" else []
ff.load_product_types = lambda: {("B0AAA", "es"): "ABRASIVE_WHEELS"}
ff.load_sku_map = lambda: {("B0AAA", "es"): ("17586000", "catalog")}
ft.sku_for = lambda tpls, asin: ("", "", "")
# сборку .xlsm подменяем: шаблон-заглушка без байтов, а проверяем
# мы отправку, не выгрузку
ff.build_flat_cached = lambda _plan, sig, day: ("f.xlsm", "m", b"x")

ACC = pd.DataFrame([dict(asin="B0AAA", marketplace="es",
                         before_title="Título viejo muy largo " * 3,
                         after_title="Título nuevo", highlights="",
                         after_len=12,
                         accepted_at=pd.Timestamp("2026-08-28"))])
CAND = pd.DataFrame([dict(asin="B0AAA", marketplace="es", sku_group="17586000",
                          title="Título viejo muy largo " * 3,
                          fetched_at=pd.Timestamp("2026-08-26"),
                          main_image=None)])
PAGE_SENT: list = []
sp.push_title = lambda *a, **k: PAGE_SENT.append(a) or {"ok": True}
sp.missing_secrets = lambda: []
sp.load_pushes = lambda: {}


def page_sql(sql, conn, **kw):
    s = str(sql)
    if "FROM diagnosis d" in s and "title_over_limit" in s:
        return CAND.copy()
    if "FROM synthesis_changes" in s and "before_text AS before_title" in s:
        return ACC.copy()
    if "FROM synthesis_skill" in s:
        return pd.DataFrame([dict(scope="title_split", skill_text="м",
                                  version=1)])
    return pd.DataFrame()


pd.read_sql = page_sql
from streamlit.testing.v1 import AppTest                # noqa: E402

at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
at.switch_page("pages/synthesis.py").run()
btn = next((b for b in at.button if "Отправить в Amazon" in str(b.label)), None)
check("кнопка отправки на панели есть", btn is not None)
check("до нажатия ничего не отправлено", not PAGE_SENT)
if btn is not None:
    btn.click().run()
    check("нажатие кнопки панели НЕ отправляет, а открывает подтверждение",
          not PAGE_SENT)
    check("подтверждение появилось",
          any("Подтвердите отправку" in str(m.value) for m in at.markdown))
    send = next((b for b in at.button
                 if "Отправить 1 тайтл" in str(b.label)), None)
    check("в подтверждении есть кнопка отправки", send is not None)
    check("и кнопка отмены",
          any("Отмена" in str(b.label) for b in at.button))
    if send is not None:
        send.click().run()
        check("отправка идёт только после подтверждения", len(PAGE_SENT) == 1)
        check("ушёл ровно тот SKU и рынок",
              PAGE_SENT and PAGE_SENT[0][0] == "17586000"
              and PAGE_SENT[0][1] == "es")

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
