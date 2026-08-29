# -*- coding: utf-8 -*-
"""
tests/test_card_actions.py — область действия кнопок в карточке и наверху.

Кнопки называются одинаково, а делают разное: в карточке — по ОДНОМУ
товару, наверху — по ВСЕМ принятым под фильтром. Перепутать их легко,
и цена ошибки разная в две стороны: скачать файл на 40 товаров вместо
одного — потеря времени, отправить в Amazon сорок тайтлов вместо одного —
сорок правок в чужом каталоге.

Поэтому проверяется не наличие кнопок, а именно РАЗМЕР их выборки:
файл из карточки содержит одну строку при трёх принятых, файл сверху —
три. Плюс то, что до приёмки карточные кнопки неактивны: они работают
с synthesis_changes, а до приёмки там ничего нет.

Отдельно — что карточка ПЕРЕЖИВАЕТ приёмку. Принятый черновик выпадает
из очереди разбора, и без третьего источника (принятая правка) карточка
исчезала бы сразу после «Принять», унося с собой обе кнопки.

Запуск (pytest не нужен):  python tests/test_card_actions.py
"""
from __future__ import annotations

import io
import pathlib
import sys
import types
import zipfile

import openpyxl
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import services.db                                     # noqa: E402
services.db.get_conn = lambda: type(
    "C", (), {"close": lambda self: None})()

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


MP = "es"
PAIRS = [("B0AAA", "17557000"), ("B0BBB", "17558000"), ("B0CCC", "17559000")]
# четвёртый — с черновиком, но БЕЗ приёмки: на нём проверяется, что
# карточные кнопки до приёмки неактивны
PENDING = ("B0DDD", "17560000")

CAND = pd.DataFrame([
    dict(asin=a, marketplace=MP, sku_group=sku,
         title="Dnipro-M BH-20 Martillo Percutor " * 4,
         fetched_at=pd.Timestamp("2026-08-29"), main_image=None)
    for a, sku in PAIRS + [PENDING]])
REVIEW = pd.DataFrame([dict(
    id=1, asin=PENDING[0], marketplace=MP,
    created_at=pd.Timestamp("2026-08-29"),
    title_before="Dnipro-M BH-20 Martillo " * 4,
    title_after="Martillo Percutor 17560000", highlights_after="",
    dropped="", model="claude-sonnet-5", skill_version=7,
    coverage_score=88.0)])
ACC = pd.DataFrame([
    dict(asin=a, marketplace=MP,
         before_title="Dnipro-M BH-20 Martillo " * 4,
         after_title=f"Martillo Percutor {sku}", highlights="",
         after_len=25, accepted_at=pd.Timestamp("2026-08-29"))
    for a, sku in PAIRS])
ACC_MAP = pd.DataFrame([
    dict(asin=a, marketplace=MP, accepted_at=pd.Timestamp("2026-08-29"),
         status="accepted", after_len=25, coverage_score=88.0,
         model="claude-sonnet-5", after_text=f"Martillo Percutor {sku}",
         after_extra=None)
    for a, sku in PAIRS])


def fake_sql(sql, conn, **kw):
    s = str(sql)
    # порядок веток важен: запрос очереди разбора сам ссылается
    # на synthesis_changes в NOT EXISTS, и по подстроке «DISTINCT ON»
    # он уходил бы в ветку принятых правок с чужими колонками
    if "FROM synthesis_drafts d" in s:
        return REVIEW.copy()      # черновик только у непринятого товара
    if "FROM diagnosis d" in s and "title_over_limit" in s:
        return CAND.copy()
    if "FROM synthesis_changes" in s and "before_text AS before_title" in s:
        return ACC.copy()
    if "FROM synthesis_changes" in s and "DISTINCT ON" in s:
        return ACC_MAP.copy()
    if "FROM synthesis_skill" in s:
        return pd.DataFrame([dict(scope="title_split", skill_text="м",
                                  version=7)])
    return pd.DataFrame()


pd.read_sql = fake_sql

# настоящий шаблон в репозиторий не кладётся — берём общую миниатюру,
# она проходит ровно тот же путь сборки
sys.path.insert(0, str(ROOT / "tests"))
import services.flatfile as ff                          # noqa: E402
import services.flatfile_template as ft                 # noqa: E402
from fixture_template import build as build_template    # noqa: E402

tpl = ft.parse_template("0_TEST-RANGE.xlsx", build_template())

ff.templates_for = lambda mp: [tpl] if mp == MP else []
ff.load_product_types = lambda: {(a, MP): "ABRASIVE_WHEELS"
                                 for a, _ in PAIRS + [PENDING]}
ff.load_sku_map = lambda: {(a, MP): (sku, "catalog")
                           for a, sku in PAIRS + [PENDING]}
# sku_for импортирован в services.flatfile по имени, поэтому
# подменяем связанное имя, а не исходное: иначе SKU придёт
# из карты шаблона и проверка «свой SKU» ничего не докажет
ff.sku_for = lambda tpls, asin: ("", "", "")

import services.spapi as sp                             # noqa: E402
sp.missing_secrets = lambda: []
sp.load_pushes = lambda: {}
PUSHED: list = []
sp.push_title = lambda *a, **k: PUSHED.append(a) or {
    "ok": True, "status": "ACCEPTED", "submission_id": "s", "issues": [],
    "skipped": [], "sent_highlights": False}
sp.log_push = lambda *a, **k: None

from streamlit.testing.v1 import AppTest                # noqa: E402

at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
at.switch_page("pages/synthesis.py").run()
check("страница отрисована без ошибки", not at.exception)


def by_key(prefix: str) -> list:
    return [b for b in (list(at.button) + list(at.download_button))
            if str(getattr(b, "key", "")).startswith(prefix)]


def rows_in(data: bytes) -> int:
    """Строк данных в собранном файле (или в первом файле zip)."""
    blob = data
    if data[:2] == b"PK" and b"Plantilla" not in data[:4000]:
        z = zipfile.ZipFile(io.BytesIO(data))
        inner = [n for n in z.namelist() if n.endswith((".xlsx", ".xlsm"))]
        if inner:
            blob = z.read(inner[0])
    ws = openpyxl.load_workbook(io.BytesIO(blob), read_only=True,
                                data_only=True)["Plantilla"]
    return len([r for r in ws.iter_rows(min_row=7, values_only=True)
                if any(v is not None for v in r)])


def page_module():
    """Функции страницы без вкладок: AppTest не отдаёт байты
    download_button, поэтому размер выборки проверяем на функциях —
    на том же коде, который кнопка и вызывает."""
    src = (ROOT / "pages/synthesis.py").read_text(encoding="utf-8")
    mod = types.ModuleType("syn")
    mod.__dict__["__name__"] = "syn"
    exec(compile(src[:src.index("with tab_queue:")], "syn", "exec"),
         mod.__dict__)
    return mod


syn = page_module()

# --- карточка: файл ровно по своему товару
card_dl = by_key("c-flat-B0AAA")
check("в карточке есть кнопка скачивания", len(card_dl) == 1)

one = syn.single_plan("B0AAA", MP)
check("план карточки — один товар",
      len(one) == 1 and len(one[0]["rows"]) == 1)
check("и это её собственный SKU",
      one and one[0]["rows"][0]["sku"] == "17557000")
_, _, one_bytes = ff.build_flat_export(one, "2026-08-29")
check("файл карточки содержит ОДНУ строку при трёх принятых",
      rows_in(one_bytes) == 1)

# --- верх: файл по всем принятым
top_dl = by_key("exp-flat")
check("наверху есть кнопка скачивания", len(top_dl) == 1)
allp, _bad = syn.plan_export(syn.load_accepted_titles((MP,)))
check("план сверху — все три принятых",
      sum(len(i["rows"]) for i in allp) == 3)
_, _, all_bytes = ff.build_flat_export(allp, "2026-08-29")
check("файл сверху содержит ТРИ строки", rows_in(all_bytes) == 3)

# --- подписи разводят область действия
labels = " | ".join(str(b.label) for b in top_dl + by_key("push-open"))
check("у верхних кнопок в подписи «для всех принятых»",
      "для всех принятых" in labels)
card_labels = " | ".join(str(b.label) for b in
                         card_dl + by_key("c-push-B0AAA"))
check("у карточных кнопок такой подписи нет",
      "для всех принятых" not in card_labels)

# --- отправка из карточки шлёт один товар и именно свой
send_btn = by_key("c-push-B0AAA")
check("в карточке есть кнопка отправки", len(send_btn) == 1)
if send_btn:
    send_btn[0].click().run()
    check("нажатие открывает подтверждение, а не шлёт",
          not PUSHED and any("Подтвердите отправку" in str(m.value)
                             for m in at.markdown))
    confirm = by_key("push-send-push-confirm-B0AAA")
    check("подтверждение принадлежит этой карточке", len(confirm) == 1)
    if confirm:
        confirm[0].click().run()
        check("ушёл ровно один товар", len(PUSHED) == 1)
        check("и это SKU карточки, а не первый попавшийся",
              PUSHED and PUSHED[0][0] == "17557000")

# --- до приёмки кнопки карточки неактивны
pend_dl = by_key(f"c-flat-off-{PENDING[0]}")
pend_push = by_key(f"c-push-off-{PENDING[0]}")
check("до приёмки кнопка файла неактивна", len(pend_dl) == 1)
check("до приёмки кнопка отправки неактивна", len(pend_push) == 1)
check("и обе объясняют, чего не хватает",
      all("примите правку" in str(getattr(b, "help", "") or "")
          for b in pend_dl + pend_push))
check("активных кнопок у непринятого товара нет",
      not by_key(f"c-flat-{PENDING[0]}")
      and not by_key(f"c-push-{PENDING[0]}"))
check("а «Принять» у него есть — карточка живая",
      len(by_key(f"q-acc-{PENDING[0]}")) == 1)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
