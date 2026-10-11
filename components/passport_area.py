# -*- coding: utf-8 -*-
"""
components/passport_area.py — область «Контент → Паспорт SKU», этап 1.

Три вкладки v1 (договорённость 07.10.2026): Реестр Паспортов, Создание
Паспорта, Взаимодействие с Верификатором. Image Collection — после v1.

Этап 1 — только чтение. Каждое изменяющее действие отвечает
FEATURE_DISABLED и говорит об этом вслух (ТЗ §13): кнопка, которая
выглядит рабочей и молча ничего не делает, хуже отсутствующей.

Вкладки — не `st.tabs`, а сегмент с ключом: ТЗ требует переходить из
Реестра СРАЗУ в нужную вкладку и к нужному объекту (вопрос Q-…, блокер,
ограничение), а `st.tabs` из кода не переключается. Контекст товара — SKU
и версия — живёт в `session_state` и переносится между вкладками; смена
товара только явная (ТЗ §8).

Правила показа — в `services/passport.py`, здесь только раскладка.
"""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

import auth
from i18n import t
from services import passport as pp
from services.passport import txt

INK = "#1A1815"
MUTED = "#57534A"
BORDER = "#E7E4DD"
OK_GREEN = "#2F6B3A"
WARN_BG = "#FDF3D8"
WARN_INK = "#854F0B"
RED = "#A32D2D"
NEUTRAL_BG = "#F1EFE9"

TABS = ("registry", "create", "verifier")

# Цвет состояния — не единственный носитель смысла (ТЗ 9.6.5): у каждого
# чипа текст. Оранжевый — только для боли (правило 6), здесь его нет.
STATE_STYLE = {
    "READY": ("#E4EFE6", OK_GREEN),
    "READY_WITH_LIMITATIONS": (WARN_BG, WARN_INK),
    "NOT_READY": (NEUTRAL_BG, INK),
    "BLOCKED": ("#F6E1E1", RED),
    None: (NEUTRAL_BG, MUTED),
}
FRESH_STYLE = {
    pp.CURRENT: ("#E4EFE6", OK_GREEN),
    pp.UPDATING: (NEUTRAL_BG, INK),
    pp.STALE: ("#F6E1E1", RED),
    pp.LOAD_ERROR: ("#F6E1E1", RED),
}
CHIP = "font-size:12px;font-weight:600;border-radius:5px;padding:2px 8px;white-space:nowrap;"


def chip(text: str, bg: str, fg: str, title: str = "") -> str:
    tip = f' title="{html.escape(title)}"' if title else ""
    return f'<span{tip} style="background:{bg};color:{fg};{CHIP}">{html.escape(text)}</span>'


def state_label(state: str | None) -> str:
    return t(f"pp.state.{state}") if state else t("pp.state.ABSENT")


def me() -> tuple[str, tuple]:
    u = auth.current()
    return (u.email or ""), pp.CANONICAL_ROLES.get(u.role, ())


# ---------------------------------------------------------------- навигация
def _go(tab: str, sku: str | None = None, question: str | None = None, show: str | None = None) -> None:
    """Колбэк перехода: пишет ключ сегмента ДО его создания на следующем
    прогоне (правило 7б), поэтому только из колбэка."""
    st.session_state["pp-tab"] = tab
    if sku is not None:
        st.session_state["pp-sku"] = sku
    st.session_state["pp-question"] = question
    st.session_state["pp-show"] = show


def _change_product() -> None:
    for k in ("pp-sku", "pp-question", "pp-show"):
        st.session_state.pop(k, None)
    st.session_state["pp-tab"] = "registry"


def context_header(r: dict) -> None:
    """Выбранный товар — в заголовке каждой вкладки (ТЗ §8)."""
    sku = st.session_state.get("pp-sku")
    if not sku or not r:
        return
    bg, fg = STATE_STYLE.get(r.get("state"), STATE_STYLE[None])
    name = html.escape(txt(r.get("name")) or "—")
    model = txt(r.get("model"))
    bar = st.container(horizontal=True, vertical_alignment="center", gap="small")
    bar.markdown(
        f'<span class="ls-mono" style="font-weight:600;">{html.escape(sku)}</span>'
        f'<span style="color:{MUTED};"> · {name}{" · " + html.escape(model) if model else ""}</span> '
        + chip(state_label(r.get("state")), bg, fg), unsafe_allow_html=True, width="content")
    bar.button(t("pp.change_product"), key="pp-change", type="tertiary", on_click=_change_product)


# ---------------------------------------------------------------- Реестр
def _registry_data() -> tuple[dict, bool]:
    """Реестр с последним удачным чтением: при сбое показывается последнее
    подтверждённое состояние с датой, а не пустота (ТЗ 9.6.4)."""
    data = pp.load_registry()
    if data["error"] is None and not data["missing"]:
        st.session_state["pp-last-good"] = data
        return data, False
    return st.session_state.get("pp-last-good", data), data["error"] is not None


def _reset_filters() -> None:
    for k in ("pp-q", "pp-states", "pp-mine"):
        st.session_state.pop(k, None)


def render_registry() -> None:
    data, load_error = _registry_data()
    if data.get("missing"):
        st.warning(t("pp.migration_missing", path=pp.MIGRATION))
    if load_error:
        at = data.get("read_at")
        st.error(t("pp.load_error", at=at.strftime("%d.%m.%Y %H:%M") if at is not None else "—"))
    directory, dir_err = pp.sku_directory()
    if dir_err:
        st.warning(t("pp.directory_error"))

    f = st.container(horizontal=True, vertical_alignment="bottom", gap="small")
    query = f.text_input(t("pp.search"), key="pp-q", placeholder=t("pp.search_ph"))
    states = f.multiselect(t("pp.f_state"), list(pp.STATES) + ["ABSENT"], key="pp-states",
                           format_func=lambda s: t(f"pp.state.{s}"), placeholder=t("pp.any"))
    mine = f.selectbox(t("pp.f_mine"), ["all", "yes", "no"], key="pp-mine",
                       format_func=lambda s: t(f"pp.mine.{s}"))
    f.button(t("pp.reset"), key="pp-reset", on_click=_reset_filters)

    view, total = pp.search(directory, data.get("objects"), query)
    email, roles = me()
    rows = pp.registry_rows(view, data, pp.duplicate_map(directory), email, roles, load_error)
    rows = pp.filter_rows(rows, states, mine)

    if rows.empty:
        st.info(t("pp.nothing_found", q=query) if query else t("pp.empty_hint"))
        return
    st.caption(t("pp.found", n=total, shown=len(rows)))

    table = pd.DataFrame({
        "product": rows.apply(lambda r: " · ".join(x for x in (r["name"], r["model"]) if x) or "—", axis=1),
        "sku": rows["sku"],
        "pv": rows["product_version"],
        "state": rows["state"].map(state_label),
        "ver": rows["passport_version"],
        "q": rows["questions"],
        "lim": rows.apply(lambda r: _limits_text(r), axis=1),
        "mine": rows["my_action"].map(lambda v: t("pp.mine_yes") if v else t("pp.mine_no")),
        "fresh": rows["fresh"].map(lambda v: t(f"pp.fresh.{v}")),
        "last": rows.apply(_last_text, axis=1),
        # NOT_READY без адресного запроса — «Действие не требуется» (ТЗ 9.10),
        # а не кнопка запуска; сама кнопка в карточке лишь открывает работу.
        "next": rows["action"].map(lambda a: t("pp.no_action_short") if a == pp.OPEN_WORK else t(f"pp.act.{a}")),
    })
    pick = st.dataframe(
        table, key="pp-table", hide_index=True, width="stretch",
        on_select="rerun", selection_mode="single-row",
        column_config={
            "product": st.column_config.TextColumn(t("pp.col.product")),
            "sku": st.column_config.TextColumn(t("pp.col.sku")),
            "pv": st.column_config.TextColumn(t("pp.col.pv")),
            "state": st.column_config.TextColumn(t("pp.col.state")),
            "ver": st.column_config.TextColumn(t("pp.col.ver")),
            "q": st.column_config.NumberColumn(t("pp.col.q")),
            "lim": st.column_config.TextColumn(t("pp.col.lim")),
            "mine": st.column_config.TextColumn(t("pp.col.mine")),
            "fresh": st.column_config.TextColumn(t("pp.col.fresh")),
            "last": st.column_config.TextColumn(t("pp.col.last")),
            "next": st.column_config.TextColumn(t("pp.col.next")),
        })
    picked = (pick.selection.rows if pick and getattr(pick, "selection", None) else [])
    by_sku = {r["sku"]: r for _, r in rows.iterrows()}
    if picked:
        st.session_state["pp-sku"] = rows.iloc[picked[0]]["sku"]
    # Карточка — по выбранному SKU контекста, а не только по выделению в
    # таблице: вернувшись из другой вкладки, человек видит тот же товар
    # (ТЗ §8 — контекст сохраняется, смена товара только явная).
    current = by_sku.get(st.session_state.get("pp-sku"))
    if current is not None:
        render_card(current, data)
    else:
        st.caption(t("pp.pick_hint"))


def _limits_text(r) -> str:
    parts = []
    if r["limitations"]:
        parts.append(t("pp.lim_n", n=int(r["limitations"])))
    if r["blocks"]:
        parts.append(t("pp.blk_n", n=int(r["blocks"])) + " ⚠")
    return " · ".join(parts) or "—"


def _last_text(r) -> str:
    at = r.get("last_event_at")
    if at is None or pd.isna(at):
        return "—"
    return f'{pd.Timestamp(at).strftime("%d.%m.%Y %H:%M")} · {r["last_event_type"]}'


def render_card(r: pd.Series, data: dict) -> None:
    """Карточка выбранного SKU (ТЗ 9.5): одно основное действие, вторичные —
    «Открыть Паспорт» и «Открыть папку материалов»."""
    box = st.container(border=True)
    bg, fg = STATE_STYLE.get(r["state"], STATE_STYLE[None])
    fbg, ffg = FRESH_STYLE[r["fresh"]]
    box.markdown(
        f'<div style="font-size:18px;font-weight:600;">{html.escape(r["name"] or "—")}</div>'
        f'<div class="ls-mono" style="color:{MUTED};">{html.escape(r["sku"])}'
        f'{" · " + html.escape(r["model"]) if r["model"] else ""}'
        f'{" · " + t("pp.pv_short", v=html.escape(r["product_version"])) if r["product_version"] else ""}</div>'
        f'<div style="margin-top:6px;">{chip(state_label(r["state"]), bg, fg)} '
        f'{chip(t("pp.fresh." + r["fresh"]), fbg, ffg)}'
        f'{" " + chip(t("pp.ver_short", v=r["passport_version"]), NEUTRAL_BG, INK) if r["passport_version"] else ""}'
        f'</div>', unsafe_allow_html=True)
    if r["duplicate_of"]:
        box.warning(t("pp.duplicate", skus=", ".join(r["duplicate_of"])))
    if r["fresh"] in (pp.STALE, pp.LOAD_ERROR):
        box.warning(t("pp.mutations_locked"))
    for _, b in pp.active_blocks(data.get("blocks"), r["sku"]).iterrows():
        box.error(t("pp.block_line", id=b["block_id"], reason=txt(b["reason"]),
                    who=txt(b["responsible_party"]), resume=txt(b["resume_condition"])))

    row = box.container(horizontal=True, gap="small")
    act, target = r["action"], r["action_target"]
    label = t(f"pp.act.{act}")
    if act == pp.CREATE:
        row.button(label, key="pp-act", type="primary", on_click=_go, args=("create", r["sku"]))
    elif act == pp.ANSWER:
        row.button(label, key="pp-act", type="primary", on_click=_go, args=("verifier", r["sku"], target))
    elif act == pp.DO_REQUIRED:
        row.button(label, key="pp-act", type="primary", on_click=_go,
                   args=("registry", r["sku"], None, "block:" + txt(target)))
    elif act == pp.WAIT:
        row.caption(label)
    else:
        show = {pp.OPEN_LIMITATIONS: "limitations", pp.OPEN_WORK: "work",
                pp.OPEN_PASSPORT: "passport", pp.COMPARE: "compare"}[act]
        row.button(label, key="pp-act", type="primary", on_click=_go, args=("registry", r["sku"], None, show))
    if r["has_passport"] and act != pp.OPEN_PASSPORT:
        row.button(t("pp.open_passport"), key="pp-open", on_click=_go,
                   args=("registry", r["sku"], None, "passport"))
    if r["materials_url"]:
        row.link_button(t("pp.open_folder"), r["materials_url"])
    elif r["has_passport"]:
        row.button(t("pp.open_folder"), key="pp-folder", disabled=True, help=t("pp.folder_none"))

    show = st.session_state.get("pp-show")
    if st.session_state.get("pp-sku") == r["sku"] and show:
        _render_detail(box, show, r, data)


def _render_detail(box, show: str, r: pd.Series, data: dict) -> None:
    """Объект, к которому ведёт действие строки: ограничения, текущая работа,
    read-only сведения о Паспорте, дубликаты. Редактирования нет нигде."""
    if show == "limitations":
        obj = _obj(data, r["sku"])
        for lim in pp._limitations(obj):
            text = txt(lim.get("text") if isinstance(lim, dict) else lim)
            box.markdown(f"- {html.escape(text)}")
    elif show == "work":
        box.info(t("pp.no_action_needed"))
        runs = data.get("runs")
        part = runs[runs["sku_id"].astype(str) == r["sku"]] if runs is not None and not runs.empty else runs
        if part is not None and not part.empty:
            box.caption(t("pp.run_line", n=len(part)))
    elif show == "passport":
        obj = _obj(data, r["sku"])
        if obj is not None:
            box.markdown(t("pp.passport_meta", pid=obj["passport_id"], ver=obj["passport_version"],
                           sha=txt(obj["sha256"])[:12]))
        box.caption(t("pp.read_only"))
    elif show == "compare":
        box.caption(t("pp.compare_hint"))
        for other in r["duplicate_of"]:
            box.button(t("pp.pick_sku", sku=other), key=f"pp-pick-{other}",
                       on_click=lambda s=other: st.session_state.update({"pp-q": s, "pp-show": None}))
    elif show.startswith("block:"):
        box.info(t("pp.block_action_disabled"))


def _obj(data: dict, sku: str):
    objs = data.get("objects")
    if objs is None or objs.empty:
        return None
    part = objs[objs["sku_id"].astype(str) == sku]
    return None if part.empty else part.iloc[0]


# ---------------------------------------------------------------- Создание
def render_create(r: dict) -> None:
    if not st.session_state.get("pp-sku") or not r:
        st.info(t("pp.create_pick"))
        st.button(t("pp.to_registry"), key="pp-to-reg", on_click=_go, args=("registry",))
        return
    if r.get("duplicate_of"):
        st.warning(t("pp.duplicate", skus=", ".join(r["duplicate_of"])))
        return
    row = st.container(horizontal=True, gap="small")
    if r.get("has_passport"):
        # Существующий Паспорт: безопасное основное действие — «Передать новые
        # данные», разрушительное «Создать новый Паспорт» — отдельно (ТЗ 10.4).
        st.info(t("pp.create_exists", ver=r.get("passport_version") or "—"))
        _feature_disabled(row, "pp-delta-off", t("pp.act.DELTA"), "listing_suite.source_evidence_delta", True)
        _feature_disabled(row, "pp-recreate-off", t("pp.act.RECREATE"), "listing_suite.passport_recreate", False)
    else:
        st.info(t("pp.create_absent"))
        _feature_disabled(row, "pp-create-off", t("pp.act.CREATE"), "listing_suite.passport_create", True)
    # Подсказка выключенной кнопки видна только при наведении — причина
    # обязана стоять текстом, иначе выключенная кнопка читается поломкой.
    st.caption(t("pp.stage_disabled"))


def _feature_disabled(box, key: str, label: str, flag: str, primary: bool) -> None:
    """Выключенная функция говорит об этом и называет флаг (ТЗ §13:
    FEATURE_DISABLED не имитирует выполнение)."""
    pp.flag_on(flag)              # неизвестное имя флага — KeyError, а не «выключено»
    box.button(label, key=key, type="primary" if primary else "secondary", disabled=True,
               help=t("pp.feature_disabled", flag=flag))


# ---------------------------------------------------------------- Верификатор
def render_verifier() -> None:
    data = pp.load_questions()
    if data.get("missing"):
        st.warning(t("pp.migration_missing", path=pp.MIGRATION))
        return
    if data.get("error"):
        st.error(t("pp.q_load_error"))
        return
    reg, _ = _registry_data()
    email, roles = me()
    rows = pp.question_rows(data, reg.get("blocks"), email, roles)
    c = pp.question_counters(rows)
    m = st.container(horizontal=True, gap="medium")
    for key in ("mine", "check", "clarify", "resolved"):
        m.metric(t(f"pp.qc.{key}"), c[key])

    f = st.container(horizontal=True, vertical_alignment="bottom", gap="small")
    states = f.multiselect(t("pp.qf.state"), list(pp.USER_STATES), key="pp-qstates", placeholder=t("pp.any"),
                           default=None if "pp-qstates" in st.session_state else list(pp.DEFAULT_QUESTION_STATES),
                           format_func=lambda s: t(f"pp.qs.{s}"))
    only_mine = f.toggle(t("pp.qf.mine"), key="pp-qmine", value=True)
    sku = st.session_state.get("pp-sku")
    want = st.session_state.get("pp-question")
    if rows.empty:
        st.info(t("pp.q_empty"))
        return
    view = rows
    if want:
        view = rows[rows["question_id"] == want]
    else:
        if states:
            view = view[view["user_state"].isin(states)]
        if only_mine:
            view = view[view["mine"]]
        if sku:
            view = view[view["sku_id"].astype(str) == sku]
    if view.empty:
        st.info(t("pp.q_none_filtered"))
        return
    table = pd.DataFrame({
        "sku": view["sku_id"].astype(str),
        "question": view["question_text"].map(lambda s: txt(s)[:90]) + " · " + view["question_id"],
        "type": view["question_type"].map(lambda s: t(f"pp.qt.{s}")),
        "state": view["user_state"].map(lambda s: t(f"pp.qs.{s}")),
        "impact": view["impact"].map(lambda s: t(f"pp.qi.{s}")),
        "who": view.apply(lambda r: txt(r.get("responsible_user")) or txt(r.get("responsible_role")), axis=1),
        "updated": view["updated_at"].map(lambda v: "—" if v is None or pd.isna(v)
                                          else pd.Timestamp(v).strftime("%d.%m.%Y %H:%M")),
        "next": view.apply(lambda r: t("pp.act.ANSWER") if r["mine"] and r["user_state"] in pp.DEFAULT_QUESTION_STATES
                           else t("pp.q_open"), axis=1),
    })
    pick = st.dataframe(table, key="pp-qtable", hide_index=True, width="stretch",
                        on_select="rerun", selection_mode="single-row",
                        column_config={k: st.column_config.TextColumn(t(f"pp.qcol.{k}")) for k in table.columns})
    picked = list(pick.selection.rows) if pick and getattr(pick, "selection", None) else []
    if not picked and want:
        picked = [0]          # пришли из Реестра к точному Q-… — он и открыт
    if picked:
        render_question(view.iloc[picked[0]], data)


def render_question(q: pd.Series, data: dict) -> None:
    """Карточка вопроса (ТЗ 11.3.3) и история только для чтения. Поля ответа
    выключены до этапа 4 и говорят почему."""
    box = st.container(border=True)
    box.markdown(f'<div class="ls-mono" style="color:{MUTED};">{html.escape(txt(q["question_id"]))}</div>'
                 f'<div style="font-size:16px;font-weight:600;">{html.escape(txt(q["question_text"]))}</div>',
                 unsafe_allow_html=True)
    for key, field in (("why", "reason_text"), ("affected", "affected_object"),
                       ("expected", "expected_answer"), ("closure", "closure_criterion")):
        val = txt(q.get(field))
        if val:
            box.markdown(f"**{t('pp.qcard.' + key)}** {html.escape(val)}")
    answers = data.get("answers")
    hist = answers[answers["question_id"] == q["question_id"]] if answers is not None and not answers.empty else None
    if hist is not None and not hist.empty:
        box.markdown(f"**{t('pp.qcard.history')}**")
        for _, a in hist.sort_values("answer_version").iterrows():
            box.caption(t("pp.answer_line", v=int(a["answer_version"]), who=txt(a["author"]),
                          text=txt(a.get("answer_text"))[:200]))
    box.text_area(t("pp.answer"), key=f"pp-ans-{q['question_id']}", placeholder=t("pp.answer_ph"),
                  disabled=True)
    box.button(t("pp.send_answer"), key=f"pp-send-{q['question_id']}", type="primary", disabled=True,
               help=t("pp.feature_disabled", flag="listing_suite.verifier_answers"))
    box.caption(t("pp.feature_disabled", flag="listing_suite.verifier_answers"))


# ---------------------------------------------------------------- вход
def context_row() -> dict:
    """Строка Реестра для товара из контекста — для заголовка и вкладок,
    независимо от того, что сейчас в поиске."""
    sku = st.session_state.get("pp-sku")
    if not sku:
        return {}
    data, load_error = _registry_data()
    directory, _ = pp.sku_directory()
    view = directory[directory["sku"].astype(str) == sku] if not directory.empty else directory
    if view.empty:
        view = pd.DataFrame([{"sku": sku, "name": "", "ean": "", "asins": "", "is_active": True}])
    email, roles = me()
    rows = pp.registry_rows(view, data, pp.duplicate_map(directory), email, roles, load_error)
    return rows.iloc[0].to_dict() if not rows.empty else {}


def render() -> None:
    if "pp-tab" not in st.session_state:
        st.session_state["pp-tab"] = "registry"
    tab = st.segmented_control(t("pp.area"), list(TABS), key="pp-tab", selection_mode="single",
                               format_func=lambda k: t(f"pp.tab.{k}"),
                               label_visibility="collapsed") or "registry"
    head = st.container()
    if tab == "registry":
        render_registry()
    elif tab == "create":
        render_create(context_row())
    else:
        render_verifier()
    # Заголовок рисуется ПОСЛЕ вкладки в заранее занятое место: выбор строки
    # в Реестре меняет товар контекста в этом же прогоне.
    with head:
        context_header(context_row())
