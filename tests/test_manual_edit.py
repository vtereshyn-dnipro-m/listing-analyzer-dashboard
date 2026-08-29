# -*- coding: utf-8 -*-
"""
tests/test_manual_edit.py — ручная правка тайтла в карточке результата.

Кнопка простая, но она меняет смысл записи в synthesis_changes, и здесь
легко получить тихое враньё двух видов:

  · принятый руками текст, записанный как «сгенерировано моделью» —
    тогда доля ручных правок (мера того, насколько методология попадает)
    показывает ноль при любом числе переписываний;
  · и обратное: открыл форму, ничего не изменил, нажал сохранить — это
    всё ещё «как сгенерировано», и метить такое ручной правкой значит
    портить ту же метрику с другой стороны.

Поэтому источник считается по фактическому тексту, а не по тому, что
форму открывали. Плюс проверяется, что правка проходит те же проверки
кодом, что и генерация: лимит длины руками не обходится.

Запуск (pytest не нужен):  python tests/test_manual_edit.py
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


ASIN, MP = "B0AAA", "es"
DRAFT_TITLE = "Dnipro-M BH-20 Martillo Percutor 1500W"
DRAFT_HL = "Mandril SDS-Plus, maletin incluido"

CAND = pd.DataFrame([dict(asin=ASIN, marketplace=MP, sku_group="17557000",
                          title="Dnipro-M BH-20 Martillo Percutor " * 4,
                          fetched_at=pd.Timestamp("2026-08-28"),
                          main_image=None)])
REVIEW = pd.DataFrame([dict(id=1, asin=ASIN, marketplace=MP,
                            created_at=pd.Timestamp("2026-08-29"),
                            title_before="Dnipro-M BH-20 Martillo " * 4,
                            title_after=DRAFT_TITLE,
                            highlights_after=DRAFT_HL, dropped="",
                            model="claude-sonnet-5", skill_version=7,
                            coverage_score=88.0)])

SAVED: list[dict] = []


def fake_sql(sql, conn, **kw):
    s = str(sql)
    if "FROM diagnosis d" in s and "title_over_limit" in s:
        return CAND.copy()
    if "FROM synthesis_drafts d" in s and "title_before" in s:
        return REVIEW.copy()
    if "FROM synthesis_skill" in s:
        return pd.DataFrame([dict(scope="title_split", skill_text="м",
                                  version=7)])
    return pd.DataFrame()


pd.read_sql = fake_sql


class _Cur:
    def execute(self, sql, params=None):
        if "INSERT INTO synthesis_changes" in str(sql):
            SAVED.append({"title": params[4], "highlights": params[6],
                          "source": params[-1]})

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


services.db.get_conn = lambda: _Conn()
from streamlit.testing.v1 import AppTest              # noqa: E402


def fresh():
    a = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
    a.switch_page("pages/synthesis.py").run()
    return a


def button(a, label):
    return next((b for b in a.button if label in str(b.label)), None)


def by_key(a, key):
    """Кнопка карточки результата по ключу виджета. По подписи искать
    нельзя: «Перегенерировать» есть и на вкладке разбора, и у «любого
    товара» — совпадение по тексту ничего не доказывает."""
    return next((b for b in a.button if str(getattr(b, "key", "")) == key), None)


at = fresh()
check("карточка результата отрисована", button(at, "Принять") is not None)
check("кнопка «Редактировать» есть", button(at, "Редактировать") is not None)
check("до нажатия полей ввода нет", len(at.text_area) == 0)

button(at, "Редактировать").click().run()
check("по нажатию появились два поля", len(at.text_area) == 2)
check("в поля подставлен текст черновика",
      at.text_area[0].value == DRAFT_TITLE and at.text_area[1].value == DRAFT_HL)
check("в режиме правки есть «Сохранить правку» и «Отмена»",
      button(at, "Сохранить правку") is not None
      and button(at, "Отмена") is not None)
check("«Перегенерировать» этой карточки в режиме правки убрана",
      by_key(at, f"q-re-{ASIN}-{MP}") is None)

# --- сохранение без изменений: это всё ещё «как сгенерировано»
button(at, "Сохранить правку").click().run()
check("сохранение без правок записано как ai",
      len(SAVED) == 1 and SAVED[0]["source"] == "ai")
check("текст ушёл тот же", SAVED and SAVED[0]["title"] == DRAFT_TITLE)

# --- сохранение после правки: manual
SAVED.clear()
at = fresh()
button(at, "Редактировать").click().run()
EDITED = "Martillo Percutor SDS-Plus 1500W BH-20"
at.text_area[0].set_value(EDITED).run()
check("счётчик пересчитан по новому тексту",
      any(f"{len(EDITED)}/75" in str(m.value) for m in at.markdown))
check("подписано, что уйдёт как ручная правка",
      any("ручная правка" in str(c.value) for c in at.caption))
button(at, "Сохранить правку").click().run()
check("правка записана как manual",
      len(SAVED) == 1 and SAVED[0]["source"] == "manual")
check("сохранён отредактированный текст, а не исходный",
      SAVED and SAVED[0]["title"] == EDITED)

# --- лимит длины руками не обходится
SAVED.clear()
at = fresh()
button(at, "Редактировать").click().run()
at.text_area[0].set_value("x" * 90).run()
save = button(at, "Сохранить правку")
check("при превышении лимита кнопка сохранения заблокирована",
      save is not None and save.disabled)

# --- отмена возвращает исходный вид
at = fresh()
button(at, "Редактировать").click().run()
at.text_area[0].set_value("что-то другое").run()
button(at, "Отмена").click().run()
check("после отмены полей ввода нет", len(at.text_area) == 0)
check("после отмены вернулись обычные кнопки карточки",
      by_key(at, f"q-acc-{ASIN}-{MP}") is not None
      and by_key(at, f"q-re-{ASIN}-{MP}") is not None
      and by_key(at, f"q-edit-{ASIN}-{MP}") is not None)
check("отмена ничего не сохранила", not SAVED)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
