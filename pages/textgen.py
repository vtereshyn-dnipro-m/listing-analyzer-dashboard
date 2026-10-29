# -*- coding: utf-8 -*-
"""
pages/textgen.py — «Генератор текстов (пилот)».

Логическая страница (ТЗ владельца 29.10.2026, блоки 1–6; здесь — 1, 3 и 5):

1. **Товар — один выбор на всю страницу**: список Реестра (весь справочник SKU
   Кабинета и товары с паспортом, как в «Паспорт SKU») и поиск по SKU, названию,
   модели, ASIN и EAN. Выбор общий с «Паспорт SKU» и Верификатором (`pp-sku`) в обе
   стороны. Площадка и язык — ES, только подписью. ASIN ES — только если он ровно
   один (`textgen.pick_asin`), иначе пусто с причиной.
3. **Генерация по паспорту**: платный вызов модели по нажатию с правом
   `ls.textgen.accept`, черновики в `content_versions`, в Amazon ничего. Без паспорта
   блок на месте, кнопка выключена с причиной.
5. **Ручная проверка — свёрнуто внизу**: тайтл и Item Highlights руками, правила на
   каждом изменении; ключи по типу. В генерацию не идёт, факты паспорта здесь не
   проверяются. Тип — `passport.sku_type`, модель для префикса — из паспорта.

Характеристик листинга на странице нет (решение владельца 29.10.2026): факты —
только паспорта, иначе смешались бы с значениями листинга.

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

from components import passport_area
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

# Пилот — только Amazon ES: площадка и язык не выбираются (решение владельца 29.10.2026).
MP = "es"

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
    """Снапшот листинга: нынешний тайтл для отметки ключей (характеристик листинга
    на странице нет)."""
    try:
        return _raw_cached(asin, marketplace), None
    except _ReadFailed as e:
        return None, str(e)


def counter(n: int, limit: int) -> str:
    color = ACCENT if n > limit else (GREEN if n else MUTED)
    return f'<span style="color:{color};font-weight:600">{n} / {limit}</span>'


def _upload() -> None:
    """Паспорт SKU (docx): копия — в томе UC, неизменная; SKU, id и версия — из шапки
    файла (services/passport_copies.py). Права — в момент нажатия, как везде."""
    section(t("tg.pp.title"))
    passport_upload.render("tg-pp", say)


def load_keys(tool_type: str, marketplace: str, title: str):
    try:
        df, n = _keys_cached(tool_type, marketplace, title)
        return df, None, n
    except _ReadFailed as e:
        return None, str(e), 0


# ------------------------------------------------- 1. товар — один выбор
# Один выбор на всю страницу и общий с «Паспорт SKU» и Верификатором (pp-sku), в
# обе стороны: тот же список, что в Реестре, и тот же колбэк (set_context).
# Генератор на свой SKU больше не уходит (решение владельца 29.10.2026).
section(t("tg.b1.title"))
reg = passport_svc.load_registry()
link_dir, link_mx, link_errs = _links()
directory, dir_err = passport_svc.sku_directory()
u = passport_area.universe(directory, reg.get("objects"))
query = st.text_input(t("tg.b1.search"), key="tg-q", placeholder=t("pp.search_ph"))
only = None
if query.strip():
    view, total = passport_svc.search(directory, reg.get("objects"), query)
    only = list(view["sku"].astype(str))
    say.caption(t("tg.b1.found", n=total, shown=len(only)))
passport_area.render_picker(directory, dir_err, reg.get("objects"), u, only=only)
g_sku = st.session_state.get("pp-sku")

say.caption(t("tg.b1.mp_lang"))
if not g_sku:
    say.info(t("tg.b1.pick_first"))
    _upload()
    st.stop()

# Тип товара — из данных листинга (как в Реестре): он определяет правила генерации
# и ручной проверки — аккумулятор и зарядка с вольтажем в тайтле, инструмент без.
g_type, g_terr = passport_svc.sku_type(g_sku)
if g_terr:
    say.caption(t("tg.gen.type_error", err=str(g_terr)[:160]))
say.caption(t("tg.gen.type", type=t(f"tg.type.{g_type}")) if g_type else t("tg.gen.type_unknown"))
# ASIN ES — только если он ровно один (тот же pick_asin, что у черновиков): для
# снапшота и ключей. Не прочитался хоть один источник связи — None, а не неполный
# список: он дал бы «ровно один» там, где их на деле два.
g_link_asins = (None if link_errs or link_dir is None or link_mx is None
                else tg.asins_for_sku(g_sku, link_dir, link_mx))
g_asin, g_asin_why = tg.pick_asin(g_link_asins)
if link_errs:
    say.caption(t("tg.link.error", err="; ".join(link_errs)))
say.caption(t("tg.b1.asin", asin=g_asin) if g_asin else
            t("tg.b1.asin_none", why=t(f"tg.b1.why.{g_asin_why['code']}")
              + (f" ({g_asin_why['detail']})" if g_asin_why.get("detail") else "")))
current_title = ""
if g_asin:
    raw, err = load_raw(g_asin, MP)
    if err:
        say.error(t("tg.load_error", err=err))
    else:
        current_title = (raw or {}).get("title") or ""

_upload()

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
g_copy = None
if copies_err:
    say.error(t("tg.gen.copies_error", err=copies_err))
elif not copies_df.empty:
    mine = copies_df[copies_df["sku_id"].astype(str) == g_sku]
    g_copy = mine.iloc[0].to_dict() if not mine.empty else None
g_mp = MP
g_model_code = None
# Какой ASIN уйдёт в черновики — видно ДО нажатия (для любой площадки), и решает
# его ТОТ ЖЕ pick_asin, что и запись: экран не обещает другого (проверка #171).
g_pick, g_why = tg.pick_asin(g_link_asins)
say.caption(t("tg.link.draft_asin", mp=g_mp.upper(), asin=g_pick) if g_pick
            else t("tg.link.draft_no_asin", mp=g_mp.upper(), why=t(f"tg.code.{g_why['code']}")
                   + (f" ({g_why['detail']})" if g_why.get("detail") else "")))
g_conf, g_dropped, g_decided, g_derr = [], [], [], None
if g_copy is not None:
    say.caption(t("tg.gen.passport", pid=cell_text(g_copy, "passport_id"),
                  aid=cell_text(g_copy, "source_artifact_id")))
    try:
        g_conf, g_dropped, g_decided, g_derr = _copy_conflicts(
            cell_text(g_copy, "archived_locator"), cell_text(g_copy, "sha256"),
            cell_text(g_copy, "source_artifact_id"))
    except Exception as e:  # noqa: BLE001 — сбой называется: молчание выглядело бы «конфликтов нет»
        say.warning(t("tg.gen.conflicts_error", err=f"{type(e).__name__}: {str(e)[:160]}"))
    try:
        # модель для префикса Highlights в ручной проверке (блок 5) — из паспорта
        g_model_code = tg.model_code(_copy_facts(cell_text(g_copy, "archived_locator"),
                                                 cell_text(g_copy, "sha256")))
    except Exception:  # noqa: BLE001 — сбой чтения копии уже назван строкой выше
        g_model_code = None
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
try:
    g_method, g_mver, _ = _textgen_method()
except _ReadFailed:
    pass                                  # причина — ниже, вместе с лимитами
# модель и методология названы ДО нажатия (решение владельца 29.10.2026)
say.caption(t("tg.gen.model_method", model=g_model, ver=g_mver or "—"))
if copies_err:
    g_reason = "COPIES"
elif g_copy is None:
    # без паспорта блок на месте, кнопка выключена с причиной (решение 29.10.2026)
    g_reason = "NO_PASSPORT"
    say.warning(t("tg.gen.err.NO_PASSPORT", detail=""))
elif table_exists("textgen_calls") is False:
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


# ------------------------------------------------- 5. ручная проверка — свёрнуто
# Тайтл и Highlights руками и ключи по типу — подсказка человеку. В генерацию не
# идёт, факты паспорта здесь не проверяются. Тип — из выбранного SKU
# (passport.sku_type), модель для префикса Highlights — из паспорта; паспорта нет —
# модели нет, и префикс честно назван непроверенным (решение владельца 29.10.2026).
with st.expander(t("tg.b5.title"), expanded=False):
    say.caption(t("tg.b5.hint"))
    title_in = st.text_input(t("tg.title_label"), key=f"tg-title-{g_sku}")
    hl_in = st.text_area(t("tg.hl_label"), key=f"tg-hl-{g_sku}", height=90)
    say.markdown(f'{t("tg.title_len")}: ' + counter(len(title_in), tr.TITLE_LIMIT) + " · "
                 + f'{t("tg.hl_len")}: ' + counter(len(hl_in), tr.Ruleset().highlight_limit),
                 unsafe_allow_html=True)
    if title_in or hl_in:
        found = tr.check(title_in, hl_in, kind=tg.kind_of(g_type), model=g_model_code if hl_in else None)
        if found:
            say.error(t("tg.violations", n=len(found)))
            for v in found:
                say.markdown(f"- **{t(f'tg.code.{v.code}')}** ({t(f'tg.where.{v.field}')})"
                             + (f": `{v.detail}`" if v.detail else ""))
        else:
            say.success(t("tg.all_ok"))
        # Без модели префикс «Model …: » не проверить. «Нарушений нет» без этой
        # оговорки выдавало бы непроверенное за проверенное.
        if hl_in and not g_model_code:
            say.warning(t("tg.no_model_prefix"))

    section(t("tg.keys"))
    say.caption(t("tg.b5.keys_hint"))
    keys_df = None
    if g_type:
        keys_df, kerr, n_asins = load_keys(g_type, MP, current_title)
        if kerr:
            say.error(t("tg.keys_error", err=kerr))
        elif keys_df is None or keys_df.empty:
            say.caption(t("tg.keys_empty", n=n_asins))
        else:
            say.caption(t("tg.keys_from", n=n_asins))
    else:
        say.caption(t("tg.keys_no_type"))
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
