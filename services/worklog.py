# -*- coding: utf-8 -*-
"""
services/worklog.py — след работы по товару.

Собирает в одну карту всё, что с товаром уже делали: черновики сплита,
принятые правки, аудиты фото и A+. Нужно, чтобы в Матрице и Каталоге
было видно не только «собран / не собран», но и «что мы с ним делали».
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from i18n import t

from services.db import get_conn


@st.cache_data(ttl=60)
def load_worklog() -> pd.DataFrame:
    """По каждому ASIN×MP: черновики, принятая правка, грейды фото и A+."""
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            WITH d AS (
                SELECT asin, marketplace, count(*) AS drafts,
                       max(created_at) AS last_draft
                FROM synthesis_drafts GROUP BY 1, 2
            ),
            c AS (
                SELECT DISTINCT ON (asin, marketplace)
                       asin, marketplace, accepted_at, status, coverage_score
                FROM listing_changes
                ORDER BY asin, marketplace, accepted_at DESC
            ),
            g AS (
                SELECT DISTINCT ON (asin, marketplace)
                       asin, marketplace, grade AS photo_grade,
                       created_at AS photo_at
                FROM photo_analysis WHERE analysis_type = 'gallery'
                ORDER BY asin, marketplace, created_at DESC
            ),
            a AS (
                SELECT DISTINCT ON (asin, marketplace)
                       asin, marketplace, grade AS aplus_grade
                FROM photo_analysis WHERE analysis_type = 'aplus'
                ORDER BY asin, marketplace, created_at DESC
            )
            SELECT COALESCE(d.asin, c.asin, g.asin, a.asin)               AS asin,
                   COALESCE(d.marketplace, c.marketplace,
                            g.marketplace, a.marketplace)                 AS marketplace,
                   d.drafts, d.last_draft,
                   c.accepted_at, c.status, c.coverage_score,
                   g.photo_grade, g.photo_at, a.aplus_grade
            FROM d
            FULL JOIN c ON c.asin = d.asin AND c.marketplace = d.marketplace
            FULL JOIN g ON g.asin = COALESCE(d.asin, c.asin)
                       AND g.marketplace = COALESCE(d.marketplace, c.marketplace)
            FULL JOIN a ON a.asin = COALESCE(d.asin, c.asin, g.asin)
                       AND a.marketplace = COALESCE(d.marketplace, c.marketplace,
                                                    g.marketplace)
            """,
            conn,
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def worklog_map() -> dict:
    df = load_worklog()
    if df.empty:
        return {}
    return {(r["asin"], r["marketplace"]): r.to_dict()
            for _, r in df.iterrows()}


def work_badges(w: dict | None) -> str:
    """HTML-значки следа работы для строки товара."""
    if not w:
        return ""
    parts = []
    if w.get("accepted_at") is not None and not pd.isna(w.get("accepted_at")):
        d = pd.to_datetime(w["accepted_at"]).strftime("%d.%m")
        cov = w.get("coverage_score")
        cov_s = f" {int(cov)}%" if cov is not None and not pd.isna(cov) else ""
        parts.append(
            f'<span style="background:#DCEEE0;color:#2F6B3A;border-radius:5px;'
            f'padding:1px 7px;font-size:11px;">{t("work.change_badge")} {d}{cov_s}</span>')
    elif w.get("drafts") and not pd.isna(w.get("drafts")):
        parts.append(
            f'<span style="background:#FAEEDA;color:#854F0B;border-radius:5px;'
            f'padding:1px 7px;font-size:11px;">{t("work.draft_badge")} '
            f'{int(w["drafts"])}</span>')
    for key, label in (("photo_grade", t("metric.photos")),
                   ("aplus_grade", t("metric.aplus"))):
        g = w.get(key)
        if g and not pd.isna(g):
            ok = str(g) in ("A", "B")
            bg, fg = ("#DCEEE0", "#2F6B3A") if ok else ("#FCE8DC", "#E8590C")
            parts.append(
                f'<span style="background:{bg};color:{fg};border-radius:5px;'
                f'padding:1px 7px;font-size:11px;">{label} {g}</span>')
    return " ".join(parts)


def has_work(w: dict | None) -> bool:
    if not w:
        return False
    for k in ("drafts", "accepted_at", "photo_grade", "aplus_grade"):
        v = w.get(k)
        if v is not None and not (isinstance(v, float) and pd.isna(v)):
            return True
    return False 
