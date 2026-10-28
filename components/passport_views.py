# -*- coding: utf-8 -*-
"""
components/passport_views.py — паспорт SKU из копии docx на экранах раздела
«Паспорт SKU» (решение владельца 28.10.2026: один паспорт на SKU для раздела и
генератора).

  · `render_passport` — что в паспорте: комплектация с количествами и
    конфликты со статусом и источником решения;
  · `render_sku_summary` — «собрано по SKU»: название, модель, тип,
    характеристики с источником каждого значения, текущий тайтл и ASIN —
    из справочника, матрицы и снапшота, руками ничего не вбивается;
  · `render_conflict_decisions` — решение верификатора по конфликту копии:
    сторона A, сторона B или своё значение и проверяемый источник. Право —
    `ls.textgen.accept` в момент нажатия; запись — `services/passport_decisions`.

Копия паспорта не меняется никогда: решение — отдельная строка.
"""
from __future__ import annotations

import copy as _copy
import hashlib

import pandas as pd
import streamlit as st

import auth
from i18n import t
from services import passport as pp
from services import passport_copies as pc
from services import passport_decisions as pdec
from services import passport_facts as pf
from services import product_specs as ps
from services import textgen as tg
from components.ui import md_escape as esc
from services.passport import txt

KIT_SECTION = "комплектація"


class _ReadFailed(Exception):
    pass


@st.cache_data(ttl=24 * 3600, show_spinner=False, max_entries=100)
def _copy_facts(locator: str, sha: str) -> pf.Facts:
    """Факты копии по SHA: копия неизменна. Сбой — исключение, а не кэш пустоты."""
    store = pc.volume_store()
    if store is None:
        raise _ReadFailed(t("tg.pp.no_store"))
    data = store.get(locator)
    if hashlib.sha256(data).hexdigest() != sha:
        raise _ReadFailed(t("pp.view.sha_mismatch"))
    return pf.read(data)


def copy_error_text(err: str) -> str:
    """Код сбоя чтения копии (`passport.COPY_*`) — словами; текст исключения — как есть."""
    return t(f"pp.view.err.{err}") if err in (pp.COPY_NO_STORE, pp.COPY_SHA_MISMATCH) else err


def copy_facts(r: dict) -> tuple[pf.Facts | None, dict, str | None, bool]:
    """(факты с решениями, решения, причина сбоя, нет миграции решений)."""
    try:
        facts = _copy.deepcopy(_copy_facts(r["storage_path"], r["sha256"]))
    except Exception as e:  # noqa: BLE001 — причина на экран: «не прочитано» ≠ «пусто»
        return None, {}, f"{type(e).__name__}: {str(e)[:160]}", False
    decisions, err, missing = pdec.load(r["source_artifact_id"], r["sha256"])
    pf.apply_decisions(facts, decisions)
    return facts, decisions, err, missing


def _state_of(c: dict) -> str:
    if c.get("decision"):
        return t("pp.cf.decided")
    return t("pp.cf.closed") if pf.is_closed_status(c.get("status")) else t("pp.cf.open")


def _source_of(c: dict) -> str:
    d = c.get("decision")
    if d:
        at = d.get("decided_at")
        when = pd.Timestamp(at).strftime("%d.%m.%Y %H:%M") if at is not None and not pd.isna(at) else ""
        return " · ".join(x for x in (txt(d.get("decision_source")), txt(d.get("decided_by")), when) if x)
    return txt(c.get("source"))


def render_passport(box, r: dict) -> None:
    """Комплектация и конфликты паспорта-копии (только чтение)."""
    if r.get("source") != "copy":
        return
    box.markdown(t("pp.view.copy", aid=esc(r["source_artifact_id"]), loc=esc(r["storage_path"])))
    facts, _dec, err, missing = copy_facts(r)
    if facts is None:
        box.error(t("pp.view.read_error", err=esc(err)))
        return
    if err:
        box.warning(t("pp.dec.load_error", err=esc(err)))
    kit = next((s for s in facts.sections if s.title.strip().lower().startswith(KIT_SECTION)), None)
    box.markdown(f"**{t('pp.view.kit')}**")
    if kit is None or len(kit.rows) < 2:
        box.caption(t("pp.view.kit_none"))
    else:
        head = [h.strip().lower() for h in kit.rows[0]]

        def col(row, *names):
            for n in names:
                for i, h in enumerate(head):
                    if h.startswith(n) and i < len(row):
                        return row[i]
            return ""
        box.dataframe(pd.DataFrame([{
            "id": row[0], "item": col(row, "елемент", "назва"), "qty": col(row, "кількість"),
            "status": col(row, "статус"), "src": col(row, "джерело")} for row in kit.rows[1:]]),
            hide_index=True, width="stretch", column_config={
                "id": st.column_config.TextColumn(t("pp.view.col.id")),
                "item": st.column_config.TextColumn(t("pp.view.col.item")),
                "qty": st.column_config.TextColumn(t("pp.view.col.qty")),
                "status": st.column_config.TextColumn(t("pp.view.col.status")),
                "src": st.column_config.TextColumn(t("pp.view.col.src"))})
    box.markdown(f"**{t('pp.view.conflicts')}**")
    if not facts.conflicts:
        box.caption(t("pp.view.conflicts_none"))
        return
    box.dataframe(pd.DataFrame([{
        "id": c.get("id"), "field": c.get("field"), "a": c.get("a"), "b": c.get("b"),
        "status": c.get("status"), "state": _state_of(c),
        "value": pf.decided_value(c) if c.get("decision") else "", "src": _source_of(c)} for c in facts.conflicts]),
        hide_index=True, width="stretch", column_config={
            "id": st.column_config.TextColumn(t("pp.view.col.id")),
            "field": st.column_config.TextColumn(t("pp.view.col.field")),
            "a": st.column_config.TextColumn(t("pp.view.col.a")),
            "b": st.column_config.TextColumn(t("pp.view.col.b")),
            "status": st.column_config.TextColumn(t("pp.view.col.status")),
            "state": st.column_config.TextColumn(t("pp.view.col.state")),
            "value": st.column_config.TextColumn(t("pp.view.col.value")),
            "src": st.column_config.TextColumn(t("pp.view.col.decision_src"))})
    if missing:
        box.caption(t("pp.dec.migration_missing", file=pdec.MIGRATION))


# ---------------------------------------------------------------- собрано по SKU
@st.cache_data(ttl=600, show_spinner=False)
def _matrix_es():
    from services.db import safe_read
    # конкуренты — не наши ASIN, даже с нашим sku_group (проверка #168)
    df, err = safe_read("SELECT asin, sku_group FROM product_matrix"
                        " WHERE marketplace = %(mp)s AND is_competitor IS NOT TRUE", {"mp": "es"})
    if err:
        raise _ReadFailed(err)
    return df


@st.cache_data(ttl=300, show_spinner=False)
def _product(asin: str):
    data, err = ps.load(asin, "es")
    if err:
        raise _ReadFailed(err)
    return data


def render_sku_summary(r: dict) -> None:
    """Что о товаре уже известно по SKU — без ручного ввода. Источник у каждого
    значения; сбой источника называется, а не выдаётся за «нет данных»."""
    st.markdown(f"**{t('pp.sum.title')}**")
    st.caption(t("pp.sum.hint"))
    lines = [(t("pp.sum.name"), txt(r.get("name")) or "—", t("pp.sum.src.directory")),
             (t("pp.sum.ean"), txt(r.get("ean")) or "—", t("pp.sum.src.directory")),
             (t("pp.sum.asins_all"), txt(r.get("asins")) or "—", t("pp.sum.src.directory"))]
    if txt(r.get("model")):
        lines.append((t("tg.model"), txt(r["model"]),
                      t("pp.sum.src.passport") if r.get("source") == "copy" else t("pp.sum.src.registry")))
    directory, derr = pp.sku_directory()
    try:
        es = tg.asins_for_sku(r["sku"], directory if not derr else None, _matrix_es())
        es_err = None
    except _ReadFailed as e:
        es, es_err = [], str(e)
    lines.append((t("pp.sum.asin_es"), ", ".join(es) if es else "—", t("pp.sum.src.matrix")))
    st.dataframe(pd.DataFrame([{"field": a, "value": b, "src": c} for a, b, c in lines]), hide_index=True,
                 width="stretch", column_config={"field": st.column_config.TextColumn(t("tg.col.field")),
                                                 "value": st.column_config.TextColumn(t("tg.col.value")),
                                                 "src": st.column_config.TextColumn(t("tg.col.source"))})
    if derr:
        st.caption(t("tg.link.src_dir", err=esc(str(derr)[:120])))
    if es_err:
        # «не прочитано», а не «нет ASIN»: сбой матрицы не выдаётся за пустоту
        st.caption(t("tg.link.src_matrix", err=esc(es_err[:120])))
        return
    if not es:
        st.caption(t("pp.sum.no_es"))
        return
    if len(es) > 1:
        st.caption(t("pp.sum.many_es", asins=esc(", ".join(es)), asin=esc(es[0])))
    try:
        raw = _product(es[0])
    except _ReadFailed as e:
        st.caption(t("tg.load_error", err=esc(str(e)[:160])))
        return
    specs = ps.extract(es[0], "es", **raw)
    c1, c2 = st.columns(2)
    c1.metric(t("tg.type"), t(f"tg.type.{specs.tool_type}") if specs.tool_type else t("tg.type_unknown"))
    c2.metric(t("tg.model"), specs.model or "—")
    st.caption(t("pp.sum.title_now", asin=esc(es[0]), title=esc(raw.get("title") or "—")))
    rows = [{"field": t(f"tg.field.{k}"), "value": ps.fmt(k, s.value), "src": t(f"tg.src.{s.source}")}
            for k, s in specs.values.items()]
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                     column_config={"field": st.column_config.TextColumn(t("tg.col.field")),
                                    "value": st.column_config.TextColumn(t("tg.col.value")),
                                    "src": st.column_config.TextColumn(t("tg.col.source"))})
    else:
        st.caption(t("tg.no_specs"))
    if specs.kit:
        st.caption(f"{t('tg.kit')}: " + esc("; ".join(specs.kit)))


# ---------------------------------------------------------------- решения верификатора
def _gen() -> int:
    return int(st.session_state.get("pp-cfd-gen", 0))


def render_conflict_decisions(r: dict) -> None:
    """Конфликты копии паспорта и решение по каждому (решение владельца 28.10.2026)."""
    if not r or r.get("source") != "copy":
        return
    st.markdown(f"**{t('pp.dec.title', sku=esc(r['sku']), aid=esc(r['source_artifact_id']))}**")
    st.caption(t("pp.dec.hint"))
    done = st.session_state.pop("pp-cfd-done", None)
    if done:
        st.success(t("pp.dec.saved", cid=done[0], id=done[1]))
    facts, decisions, err, missing = copy_facts(r)
    if facts is None:
        st.error(t("pp.view.read_error", err=esc(err)))
        return
    if err:
        st.error(t("pp.dec.load_error", err=esc(err)))
    if not facts.conflicts:
        st.caption(t("pp.view.conflicts_none"))
        return
    may = auth.can("ls.textgen.accept")
    blocked = missing or bool(err)
    if missing:
        st.warning(t("pp.dec.migration_missing", file=pdec.MIGRATION))
    elif not may:
        st.caption(t("pp.dec.denied_hint"))
    g = _gen()
    for i, c in enumerate(facts.conflicts):
        cid = txt(c.get("id"))
        # В ключе — и место строки: повтор id или пустой id в таблице паспорта не
        # должен ронять вкладку DuplicateElementKey (проверка #176).
        k = f"{i}-{cid}-{g}"
        box = st.container(border=True)
        box.markdown(f'**{esc(cid) or "—"}** · {esc(txt(c.get("field")))} · {_state_of(c)}')
        box.caption(t("pp.dec.sides", a=esc(txt(c.get("a"))), b=esc(txt(c.get("b"))),
                      status=esc(txt(c.get("status"))) or "—"))
        if c.get("decision"):
            box.caption(t("pp.dec.current", value=esc(pf.decided_value(c)), src=esc(_source_of(c))))
        if pf.is_closed_status(c.get("status")) and not c.get("decision"):
            box.caption(t("pp.dec.closed_in_passport", src=esc(txt(c.get("source"))) or "—"))
            continue
        kind = box.radio(t("pp.dec.choice"), list(pf.DECISIONS), key=f"pp-cfd-kind-{k}", horizontal=True,
                         format_func=lambda x: t(f"pp.dec.kind.{x}"), index=None)
        value = box.text_input(t("pp.dec.value"), key=f"pp-cfd-value-{k}", help=t("pp.dec.value_help"))
        source = box.text_input(t("pp.dec.source"), key=f"pp-cfd-src-{k}", placeholder=t("pp.dec.source_ph"))
        if box.button(t("pp.dec.save"), key=f"pp-cfd-save-{k}", disabled=blocked or not may or kind is None):
            _save_decision(box, r, facts, c, kind, value, source)


def _save_decision(box, r: dict, facts: pf.Facts, c: dict, kind: str, value: str, source: str) -> None:
    """Запись решения; право — в момент нажатия, проверки — до записи."""
    cid = txt(c.get("id"))
    if not auth.require("ls.textgen.accept", object_type="passport_conflict", object_id=cid):
        return                      # отказ на экран выводит сам auth.require
    why = pdec.check(facts, cid, kind, value, source)
    if why:
        box.error(t(f"pp.dec.err.{why}"))
        return
    from services.db import get_conn
    try:
        conn = get_conn()
    except Exception as e:  # noqa: BLE001
        box.error(t("pp.dec.err.DB", detail=f"{type(e).__name__}: {str(e)[:160]}"))
        return
    try:
        new_id = pdec.record(conn, copy={"source_artifact_id": r["source_artifact_id"], "sha256": r["sha256"]},
                             sku=r["sku"], passport_id=r["passport_id"], conflict_id=cid, decision=kind,
                             value=value, source=source, actor=auth.actor())
    except Exception as e:  # noqa: BLE001 — триггер базы называет причину
        box.error(t("pp.dec.err.DB", detail=f"{type(e).__name__}: {str(e)[:200]}"))
        return
    finally:
        conn.close()
    st.session_state["pp-cfd-gen"] = _gen() + 1        # поля пересоздаются пустыми (правило 7б)
    st.session_state["pp-cfd-done"] = (cid, new_id)
    st.rerun()
