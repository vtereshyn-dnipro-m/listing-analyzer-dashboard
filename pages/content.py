# -*- coding: utf-8 -*-
"""
pages/content.py — «Контент». Первая вкладка: «Перевод» макетов Figma.

Вкладка называется «Перевод», а не «Локализация»: работа здесь именно
с текстом, а локализация подразумевает больше — единицы измерения,
форматы, замену изображений под рынок. Внутренние имена (`loc.*`
в словаре, `services/localization.py`, таблицы `figma_*`) остались
прежними: это код, а не то, что видит человек.

Дизайнер рисует карточку по-английски, продаётся она в четырёх странах.
Экран отвечает на два вопроса: что ещё не переведено и влезет ли перевод
в макет.

Второй вопрос — главный. Испанский и немецкий длиннее английского
примерно на пятую часть, слой в макете фиксированной ширины, и текст,
не влезающий в слой, обнаруживается при экспорте — когда работа уже
сделана. Поэтому длина считается ДО вставки и стоит в каждой строке.

Вкладок пока одна, но структура заложена на несколько: сюда же пойдут
остальные задачи по контенту.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from i18n import t
from services import figma
from services.localization import (
    ALL_LANGS, TARGET_LANGS, SYNC_EVERY_HOURS,
    demo_layers, demo_products, fits, load_layers, load_products, needs_sync,
    over_rows, product_state, save_parsed, summarize, sync_age_hours,
)
from components.ui import inject_fonts, eyebrow

inject_fonts()
st.title(t("nav.content"))

ACCENT = "#E8590C"
INK = "#1A1815"
MUTED = "#57534A"
BORDER = "#E7E4DD"
OK_GREEN = "#2F6B3A"
WARN_BG = "#FDF3D8"
WARN_INK = "#854F0B"

STATE_COLOR = {"all": OK_GREEN, "partial": "#B4763A", "none": "#A32D2D"}

tab_loc, = st.tabs([t("loc.tab")])


# ---------------------------------------------------------------- данные
def products_source() -> tuple[pd.DataFrame, str | None, bool]:
    """Товары макетов: из базы, а при пустой базе — демонстрационные.

    Третьим значением возвращается признак демо. Он обязателен: демо,
    неотличимое от настоящих данных, — худшее, что здесь можно сделать,
    по нему начнут считать объём работы.
    """
    df, err = load_products()
    if err or df.empty:
        return demo_products(), err, True
    return df, None, False


def layers_source(product_id: int, lang: str, demo: bool):
    if demo:
        return demo_layers(product_id, lang), None
    return load_layers(product_id, lang)


# ---------------------------------------------------------------- вид
def summary_html(s: dict) -> str:
    """Четыре числа шапки. Одной строкой — правило 1."""
    cards = [(t("loc.sum_total"), s["total"], INK),
             (t("loc.sum_all"), s["all"], STATE_COLOR["all"]),
             (t("loc.sum_partial"), s["partial"], STATE_COLOR["partial"]),
             (t("loc.sum_none"), s["none"], STATE_COLOR["none"])]
    cells = "".join(
        f'<div style="flex:1 1 0;min-width:120px;background:#FFF;'
        f'border:1px solid {BORDER};border-radius:10px;padding:10px 14px;">'
        f'<div style="font-size:11px;letter-spacing:.06em;'
        f'text-transform:uppercase;color:{MUTED};">{label}</div>'
        f'<div class="ls-mono" style="font-size:22px;font-weight:700;'
        f'color:{color};">{value}</div></div>'
        for label, value, color in cards)
    return (f'<div style="display:flex;gap:10px;flex-wrap:wrap;'
            f'margin-bottom:14px;">{cells}</div>')


def lang_chips(done: set) -> str:
    """Метки языков: зелёная — перевод есть, серая — нет."""
    out = []
    for lg in ALL_LANGS:
        have = lg == "en" or lg in done
        bg, fg = ("#E4EFE6", OK_GREEN) if have else ("#F1EFE9", MUTED)
        out.append(f'<span style="background:{bg};color:{fg};font-size:11px;'
                   f'font-weight:600;border-radius:5px;padding:2px 7px;'
                   f'margin-right:4px;">{lg.upper()}</span>')
    return "".join(out)


def product_row_html(r: pd.Series) -> str:
    done = set(r.get("langs_done") or ())
    edge = STATE_COLOR[product_state(done)]
    sku = "" if pd.isna(r.get("sku")) else str(r.get("sku") or "")
    return (
        f'<div class="ls-card" style="background:#fff;border:1px solid {BORDER};'
        f'border-left:3px solid {edge};border-radius:0 10px 10px 0;'
        f'padding:9px 12px;display:flex;gap:12px;align-items:center;">'
        f'<div style="flex:1;min-width:0;">'
        f'<div style="font-size:13px;font-weight:600;color:{INK};'
        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
        f'{r.get("name") or "—"}</div>'
        f'<div class="ls-mono" style="font-size:11px;color:{MUTED};">'
        f'{r.get("asin")}{" · " + sku if sku else ""}'
        f' · {r.get("section_type") or ""}</div></div>'
        f'<div style="flex:0 0 auto;">{lang_chips(done)}</div>'
        f'<div class="ls-mono" style="flex:0 0 auto;font-size:12px;'
        f'color:{MUTED};white-space:nowrap;">'
        f'{t("loc.layers_n", n=int(r.get("layers_count") or 0))}</div></div>')


def counter_html(n: int, lim: int | None, state: str) -> str:
    """«18 / 22» — длина перевода и предел слоя.

    Предел показывается всегда, даже когда всё влезает: без второго числа
    первое ничего не значит.
    """
    if lim is None:
        return (f'<span class="ls-mono" style="color:{MUTED};font-size:12px;">'
                f'{n} / —</span>')
    color = {"over": "#A32D2D", "tight": WARN_INK}.get(state, OK_GREEN)
    mark = " ⚠" if state == "over" else ""
    return (f'<span class="ls-mono" style="color:{color};font-weight:700;'
            f'font-size:12px;white-space:nowrap;">{n} / {lim}{mark}</span>')


# ---------------------------------------------------------------- экраны
def render_sync_bar(products: pd.DataFrame, demo: bool) -> None:
    """Когда читали Figma и кнопка перечитать.

    Читаем раз в сутки и по кнопке — не из экономии, а потому что при
    исчерпанном лимите Figma просит ждать сотни секунд на КАЖДУЮ
    попытку. Автоматический повтор здесь только растянул бы ожидание.
    """
    miss = figma.missing_secrets()
    age = sync_age_hours(products) if not demo else None
    c1, c2 = st.columns([2.2, 7], gap="small", vertical_alignment="center")

    if c1.button(t("loc.resync"), key="loc-sync", type="primary",
                 disabled=bool(miss),
                 help=t("loc.no_secrets", keys=", ".join(miss)) if miss else None):
        with st.status(t("loc.sync_run"), expanded=True) as status:
            try:
                doc = figma.fetch_document()
                status.write("· " + t("loc.sync_parsing"))
                parsed = figma.parse_document(doc)
                for p in parsed["products"]:
                    p["file_key"] = figma.file_key()
                n_p, n_l, err = save_parsed(parsed)
                if err:
                    status.update(label=t("loc.sync_failed"), state="error")
                    st.error("⚠ " + t("loc.save_failed", e=err))
                else:
                    status.update(label=t("loc.sync_done", p=n_p, l=n_l),
                                  state="complete")
                st.session_state["loc-sync-report"] = {
                    "skipped_sections": parsed["skipped_sections"],
                    "skipped_pages": parsed["skipped_pages"],
                    "source_checked": parsed.get("source_checked", 0),
                    "source_over": parsed.get("source_over", 0),
                }
                load_products.clear()
                st.rerun()
            except figma.FigmaError as e:
                status.update(label=t("loc.sync_failed"), state="error")
                wait = getattr(e, "retry_after", None)
                if wait:
                    st.error("⚠ " + t("loc.rate_limited", s=int(wait),
                                      m=max(1, int(wait) // 60)))
                else:
                    st.error("⚠ " + t("loc.sync_error", e=str(e)))

    if miss:
        c2.caption("⚠ " + t("loc.no_secrets", keys=", ".join(miss)))
    elif age is None:
        c2.caption(t("loc.never_synced"))
    else:
        stale = " · " + t("loc.stale") if needs_sync(products) else ""
        c2.caption(t("loc.synced_ago", h=int(age), every=SYNC_EVERY_HOURS)
                   + stale)

    # что не разобралось при последнем чтении — видно, а не потеряно
    rep = st.session_state.get("loc-sync-report") or {}
    # английский текст уже стоит в макете и в него влезает; если расчёт
    # утверждает обратное на заметной доле слоёв — занижен коэффициент
    _checked, _over = rep.get("source_checked") or 0, rep.get("source_over") or 0
    if _checked and _over / _checked > 0.25:
        st.warning("⚠ " + t("loc.ratio_off", over=_over, total=_checked))
    if rep.get("skipped_sections"):
        with st.expander(t("loc.skipped_n", n=len(rep["skipped_sections"]))):
            st.caption(t("loc.skipped_hint"))
            for line in rep["skipped_sections"][:20]:
                st.code(line, language=None)


def render_list(products: pd.DataFrame, demo: bool) -> None:
    render_sync_bar(products, demo)
    st.markdown(summary_html(summarize(products)), unsafe_allow_html=True)
    st.caption(t("loc.list_hint"))

    # без перевода — наверх: это и есть очередь работы
    view = products.copy()
    view["_o"] = view["langs_done"].map(
        lambda d: {"none": 0, "partial": 1, "all": 2}[product_state(set(d or ()))])
    view = view.sort_values(["_o", "name"])

    for _, r in view.iterrows():
        c1, c2 = st.columns([9, 2.6], gap="small", vertical_alignment="center")
        c1.markdown(product_row_html(r), unsafe_allow_html=True)
        done = set(r.get("langs_done") or ())
        missing = [lg for lg in TARGET_LANGS if lg not in done]
        # кнопка ведёт на первый непереведённый язык: он и есть работа
        target = missing[0] if missing else TARGET_LANGS[0]
        if c2.button(f'{t("loc.translate")} · {target.upper()}',
                     key=f"loc-open-{r['id']}",
                     type="primary" if missing else "secondary"):
            st.session_state["loc-product"] = int(r["id"])
            st.session_state["loc-lang"] = target
            st.rerun()


def render_editor(products: pd.DataFrame, demo: bool) -> None:
    pid = int(st.session_state["loc-product"])
    row = products[products["id"] == pid]
    if row.empty:
        st.session_state.pop("loc-product", None)
        st.rerun()
    row = row.iloc[0]
    lang = st.session_state.get("loc-lang") or TARGET_LANGS[0]

    b1, b2, b3 = st.columns([1.4, 2.0, 6], gap="small")
    if b1.button("← " + t("loc.back"), key="loc-back"):
        for k in ("loc-product", "loc-lang"):
            st.session_state.pop(k, None)
        st.rerun()
    lang = b2.radio(
        "lang", list(TARGET_LANGS), horizontal=True,
        index=list(TARGET_LANGS).index(lang) if lang in TARGET_LANGS else 0,
        format_func=str.upper, label_visibility="collapsed", key="loc-lang")

    st.markdown(eyebrow(f'{row.get("name") or row.get("asin")} · '
                        f'{row.get("asin")} · {lang.upper()}'),
                unsafe_allow_html=True)

    layers, err = layers_source(pid, lang, demo)
    if err:
        st.error("⚠ " + t("loc.load_failed", e=err))
        return
    if layers.empty:
        st.info(t("loc.no_layers"))
        return

    # Шапка таблицы: подписи колонок здесь, а не в каждой строке —
    # иначе на десяти строках они читаются как часть текста
    st.markdown(
        f'<div style="display:flex;gap:10px;font-size:11px;'
        f'letter-spacing:.06em;text-transform:uppercase;color:{MUTED};'
        f'padding:0 2px 4px;"><div style="flex:1;">{t("loc.col_src")}</div>'
        f'<div style="flex:1;">{t("loc.col_dst")}</div>'
        f'<div style="flex:0 0 86px;text-align:right;">'
        f'{t("loc.col_chars")}</div></div>', unsafe_allow_html=True)

    edited: dict = {}
    for _, lr in layers.iterrows():
        key = f"loc-txt-{pid}-{lang}-{lr['layer_id']}"
        current = st.session_state.get(key, lr.get("translated_text") or "")
        n, lim, state = fits(current, lr.get("char_limit"))
        edited[lr["layer_id"]] = current

        # строка целиком подсвечивается, когда текст не влезает: цветной
        # счётчик на краю экрана теряется, а строка — нет
        box = f"locrow-{pid}-{lang}-{lr['layer_id']}"
        if state == "over":
            st.markdown(f'<style>.st-key-{box}{{background:{WARN_BG};'
                        f'border-radius:8px;padding:2px 6px;}}</style>',
                        unsafe_allow_html=True)
        with st.container(key=box):
            c1, c2, c3 = st.columns([1, 1, 0.34], gap="small",
                                    vertical_alignment="center")
            c1.markdown(
                f'<div style="font-size:13px;color:{INK};padding-top:6px;">'
                f'{lr["source_text"]}</div>', unsafe_allow_html=True)
            c2.text_input(lr["layer_id"], value=current, key=key,
                          label_visibility="collapsed")
            c3.markdown(counter_html(n, lim, state), unsafe_allow_html=True)

    check = layers.copy()
    check["translated_text"] = check["layer_id"].map(edited)
    n_over = over_rows(check)
    if n_over:
        st.warning("⚠ " + t("loc.over_warning", n=n_over))

    a1, a2, a3 = st.columns([2.0, 2.0, 5], gap="small")
    a1.button(t("loc.apply_figma"), type="primary", key="loc-apply",
              disabled=True, help=t("loc.apply_soon"))
    a2.button(t("loc.retranslate"), key="loc-retry",
              disabled=True, help=t("loc.model_soon"))
    # Предел — расчётный, и об этом надо сказать прямо: ширина слоя
    # приходит в пикселях, а знаки разной ширины. Без этой строки текст,
    # не влезший на самой границе, выглядит ошибкой расчёта.
    st.caption(t("loc.limit_note", ratio=figma.AVG_CHAR_RATIO))
    st.caption(t("loc.export_note"))


with tab_loc:
    products, err, demo = products_source()
    if err:
        # «нет данных» и «не смогли прочитать» — разные вещи
        st.error("⚠ " + t("loc.load_failed", e=err))
    if demo:
        st.info("ℹ " + t("loc.demo_notice"))
    if "loc-product" in st.session_state:
        render_editor(products, demo)
    else:
        render_list(products, demo)
