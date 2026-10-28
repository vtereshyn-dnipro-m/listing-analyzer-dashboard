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
import deploy_sync

from components import passport_upload
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
def _matrix_mp(mp: str):
    from services.db import safe_read
    # конкуренты — не наши ASIN, даже с нашим sku_group (проверка #168)
    df, err = safe_read("SELECT asin, sku_group FROM product_matrix"
                        " WHERE marketplace = %(mp)s AND is_competitor IS NOT TRUE", {"mp": mp})
    if err:
        raise _ReadFailed(err)
    return df


def _matrix_es():
    return _matrix_mp("es")


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
pp_header = passport_upload.render("tg-pp", say)

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
def _copy_facts(locator: str, sha: str) -> pf.Facts:
    """Поля «Конфлікти» сохранённой копии и строки фактов, снятые из-за них, — для
    подписи «нужно решение». Ключ — SHA: копия неизменна, читать том на каждой
    перерисовке незачем. Сбой — исключение (не кешируется), страница его называет."""
    store = pc.volume_store()
    if store is None:
        raise _ReadFailed(t("tg.pp.no_store"))
    data = store.get(locator)
    if hashlib.sha256(data).hexdigest() != sha:
        raise _ReadFailed("SHA")
    return pf.read(data)


def _copy_conflicts(locator: str, sha: str, artifact_id: str) -> tuple[list[str], list[str], list[str], str | None]:
    """Открытые поля, снятые строки, решённые конфликты и сбой чтения решений.
    Копия кэшируется по SHA, решения — нет: их пишут в любой момент, и закрытый
    конфликт должен перестать числиться открытым сразу (решение владельца 28.10.2026)."""
    import copy as _copy

    from services import passport_decisions as pdec
    facts = _copy.deepcopy(_copy_facts(locator, sha))
    decisions, derr, _missing = pdec.load(artifact_id, sha)
    pf.apply_decisions(facts, decisions)
    open_fields, dropped, decided = pf.conflict_summary(facts)
    return open_fields, dropped, [f"{f} → {v} ({s})" for f, v, s in decided], derr


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
    # Тот же SKU, что выбран в разделе «Паспорт SKU» (pp-sku): контекст сменился —
    # генератор встаёт на него. Значение пишется ДО создания виджета (правило 7б);
    # дальше человек вправе выбрать здесь другой (поручение владельца 28.10.2026).
    g_ctx = st.session_state.get("pp-sku")
    if g_ctx in skus and st.session_state.get("tg-gen-ctx") != g_ctx:
        st.session_state["tg-gen-sku"] = g_ctx
    st.session_state["tg-gen-ctx"] = g_ctx
    if st.session_state.get("tg-gen-sku") not in skus:
        st.session_state.pop("tg-gen-sku", None)
    g1, g2 = st.columns(2)
    g_sku = g1.selectbox(t("tg.gen.sku"), skus, key="tg-gen-sku",
                         **({} if "tg-gen-sku" in st.session_state else {"index": skus.index(pre)}))
    mps = list(tg.LANGUAGE)
    g_mp = g2.selectbox(t("tg.gen.mp"), mps, index=mps.index("es"), format_func=str.upper, key="tg-gen-mp")
    g_copy = copies_df[copies_df["sku_id"] == g_sku].iloc[0].to_dict()
    # Тип товара — из данных листинга (как в Реестре): он определяет правила
    # генерации — аккумулятор и зарядка с вольтажем в тайтле, инструмент без.
    g_type, g_terr = passport_svc.sku_type(g_sku)
    if g_terr:
        say.caption(t("tg.gen.type_error", err=str(g_terr)[:160]))
    say.caption(t("tg.gen.type", type=t(f"tg.type.{g_type}")) if g_type else t("tg.gen.type_unknown"))
    g_asins = tg.asins_for_sku(g_sku, link_dir, link_mx)
    # ASIN для черновиков — на ВЫБРАННОЙ площадке (решение владельца 23.10.2026).
    # Не прочитался хоть один источник связи — None: неполный список дал бы
    # «ровно один» там, где их на деле два.
    g_mx_mp, g_mx_err = link_mx, None
    if g_mp != "es":
        try:
            g_mx_mp = _matrix_mp(g_mp)
        except Exception as e:  # noqa: BLE001 — сбой называется, а не выдаётся за «ASIN нет»
            g_mx_mp, g_mx_err = None, t("tg.link.src_matrix", err=str(e)[:120])
    g_link_asins = (None if link_errs or g_mx_err or link_dir is None or g_mx_mp is None
                    else tg.asins_for_sku(g_sku, link_dir, g_mx_mp))
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
    if g_mx_err:
        say.caption(t("tg.link.error", err=g_mx_err))
    # Какой ASIN уйдёт в черновики — видно ДО нажатия (для любой площадки), и решает
    # его ТОТ ЖЕ pick_asin, что и запись: экран не обещает другого (проверка #171).
    g_pick, g_why = tg.pick_asin(g_link_asins)
    say.caption(t("tg.link.draft_asin", mp=g_mp.upper(), asin=g_pick) if g_pick
                else t("tg.link.draft_no_asin", mp=g_mp.upper(), why=t(f"tg.code.{g_why['code']}")
                       + (f" ({g_why['detail']})" if g_why.get("detail") else "")))
    say.caption(t("tg.gen.passport", pid=cell_text(g_copy, "passport_id"), aid=cell_text(g_copy, "source_artifact_id")))
    try:
        g_conf, g_dropped, g_decided, g_derr = _copy_conflicts(
            cell_text(g_copy, "archived_locator"), cell_text(g_copy, "sha256"), cell_text(g_copy, "source_artifact_id"))
    except Exception as e:  # noqa: BLE001 — сбой называется: молчание выглядело бы «конфликтов нет»
        g_conf, g_dropped, g_decided, g_derr = [], [], [], None
        say.warning(t("tg.gen.conflicts_error", err=f"{type(e).__name__}: {str(e)[:160]}"))
    if g_derr:
        say.warning(t("tg.gen.decisions_error", err=g_derr))
    if g_decided:
        say.caption(t("tg.gen.decided", items="; ".join(g_decided)))
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
                                asins=g_link_asins, ai_error=ai.last_call_error,
                                rules_version=deploy_sync.current_commit(), tool_type=g_type)
                    except Exception as e:  # noqa: BLE001 — база или том: причина на экран
                        say.error(t("tg.gen.err.DB", detail=f"{type(e).__name__}: {str(e)[:200]}"))
                    else:
                        if res.status == "OK":
                            say.success(t("tg.gen.done", proposal=res.proposal_id, cost=res.cost_usd))
                            if not res.stamped:
                                say.caption(t("tg.gen.no_stamp", file=tg.STAMP_MIGRATION))
                            elif not res.rules_version:
                                say.caption(t("tg.gen.no_rules_version"))
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
                if v.get("code") in tg.ASIN_CODES:
                    continue          # пометка про ASIN — не нарушение, она ниже отдельной строкой
                any_bad = True
                say.markdown(_check_line(v))
        if not any_bad:
            say.success(t("tg.gen.ok_checks"))
        notes = [v for _, row in lat.iterrows() for v in (
            row["checks"] if isinstance(row["checks"], list)
            else (json.loads(row["checks"]) if isinstance(row["checks"], str) and row["checks"] else []))
            if v.get("code") in tg.ASIN_CODES]
        r_asin = cell_text(r0, "asin")
        say.caption(t("tg.link.saved_asin", asin=r_asin) if r_asin else
                    t("tg.link.saved_no_asin", why="; ".join(
                        t(f"tg.code.{v['code']}") + (f" ({v['detail']})" if v.get("detail") else "") for v in notes)
                        or t("tg.link.saved_no_reason")))
