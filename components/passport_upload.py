"""Загрузка паспорта SKU (docx) в том UC — один блок для генератора и раздела
«Паспорт SKU» (решение владельца 28.10.2026: один паспорт на SKU для всего
приложения).

Копия неизменная (триггер passport_copy_frozen), SKU, id и версия — из шапки
файла (`services/passport_copies.py`). Другой действующий паспорт SKU — вопрос
«заменить?» (решение владельца 21.10.2026), ответ — второй кнопкой. Права — в
момент нажатия, `ls.textgen.accept`.

`prefix` разводит ключи виджетов и состояния двух страниц (правило 8), `say` —
вывод сообщений страницы (генератор экранирует «$»).
"""
from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

import auth
from i18n import t
from services import passport_copies as pc


def render(prefix: str, say=st, sku_hint: str | None = None, lock_sku: bool = False) -> dict | None:
    """Поле загрузки, сохранение и список копий SKU. Возвращает шапку файла
    (или None). `sku_hint` — SKU, выбранный на странице: файл другого SKU
    называется вслух. `lock_sku` — на странице выбранного товара («Создание»)
    чужой паспорт не сохраняется вовсе (проверка #176); генератор SKU не
    выбирает и сохраняет по шапке файла."""
    say.caption(t("tg.pp.hint", volume=pc.VOLUME))
    up = st.file_uploader(t("tg.pp.upload"), type=["docx"], key=f"{prefix}-file")
    header = None
    if up is not None:
        data = up.getvalue()
        try:
            header = pc.read_header(data)
        except pc.CopyError as e:
            say.error(t(f"tg.pp.err.{e.code}", detail=e.detail))
    if not header:
        return None
    state = header.get("state") or "—"
    say.markdown(t("tg.pp.header", sku=header["sku_id"], pid=header["passport_id"],
                   ver=header["passport_version"], state=state))
    other = bool(sku_hint) and header["sku_id"] != sku_hint
    if other:
        say.warning(t("pp.up.other_sku_locked" if lock_sku else "pp.up.other_sku",
                      file_sku=header["sku_id"], sku=sku_hint))
    if state != "READY":
        say.warning(t("tg.pp.not_ready", state=state))
    say.caption(t("tg.pp.path", path=f"{pc.ROOT}/{pc.copy_path(header)}"))
    may = auth.can("ls.textgen.accept") and not (lock_sku and other)
    if not may:
        say.caption(t("tg.pp.denied_hint"))
    sha = hashlib.sha256(data).hexdigest()
    ask_state = f"{prefix}-ask"

    def _save(replace: tuple = ()) -> None:
        st.session_state.pop(ask_state, None)
        if not auth.require("ls.textgen.accept", object_type="passport", object_id=header["passport_id"]):
            return
        try:
            store = pc.volume_store()
        except pc.CopyError as e:
            say.error(t(f"tg.pp.err.{e.code}", detail=e.detail))
            return
        if store is None:
            say.error(t("tg.pp.no_store"))
            return
        from services.db import get_conn
        try:
            conn = get_conn()
        except Exception as e:  # noqa: BLE001
            say.error(t("tg.pp.err.DB_FAILED", detail=f"{type(e).__name__}: {str(e)[:160]}"))
            return
        try:
            res = pc.register(data, up.name, actor=auth.actor(), store=store, conn=conn, replace=replace)
        except pc.CopyError as e:
            if e.code == "OTHER_PASSPORT_ACTIVE":
                # Вопрос — заново и с новым ключом кнопки: нажатие по прежнему
                # вопросу не должно ответить на другой (проверка #164).
                st.session_state[ask_state] = (sha, e.active)
                st.rerun()           # соединение закроет finally
            else:
                say.error(t(f"tg.pp.err.{e.code}", detail=e.detail))
        except Exception as e:  # noqa: BLE001 — база: файл уже в томе, повтор его узнает
            say.error(t("tg.pp.err.DB_FAILED", detail=f"{type(e).__name__}: {str(e)[:160]}"))
        else:
            if res.status == "DUPLICATE":
                say.info(t("tg.pp.duplicate", aid=res.artifact_id, loc=res.locator))
            else:
                say.success(t("tg.pp.saved", aid=res.artifact_id, loc=res.locator, sha=sha[:12]))
                if res.superseded:
                    say.info(t("tg.pp.superseded", ids=", ".join(res.superseded)))
                from services import passport as pp_svc
                pp_svc.load_registry.clear()   # Реестр должен увидеть новую копию сразу
        finally:
            conn.close()

    ask_box = st.empty()
    if st.button(t("tg.pp.save"), type="primary", disabled=not may, key=f"{prefix}-save"):
        _save()
    ask = st.session_state.get(ask_state)
    if ask and ask[0] == sha:
        # Вопрос привязан к ЭТОМУ файлу и к ЭТОМУ набору копий: ключ кнопки несёт
        # их отпечаток, поэтому новый вопрос — новая кнопка.
        ask_key = hashlib.sha256("|".join(ask[1]).encode("utf-8")).hexdigest()[:12]
        with ask_box.container():
            say.warning(t("tg.pp.ask_replace", sku=header["sku_id"], ids=", ".join(ask[1]),
                          pid=header["passport_id"]))
            go = st.button(t("tg.pp.replace"), disabled=not may, key=f"{prefix}-replace-{ask_key}")
        if go:
            ask_box.empty()          # ответ получен — вопрос над итогом не висит
            _save(replace=tuple(ask[1]))
    copies_table(header["sku_id"], say)
    return header


def copies_table(sku: str, say=st) -> None:
    """Копии паспорта SKU: версия, SHA, действует ли."""
    lst, lerr = pc.copies(sku)
    say.markdown(f"**{t('tg.pp.list', sku=sku)}**")
    if lerr:
        say.error(t("tg.pp.list_error", err=lerr))
        return
    if lst.empty:
        say.caption(t("tg.pp.none", sku=sku))
        return
    view = pd.DataFrame({
        "id": lst["source_artifact_id"],
        "ver": lst["archived_locator"].map(lambda x: pc.version_of(x) if isinstance(x, str) else None),
        "sha": lst["sha256"].map(lambda x: x[:12] if isinstance(x, str) else ""),
        "pid": lst["passport_id"],
        "life": lst["lifecycle"].map(lambda x: t(f"tg.pp.life.{x}") if x in ("ACTIVE", "OLD") else x),
        "by": lst["registered_by"],
        "at": lst["recorded_at"],
    })
    st.dataframe(view, hide_index=True, width="stretch",
                 column_config={"id": st.column_config.TextColumn(t("tg.pp.col.id")),
                                "ver": st.column_config.NumberColumn(t("tg.pp.col.version")),
                                "pid": st.column_config.TextColumn(t("tg.pp.col.pid")),
                                "sha": st.column_config.TextColumn(t("tg.pp.col.sha")),
                                "life": st.column_config.TextColumn(t("tg.pp.col.lifecycle")),
                                "by": st.column_config.TextColumn(t("tg.pp.col.by")),
                                "at": st.column_config.DatetimeColumn(t("tg.pp.col.at"))})
