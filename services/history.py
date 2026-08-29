# -*- coding: utf-8 -*-
"""
services/history.py — история изменений по товару.

Карточка показывает текущее состояние, а вопрос у человека обычно другой:
что с этим товаром уже делали. Ответ разложен по трём таблицам, и по
отдельности ни одна на него не отвечает:

  · `listing_push_log` — что ушло в Amazon и чем он ответил;
  · `synthesis_changes` — что человек принял, какой методологией и моделью
    это сделано, принято как есть или переписано руками;
  · `synthesis_drafts` — сколько раз генерировали. Само по себе число
    бесполезно, но разложенное между приёмками оно отвечает «сколько
    заходов понадобилось».

Слова «отклонено» здесь нет намеренно. Отказ мы нигде не сохраняем:
сгенерированное, не ставшее правкой, — это перегенерация или брошенная
работа. Назвать это отклонением значит показать факт, которого в данных
нет. Считаем и говорим то, что знаем: между приёмками сгенерировано N
и не принято.

Новых полей не требуется — всё берётся из существующих таблиц.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from i18n import t
from services.db import get_conn

ERR_KEY = "history.load_error"


def _query(sql: str) -> pd.DataFrame:
    """Один запрос. Ошибку не глотаем: пустая история и недоступная
    история — разные вещи, и вторую человек должен видеть."""
    try:
        conn = get_conn()
        df = pd.read_sql(sql, conn)
        conn.close()
        return df
    except Exception as e:
        try:
            st.session_state[ERR_KEY] = f"{type(e).__name__}: {e}"
        except Exception:
            pass
        return pd.DataFrame()


def load_error() -> str | None:
    try:
        return st.session_state.get(ERR_KEY)
    except Exception:
        return None


@st.cache_data(ttl=60, show_spinner=False)
def load_history() -> dict:
    """(asin, marketplace) -> список событий, от свежего к старому.

    Событие: {kind, at, before, after, ...}. kind — 'push' или 'accept'.
    """
    try:
        st.session_state.pop(ERR_KEY, None)
    except Exception:
        pass

    pushes = _query(
        """
        SELECT asin, marketplace, pushed_at, before_text, after_text,
               status, ok, submission_id, issues, error
        FROM listing_push_log
        ORDER BY pushed_at DESC
        """)
    accepts = _query(
        """
        SELECT asin, marketplace, accepted_at, before_text, after_text,
               skill_version, model, source
        FROM synthesis_changes
        WHERE status = 'accepted' AND change_type = 'title_split'
        ORDER BY accepted_at DESC
        """)
    drafts = _query(
        "SELECT asin, marketplace, created_at FROM synthesis_drafts "
        "ORDER BY created_at")

    out: dict = {}

    def key(r) -> tuple:
        return (str(r["asin"]), str(r["marketplace"]).lower())

    if not pushes.empty:
        for _, r in pushes.iterrows():
            out.setdefault(key(r), []).append({
                "kind": "push", "at": r["pushed_at"],
                "before": r.get("before_text"), "after": r.get("after_text"),
                "status": str(r.get("status") or ""),
                "ok": bool(r.get("ok")),
                "submission_id": r.get("submission_id"),
                "detail": r.get("issues") or r.get("error"),
            })

    # черновики раскладываем по интервалам между приёмками: сколько заходов
    # понадобилось до каждой принятой правки. Сам принятый тоже был
    # черновиком, поэтому из интервала вычитается один
    by_pair_drafts: dict = {}
    if not drafts.empty:
        for _, r in drafts.iterrows():
            by_pair_drafts.setdefault(key(r), []).append(r["created_at"])

    if not accepts.empty:
        for k, grp in accepts.groupby(["asin", "marketplace"]):
            pair = (str(k[0]), str(k[1]).lower())
            times = sorted(by_pair_drafts.get(pair, []))
            rows = grp.sort_values("accepted_at")     # от старой к свежей
            prev = None
            events = []
            for _, r in rows.iterrows():
                at = r["accepted_at"]
                n = len([x for x in times
                         if (prev is None or x > prev) and x <= at])
                events.append({
                    "kind": "accept", "at": at,
                    "before": r.get("before_text"),
                    "after": r.get("after_text"),
                    "skill_version": r.get("skill_version"),
                    "model": r.get("model"),
                    "source": str(r.get("source") or "ai"),
                    "tries": max(0, n - 1),
                })
                prev = at
            out.setdefault(pair, []).extend(events)

    for pair in out:
        out[pair].sort(key=lambda e: pd.Timestamp(e["at"]), reverse=True)
    return out


def stamp(v) -> str:
    try:
        return pd.to_datetime(v).strftime("%d.%m %H:%M")
    except Exception:
        return ""


def summary(events: list[dict]) -> str:
    """Свёрнутая строка: последняя отправка. Она и есть вопрос, ради
    которого историю открывают, — дошло до Amazon или нет."""
    last = next((e for e in events if e["kind"] == "push"), None)
    if last is None:
        return t("hist.no_push")
    return t("hist.last_push", day=stamp(last["at"]),
             status=(t("hist.accepted_by_amazon") if last["ok"]
                     else t("hist.rejected_by_amazon")))
