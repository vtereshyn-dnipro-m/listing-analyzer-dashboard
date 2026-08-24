# -*- coding: utf-8 -*-
"""
services/flatfile.py — выгрузка принятых тайтлов для загрузки в Amazon.

Источник — listing_changes со статусом accepted: это и есть «правка,
которую человек принял». Прямой отправки в Amazon нет и не планируется:
файл выгружается, человек грузит его сам через Seller Central.

Два формата:
  · flat file — tab-delimited txt на КАЖДЫЙ маркетплейс (у Amazon
    загрузка всегда в рамках одной страны), колонки sku / product_name /
    update_delete = PartialUpdate. Несколько стран — zip из таких файлов;
  · CSV для человека — с ASIN, старым и новым тайтлом, длиной и датой.

SKU для flat file берётся из данных Amazon (catalog_source, затем
listing_issues) и только в последнюю очередь из product_matrix.sku_group:
в Seller Central загрузка идёт по продавцовому SKU, а sku_group — наша
группировка, она может не совпасть. Строки, где пришлось взять запасной
источник, помечены в sku_fallback — страница о них предупреждает.
"""
from __future__ import annotations

import io
import zipfile

import pandas as pd
import streamlit as st

from services.db import get_conn

FLAT_COLUMNS = ["sku", "product_name", "update_delete"]
UPDATE_MODE = "PartialUpdate"
CSV_COLUMNS = ["sku", "asin", "marketplace", "title_before", "title_after",
               "len_after", "accepted_at"]


@st.cache_data(ttl=60)
def load_sku_map() -> dict:
    """(asin, marketplace) -> (sku, источник). Приоритет: зеркало каталога
    Amazon, затем реплика Кабинета, затем наша матрица."""
    out: dict = {}
    queries = [
        ("matrix", "SELECT asin, marketplace, sku_group AS sku "
                   "FROM product_matrix WHERE sku_group <> ''"),
        ("issues", "SELECT DISTINCT asin, marketplace, sku FROM listing_issues "
                   "WHERE sku IS NOT NULL AND sku <> ''"),
        ("catalog", "SELECT asin, marketplace, sku_group AS sku "
                    "FROM catalog_source WHERE sku_group IS NOT NULL "
                    "AND sku_group <> ''"),
    ]
    # порядок обхода — от запасного к приоритетному: последний перезаписывает
    for source, sql in queries:
        try:
            conn = get_conn()
            df = pd.read_sql(sql, conn)
            conn.close()
        except Exception:
            continue
        for _, r in df.iterrows():
            key = (str(r["asin"]), str(r["marketplace"]).lower())
            sku = str(r["sku"]).strip()
            if sku:
                out[key] = (sku, source)
    return out


@st.cache_data(ttl=60)
def load_accepted_titles(marketplaces: tuple | None = None) -> pd.DataFrame:
    """Принятые правки тайтла: последняя по каждой паре товар × рынок.

    Только status = 'accepted' — черновики и отклонённое не выгружаются.
    """
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT DISTINCT ON (asin, marketplace)
                   asin, marketplace, before_title, after_title, after_len,
                   accepted_at
            FROM listing_changes
            WHERE status = 'accepted' AND change_type = 'title_split'
              AND after_title IS NOT NULL AND after_title <> ''
            ORDER BY asin, marketplace, accepted_at DESC
            """, conn)
        conn.close()
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df

    df["marketplace"] = df["marketplace"].astype(str).str.lower()
    if marketplaces:
        df = df[df["marketplace"].isin([str(m).lower() for m in marketplaces])]
    if df.empty:
        return df

    smap = load_sku_map()
    pairs = [(str(a), str(m)) for a, m in zip(df["asin"], df["marketplace"])]
    df = df.copy()
    df["sku"] = [smap.get(p, (p[0], "asin"))[0] for p in pairs]
    # источник sku: не «catalog»/«issues» — значит взят запасной,
    # в Seller Central такой SKU может не найтись
    df["sku_source"] = [smap.get(p, ("", "asin"))[1] for p in pairs]
    df["sku_fallback"] = ~df["sku_source"].isin(["catalog", "issues"])
    return df.sort_values(["marketplace", "sku"])


def flat_bytes(df: pd.DataFrame) -> bytes:
    """Flat file одного маркетплейса: TSV, UTF-8, без индекса."""
    out = df.copy()
    out["product_name"] = out["after_title"]
    out["update_delete"] = UPDATE_MODE
    return out[FLAT_COLUMNS].to_csv(
        sep="\t", index=False, lineterminator="\r\n").encode("utf-8")


def csv_bytes(df: pd.DataFrame) -> bytes:
    """CSV для человека: utf-8-sig, чтобы Excel не ломал кириллицу."""
    out = df.copy()
    out["title_before"] = out["before_title"].fillna("")
    out["title_after"] = out["after_title"]
    out["len_after"] = [
        (len(str(t)) if not pd.isna(t) else 0) for t in out["after_title"]]
    out["accepted_at"] = pd.to_datetime(
        out["accepted_at"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
    return out[CSV_COLUMNS].to_csv(index=False).encode("utf-8-sig")


def flat_name(mp: str, n: int, day: str) -> str:
    return f"amazon_titles_{mp}_{day}_{n}.txt"


def build_flat_export(df: pd.DataFrame, day: str) -> tuple[str, str, bytes]:
    """(имя файла, mime, содержимое). Один маркетплейс — txt, несколько — zip:
    Amazon принимает flat file только в рамках одной страны."""
    mps = sorted(df["marketplace"].unique())
    if len(mps) == 1:
        mp = mps[0]
        sub = df[df["marketplace"] == mp]
        return (flat_name(mp, len(sub), day), "text/tab-separated-values",
                flat_bytes(sub))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for mp in mps:
            sub = df[df["marketplace"] == mp]
            z.writestr(flat_name(mp, len(sub), day), flat_bytes(sub))
    return (f"amazon_titles_{'-'.join(mps)}_{day}_{len(df)}.zip",
            "application/zip", buf.getvalue())


def build_csv_export(df: pd.DataFrame, day: str) -> tuple[str, str, bytes]:
    mps = sorted(df["marketplace"].unique())
    tag = mps[0] if len(mps) == 1 else "-".join(mps)
    return (f"titles_{tag}_{day}_{len(df)}.csv", "text/csv", csv_bytes(df))
