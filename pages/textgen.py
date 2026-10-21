# -*- coding: utf-8 -*-
"""
pages/textgen.py — «Генератор текстов (пилот)», шаг 4: каркас БЕЗ модели.

Ярослав выбирает пилотный товар → видит характеристики (с источником каждого
значения), чего не хватает, расхождения карточки, набор и ключи по типу товара
→ пишет тайтл и Item Highlights руками → правила тайтла проверяют их на каждом
изменении. Модель не вызывается, в Amazon ничего не уходит. В базу и в том UC
пишет только загрузка паспорта docx (последний блок, право `ls.textgen.accept`,
`services/passport_copies.py`).

Данные и проверки — из существующих модулей, без копий:
`services/product_specs.py` (характеристики), `services/seo.py` (ключи по типу,
чужие бренды — forbid), `services/title_rules.py` (правила тайтла, решения
владельца 20–21.10.2026).

Видят страницу администратор и роль `textgen_pilot` (auth.py). В режиме
раскатки (`ls_auth_enabled = 2`) видно всем — так устроен вход во всём
приложении.
"""
from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

import auth

from components.ui import eyebrow, inject_fonts
from i18n import t
from services import passport_copies as pc
from services import product_specs as ps
from services import seo
from services import title_rules as tr

ACCENT = "#E8590C"
GREEN = "#2F6B3A"
MUTED = "#57534A"

# Пять пилотных товаров ES (TASKS.md, T-20). Пилот — пять, а не весь каталог.
PILOT = [("B0H75P364R", "es"), ("B0FZFCQN3H", "es"), ("B0H75XRDBK", "es"),
         ("B0GTRRBZNK", "es"), ("B0DK5VZYVD", "es")]
MP_BY_ASIN = dict(PILOT)

inject_fonts()
st.title(t("nav.textgen"))


def section(text: str) -> None:
    st.markdown(eyebrow(text), unsafe_allow_html=True)


st.info(t("tg.pilot_note"))


# Кешируется только УДАЧНОЕ чтение: сбой поднимается исключением, а исключения
# `st.cache_data` не запоминает. Иначе разовый сбой базы висел бы на экране
# весь срок кеша, хотя база давно ответила.
class _ReadFailed(Exception):
    pass


@st.cache_data(ttl=300, show_spinner=False)
def _raw_cached(asin: str, marketplace: str):
    data, err = ps.load(asin, marketplace)
    if err:
        raise _ReadFailed(err)
    return data


@st.cache_data(ttl=600, show_spinner=False)
def _keys_cached(tool_type: str, marketplace: str, title: str):
    asins, err = ps.same_type_asins(tool_type, marketplace)
    if err:
        raise _ReadFailed(err)
    df = seo.build_type_keyword_table(asins, marketplace, title)
    err = seo.sqp_error()
    if err:
        raise _ReadFailed(err)
    return df, len(asins)


def load_raw(asin: str, marketplace: str):
    """Одно чтение на товар: из него и характеристики, и нынешний тайтл."""
    try:
        return _raw_cached(asin, marketplace), None
    except _ReadFailed as e:
        return None, str(e)


def load_keys(tool_type: str, marketplace: str, title: str):
    try:
        df, n = _keys_cached(tool_type, marketplace, title)
        return df, None, n
    except _ReadFailed as e:
        return None, str(e), 0


def _label(asin: str) -> str:
    return f"{asin} · {MP_BY_ASIN[asin].upper()}"


asin = st.selectbox(t("tg.pick"), [a for a, _ in PILOT], format_func=_label, key="tg-asin")
mp = MP_BY_ASIN[asin]

raw, err = load_raw(asin, mp)
if err:
    st.error(t("tg.load_error", err=err))
    st.stop()
specs = ps.extract(asin, mp, **raw)
current_title = raw.get("title") or ""

# ------------------------------------------------------------- товар
section(t("tg.product"))
c1, c2, c3 = st.columns(3)
c1.metric(t("tg.type"), t(f"tg.type.{specs.tool_type}") if specs.tool_type else t("tg.type_unknown"))
c2.metric(t("tg.model"), specs.model or "—")
c3.metric(t("tg.power_source"), t("tg.corded") if specs.corded else
          (t("tg.cordless") if specs.corded is False else "—"))
st.caption(t("tg.current_title", n=len(current_title), title=current_title or "—"))

# ------------------------------------------------- характеристики
section(t("tg.specs"))
rows = [{"field": t(f"tg.field.{k}"), "value": ps.fmt(k, s.value), "src": t(f"tg.src.{s.source}")}
        for k, s in specs.values.items()]
if rows:
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                 column_config={"field": st.column_config.TextColumn(t("tg.col.field")),
                                "value": st.column_config.TextColumn(t("tg.col.value")),
                                "src": st.column_config.TextColumn(t("tg.col.source"))})
else:
    st.caption(t("tg.no_specs"))

parts = ps.title_parts(specs)
st.markdown(f"**{t('tg.for_title')}:** " + (", ".join(parts) if parts else "—"))
if specs.missing:
    st.warning(t("tg.missing", fields=", ".join(t(f"tg.field.{f}") for f in specs.missing)))
for fld, have, other in specs.conflicts:
    st.warning(t("tg.conflict", field=t(f"tg.field.{fld}"),
                 a=ps.fmt(fld, have.value), a_src=t(f"tg.src.{have.source}"),
                 b=ps.fmt(fld, other.value), b_src=t(f"tg.src.{other.source}")))
if specs.kit:
    st.markdown(f"**{t('tg.kit')}:** " + "; ".join(specs.kit))
else:
    st.caption(t("tg.no_kit"))

# --------------------------------------------------------- ключи
section(t("tg.keys"))
keys_df = None
if specs.tool_type:
    keys_df, kerr, n_asins = load_keys(specs.tool_type, mp, current_title)
    if kerr:
        st.error(t("tg.keys_error", err=kerr))
    elif keys_df is None or keys_df.empty:
        st.caption(t("tg.keys_empty", n=n_asins))
    else:
        st.caption(t("tg.keys_from", n=n_asins))
else:
    st.caption(t("tg.keys_no_type"))

# ------------------------------------------------- ручной ввод
section(t("tg.write"))
st.caption(t("tg.write_hint"))
title_in = st.text_input(t("tg.title_label"), key=f"tg-title-{asin}")
hl_in = st.text_area(t("tg.hl_label"), key=f"tg-hl-{asin}", height=90)


def counter(n: int, limit: int) -> str:
    color = ACCENT if n > limit else (GREEN if n else MUTED)
    return f'<span style="color:{color};font-weight:600">{n} / {limit}</span>'


st.markdown(f'{t("tg.title_len")}: ' + counter(len(title_in), tr.TITLE_LIMIT) + " · "
            + f'{t("tg.hl_len")}: ' + counter(len(hl_in), tr.Ruleset().highlight_limit),
            unsafe_allow_html=True)

if title_in or hl_in:
    found = tr.check(title_in, hl_in, kind=specs.kind, model=specs.model if hl_in else None)
    if found:
        st.error(t("tg.violations", n=len(found)))
        for v in found:
            st.markdown(f"- **{t(f'tg.code.{v.code}')}** ({t(f'tg.where.{v.field}')})"
                        + (f": `{v.detail}`" if v.detail else ""))
    else:
        st.success(t("tg.all_ok"))
    # Без модели префикс «Model …: » не проверить. «Нарушений нет» без этой
    # оговорки выдавало бы непроверенное за проверенное.
    if hl_in and not specs.model:
        st.warning(t("tg.no_model_prefix"))

if keys_df is not None and not keys_df.empty:
    typed = f"{title_in} {hl_in}"
    view = pd.DataFrame({
        "query": keys_df["search_query"],
        "volume": keys_df["volume"],
        "tier": keys_df["tier"].map(lambda x: t(f"tg.tier.{x}")),
        "asins": keys_df["asins"],
        "typed": keys_df["search_query"].map(lambda q: bool(typed.strip()) and tr.phrase_present(q, typed)),
    })
    st.dataframe(view, hide_index=True, width="stretch",
                 column_config={"query": st.column_config.TextColumn(t("tg.col.query")),
                                "volume": st.column_config.NumberColumn(t("tg.col.volume")),
                                "tier": st.column_config.TextColumn(t("tg.col.tier")),
                                "asins": st.column_config.NumberColumn(t("tg.col.asins")),
                                "typed": st.column_config.CheckboxColumn(t("tg.col.typed"))})

# ------------------------------------------------- паспорт SKU (docx)
# Копия паспорта — в томе UC, неизменная; SKU, id и версия — из шапки файла
# (services/passport_copies.py). Права — в момент нажатия, как везде.
section(t("tg.pp.title"))
st.caption(t("tg.pp.hint", volume=pc.VOLUME))
up = st.file_uploader(t("tg.pp.upload"), type=["docx"], key="tg-pp-file")
pp_header = None
if up is not None:
    pp_data = up.getvalue()
    try:
        pp_header = pc.read_header(pp_data)
    except pc.CopyError as e:
        st.error(t(f"tg.pp.err.{e.code}", detail=e.detail))
if pp_header:
    state = pp_header.get("state") or "—"
    st.markdown(t("tg.pp.header", sku=pp_header["sku_id"], pid=pp_header["passport_id"],
                  ver=pp_header["passport_version"], state=state))
    if state != "READY":
        st.warning(t("tg.pp.not_ready", state=state))
    st.caption(t("tg.pp.path", path=f"{pc.ROOT}/{pc.copy_path(pp_header)}"))
    may = auth.can("ls.textgen.accept")
    if not may:
        st.caption(t("tg.pp.denied_hint"))
    if st.button(t("tg.pp.save"), type="primary", disabled=not may, key="tg-pp-save"):
        if auth.require("ls.textgen.accept", object_type="passport", object_id=pp_header["passport_id"]):
            store = pc.volume_store()
            if store is None:
                st.error(t("tg.pp.no_store"))
            else:
                from services.db import get_conn
                try:
                    conn = get_conn()
                except Exception as e:  # noqa: BLE001
                    conn = None
                    st.error(t("tg.pp.err.DB_FAILED", detail=f"{type(e).__name__}: {str(e)[:160]}"))
                if conn is not None:
                    try:
                        res = pc.register(pp_data, up.name, actor=auth.actor(), store=store, conn=conn)
                    except pc.CopyError as e:
                        st.error(t(f"tg.pp.err.{e.code}", detail=e.detail))
                    except Exception as e:  # noqa: BLE001 — база: файл уже в томе, повтор его узнает
                        st.error(t("tg.pp.err.DB_FAILED", detail=f"{type(e).__name__}: {str(e)[:160]}"))
                    else:
                        if res.status == "DUPLICATE":
                            st.info(t("tg.pp.duplicate", aid=res.artifact_id, loc=res.locator))
                        else:
                            st.success(t("tg.pp.saved", aid=res.artifact_id, loc=res.locator,
                                         sha=hashlib.sha256(pp_data).hexdigest()[:12]))
                            if res.superseded:
                                st.info(t("tg.pp.superseded", ids=", ".join(res.superseded)))
                    finally:
                        conn.close()
    lst, lerr = pc.copies(pp_header["sku_id"])
    st.markdown(f"**{t('tg.pp.list', sku=pp_header['sku_id'])}**")
    if lerr:
        st.error(t("tg.pp.list_error", err=lerr))
    elif lst.empty:
        st.caption(t("tg.pp.none", sku=pp_header["sku_id"]))
    else:
        view = pd.DataFrame({
            "id": lst["source_artifact_id"],
            "ver": lst["archived_locator"].map(lambda x: pc.version_of(x) if isinstance(x, str) else None),
            "sha": lst["sha256"].map(lambda x: x[:12] if isinstance(x, str) else ""),
            "life": lst["lifecycle"],
            "by": lst["registered_by"],
            "at": lst["recorded_at"],
        })
        st.dataframe(view, hide_index=True, width="stretch",
                     column_config={"id": st.column_config.TextColumn(t("tg.pp.col.id")),
                                    "ver": st.column_config.NumberColumn(t("tg.pp.col.version")),
                                    "sha": st.column_config.TextColumn(t("tg.pp.col.sha")),
                                    "life": st.column_config.TextColumn(t("tg.pp.col.lifecycle")),
                                    "by": st.column_config.TextColumn(t("tg.pp.col.by")),
                                    "at": st.column_config.DatetimeColumn(t("tg.pp.col.at"))})
