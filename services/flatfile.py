# -*- coding: utf-8 -*-
"""
services/flatfile.py — выгрузка принятых тайтлов для загрузки в Amazon.

Источник — synthesis_changes со статусом accepted: это и есть «правка,
которую человек принял». Файл выгружается, человек грузит его сам через
Seller Central; прямая отправка по SP-API живёт отдельно — см.
[services/spapi.py](services/spapi.py). Раскладка по товарам общая
(`plan_export`): SKU и product_type у обоих путей обязаны совпадать.

Два формата:
  · flat file — настоящий шаблон Amazon (.xlsm, вкладка «Plantilla»):
    служебные строки 1–6 переносятся из эталона без изменений, наши строки
    дописываются с 7-й. Эталон загружает человек, см.
    [services/flatfile_template.py](services/flatfile_template.py);
  · CSV для человека — с ASIN, старым и новым тайтлом, длиной и датой.

Почему файлов может быть несколько: загрузка у Amazon идёт в рамках одной
страны, а внутри страны один шаблон покрывает лишь часть типов товара
(60 типов бренда поделены между двумя отчётами без пересечений). Поэтому
строки раскладываются по шаблонам, и при нескольких файлах отдаётся zip.

SKU и product_type берутся в первую очередь из самого отчёта Кабинета —
там настоящие продавцовые SKU. Запасные источники (catalog_source,
listing_issues, product_matrix.sku_group) остаются для товаров, которых
в отчёте ещё нет; такие строки помечены и страница о них предупреждает.
"""
from __future__ import annotations

import io
import zipfile

import pandas as pd
import streamlit as st

from services.db import get_conn
from services.flatfile_template import (
    build_file, sku_for, templates_for, type_index)

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
                   asin, marketplace,
                   before_text AS before_title,
                   after_text  AS after_title,
                   after_extra AS highlights,
                   after_len, accepted_at
            FROM synthesis_changes
            WHERE status = 'accepted' AND change_type = 'title_split'
              AND after_text IS NOT NULL AND after_text <> ''
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


@st.cache_data(ttl=300, show_spinner=False)
def load_product_types() -> dict:
    """(asin, marketplace) -> product_type из listing_attributes.

    Запасной источник: у товара, которого ещё нет в отчёте Кабинета,
    тип берём из каталога Amazon — он тот же самый.
    """
    try:
        conn = get_conn()
        df = pd.read_sql(
            "SELECT asin, marketplace, product_type FROM listing_attributes "
            "WHERE product_type IS NOT NULL AND product_type <> ''", conn)
        conn.close()
    except Exception:
        return {}
    return {(str(r["asin"]), str(r["marketplace"]).lower()):
            str(r["product_type"]).strip() for _, r in df.iterrows()}


def plan_export(df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    """Разложить принятые правки по шаблонам.

    Возвращает (план, проблемы). План — список файлов: маркетплейс, шаблон
    и строки к нему. Проблемы — строки, которые в файл не попали, с причиной:
    молча терять их нельзя, человек принял правку и ждёт её в выгрузке.
    """
    plan: dict[tuple, dict] = {}
    problems: list[dict] = []
    if df.empty:
        return [], []
    pt_map = load_product_types()
    smap = load_sku_map()

    for mp in sorted(df["marketplace"].unique()):
        tpls = templates_for(mp)
        sub = df[df["marketplace"] == mp]
        if not tpls:
            problems += [{"asin": r["asin"], "marketplace": mp,
                          "reason": "no_template"} for _, r in sub.iterrows()]
            continue
        idx = type_index(tpls)
        for _, r in sub.iterrows():
            asin = str(r["asin"])
            sku, ptype, src = sku_for(tpls, asin)
            if not sku:
                sku, src = smap.get((asin, mp), ("", ""))[0], "fallback"
            if not ptype:
                ptype = pt_map.get((asin, mp), "")
            if not sku:
                problems.append({"asin": asin, "marketplace": mp,
                                 "reason": "no_sku"})
                continue
            if not ptype:
                problems.append({"asin": asin, "marketplace": mp,
                                 "reason": "no_type"})
                continue
            tpl = idx.get(ptype)
            if tpl is None:
                problems.append({"asin": asin, "marketplace": mp,
                                 "reason": "type_unknown", "detail": ptype})
                continue
            key = (mp, tpl["slot"])
            plan.setdefault(key, {"marketplace": mp, "tpl": tpl, "rows": []})
            plan[key]["rows"].append({
                "sku": sku, "product_type": ptype,
                "title": str(r["after_title"]), "asin": asin, "sku_source": src,
                # «было» нужно и диалогу подтверждения отправки, и журналу:
                # человек перед записью в чужой каталог должен видеть пару
                "before": str(r.get("before_title") or ""),
                # Item Highlights нужны прямой отправке; в flat file они
                # не идут — там обновляется только тайтл
                "highlights": ("" if pd.isna(r.get("highlights"))
                               else str(r.get("highlights") or ""))})

    return [plan[k] for k in sorted(plan)], problems


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


XLSM_MIME = "application/vnd.ms-excel.sheet.macroEnabled.12"
XLSX_MIME = ("application/vnd.openxmlformats-officedocument"
             ".spreadsheetml.sheet")


def flat_ext(tpl: dict) -> str:
    """Расширение как у шаблона-источника: мы отдаём его же архив с
    подменённым листом, и звать xlsm то, что пришло xlsx, — врать."""
    return ".xlsx" if str(tpl.get("file_name", "")).lower().endswith(".xlsx") \
        else ".xlsm"


def flat_name(item: dict, day: str) -> str:
    """Имя по шаблону-источнику: человек грузит файл обратно в тот же раздел
    Кабинета, откуда взял шаблон, — по имени видно, в какой именно."""
    return (f"{item['tpl']['slot']}_{item['marketplace']}_{day}_"
            f"{len(item['rows'])}{flat_ext(item['tpl'])}")


def build_flat_export(plan: list[dict], day: str) -> tuple[str, str, bytes]:
    """(имя файла, mime, содержимое). Один шаблон — файл, несколько — zip."""
    if len(plan) == 1:
        item = plan[0]
        mime = XLSX_MIME if flat_ext(item["tpl"]) == ".xlsx" else XLSM_MIME
        return (flat_name(item, day), mime,
                build_file(item["tpl"], item["rows"]))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for item in plan:
            z.writestr(flat_name(item, day),
                       build_file(item["tpl"], item["rows"]))
    mps = sorted({i["marketplace"] for i in plan})
    total = sum(len(i["rows"]) for i in plan)
    return (f"amazon_titles_{'-'.join(mps)}_{day}_{total}.zip",
            "application/zip", buf.getvalue())


def plan_signature(plan: list[dict]) -> str:
    """Отпечаток плана для кэша: сборка перепаковывает трёхмегабайтный
    архив, гонять её на каждую перерисовку страницы незачем."""
    return "|".join(f"{i['tpl']['slot']}:{i['marketplace']}:" + ",".join(
        f"{r['sku']}={len(r['title'])}" for r in i["rows"]) for i in plan)


@st.cache_data(ttl=600, show_spinner=False)
def build_flat_cached(_plan: list[dict], sig: str,
                      day: str) -> tuple[str, str, bytes]:
    """Кэш поверх build_flat_export. `_plan` с подчёркиванием — Streamlit
    не хеширует такие аргументы, ключом служит sig."""
    return build_flat_export(_plan, day)


def build_csv_export(df: pd.DataFrame, day: str) -> tuple[str, str, bytes]:
    mps = sorted(df["marketplace"].unique())
    tag = mps[0] if len(mps) == 1 else "-".join(mps)
    return (f"titles_{tag}_{day}_{len(df)}.csv", "text/csv", csv_bytes(df))
