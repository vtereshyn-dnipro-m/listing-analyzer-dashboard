# -*- coding: utf-8 -*-
"""
pages/textgen.py — «Генератор текстов (пилот)».

Верх — пилотный товар: характеристики (с источником каждого значения), чего не
хватает, расхождения карточки, набор и ключи по типу товара; тайтл и Item
Highlights пишутся руками, правила тайтла проверяют их на каждом изменении — без
модели. Низ — паспорт SKU: загрузка копии docx в том UC и генерация по нему
(`services/textgen.py`): платный вызов модели по нажатию с правом
`ls.textgen.accept`, черновики в `content_versions`. В Amazon ничего не уходит.

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
import json
import re

import pandas as pd
import streamlit as st

import auth

from components.ui import eyebrow, inject_fonts
from i18n import t
from services import ai
from services import passport_copies as pc
from services import passport as passport_svc
from services import passport_facts as pf
from services import product_specs as ps
from services import seo
from services import textgen as tg
from services import title_rules as tr
from services.cells import cell_text
from services.settings import get_setting

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
    say.markdown(eyebrow(text), unsafe_allow_html=True)


def esc_dollar(text: str) -> str:
    """«$» → «\\$» вне `кода`: Streamlit читает «$…$» в markdown как формулу, а
    внутри обратных кавычек обратная косая черта не работает и осталась бы на
    экране (проверка #168)."""
    parts = re.split(r"(`[^`]*`)", str(text))
    return "".join(p if p.startswith("`") and p.endswith("`") and len(p) > 1 else p.replace("$", "\\$")
                   for p in parts)


class _Say:
    """st.caption / warning / … с экранированным «$» (см. esc_dollar): «$1 на
    товар … $10» иначе превращалось в курсив без знаков."""

    def __getattr__(self, name):
        fn = getattr(st, name)
        return lambda text, *a, **k: fn(esc_dollar(text), *a, **k)


say = _Say()
say.info(t("tg.pilot_note"))


# Связь SKU ↔ ASIN: справочник SKU Кабинета (точный код) и матрица ES.
@st.cache_data(ttl=600, show_spinner=False)
def _directory():
    df, err = passport_svc.sku_directory()
    if err:
        raise _ReadFailed(err)
    return df


@st.cache_data(ttl=600, show_spinner=False)
def _matrix_es():
    from services.db import safe_read
    # конкуренты — не наши ASIN, даже с нашим sku_group (проверка #168)
    df, err = safe_read("SELECT asin, sku_group FROM product_matrix"
                        " WHERE marketplace = 'es' AND is_competitor IS NOT TRUE")
    if err:
        raise _ReadFailed(err)
    return df


def _links():
    """(справочник, матрица ES, причины сбоя) — сбой одного источника не гасит другой."""
    errs, d, m = [], None, None
    try:
        d = _directory()
    except Exception as e:  # noqa: BLE001
        errs.append(t("tg.link.src_dir", err=str(e)[:120]))
    try:
        m = _matrix_es()
    except Exception as e:  # noqa: BLE001
        errs.append(t("tg.link.src_matrix", err=str(e)[:120]))
    return d, m, errs


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
link_dir, link_mx, link_errs = _links()
top_skus = tg.skus_for_asin(asin, link_dir, link_mx)
if top_skus:
    say.caption(t("tg.link.sku", skus=", ".join(top_skus)))
elif not link_errs:
    say.caption(t("tg.link.sku_none"))
if link_errs:
    # «не прочитано», а не «не найдено»: сбой источника не выдаётся за пустоту
    say.caption(t("tg.link.error", err="; ".join(link_errs)))

raw, err = load_raw(asin, mp)
if err:
    say.error(t("tg.load_error", err=err))
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
say.caption(t("tg.current_title", n=len(current_title), title=current_title or "—"))

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
    say.caption(t("tg.no_specs"))

parts = ps.title_parts(specs)
say.markdown(f"**{t('tg.for_title')}:** " + (", ".join(parts) if parts else "—"))
if specs.missing:
    say.warning(t("tg.missing", fields=", ".join(t(f"tg.field.{f}") for f in specs.missing)))
for fld, have, other in specs.conflicts:
    say.warning(t("tg.conflict", field=t(f"tg.field.{fld}"),
                 a=ps.fmt(fld, have.value), a_src=t(f"tg.src.{have.source}"),
                 b=ps.fmt(fld, other.value), b_src=t(f"tg.src.{other.source}")))
if specs.kit:
    say.markdown(f"**{t('tg.kit')}:** " + "; ".join(specs.kit))
else:
    say.caption(t("tg.no_kit"))

# --------------------------------------------------------- ключи
section(t("tg.keys"))
keys_df = None
if specs.tool_type:
    keys_df, kerr, n_asins = load_keys(specs.tool_type, mp, current_title)
    if kerr:
        say.error(t("tg.keys_error", err=kerr))
    elif keys_df is None or keys_df.empty:
        say.caption(t("tg.keys_empty", n=n_asins))
    else:
        say.caption(t("tg.keys_from", n=n_asins))
else:
    say.caption(t("tg.keys_no_type"))

# ------------------------------------------------- ручной ввод
section(t("tg.write"))
say.caption(t("tg.write_hint"))
title_in = st.text_input(t("tg.title_label"), key=f"tg-title-{asin}")
hl_in = st.text_area(t("tg.hl_label"), key=f"tg-hl-{asin}", height=90)


def counter(n: int, limit: int) -> str:
    color = ACCENT if n > limit else (GREEN if n else MUTED)
    return f'<span style="color:{color};font-weight:600">{n} / {limit}</span>'


say.markdown(f'{t("tg.title_len")}: ' + counter(len(title_in), tr.TITLE_LIMIT) + " · "
            + f'{t("tg.hl_len")}: ' + counter(len(hl_in), tr.Ruleset().highlight_limit),
            unsafe_allow_html=True)

if title_in or hl_in:
    found = tr.check(title_in, hl_in, kind=specs.kind, model=specs.model if hl_in else None)
    if found:
        say.error(t("tg.violations", n=len(found)))
        for v in found:
            say.markdown(f"- **{t(f'tg.code.{v.code}')}** ({t(f'tg.where.{v.field}')})"
                        + (f": `{v.detail}`" if v.detail else ""))
    else:
        say.success(t("tg.all_ok"))
    # Без модели префикс «Model …: » не проверить. «Нарушений нет» без этой
    # оговорки выдавало бы непроверенное за проверенное.
    if hl_in and not specs.model:
        say.warning(t("tg.no_model_prefix"))

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
say.caption(t("tg.pp.hint", volume=pc.VOLUME))
up = st.file_uploader(t("tg.pp.upload"), type=["docx"], key="tg-pp-file")
pp_header = None
if up is not None:
    pp_data = up.getvalue()
    try:
        pp_header = pc.read_header(pp_data)
    except pc.CopyError as e:
        say.error(t(f"tg.pp.err.{e.code}", detail=e.detail))
if pp_header:
    state = pp_header.get("state") or "—"
    say.markdown(t("tg.pp.header", sku=pp_header["sku_id"], pid=pp_header["passport_id"],
                  ver=pp_header["passport_version"], state=state))
    if state != "READY":
        say.warning(t("tg.pp.not_ready", state=state))
    say.caption(t("tg.pp.path", path=f"{pc.ROOT}/{pc.copy_path(pp_header)}"))
    may = auth.can("ls.textgen.accept")
    if not may:
        say.caption(t("tg.pp.denied_hint"))
    pp_sha = hashlib.sha256(pp_data).hexdigest()

    def _save(replace: tuple = ()) -> None:
        """Запись копии; право — в момент нажатия. Другой действующий паспорт SKU —
        вопрос «заменить?» (решение владельца 21.10.2026), ответ — второй кнопкой."""
        st.session_state.pop("tg-pp-ask", None)
        if not auth.require("ls.textgen.accept", object_type="passport", object_id=pp_header["passport_id"]):
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
            res = pc.register(pp_data, up.name, actor=auth.actor(), store=store, conn=conn, replace=replace)
        except pc.CopyError as e:
            if e.code == "OTHER_PASSPORT_ACTIVE":
                # Вопрос — заново и с новым ключом кнопки: нажатие по прежнему
                # вопросу не должно ответить на другой (проверка #164).
                st.session_state["tg-pp-ask"] = (pp_sha, e.active)
                st.rerun()           # соединение закроет finally
            else:
                say.error(t(f"tg.pp.err.{e.code}", detail=e.detail))
        except Exception as e:  # noqa: BLE001 — база: файл уже в томе, повтор его узнает
            say.error(t("tg.pp.err.DB_FAILED", detail=f"{type(e).__name__}: {str(e)[:160]}"))
        else:
            if res.status == "DUPLICATE":
                say.info(t("tg.pp.duplicate", aid=res.artifact_id, loc=res.locator))
            else:
                say.success(t("tg.pp.saved", aid=res.artifact_id, loc=res.locator, sha=pp_sha[:12]))
                if res.superseded:
                    say.info(t("tg.pp.superseded", ids=", ".join(res.superseded)))
        finally:
            conn.close()

    ask_box = st.empty()
    if st.button(t("tg.pp.save"), type="primary", disabled=not may, key="tg-pp-save"):
        _save()
    ask = st.session_state.get("tg-pp-ask")
    if ask and ask[0] == pp_sha:
        # Вопрос привязан к ЭТОМУ файлу и к ЭТОМУ набору копий: ключ кнопки несёт
        # их отпечаток, поэтому новый вопрос — новая кнопка.
        ask_key = hashlib.sha256("|".join(ask[1]).encode("utf-8")).hexdigest()[:12]
        with ask_box.container():
            say.warning(t("tg.pp.ask_replace", sku=pp_header["sku_id"], ids=", ".join(ask[1]),
                         pid=pp_header["passport_id"]))
            go = st.button(t("tg.pp.replace"), disabled=not may, key=f"tg-pp-replace-{ask_key}")
        if go:
            ask_box.empty()          # ответ получен — вопрос над итогом не висит
            _save(replace=tuple(ask[1]))
    lst, lerr = pc.copies(pp_header["sku_id"])
    say.markdown(f"**{t('tg.pp.list', sku=pp_header['sku_id'])}**")
    if lerr:
        say.error(t("tg.pp.list_error", err=lerr))
    elif lst.empty:
        say.caption(t("tg.pp.none", sku=pp_header["sku_id"]))
    else:
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

# ------------------------------------------------------- генерация по паспорту
# Модель — только по нажатию человека с правом ls.textgen.accept; лимиты и учёт
# денег — в services/textgen.py по журналу textgen_calls (решение владельца 21.10.2026).


@st.cache_data(ttl=120, show_spinner=False)
def _textgen_method() -> tuple[str, int, str | None]:
    """Действующая методология области textgen: (текст, версия, причина-сбоя)."""
    from services.db import safe_read
    df, err = safe_read("SELECT skill_text, version FROM synthesis_skill WHERE scope = %(s)s"
                        " AND is_active = TRUE ORDER BY version DESC LIMIT 1", {"s": tg.SCOPE})
    if err:
        raise _ReadFailed(err)
    if df.empty:
        return "", 0, None
    return cell_text(df.iloc[0], "skill_text"), int(df.iloc[0]["version"]), None


@st.cache_data(ttl=3600, show_spinner=False)
def _copy_conflicts(locator: str, sha: str) -> tuple[list[str], list[str]]:
    """Поля «Конфлікти» сохранённой копии и строки фактов, снятые из-за них, — для
    подписи «нужно решение». Ключ — SHA: копия неизменна, читать том на каждой
    перерисовке незачем. Сбой — исключение (не кешируется), страница его называет."""
    store = pc.volume_store()
    if store is None:
        raise _ReadFailed(t("tg.pp.no_store"))
    data = store.get(locator)
    if hashlib.sha256(data).hexdigest() != sha:
        raise _ReadFailed("SHA")
    facts = pf.read(data)
    facts.prompt_text()
    return [c["field"] for c in facts.conflicts if c["field"]], list(facts.dropped)


def _check_line(v: dict) -> str:
    if v.get("code") == "NO_MODEL_PREFIX_CHECK":
        return f"- {t('tg.no_model_prefix')}"
    where = "highlights" if v.get("field") == "highlight" else v.get("field")
    where_txt = t(f"tg.where.{where}") if where in ("title", "highlights") else t(
        "tg.gen.field.bullet", n=where.split("_")[1]) if str(where).startswith("bullet_") else t(f"tg.gen.field.{where}")
    detail = str(v.get("detail") or "").replace("`", "'")
    return (f"- **{t('tg.code.' + str(v.get('code')))}** ({where_txt})" + (f": `{detail}`" if detail else ""))


section(t("tg.gen.title"))
say.caption(t("tg.gen.hint"))
copies_df, copies_err = tg.active_copies()
if copies_err:
    say.error(t("tg.gen.copies_error", err=copies_err))
elif copies_df.empty:
    say.caption(t("tg.gen.no_copies"))
else:
    skus = list(copies_df["sku_id"])
    pre = pp_header["sku_id"] if pp_header and pp_header["sku_id"] in skus else skus[0]
    g1, g2 = st.columns(2)
    g_sku = g1.selectbox(t("tg.gen.sku"), skus, index=skus.index(pre), key="tg-gen-sku")
    mps = list(tg.LANGUAGE)
    g_mp = g2.selectbox(t("tg.gen.mp"), mps, index=mps.index("es"), format_func=str.upper, key="tg-gen-mp")
    g_copy = copies_df[copies_df["sku_id"] == g_sku].iloc[0].to_dict()
    g_asins = tg.asins_for_sku(g_sku, link_dir, link_mx)
    if g_asins:
        say.caption(t("tg.link.asins", asins=", ".join(g_asins)))
    if link_errs:
        say.caption(t("tg.link.error", err="; ".join(link_errs)))
    if not g_asins and link_errs:
        say.caption(t("tg.link.unread", sku=g_sku))
    elif not g_asins:
        say.caption(t("tg.link.asins_none", sku=g_sku))
        say.warning(t("tg.link.no_asin", sku=g_sku, asin=asin))
    elif asin not in g_asins and not link_errs:
        # при сбое источника связь неполная — «про разные товары» не утверждаем
        say.warning(t("tg.link.mismatch", asin=asin, sku=g_sku, asins=", ".join(g_asins),
                      top=", ".join(top_skus) or "—"))
    say.caption(t("tg.gen.passport", pid=cell_text(g_copy, "passport_id"), aid=cell_text(g_copy, "source_artifact_id")))
    try:
        g_conf, g_dropped = _copy_conflicts(cell_text(g_copy, "archived_locator"), cell_text(g_copy, "sha256"))
    except Exception as e:  # noqa: BLE001 — сбой называется: молчание выглядело бы «конфликтов нет»
        g_conf, g_dropped = [], []
        say.warning(t("tg.gen.conflicts_error", err=f"{type(e).__name__}: {str(e)[:160]}"))
    if g_conf:
        say.warning(t("tg.gen.conflicts", fields=", ".join(g_conf)))
    if g_dropped:
        say.caption(t("tg.gen.dropped", rows=", ".join(g_dropped)))

    from services.db import table_exists
    g_reason, g_detail = None, ""
    g_prov, g_model = ai.task_config(tg.TASK)
    g_maxtok = ai.task_limits(tg.TASK)[0]
    g_method, g_mver = "", 0
    if table_exists("textgen_calls") is False:
        g_reason = "NO_TABLE"
        say.warning(t("tg.gen.no_table"))
    elif table_exists("content_versions") is False:
        g_reason = "NO_CONTENT_TABLE"
        say.warning(t("tg.gen.err.NO_CONTENT_TABLE", detail="content_versions"))
    else:
        g_usage, g_uerr = tg.usage_now(g_sku)
        try:
            g_method, g_mver, _ = _textgen_method()
        except _ReadFailed as e:
            g_uerr = g_uerr or str(e)
        if g_uerr:
            g_reason = "USAGE"
            say.error(t("tg.gen.usage_error", err=g_uerr))
        else:
            say.caption(t("tg.gen.usage", n=g_usage.calls_sku, n_max=tg.LIMIT_CALLS_SKU_DAY, a=g_usage.usd_sku,
                         a_max=tg.LIMIT_USD_SKU_DAY, b=g_usage.usd_pilot, b_max=tg.LIMIT_USD_PILOT_DAY))
            g_price = tg.price(g_model, get_setting)
            if not g_method.strip() or not g_mver:
                g_reason, g_detail = "NO_METHOD", tg.SCOPE
            elif g_prov not in tg.PROVIDERS:
                g_reason, g_detail = "PROVIDER", g_prov
            elif g_price is None:
                g_reason, g_detail = "NO_PRICE", g_model
            else:
                # Кнопка гаснет заранее по худшей оценке; окончательно решает
                # проверка под блокировкой в момент нажатия.
                why = tg.block_reason(g_usage, tg.estimate(g_price, 12_000 + len(g_method), g_maxtok))
                if why:
                    g_reason, g_detail = why
            if g_reason:
                say.warning(t(f"tg.gen.err.{g_reason}", detail=g_detail))
    g_may = auth.can("ls.textgen.accept")
    if not g_may:
        say.caption(t("tg.pp.denied_hint"))
    if st.button(t("tg.gen.button"), type="primary", disabled=bool(g_reason) or not g_may, key="tg-gen-go"):
        if auth.require("ls.textgen.accept", object_type="textgen", object_id=f"{g_sku}:{g_mp}"):
            try:
                g_store = pc.volume_store()
            except pc.CopyError as e:
                g_store = False
                say.error(t("tg.gen.err.STORE", detail=e.detail))
            if g_store is None:
                say.error(t("tg.pp.no_store"))
            elif g_store:
                from services.db import get_conn as _gen_conn
                try:
                    g_conn = _gen_conn()
                except Exception as e:  # noqa: BLE001
                    g_conn = None
                    say.error(t("tg.gen.err.DB", detail=f"{type(e).__name__}: {str(e)[:160]}"))
                if g_conn is not None:
                    try:
                        with st.spinner(t("tg.gen.running")):
                            res = tg.generate(
                                sku=g_sku, marketplace=g_mp, copy=g_copy, actor=auth.actor(), store=g_store,
                                conn=g_conn, method=(g_method, g_mver), provider=g_prov, model=g_model,
                                max_tokens=g_maxtok, setting=get_setting,
                                ai_call=ai.generate_json, ai_usage=ai.usage_totals, ai_reset=ai.reset_usage,
                                ai_error=ai.last_call_error)
                    except Exception as e:  # noqa: BLE001 — база или том: причина на экран
                        say.error(t("tg.gen.err.DB", detail=f"{type(e).__name__}: {str(e)[:200]}"))
                    else:
                        if res.status == "OK":
                            say.success(t("tg.gen.done", proposal=res.proposal_id, cost=res.cost_usd))
                        else:
                            say.error(t(f"tg.gen.err.{res.code}", detail=res.detail))
                    finally:
                        g_conn.close()

    lat, lat_err = tg.latest(g_sku, g_mp)
    if lat_err:
        say.error(t("tg.gen.latest_error", err=lat_err))
    elif lat.empty:
        say.caption(t("tg.gen.none", sku=g_sku, mp=g_mp.upper()))
    else:
        r0 = lat.iloc[0]
        say.markdown("**" + t("tg.gen.latest", proposal=cell_text(r0, "proposal_id"), model=cell_text(r0, "model"),
                             at=str(r0["created_at"])[:16]) + "**")
        order = {f: i for i, f in enumerate(tg.FIELDS)}
        limits = {"title": tr.TITLE_LIMIT, "highlight": tr.Ruleset().highlight_limit}
        any_bad = False
        for _, row in sorted(lat.iterrows(), key=lambda x: order.get(x[1]["field"], 99)):
            f = row["field"]
            label = (t("tg.gen.field.bullet", n=f.split("_")[1]) if f.startswith("bullet_")
                     else t(f"tg.gen.field.{f}"))
            n = int(row["text_len"])
            say.markdown(f"{label} · " + (counter(n, limits[f]) if f in limits else str(n)), unsafe_allow_html=True)
            st.code(cell_text(row, "text"), language=None, wrap_lines=True)
            raw = row["checks"]
            items = raw if isinstance(raw, list) else (json.loads(raw) if isinstance(raw, str) and raw else [])
            for v in items:
                any_bad = True
                say.markdown(_check_line(v))
        if not any_bad:
            say.success(t("tg.gen.ok_checks"))
