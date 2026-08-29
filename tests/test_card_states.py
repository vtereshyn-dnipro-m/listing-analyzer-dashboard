# -*- coding: utf-8 -*-
"""
tests/test_card_states.py — основная кнопка показывает СЛЕДУЮЩИЙ шаг.

До этого на карточке было пять кнопок почти одного веса, а «Принять»
оставалась оранжевой даже у товара, который уже принят и отправлен, —
то есть основная кнопка предлагала сделать сделанное.

Правило одно: основная кнопка всегда ровно одна и всегда показывает,
что делать дальше.

  · не принят          → «Принять», выгрузка неактивна: выгружать нечего;
  · принят, не отправлен → «Отправить в Amazon», «Принять» вторичная
                            с отметкой даты;
  · принят и отправлен → основной нет, следующего шага не осталось;
                          правка и перегенерация доступны.

Проверяется по protobuf кнопки, а не по подписи: подписи по условию
задачи не менялись, изменился вес.

Запуск (pytest не нужен):  python tests/test_card_states.py
"""
from __future__ import annotations

import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import services.db                                     # noqa: E402
services.db.get_conn = lambda: type(
    "C", (), {"close": lambda self: None})()

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


import services.flatfile as ff                          # noqa: E402
import services.flatfile_template as ft                 # noqa: E402
import services.spapi as sp                             # noqa: E402
from fixture_template import build as build_template    # noqa: E402

TPL = ft.parse_template("0_TEST.xlsx", build_template())
PAIRS = {"B0NEW": "111", "B0ACC": "222", "B0PUSH": "333"}
MP = "es"
T = pd.Timestamp

ff.templates_for = lambda mp: [TPL]
ff.load_product_types = lambda: {(a, MP): "ABRASIVE_WHEELS" for a in PAIRS}
ff.load_sku_map = lambda: {(a, MP): (s, "catalog") for a, s in PAIRS.items()}
ff.sku_for = lambda tpls, asin: ("", "", "")
ff.build_flat_cached = lambda _p, sig, day: ("f.xlsx", "m", b"x")
sp.missing_secrets = lambda: []
sp.load_pushes = lambda: {}

CAND = pd.DataFrame([
    dict(asin=a, marketplace=MP, sku_group=s,
         title="Dnipro-M Martillo Percutor " * 5,
         fetched_at=T("2026-08-29"), main_image=None)
    for a, s in PAIRS.items()])
REVIEW = pd.DataFrame([dict(
    id=1, asin="B0NEW", marketplace=MP, created_at=T("2026-08-29"),
    title_before="было " * 20, title_after="Martillo Percutor 1500W",
    highlights_after="", dropped="", model="claude-sonnet-5",
    skill_version=8, coverage_score=88.0)])
ACCEPTED = pd.DataFrame([
    dict(asin=a, marketplace=MP, accepted_at=T("2026-08-28 12:00"),
         status="accepted", after_len=23, coverage_score=88.0,
         model="claude-sonnet-5", after_text="Martillo Percutor 1500W",
         after_extra=None)
    for a in ("B0ACC", "B0PUSH")])
ACC_TITLES = pd.DataFrame([
    dict(asin=a, marketplace=MP, before_title="было " * 10,
         after_title="Martillo Percutor 1500W", highlights="",
         after_len=23, accepted_at=T("2026-08-28"))
    for a in ("B0ACC", "B0PUSH")])
PUSH = pd.DataFrame([dict(
    asin="B0PUSH", marketplace=MP, pushed_at=T("2026-08-28 15:41"),
    before_text="было", after_text="Martillo Percutor 1500W",
    status="ACCEPTED", ok=True, submission_id="d9dbad06",
    issues=None, error=None)])


def fake_sql(sql, conn=None, **kw):
    s = str(sql)
    if "FROM listing_push_log" in s:
        return PUSH.copy()
    if "FROM synthesis_drafts d" in s and "title_before" in s:
        return REVIEW.copy()
    if "FROM synthesis_drafts" in s:
        return pd.DataFrame()
    if "FROM synthesis_changes" in s and "before_text AS before_title" in s:
        return ACC_TITLES.copy()
    if "FROM synthesis_changes" in s and "skill_version, model, source" in s:
        return ACCEPTED.assign(source="ai")
    if "FROM synthesis_changes" in s:
        return ACCEPTED.copy()
    if "FROM diagnosis d" in s and "title_over_limit" in s:
        return CAND.copy()
    if "FROM synthesis_skill" in s:
        return pd.DataFrame([dict(scope="title_split", skill_text="м",
                                  version=8)])
    return pd.DataFrame()


pd.read_sql = fake_sql
from streamlit.testing.v1 import AppTest                # noqa: E402

at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
at.switch_page("pages/synthesis.py").run()
check("страница отрисована", not at.exception)


def widget(key: str):
    for b in list(at.button) + list(at.download_button):
        if str(getattr(b, "key", "")) == key:
            return b
    return None


def weight(b) -> str:
    """primary / secondary — вес кнопки из protobuf, не из подписи."""
    if b is None:
        return "нет"
    return str(getattr(getattr(b, "proto", None), "type", "") or "secondary")


def card(asin: str) -> dict:
    return {
        "accept": widget(f"q-acc-{asin}-{MP}"),
        "edit": widget(f"q-edit-{asin}-{MP}"),
        "regen": widget(f"q-re-{asin}-{MP}"),
        "flat": widget(f"c-flat-{asin}-{MP}")
                or widget(f"c-flat-off-{asin}-{MP}"),
        "push": widget(f"c-push-{asin}-{MP}")
                or widget(f"c-push-off-{asin}-{MP}"),
    }


def primaries(c: dict) -> list[str]:
    return [k for k, b in c.items() if weight(b) == "primary"]


# --- не принят
new = card("B0NEW")
check("не принят: основная — «Принять»", primaries(new) == ["accept"])
check("не принят: выгрузка неактивна",
      new["flat"].disabled and new["push"].disabled)
check("не принят: подсказка объясняет, чего не хватает",
      "примите правку" in str(new["flat"].help or ""))

# --- принят, не отправлен
acc = card("B0ACC")
check("принят: основная — «Отправить в Amazon»", primaries(acc) == ["push"])
check("принят: «Принять» стала вторичной",
      weight(acc["accept"]) == "secondary")
check("принят: выгрузка доступна",
      not acc["flat"].disabled and not acc["push"].disabled)

# --- принят и отправлен
pushed = card("B0PUSH")
check("отправлен: основных кнопок нет", primaries(pushed) == [])
check("отправлен: правка и перегенерация доступны",
      pushed["edit"] is not None and pushed["regen"] is not None
      and not pushed["edit"].disabled and not pushed["regen"].disabled)

# --- отметки состояния
caps = [str(c.value) for c in at.caption]
check("у принятого есть отметка с датой",
      any("Принято 28.08" in c for c in caps))
check("у отправленного — строка статуса с временем и ответом Amazon",
      any("Отправлено 28.08 15:41" in c and "принято Amazon" in c
          for c in caps))

# --- группы и их порядок
SRC = (ROOT / "pages/synthesis.py").read_text(encoding="utf-8")
mds = [str(m.value) for m in at.markdown]
check("группы подписаны",
      any("Решение по тексту" in m for m in mds)
      and any("Выгрузка" in m for m in mds))
check("между группами есть черта", any("border-top:1px solid" in m
                                       for m in mds))
check("группа выгрузки с отступом", any("padding-left:14px" in m for m in mds))
check("история переехала под кнопки выгрузки",
      SRC.index("def render_card_actions") < SRC.index("render_history(asin, mp)")
      < SRC.index("def step_writer"))

# --- плотность: кнопки жмутся к содержимому, а не к доле колонки
css = " ".join(m for m in mds if "stColumn" in m)
check("колонка сжимается по содержимому, а не делит ширину",
      "flex:0 0 auto !important" in css)
check("кнопка не растягивается на всю колонку",
      "width:auto !important" in css and "width:100%" not in css)
check("подпись кнопки не переносится", "white-space:nowrap !important" in css)
check("последняя колонка забирает остаток",
      "flex:1 1 auto !important" in css)
check("на узком окне ряд переносится, а не уезжает за край",
      "flex-wrap:wrap" in css)
check("верхняя панель собрана тем же приёмом",
      ".st-key-exp_bar" in css)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
