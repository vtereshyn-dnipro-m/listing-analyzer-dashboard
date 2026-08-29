# -*- coding: utf-8 -*-
"""
tests/test_history.py — история изменений по товару.

История собирается из трёх таблиц, и главная опасность здесь — тихо
соврать про то, что уже сделано с чужим листингом. Проверяется:

  · порядок: события идут от свежего к старому, вперемешку отправки
    и приёмки. Порядок тут не косметика — по нему человек понимает,
    ушла ли в Amazon последняя принятая правка или предыдущая;
  · свёрнутая строка отвечает на главный вопрос («дошло или нет») и
    честно говорит «отправок не было», когда их не было;
  · отказ Amazon не выглядит успехом;
  · число заходов до приёмки считается ПО ИНТЕРВАЛАМ между приёмками,
    а не общим счётчиком: иначе вторая приёмка унаследует все ранние
    генерации и покажет заведомо завышенное число;
  · недоступная история отличима от пустой — молчать про сбой значит
    показать «ничего не делали» вместо «не смогли прочитать».

Слова «отклонено» в истории нет намеренно: отказ нигде не сохраняется,
и сгенерированное, не ставшее правкой, отклонённым не было.

Запуск (pytest не нужен):  python tests/test_history.py
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


PAIR = ("B0AAA", "es")
T = pd.Timestamp

PUSH = pd.DataFrame([
    dict(asin="B0AAA", marketplace="es", pushed_at=T("2026-08-29 15:41"),
         before_text="Dnipro-M BH-20 Martillo", after_text="BH-20 Martillo",
         status="ACCEPTED", ok=True, submission_id="d9dbad06",
         issues=None, error=None),
    dict(asin="B0AAA", marketplace="es", pushed_at=T("2026-08-28 10:00"),
         before_text="старый", after_text="слишком длинный",
         status="INVALID", ok=False, submission_id="sub-0",
         issues="ERROR 4000001 Title too long", error=None),
])
ACC = pd.DataFrame([
    dict(asin="B0AAA", marketplace="es", accepted_at=T("2026-08-29 12:00"),
         before_text="Dnipro-M BH-20 Martillo", after_text="BH-20 Martillo",
         skill_version=7, model="claude-sonnet-5", source="manual"),
    dict(asin="B0AAA", marketplace="es", accepted_at=T("2026-08-27 09:00"),
         before_text="старый", after_text="слишком длинный",
         skill_version=6, model="claude-sonnet-5", source="ai"),
])
# четыре генерации: три до первой приёмки, одна между приёмками
DRAFTS = pd.DataFrame([
    dict(asin="B0AAA", marketplace="es", created_at=T("2026-08-26 08:00")),
    dict(asin="B0AAA", marketplace="es", created_at=T("2026-08-26 09:00")),
    dict(asin="B0AAA", marketplace="es", created_at=T("2026-08-27 08:00")),
    dict(asin="B0AAA", marketplace="es", created_at=T("2026-08-29 11:00")),
])


def make_sql(fail: bool = False):
    def q(sql, conn, **kw):
        s = str(sql)
        if fail:
            raise RuntimeError("relation does not exist")
        if "FROM listing_push_log" in s:
            return PUSH.copy()
        if "FROM synthesis_changes" in s:
            return ACC.copy()
        if "FROM synthesis_drafts" in s:
            return DRAFTS.copy()
        return pd.DataFrame()
    return q


pd.read_sql = make_sql()
import services.history as h                            # noqa: E402

h.load_history.clear()
hist = h.load_history()
ev = hist.get(PAIR) or []

check("собраны все события обеих таблиц", len(ev) == 4)
check("порядок от свежего к старому",
      [str(e["at"]) for e in ev] == sorted(
          [str(e["at"]) for e in ev], reverse=True))
check("сверху последняя отправка",
      ev[0]["kind"] == "push" and h.stamp(ev[0]["at"]) == "29.08 15:41")
check("отправки и приёмки перемешаны по времени, а не сгруппированы",
      [e["kind"] for e in ev] == ["push", "accept", "push", "accept"])

# --- заходы считаются по интервалам, а не общим счётчиком
first = [e for e in ev if e["kind"] == "accept"][-1]    # ранняя приёмка
last = [e for e in ev if e["kind"] == "accept"][0]      # свежая
check("до первой приёмки было три генерации, из них принята одна",
      first["tries"] == 2)
check("между приёмками одна генерация — заходов сверх принятой нет",
      last["tries"] == 0)
check("источник правки сохранён", last["source"] == "manual"
      and first["source"] == "ai")
check("версия методологии видна", int(last["skill_version"]) == 7)

# --- свёрнутая строка
check("свёрнутая строка про последнюю отправку",
      "29.08 15:41" in h.summary(ev) and "принято Amazon" in h.summary(ev))
check("отказ не выдаётся за успех",
      "отбито Amazon" in h.summary([e for e in ev if not e.get("ok")
                                    and e["kind"] == "push"]))
check("без отправок так и сказано",
      h.summary([e for e in ev if e["kind"] == "accept"]) == "отправок не было")
check("у товара без событий история пуста", not hist.get(("B0ZZZ", "es")))

# --- сбой чтения отличим от пустой истории
pd.read_sql = make_sql(fail=True)
h.load_history.clear()
h.st.session_state.pop(h.ERR_KEY, None) if hasattr(h.st, "session_state") else None
empty = h.load_history()
check("при сбое история пуста", not empty)
check("и сбой не выдаётся за «ничего не делали»",
      "does not exist" in (h.load_error() or ""))

# --- слова «отклонено» в текстах истории нет
sys.path.insert(0, str(ROOT))
from i18n import LANGS                                  # noqa: E402
hist_texts = " ".join(v for k, v in LANGS["ru"].items() if k.startswith("hist."))
check("в истории нет слова «отклонено»", "отклон" not in hist_texts)
check("и нет слова «черновик»", "ерновик" not in hist_texts)

# --- NaN не должен попадать в разметку: у успешной отправки issues пуст,
# а NaN в Python истинный — в строке появлялось «nan» (правило 4 проекта)
sys.path.insert(0, str(ROOT))
import types                                            # noqa: E402
pd.read_sql = lambda *a, **k: pd.DataFrame()
_src = (ROOT / "pages/synthesis.py").read_text(encoding="utf-8")
_syn = types.ModuleType("syn")
_syn.__dict__["__name__"] = "syn"
exec(compile(_src[:_src.index("with tab_queue:")], "syn", "exec"),
     _syn.__dict__)
ok_push = {"kind": "push", "at": T("2026-08-29 15:41"),
           "before": "было", "after": "стало", "status": "ACCEPTED",
           "ok": True, "submission_id": "d9dbad06", "detail": float("nan")}
html = _syn.event_html(ok_push)
check("пустая причина не превращается в «nan»", "nan" not in html.lower())
check("submissionId показан", "d9dbad06" in html)
no_sub = _syn.event_html(dict(ok_push, submission_id=float("nan")))
check("отсутствующий submissionId не рисует «nan»",
      "nan" not in no_sub.lower() and "submissionId" not in no_sub)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
