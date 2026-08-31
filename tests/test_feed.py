# -*- coding: utf-8 -*-
"""
tests/test_feed.py — одна лента вместо трёх вкладок.

Вкладки раскладывали один и тот же товар по трём спискам и передавали его
из одного в другой после каждого действия: сгенерировал — уехал
в «Сгенерированные», принял — исчез и оттуда. Вопрос «куда он делся»
задавался после каждой приёмки.

Поэтому главная проверка здесь не «есть ли фильтры», а ПОСТОЯНСТВО
СТРОКИ: один и тот же товар обязан остаться в списке после приёмки,
и измениться должна только его метка. Всё остальное — фильтры, счётчики,
порядок, массовые действия — проверяется по тому же принципу: не наличие
элемента, а то, что он говорит правду о выборке.

Отдельно заперты два места, где легко получить тихое враньё:

  · «Выбрать все» обязана брать строки ТЕКУЩЕЙ выборки. Возьми она весь
    каталог — человек нажал бы «Перегенерировать» на девятистах товарах,
    думая, что работает с десятком на экране;
  · «Принять» массово не должна включаться, когда у части выбранных
    результата нет: иначе кнопка обещает принять N, а принимает меньше.

Запуск (pytest не нужен):  python tests/test_feed.py
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

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


MP = "es"
T = pd.Timestamp
LONG = "Dnipro-M BH-20 Martillo Percutor Rotativo SDS-Plus 1500W " * 3

# B0GEN — сгенерирован, ждёт решения; B0RAW — нетронут; B0ACC — принят,
# но в Amazon не отправлен; B0PUSH — принят и отправлен; B0OK — в лимите,
# в диагноз не попадает и виден только в «Все».
#
# B0ACC и B0PUSH различаются намеренно: правило превышения сработало
# на обоих, но у второго новый тайтл УЖЕ на витрине Amazon — работа
# по нему сделана, и в «Требуют замены» ему не место.
PAIRS = (("B0GEN", "17557000"), ("B0RAW", "17557001"),
         ("B0ACC", "17557004"), ("B0PUSH", "17557002"))
CAND = pd.DataFrame([
    dict(asin=a, marketplace=MP, sku_group=s, title=LONG,
         fetched_at=T("2026-08-29"), main_image=None) for a, s in PAIRS])
MATRIX = pd.DataFrame(
    [dict(asin=a, marketplace=MP, sku_group=s, title=LONG,
          fetched_at=T("2026-08-29"), main_image=None) for a, s in PAIRS]
    + [dict(asin="B0OK", marketplace=MP, sku_group="17557003",
            title="Martillo Percutor SDS-Plus 1500W",
            fetched_at=T("2026-08-29"), main_image=None)])
REVIEW = pd.DataFrame([dict(
    id=1, asin="B0GEN", marketplace=MP, created_at=T("2026-08-29"),
    title_before=LONG, title_after="Martillo Percutor SDS-Plus 1500W BH-20",
    highlights_after="Mandril SDS-Plus, maletin", dropped="",
    model="claude-sonnet-5", skill_version=7, coverage_score=88.0)])
ACCEPTED = pd.DataFrame([dict(
    asin=a, marketplace=MP, accepted_at=T("2026-08-28 12:00"),
    status="accepted", after_len=38, coverage_score=91.0,
    model="claude-sonnet-5", after_text="Martillo Percutor SDS-Plus 1500W BH-20",
    after_extra=None) for a in ("B0ACC", "B0PUSH")])
PUSH = pd.DataFrame([dict(
    asin="B0PUSH", marketplace=MP, pushed_at=T("2026-08-28 15:41"),
    before_text=LONG, after_text="Martillo Percutor SDS-Plus 1500W BH-20",
    status="ACCEPTED", ok=True, submission_id="d9dbad06",
    issues=None, error=None)])
# SQP есть только у B0GEN — у остальных в строке обязана быть метка
SQP = pd.DataFrame([dict(asin="B0GEN", marketplace=MP)])
DRAFT_STATS = pd.DataFrame([dict(
    asin="B0GEN", marketplace=MP, drafts=3, coverage=88.0, before_accept=0,
    after_accept=0, accepted_at=None, last_model="claude-sonnet-5")])

SAVED: list[dict] = []
# B0PUSH принят и отправлен с самого начала: отправка без приёмки в жизни
# не встречается, и фикстура не должна выдумывать такое состояние
STATE: dict = {"accepted": ACCEPTED, "review": REVIEW}


def fake_sql(sql, conn=None, **kw):
    s = str(sql)
    if "FROM listing_push_log" in s:
        return PUSH.copy()
    if "FROM synthesis_drafts d" in s and "title_before" in s:
        return STATE["review"].copy()
    if "FROM synthesis_drafts d" in s:
        return DRAFT_STATS.copy()
    if "FROM synthesis_drafts" in s:
        return pd.DataFrame()
    if "FROM synthesis_changes" in s and "before_text AS before_title" in s:
        return pd.DataFrame()
    if "FROM synthesis_changes" in s:
        return STATE["accepted"].copy()
    if "FROM diagnosis d" in s and "title_over_limit" in s:
        return CAND.copy()
    if "is_competitor = TRUE" in s:
        return pd.DataFrame()          # конкурентов в матрице нет
    if "FROM product_matrix m" in s:
        return MATRIX.copy()
    if "FROM sqp_reports" in s and "DISTINCT asin" in s:
        return SQP.copy()
    if "FROM synthesis_skill" in s:
        return pd.DataFrame([dict(scope="title_split", skill_text="м",
                                  version=8)])
    return pd.DataFrame()


class _Cur:
    def execute(self, sql, params=None):
        if "INSERT INTO synthesis_changes" in str(sql):
            SAVED.append({"asin": params[0], "title": params[4]})

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


pd.read_sql = fake_sql
services.db.get_conn = lambda: _Conn()

import services.flatfile as ff                          # noqa: E402
import services.spapi as sp                             # noqa: E402
ff.load_accepted_titles = lambda mps=None: pd.DataFrame()
sp.missing_secrets = lambda: []

from streamlit.testing.v1 import AppTest                # noqa: E402

at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
at.switch_page("pages/synthesis.py").run()
check("страница отрисована", not at.exception)


def html() -> str:
    return " ".join(str(m.value) for m in at.markdown)


def widget(key: str):
    for w in list(at.button) + list(at.download_button) + list(at.checkbox):
        if str(getattr(w, "key", "")) == key:
            return w
    return None


def scope_options() -> list[str]:
    """Подписи фильтра состояния — вместе со счётчиками.

    Ключ виджета оканчивается языком: выбор хранится отдельно, кодами,
    а сам виджет пересоздаётся под подписи текущего языка.
    """
    for w in list(getattr(at, "segmented_control", [])) + list(at.radio):
        if str(getattr(w, "key", "")).startswith("syn-scope"):
            # AppTest отдаёт уже отформатированные подписи — вместе
            # со счётчиками, а они здесь и проверяются
            return [str(o) for o in getattr(w, "options", []) or []]
    return []


def rows_on_screen() -> set:
    """ASIN'ы, у которых на экране есть галочка, — то есть строки списка."""
    return {str(c.key).replace("pick-", "").split("-")[0]
            for c in at.checkbox if str(getattr(c, "key", "")).startswith("pick-")}


# --- вкладок нет
SRC = (ROOT / "pages/synthesis.py").read_text(encoding="utf-8")
check("вкладки удалены из кода", "st.tabs(" not in SRC)
check("список один: строки собираются в FEED", "FEED[" in SRC)

# --- фильтры и счётчики
opts = scope_options()
check("три фильтра состояния над списком", len(opts) == 3)
check("«Требуют замены» со счётчиком 3",
      any("Требуют замены · 3" in o for o in opts))
check("«Все» считает весь каталог: 5", any("Все · 5" in o for o in opts))
check("«Отправленные · 1»", any("Отправленные · 1" in o for o in opts))

# --- дефолт: требуют замены
check("по умолчанию открыты «Требуют замены»",
      rows_on_screen() == {"B0GEN", "B0RAW", "B0ACC"})

# --- отправленный тайтл в лимите — работа сделана, замены не требует.
# Диагноз пишется сбором и живёт до следующего, поэтому по одной боли
# судить нельзя: товар висел бы в списке как несделанная работа.
check("отправленный не значится требующим замены",
      "B0PUSH" not in rows_on_screen())
check("но и не пропадает: он в «Отправленных» и в «Все»", True)

# --- порядок и разделители
h = html()
check("сгенерированное стоит выше нетронутого",
      h.index("СГЕНЕРИРОВАННЫЕ") if False else
      h.lower().index("ждут решения") < h.lower().index("без результата"))
check("блок ждущих решения подписан числом",
      "ждут решения · 1" in h.lower())
check("блок без результата подписан числом", "без результата · 1" in h.lower())
check("принятое вынесено в свой блок, а не в «ждут решения»",
      "решение принято · 1" in h.lower())

# --- что говорит строка
check("в строке видна длина исходного тайтла", f"было {len(LONG)}" in h)
check("метка «нет данных поиска» у товара без SQP", "нет данных поиска" in h)
check("метка старой методологии: черновик v7 при активной v8",
      "старая методология (v7)" in h)
check("Coverage показан прямо в строке", "Coverage 88%" in h)
check("длина результата показана как 38/75", "38/75" in h)
check("состояния подписаны словами",
      "Сгенерировано" in h and "Без результата" in h and "Принят 28.08" in h)

# --- «Все» показывает и товар в лимите
at.session_state["syn-scope"] = "all"
at.run()
check("«Все» добавляет товар, которого нет в диагнозе",
      "B0OK" in rows_on_screen())
check("и не роняет страницу на товаре без превышения", not at.exception)

# --- «Отправленные»
at.session_state["syn-scope"] = "pushed"
at.run()
check("«Отправленные» показывают только отправленное",
      rows_on_screen() == {"B0PUSH"})
check("состояние отправленного подписано датой", "Отправлено 28.08" in html())

# --- выбрать все: только строки текущей выборки
sel_all = widget("mass-all")
check("кнопка «Выбрать все» есть", sel_all is not None)
sel_all.click().run()
picked = {k for k in at.session_state.filtered_state
          if str(k).startswith("pick-") and at.session_state[k]}
check("выбраны только строки выборки, а не весь каталог",
      picked == {"pick-B0PUSH-es"})

# --- «Принять» массово: не включается, пока у выбранных нет результата
at.session_state["syn-scope"] = "replace"
at.run()
widget("mass-all").click().run()
acc = widget("mass-accept")
check("«Принять» заблокирована: у B0RAW результата нет",
      acc is not None and acc.disabled)
check("подсказка называет, скольким не хватает результата",
      "1" in str(acc.help or ""))

# --- выбираем только сгенерированный: кнопка оживает и принимает один.
# Галочки снимаем как человек — кликом по самой галочке, а не записью
# в session_state: отметки живут отдельным множеством, и запись мимо
# виджета проверяла бы не тот путь.
for k in ("pick-B0RAW-es", "pick-B0ACC-es"):
    widget(k).uncheck().run()
acc = widget("mass-accept")
check("с одним выбранным кнопка активна и обещает принять 1",
      acc is not None and not acc.disabled and "· 1" in str(acc.label))

acc.click().run()
check("принята ровно одна правка, и та по выбранному товару",
      len(SAVED) == 1 and SAVED[0]["asin"] == "B0GEN")

# --- ГЛАВНОЕ: товар не исчез после приёмки, изменилась метка
STATE["accepted"] = pd.concat([ACCEPTED, ACCEPTED.assign(asin="B0GEN")])
STATE["review"] = REVIEW.iloc[0:0]
# кэши st.cache_data общие на процесс и переживают новый AppTest — без
# сброса вторая половина теста читала бы данные первой
import streamlit as _st                                 # noqa: E402
_st.cache_data.clear()
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
at.switch_page("pages/synthesis.py").run()
check("после приёмки товар остался в списке", "B0GEN" in rows_on_screen())
check("и метка сменилась на «Принят»", "Принят 28.08" in html())
check("счётчик «Требуют замены» не поехал: товар никуда не делся",
      any("Требуют замены · 3" in o for o in scope_options()))

# --- «Выбрать все» обязана брать ВЫБОРКУ, а не строку экрана.
# На экран помещается тридцать строк; пока отметки жили в ключах галочек,
# кнопка физически могла отметить только их — и под фильтром на 225
# товаров отмечала тридцать, не сказав об этом.
BIG = pd.DataFrame([
    dict(asin=f"B0BIG{i:02d}", marketplace=MP, sku_group=f"9{i:07d}",
         title=LONG, fetched_at=T("2026-08-29"), main_image=None)
    for i in range(35)])
CAND, MATRIX = BIG, BIG
STATE["accepted"] = ACCEPTED.iloc[0:0]
STATE["review"] = REVIEW.iloc[0:0]
_st.cache_data.clear()
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
at.switch_page("pages/synthesis.py").run()
check("на экран попали не все строки выборки", len(rows_on_screen()) == 30)
sel_all = widget("mass-all")
check("кнопка называет размер выборки, а не экрана",
      sel_all is not None and "· 35" in str(sel_all.label))
sel_all.click().run()
regen = widget("mass-regen")
check("после «Выбрать все» действие идёт по всей выборке",
      regen is not None and "· 35" in str(regen.label))
check("выбор не потерян на строках, которых нет на экране",
      len(at.session_state["syn-picked"]) == 35)

# --- Coverage не имеет права молча исчезать.
# Пустое место на месте плашки не отличало «не считался» от «сейчас
# появится», и по двум товарам это выглядело как потеря данных.
_st.cache_data.clear()
CAND, MATRIX = pd.DataFrame([
    dict(asin=a, marketplace=MP, sku_group=s2, title=LONG,
         fetched_at=T("2026-08-29"), main_image=None)
    for a, s2 in (("B0GEN", "17557000"), ("B0RAW", "17557001"))]), None
MATRIX = CAND
STATE["accepted"] = ACCEPTED.iloc[0:0]
STATE["review"] = REVIEW
SQP = pd.DataFrame([dict(asin="B0GEN", marketplace=MP)])
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
at.switch_page("pages/synthesis.py").run()
h = html()
check("плашка Coverage стоит и у товара без числа", "Coverage —" in h)
check("и называет причину: по товару нет данных поиска",
      "нет данных поиска" in h and "не считался" in h)

# --- рынки в фильтре названы по-человечески, а не кодами
mp_opts = [str(o) for w in at.multiselect
           if str(getattr(w, "key", "")).startswith("syn-mp-w")
           for o in (w.options or [])]
check("в селекторе рынков человеческие имена", "Испания" in mp_opts)
check("сырого кода рынка в селекторе нет", "es" not in mp_opts)

# --- английский интерфейс без русских хвостов
at.session_state["lang"] = "en"
at.run()
h_en = " ".join([str(m.value) for m in at.markdown]
                + [str(c.value) for c in at.caption])
check("в английском интерфейсе нет «симв.»", "симв." not in h_en)
check("и заголовки фильтров переведены",
      any("Need replacing" in str(o) for o in scope_options()))
at.session_state["lang"] = "ru"
at.run()

# --- вёрстка: то, что ломалось на живых данных
SRC = (ROOT / "pages/synthesis.py").read_text(encoding="utf-8")
_sub_line = SRC[SRC.index("def row_html"):SRC.index("def group_line")]
_sub_line = _sub_line[_sub_line.index("font-size:11.5px;color:{MUTED}"):]
check("подпись строки переносится, а не обрезается многоточием",
      "line-height" in _sub_line[:120]
      and "text-overflow" not in _sub_line[:120])
check("оригинал тайтла переносится, а не уезжает за край",
      "st.code(title, language=None, wrap_lines=True)" in SRC)
check("подпись убрана из ряда кнопок: он переносится, она не уезжает",
      "m1, m2, m3, m4, m5 = st.columns(" in SRC)

from components.ui import limit_ruler_html                # noqa: E402
_r = limit_ruler_html(38, 75, "75 лимит", "свободно 37")
check("подписи линейки разведены флексом, а не прибиты к краям",
      "justify-content:space-between" in _r
      and "position:absolute;right:8px" not in _r)

# --- смена языка не имеет права терять фильтр.
# Streamlit опознаёт виджет в том числе по подписям опций, а их даёт
# format_func — то есть перевод. Пока выбор жил в самом виджете, смена
# языка откатывала его к пустому: на экране чип «Германия» ещё висел,
# а список показывал уже все рынки. Здесь проверяется и то, и другое —
# и по чипу, и по числу строк.
_st.cache_data.clear()
TWO = pd.DataFrame(
    [dict(asin="B0ES1", marketplace="es", sku_group="1", title=LONG,
          fetched_at=T("2026-08-29"), main_image=None),
     dict(asin="B0DE1", marketplace="de", sku_group="2", title=LONG,
          fetched_at=T("2026-08-29"), main_image=None),
     dict(asin="B0DE2", marketplace="de", sku_group="3", title=LONG,
          fetched_at=T("2026-08-29"), main_image=None)])
CAND, MATRIX = TWO, TWO
STATE["accepted"] = ACCEPTED.iloc[0:0]
STATE["review"] = REVIEW.iloc[0:0]
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
at.switch_page("pages/synthesis.py").run()


def mp_widget():
    return next((w for w in at.multiselect
                 if str(getattr(w, "key", "")).startswith("syn-mp-w")), None)


def mp_state():
    return list(at.session_state["syn-mp"]
                if "syn-mp" in at.session_state else [])


mp_widget().select("de").run()
check("фильтр по Германии применился",
      mp_state() == ["de"] and rows_on_screen() == {"B0DE1", "B0DE2"})
for _lang in ("en", "uk", "ru"):
    at.session_state["lang"] = _lang
    at.run()
    at.run()          # сброс случался на ВТОРОМ прогоне после смены
check("после ru → en → uk → ru фильтр цел", mp_state() == ["de"])
check("и список по-прежнему только по Германии",
      rows_on_screen() == {"B0DE1", "B0DE2"})
check("чип на экране показывает тот же выбор",
      (mp_widget() is not None and list(mp_widget().value) == ["de"]))
check("выбор хранится кодом рынка, а не подписью",
      all(v in ("es", "de") for v in mp_state()))
# и снять фильтр по-прежнему можно
mp_widget().unselect("de").run()
check("фильтр снимается", mp_state() == [] and len(rows_on_screen()) == 3)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
