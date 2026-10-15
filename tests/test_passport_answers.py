# -*- coding: utf-8 -*-
"""
tests/test_passport_answers.py — ответ на вопрос Верификатора (этап 4а).

Ответ — неизменяемый артефакт, и всё, что здесь проверяется, ломается тихо:

1. Двойное нажатие — один ответ, а не два (ТЗ 11.6): тот же ключ
   идемпотентности возвращает уже записанный ответ.
2. Исправление — новая версия `A-<question_id>-<NNN>` со ссылкой на
   предыдущую; прежняя не перезаписывается (06E, ТЗ 11.6).
3. Отправленный ответ показывается «ожидает проверки», а не снова
   «Требуется ответ», — хотя статус вопроса меняет Собиратель, не экран.
   Проверенный, но ещё не применённый — тоже не «решён».
4. Решение по конфликту — только четыре значения и только у владельца
   данных; без полномочий — пояснение без решения (ТЗ 11.4.3, 11.9).
5. Вопрос, требующий документа, без хранилища не отправить — и это
   сказано словами, а не молчащей кнопкой.
6. Паспорт сменился после вопроса — отправка закрыта (ТЗ 11.9).
7. Флаг выключен — кнопка выключена и называет флаг; флаг включён — ответ
   уходит в базу, поле очищается, на экране номер ответа.

База подменена целиком, сеть не трогается.

Запуск (pytest не нужен):  python tests/test_passport_answers.py
"""
from __future__ import annotations

import json
import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


TS = pd.Timestamp("2026-10-15 10:00", tz="UTC")
SHA = "a" * 64

# ------------------------------------------------------------ поддельная база
DB = {"answers": [], "verdicts": []}


def q_row(qid, qtype="ANSWER", status="SENT", role="PASSPORT_ADMIN", evidence=False, sku="54225000",
          run="RUN-54225000-001", conflict=None):
    return dict(question_id=qid, run_id=run, sku_id=sku, product_version="1.0", passport_id=f"PSP-{sku}",
                question_type=qtype, status=status, impact="REQUIRED_FOR_READINESS", block_id=None,
                responsible_role=role, responsible_user=None, question_text=f"Вопрос {qid}",
                reason_text="причина", affected_object="weight", expected_answer="число",
                closure_criterion="значение", evidence_required=evidence, due_at=None,
                conflict=json.dumps(conflict) if conflict else None, created_at=TS, updated_at=TS)


QUESTIONS = [
    q_row("Q-RUN-54225000-001-001"),
    q_row("Q-RUN-54225000-001-002", qtype="DOCUMENT"),
    q_row("Q-RUN-54225000-001-003", qtype="CONFLICT",
          conflict={"current": {"value": "7,5 кг", "source": "карточка"},
                    "new": {"value": "8,2 кг", "source": "21680000.pdf, с. 4"}}),
]
RUNS = pd.DataFrame([dict(run_id="RUN-54225000-001",
                          run_state=json.dumps({"pinned_product_truth": {"sha256": SHA}}))])
OBJECTS = pd.DataFrame([dict(passport_id="PSP-54225000", lineage_id="L", sku_id="54225000", product_version="1.0",
                             product_name="Степлер", model="CC-36", state="NOT_READY", passport_version="1",
                             sha256=SHA, storage_path=None, materials_url=None, limitations="[]",
                             last_event_type="x", last_event_at=TS, readback_sha256=SHA, readback_at=TS)])


def fake_sql(sql, con=None, params=None, **kw):
    q = " ".join(str(sql).split())
    if "to_regclass" in q:
        return pd.DataFrame([{"t": (params or {}).get("n")}])
    if "FROM passport_questions" in q and "FROM ai_runs" not in q:
        return pd.DataFrame(QUESTIONS)
    if "FROM passport_answers" in q:
        return pd.DataFrame(DB["answers"], columns=["answer_id", "question_id", "answer_version",
                                                    "supersedes_answer_id", "author", "answer_text",
                                                    "decision", "source_artifact_ids", "created_at"])
    if "FROM passport_answer_verdicts" in q:
        return pd.DataFrame(DB["verdicts"], columns=["answer_id", "seq", "verdict", "reason", "created_at"])
    if "FROM ai_runs" in q and "run_state" in q:
        return RUNS.copy()
    if "FROM passport_objects" in q:
        return OBJECTS.copy()
    return pd.DataFrame()


class _Cur:
    def __init__(self):
        self.row = None

    def execute(self, sql, params=None):
        q = " ".join(sql.split())
        if q.startswith("SELECT question_id FROM passport_questions"):
            self.row = (params[0],) if any(x["question_id"] == params[0] for x in QUESTIONS) else None
        elif q.startswith("SELECT answer_id FROM passport_answers WHERE idempotency_key"):
            hit = [a for a in DB["answers"] if a["idempotency_key"] == params[0]]
            self.row = (hit[0]["answer_id"],) if hit else None
        elif q.startswith("SELECT COALESCE(MAX(answer_version), 0)"):
            vs = [a["answer_version"] for a in DB["answers"] if a["question_id"] == params[0]]
            self.row = (max(vs) if vs else 0,)
        elif q.startswith("INSERT INTO passport_answers"):
            aid, qid, ver, sup, author, text, dec, key = params
            if not any(a["idempotency_key"] == key for a in DB["answers"]):
                DB["answers"].append(dict(answer_id=aid, question_id=qid, answer_version=ver,
                                          supersedes_answer_id=sup, author=author, answer_text=text,
                                          decision=dec, source_artifact_ids="[]", created_at=TS,
                                          idempotency_key=key))
        else:
            raise AssertionError("неожиданный SQL: " + q[:80])

    def fetchone(self):
        return self.row

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


class _Conn:
    def cursor(self):
        return _Cur()

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


pd.read_sql = fake_sql
import services.db as db                                   # noqa: E402
db.get_conn = lambda: _Conn()
import services.kdb as kdb                                 # noqa: E402
kdb.get_conn = lambda: (_ for _ in ()).throw(RuntimeError("Кабинет в тесте не нужен"))

import services.passport as pp                             # noqa: E402
import services.passport_answers as pa                     # noqa: E402
import streamlit as st                                     # noqa: E402
from streamlit.testing.v1 import AppTest                   # noqa: E402

ADMIN, CM, APPROVER = pp.CANONICAL_ROLES["admin"], pp.CANONICAL_ROLES["content_manager"], pp.CANONICAL_ROLES["approver"]
Q = {r["question_id"]: pd.Series(r) for r in QUESTIONS}
A1, DOC, CONF = "Q-RUN-54225000-001-001", "Q-RUN-54225000-001-002", "Q-RUN-54225000-001-003"


def errs(qid, text="ответ", decision=None, roles=ADMIN, state=pp.NEEDS_ANSWER, stale=False, email=""):
    return pa.check(Q[qid], user_state=state, text=text, decision=decision, email=email,
                    canonical_roles=roles, stale=stale)


# ================================================================ правила
check("обычный ответ ответственного проходит", errs(A1) == [])
check("пустой ответ — EMPTY", errs(A1, text="  ") == ["EMPTY"])
check("закрытый вопрос не принимает ответ", "NOT_OPEN" in errs(A1, state=pp.RESOLVED))
check("ожидающий проверки — тоже нет", "NOT_OPEN" in errs(A1, state=pp.AWAITING_CHECK))
check("уточнение и отклонённый ответ — можно ответить снова",
      errs(A1, state=pp.NEEDS_CLARIFICATION) == [] and errs(A1, state=pp.ANSWER_REJECTED) == [])
check("не ответственный — NOT_RESPONSIBLE", "NOT_RESPONSIBLE" in errs(A1, roles=CM))
by_mail = Q[A1].copy()
by_mail["responsible_role"], by_mail["responsible_user"] = None, "X@dniprom.com"
check("ответственный по почте — может, и регистр почты не важен",
      pa.check(by_mail, user_state=pp.NEEDS_ANSWER, text="x", decision=None, email="x@dniprom.com",
               canonical_roles=CM, stale=False) == [])
check("Паспорт сменился после вопроса — STALE", "STALE" in errs(A1, stale=True))
check("5. вопрос «документ» без хранилища — EVIDENCE_NEEDS_STORAGE", "EVIDENCE_NEEDS_STORAGE" in errs(DOC))
ev = Q[A1].copy()
ev["evidence_required"] = True
check("5. обычный вопрос с обязательным доказательством — тоже",
      "EVIDENCE_NEEDS_STORAGE" in pa.check(ev, user_state=pp.NEEDS_ANSWER, text="x", decision=None, email="",
                                            canonical_roles=ADMIN, stale=False))
check("10 001 знак — TOO_LONG", "TOO_LONG" in errs(A1, text="я" * 10_001))
check("решение у обычного вопроса — BAD_DECISION", "BAD_DECISION" in errs(A1, decision="ACCEPT_NEW"))
owner_q = Q[CONF].copy()
owner_q["responsible_role"] = "PRODUCT_OWNER"
check("4. конфликт: владелец данных, назначенный ответственным, решает без пояснения",
      pa.check(owner_q, user_state=pp.NEEDS_ANSWER, text="", decision="ACCEPT_NEW", email="",
               canonical_roles=APPROVER, stale=False) == [])
check("4. конфликт: решение без полномочий — NO_DECISION_AUTHORITY",
      "NO_DECISION_AUTHORITY" in errs(CONF, text="", decision="ACCEPT_NEW", roles=CM))
check("4. конфликт: пояснение без решения — можно", errs(CONF, text="на коробке 8,2", decision=None) == [])
check("4. конфликт: решение вне четырёх — BAD_DECISION", "BAD_DECISION" in errs(CONF, decision="MERGE"))
check("4. решения — ровно четыре из ТЗ 11.4.3",
      pa.DECISIONS == ("KEEP_CURRENT", "ACCEPT_NEW", "KEEP_DISPUTED", "NOT_APPLICABLE"))

k1 = pa.idempotency_key(A1, None, "u", "ответ", None)
check("1. ключ стабилен", k1 == pa.idempotency_key(A1, None, "u", " ответ ", None))
check("1. новая версия поверх прежней — другой ключ", k1 != pa.idempotency_key(A1, "A-x-001", "u", "ответ", None))
check("1. другой текст — другой ключ", k1 != pa.idempotency_key(A1, None, "u", "иначе", None))

# запись
aid, rep = pa.submit(_Conn(), Q[A1], author="v.tereshyn@dniprom.com", text="7,5 кг", decision=None, base_answer_id=None)
check(f"2. первая версия — A-<question_id>-001 ({aid})", aid == f"A-{A1}-001" and not rep)
aid2, rep2 = pa.submit(_Conn(), Q[A1], author="v.tereshyn@dniprom.com", text="7,5 кг", decision=None, base_answer_id=None)
check("1. двойное нажатие — тот же ответ, второй строки нет", aid2 == aid and rep2 and len(DB["answers"]) == 1)
aid3, _ = pa.submit(_Conn(), Q[A1], author="v.tereshyn@dniprom.com", text="8,2 кг", decision=None, base_answer_id=aid)
check("2. исправление — новая версия 002 со ссылкой на прежнюю, прежняя цела",
      aid3 == f"A-{A1}-002" and DB["answers"][1]["supersedes_answer_id"] == aid and DB["answers"][0]["answer_text"] == "7,5 кг")
try:
    pa.submit(_Conn(), pd.Series({"question_id": "Q-NOPE-001"}), author="u", text="x", decision=None, base_answer_id=None)
    check("неизвестный вопрос — ошибка, а не тихая запись", False)
except LookupError:
    check("неизвестный вопрос — ошибка, а не тихая запись", True)

# состояние после ответа
answers = pd.DataFrame(DB["answers"])
check("3. отправленный, ещё не проверенный ответ — «ожидает проверки», не «Требуется ответ»",
      pp.user_state(Q[A1], answers, pd.DataFrame(columns=["answer_id", "seq", "verdict"])) == pp.AWAITING_CHECK)
check("3. проверенный, но вопрос ещё не закрыт Собирателем — не «решён»",
      pp.user_state(Q[A1], answers, pd.DataFrame([dict(answer_id=aid3, seq=1, verdict="VERIFIED")])) == pp.AWAITING_CHECK)
check("3. уточнение по последней версии — «Нужно уточнение»",
      pp.user_state(Q[A1], answers, pd.DataFrame([dict(answer_id=aid3, seq=1, verdict="PARTIAL")])) == pp.NEEDS_CLARIFICATION)
check("3. вопрос без ответа — «Требуется ответ»",
      pp.user_state(Q[CONF], answers, pd.DataFrame(columns=["answer_id", "seq", "verdict"])) == pp.NEEDS_ANSWER)

# устаревший вопрос
check("6. снимок вопроса совпадает с Паспортом — не устарел", not pa.is_stale(Q[A1], RUNS, OBJECTS))
moved = OBJECTS.copy()
moved["sha256"] = "b" * 64
check("6. Паспорт сменил SHA после вопроса — устарел", pa.is_stale(Q[A1], RUNS, moved))
check("6. снимка нет — судить не по чему, не запираем", not pa.is_stale(Q[A1], RUNS.iloc[0:0], OBJECTS))

src = (ROOT / "services" / "passport_answers.py").read_text(encoding="utf-8")
check("в passport_questions ответ не пишет: статус вопроса меняет Собиратель",
      "UPDATE passport_questions" not in src and "INSERT INTO passport_questions" not in src)

# ================================================================ экран
DB["answers"].clear()


def page(**state):
    st.cache_data.clear()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=240).run()
    at.switch_page("pages/content.py")
    for k, v in {"pp-tab": "verifier", **state}.items():
        at.session_state[k] = v
    return at.run()


at = page(**{"pp-question": A1})
check("вкладка Верификатора с формой ответа открывается", not at.exception)
send = next((b for b in at.button if b.key == f"pp-send-{A1}"), None)
check("7. флаг выключен — «Отправить ответ» выключена", send is not None and send.disabled)
check("7. и флаг назван текстом", any("listing_suite.verifier_answers" in str(c.value) for c in at.caption))

at = page(**{"pp-question": DOC})
check("5. у вопроса «документ» причина сказана словами",
      any("хранилищем" in str(w.value) for w in at.warning))

at = page(**{"pp-question": CONF})
labels = [str(o.content) for w in at.get("button_group") if str(getattr(w, "key", "")).startswith(f"pp-dec-{CONF}")
          for o in w.proto.options]
check(f"4. у конфликта четыре решения подписями ТЗ ({labels})",
      labels == ["Оставить текущее значение", "Принять новое значение", "Сохранить как спорное",
                 "Не относится к этому SKU / scope"])
check("4. обе стороны конфликта на экране", any("8,2 кг" in str(c.value) for c in at.caption)
      and any("7,5 кг" in str(c.value) for c in at.caption))

# флаг включён: ответ уходит в базу, поле очищается
_real = pp.flag_on
pp.flag_on = lambda name: True if name == "listing_suite.verifier_answers" else _real(name)
at = page(**{"pp-question": A1})
box = next(w for w in at.text_area if str(w.key).startswith(f"pp-ans-{A1}-"))
box.set_value("Вес нетто 8,2 кг по инструкции").run()
send = next(b for b in at.button if b.key == f"pp-send-{A1}")
check("7. флаг включён и ответ заполнен — кнопка включена", not send.disabled)
send.click().run()
check(f"7. ответ записан в базу ({[a['answer_id'] for a in DB['answers']]})",
      len(DB["answers"]) == 1 and DB["answers"][0]["answer_text"] == "Вес нетто 8,2 кг по инструкции")
check("7. на экране номер ответа", any(f"A-{A1}-001" in str(s.value) for s in at.success))
check("7. поле ответа пересоздано пустым (правило 7б)",
      not any(str(w.key).startswith(f"pp-ans-{A1}-") and w.value for w in at.text_area))
pp.flag_on = _real

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
