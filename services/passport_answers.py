# -*- coding: utf-8 -*-
"""
services/passport_answers.py — ответ на вопрос Верификатора (этап 4а).

Норматив — ТЗ v1.0 §11 «Взаимодействие с Верификатором» и 06E MVP-14.
Здесь ответ без вложений: текст и решение по конфликту. Документ или ссылка
как доказательство — это исходный материал, его копия ложится в
`product_root`, а где он живёт, ещё не решено. Поэтому вопрос, который
требует документа, отправить пока нельзя, и это сказано словами.

Что держит модуль:

- **Ответ неизменяем.** Каждая отправка — новая версия `A-<question_id>-<NNN>`
  (шаблон ID из 06E), прежняя не перезаписывается; исправление — новая
  версия со ссылкой на предыдущую (ТЗ 11.6). Базу держит триггер
  «только дописывание».
- **Двойное нажатие — один ответ.** Ключ идемпотентности считается от
  вопроса, версии, на которую отвечают, автора и содержания: тот же ключ —
  та же запись, а не вторая (ТЗ 11.6).
- **Ответ не закрывает вопрос и не меняет его статус.** Переходы вопроса
  фиксирует Собиратель (06E), а «Ответ получен / ожидает проверки»
  выводится из факта непроверенной версии (`passport.user_state`).
- **Решение по конфликту — только четыре значения и только у того, кто
  вправе решать.** Без полномочий можно передать пояснение, но не решение
  (ТЗ 11.9). `ACCEPT_NEW` не меняет Паспорт: это кандидат до проверки и
  применения Собирателем (ТЗ 11.4.3).
- **Устаревший Паспорт запирает отправку.** Если версия или SHA Паспорта
  после вопроса изменились, ответ не отправляется до сверки, и вопрос не
  закрывается молча (ТЗ 11.9).
"""
from __future__ import annotations

import hashlib
import json

from services import passport as pp

DECISIONS = ("KEEP_CURRENT", "ACCEPT_NEW", "KEEP_DISPUTED", "NOT_APPLICABLE")
# Канонические роли, которым принадлежит решение владельца данных.
DECISION_ROLES = ("PRODUCT_OWNER", "PRODUCT_OWNER_WITH_RECREATE_AUTHORITY", "PASSPORT_ADMIN")
MAX_TEXT = 10_000
OPEN_STATES = (pp.NEEDS_ANSWER, pp.NEEDS_CLARIFICATION, pp.ANSWER_REJECTED)


def can_decide(canonical_roles: tuple) -> bool:
    return any(r in DECISION_ROLES for r in canonical_roles)


def may_answer(q, email: str, canonical_roles: tuple) -> bool:
    """Отвечает назначенный ответственный (ТЗ 11.1); администратор Паспорта —
    тоже: он отвечает за весь контур."""
    return pp.is_mine(q, email, canonical_roles) or "PASSPORT_ADMIN" in canonical_roles


def check(q, *, user_state: str, text: str, decision: str | None, email: str,
          canonical_roles: tuple, stale: bool) -> list[str]:
    """Причины, по которым ответ сейчас не отправить. Пусто — можно.

    Коды — подписи интерфейса (`pp.ans.err.<код>`), а не результаты
    контракта: это проверка формы до записи."""
    errs = []
    if user_state not in OPEN_STATES:
        errs.append("NOT_OPEN")
    if not may_answer(q, email, canonical_roles):
        errs.append("NOT_RESPONSIBLE")
    if stale:
        errs.append("STALE")
    qtype = pp.txt(q.get("question_type"))
    body = (text or "").strip()
    if len(body) > MAX_TEXT:
        errs.append("TOO_LONG")
    if qtype == "DOCUMENT" or bool(q.get("evidence_required")) is True:
        # Документ — исходный материал; без хранилища его не принять.
        errs.append("EVIDENCE_NEEDS_STORAGE")
    if qtype == "CONFLICT":
        if decision is not None and decision not in DECISIONS:
            errs.append("BAD_DECISION")
        if decision is not None and not can_decide(canonical_roles):
            errs.append("NO_DECISION_AUTHORITY")
        if decision is None and not body:
            errs.append("EMPTY")
    elif decision is not None:
        errs.append("BAD_DECISION")
    elif not body:
        errs.append("EMPTY")
    return errs


def idempotency_key(question_id: str, base_answer_id: str | None, author: str,
                    text: str, decision: str | None) -> str:
    """Один и тот же ответ на одну и ту же версию — один ключ. Новая версия
    поверх проверенной или другой текст — другой ключ."""
    payload = json.dumps([question_id, base_answer_id, author, (text or "").strip(), decision],
                         ensure_ascii=False, separators=(",", ":"))
    return "LS-ANS-" + hashlib.sha256(payload.encode()).hexdigest()


def latest_answer(answers, question_id: str) -> dict | None:
    if answers is None or answers.empty:
        return None
    part = answers[answers["question_id"] == question_id]
    if part.empty:
        return None
    return part.sort_values("answer_version").iloc[-1].to_dict()


def is_stale(q, runs, objects) -> bool:
    """Вопрос задан по снимку Паспорта, закреплённому в запуске
    (`run_state.pinned_product_truth`). Текущий Паспорт с другой версией или
    SHA — вопрос устарел. Снимка нет — судить не по чему, отправку не
    запираем: иначе вопросы без запуска нельзя было бы закрыть вовсе."""
    run_id, pid = pp.txt(q.get("run_id")), pp.txt(q.get("passport_id"))
    if runs is None or runs.empty or objects is None or objects.empty or not run_id:
        return False
    r = runs[runs["run_id"].astype(str) == run_id]
    o = objects[objects["passport_id"].astype(str) == pid] if pid else objects.iloc[0:0]
    if r.empty or o.empty or "run_state" not in r.columns:
        return False
    state = r.iloc[0]["run_state"]
    if isinstance(state, str):
        try:
            state = json.loads(state)
        except ValueError:
            return False
    pin = (state or {}).get("pinned_product_truth") or {}
    sha = pin.get("sha256")
    return bool(sha) and sha != pp.txt(o.iloc[0]["sha256"])


def submit(conn, q, *, author: str, text: str, decision: str | None, base_answer_id: str | None) -> tuple[str, bool]:
    """Записать новую версию ответа. Возвращает (answer_id, повтор).

    Одна транзакция: следующий номер версии считается под блокировкой
    вопроса, вставка — с `ON CONFLICT (idempotency_key) DO NOTHING`, затем
    повторное чтение по ключу. Повтор того же ключа отдаёт уже записанный
    ответ, второй строки нет."""
    qid = pp.txt(q["question_id"])
    key = idempotency_key(qid, base_answer_id, author, text, decision)
    with conn, conn.cursor() as cur:
        cur.execute("SELECT question_id FROM passport_questions WHERE question_id = %s FOR UPDATE", (qid,))
        if cur.fetchone() is None:
            raise LookupError(qid)
        cur.execute("SELECT answer_id FROM passport_answers WHERE idempotency_key = %s", (key,))
        row = cur.fetchone()
        if row:
            return row[0], True
        cur.execute("SELECT COALESCE(MAX(answer_version), 0) FROM passport_answers WHERE question_id = %s", (qid,))
        version = int(cur.fetchone()[0]) + 1
        answer_id = f"A-{qid}-{version:03d}"
        cur.execute(
            """INSERT INTO passport_answers
                   (answer_id, question_id, answer_version, supersedes_answer_id, author,
                    answer_text, decision, source_artifact_ids, idempotency_key)
               VALUES (%s, %s, %s, %s, %s, %s, %s, '[]'::jsonb, %s)
               ON CONFLICT (idempotency_key) DO NOTHING""",
            (answer_id, qid, version, base_answer_id, author, (text or "").strip() or None, decision, key))
        cur.execute("SELECT answer_id FROM passport_answers WHERE idempotency_key = %s", (key,))
        back = cur.fetchone()
        if back is None:
            raise RuntimeError("ответ не прочитался после записи")
        return back[0], back[0] != answer_id
