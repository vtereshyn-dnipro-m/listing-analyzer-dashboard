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

import json

import pandas as pd
import streamlit as st

from i18n import t, plural
from services import ai, figma, translate
from services.cells import cell_text
from services.localization import (
    aplus_part, slide_of, slide_order,
    ALL_LANGS, TARGET_LANGS, SYNC_EVERY_HOURS,
    demo_layers, demo_products, export_payload, export_rows, fits, glossary,
    lang_gaps, load_layers, load_products, missing_plan,
    load_prompt, needs_sync, over_rows, preview_node, product_state,
    preview_png, save_model_translation, save_parsed, save_prompt,
    save_translation, summarize, sync_age_hours,
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
    sku = cell_text(r, "sku")
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
        f' · {cell_text(r, "section_type")}</div></div>'
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

    # Пробный заход по умолчанию: четыре товара вместо двадцати одного.
    # Галочка, а не константа в коде, потому что решение «идём на весь
    # файл» принимает человек, когда убедится, что перевод годный.
    first_pass = c2.checkbox(
        t("loc.first_pass", n=len(figma.FIRST_PASS_ASINS)),
        value=True, key="loc-first-pass",
        help=t("loc.first_pass_help",
               asins=", ".join(figma.FIRST_PASS_ASINS)))

    if c1.button(t("loc.resync"), key="loc-sync", type="primary",
                 disabled=bool(miss),
                 help=t("loc.no_secrets", keys=", ".join(miss)) if miss else None):
        with st.status(t("loc.sync_run"), expanded=True) as status:
            try:
                doc = figma.fetch_document()
                status.write("· " + t("loc.sync_parsing"))
                parsed = figma.parse_document(
                    doc,
                    only_asins=set(figma.FIRST_PASS_ASINS) if first_pass
                    else None)
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
                    "aplus_frames": parsed.get("aplus_frames", 0),
                    "aplus_orphans": parsed.get("aplus_orphans", []),
                    "dupe_frames": parsed.get("dupe_frames", []),
                    "typo_frames": parsed.get("typo_frames", []),
                    "limited": bool(first_pass),
                }
                _invalidate()
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
    # список из четырёх товаров не должен выглядеть как весь файл:
    # по нему начнут считать объём работы, как по демо-данным
    if rep.get("limited"):
        st.info("ℹ " + t("loc.first_pass_notice",
                         n=len(figma.FIRST_PASS_ASINS)))
    if rep.get("aplus_frames"):
        st.caption(t("loc.aplus_linked", n=int(rep["aplus_frames"])))
    # модуль без подписи над ним ни к кому не привязан — и это надо
    # назвать: иначе половина макетов молча выпадает из перевода
    if rep.get("aplus_orphans"):
        with st.expander(t("loc.aplus_orphans_n", n=len(rep["aplus_orphans"]))):
            st.caption(t("loc.aplus_orphans_hint"))
            for line in rep["aplus_orphans"][:20]:
                st.markdown(f'<div class="ls-mono" style="font-size:12px;'
                            f'color:{MUTED};">{line}</div>',
                            unsafe_allow_html=True)
    # два фрейма с одним именем на одной странице — один slot на два
    # слоя: в базе остаётся последний, плагин на таком слоте откажется
    if rep.get("dupe_frames"):
        with st.expander(t("loc.dupes_n", n=len(rep["dupe_frames"]))):
            st.caption(t("loc.dupes_hint"))
            for line in rep["dupe_frames"][:20]:
                st.markdown(f'<div class="ls-mono" style="font-size:12px;'
                            f'color:{MUTED};">{line}</div>',
                            unsafe_allow_html=True)
    # опечатки разобраны, но названы: чинить их надо в Figma,
    # а не держать поправку в коде вечно
    if rep.get("typo_frames"):
        with st.expander(t("loc.typo_n", n=len(rep["typo_frames"]))):
            st.caption(t("loc.typo_hint"))
            for line in rep["typo_frames"][:20]:
                st.markdown(f'<div class="ls-mono" style="font-size:12px;'
                            f'color:{MUTED};">{line}</div>',
                            unsafe_allow_html=True)
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


def _toggle_sel(pid: int, key: str) -> None:
    sel = set(st.session_state.get("loc-sel") or ())
    (sel.add if st.session_state.get(key) else sel.discard)(pid)
    st.session_state["loc-sel"] = sel


def _set_sel(ids) -> None:
    """Поменять набор целиком и пересоздать галочки (правило 7б)."""
    st.session_state["loc-sel"] = set(int(i) for i in ids)
    st.session_state["loc-sel-gen"] = int(st.session_state.get("loc-sel-gen", 0)) + 1


def bulk_counts(view: pd.DataFrame, sel: set) -> tuple[int, int, int]:
    """(строк, товаров, языков) — сколько РЕАЛЬНО не хватает у выбранных.

    Считается от `lang_gaps`, уже загруженных для списка, без походов
    в базу: товар считается, если у него есть хоть один пробел, язык —
    если пробел есть хоть у одного товара. «4 товара, 2 языка» —
    это не «выбрано 4», а «4, у которых есть работа».
    """
    rows, prods, langs = 0, 0, set()
    for _, r in view.iterrows():
        if int(r["id"]) not in sel:
            continue
        gaps = r.get("lang_gaps") or {}
        got = {lg: n for lg, n in gaps.items() if n}
        if got:
            prods += 1
            rows += sum(got.values())
            langs |= set(got)
    return rows, prods, len(langs)


def bulk_label(rows: int, prods: int, langs: int) -> str:
    """«142 строки, 4 товара, 2 языка» — три числа словами со склонением."""
    return ", ".join((plural("loc.rows_n", rows), plural("loc.products_n", prods),
                      plural("loc.langs_n", langs)))


def render_bulk_bar(view: pd.DataFrame, demo: bool) -> set:
    """Выбор товаров и два действия по выбранным. Возвращает набор id.

    Раньше всё шло по одному: открыл, перевёл, вернулся, открыл
    следующий — четыре товара на четыре языка это шестнадцать
    заходов. Теперь отмечаются товары, и одна кнопка переводит всё,
    чего у них нет, на все недостающие языки; вторая отдаёт ОДИН файл
    для плагина со всеми переводами выбранных, а не по файлу на товар.
    """
    ids = [int(i) for i in view["id"]]
    sel = set(st.session_state.get("loc-sel") or ()) & set(ids)
    st.session_state["loc-sel"] = sel
    rows, prods, langs = bulk_counts(view, sel)

    key = "loc-bulk"
    st.markdown(
        f'<style>.st-key-{key} div[data-testid="stHorizontalBlock"]'
        '{gap:10px !important;align-items:center;flex-wrap:wrap;}'
        f'.st-key-{key} div[data-testid="stColumn"]'
        '{flex:0 0 auto !important;width:auto !important;min-width:0 !important;}'
        f'.st-key-{key} div[data-testid="stColumn"]:last-child'
        '{flex:1 1 auto !important;}'
        f'.st-key-{key} .stButton button,.st-key-{key} .stDownloadButton button'
        '{white-space:nowrap !important;width:auto !important;}</style>',
        unsafe_allow_html=True)
    with st.container(key=key):
        c_all, c_none, c_go, c_dl, c_rest = st.columns([1, 1, 3, 3, 4], gap="small",
                                                       vertical_alignment="center")
        if c_all.button(f'{t("loc.select_all")} · {len(ids)}', key="loc-sel-all"):
            _set_sel(ids)
            st.rerun()
        if c_none.button(t("loc.select_none"), key="loc-sel-none",
                         disabled=not sel):
            _set_sel(())
            st.rerun()

        # Главное действие: всё, чего нет, по выбранным. Число честное —
        # не «выбрано 4», а сколько строк, товаров и языков в работе.
        go = c_go.button(
            f'{t("loc.translate_missing")} · {bulk_label(rows, prods, langs)}'
            if rows else t("loc.translate_missing"),
            key="loc-bulk-go", type="primary", disabled=not rows or demo,
            help=t("loc.bulk_help"))

        # Один файл на все выбранные товары и языки. Только то, что
        # переведено, — и в подписи сказано, сколько.
        payload, n_exp, n_prod_exp = _bulk_export(view, sel, demo)
        c_dl.download_button(
            f'{t("loc.export_figma")} · {plural("loc.rows_n", n_exp)}, '
            f'{plural("loc.products_n", n_prod_exp)}' if n_exp
            else t("loc.export_figma"),
            key="loc-bulk-dl", disabled=not n_exp,
            file_name="figma-translations.json", mime="application/json",
            data=json.dumps(payload, ensure_ascii=False, indent=2),
            help=t("loc.export_help"))
        if sel and not rows and not n_exp:
            c_rest.caption(t("loc.bulk_nothing"))

    render_copy_box(payload, "loc-bulk-copy", n_exp)
    if go:
        _bulk_translate(view, sel)
    _render_bulk_result()
    return sel


def render_copy_box(payload: dict, key: str, n_rows: int) -> None:
    """JSON для плагина — текстом, чтобы вставить из буфера.

    Главное трение файла — не сам файл, а дорога: скачать, найти
    в папке загрузок, загрузить в плагин. У `st.code` штатная иконка
    «скопировать», а у плагина — поле для вставки; путь становится
    «скопировал — вставил». Забор по сети пробовали и сняли:
    приложение на Cloud закрыто авторизацией, и до маршрута плагин
    не доходит. Файл остался вторым путём, для больших выгрузок.

    Свёрнуто в expander: полотно JSON на триста строк под таблицей
    не нужно никому, пока его не копируют.
    """
    if not n_rows:
        return
    with st.expander(t("loc.copy_json", n=plural("loc.rows_n", n_rows)),
                     expanded=False):
        st.caption(t("loc.copy_json_hint"))
        st.code(json.dumps(payload, ensure_ascii=False, indent=2),
                language="json", line_numbers=False, wrap_lines=False)


def _bulk_export(view: pd.DataFrame, sel: set, demo: bool):
    """(payload, строк, товаров) для кнопки выгрузки."""
    if not sel or demo:
        return {"file_key": None, "items": []}, 0, 0
    rows_df, err = export_rows(tuple(sorted(sel)))
    if err:
        st.error("⚠ " + t("loc.load_failed", e=err))
        return {"file_key": None, "items": []}, 0, 0
    file_key = cell_text(view.iloc[0], "figma_file_key")
    payload = export_payload(file_key, rows_df)
    n_prod = rows_df["asin"].nunique() if not rows_df.empty else 0
    return payload, int(len(rows_df)), int(n_prod)


def _bulk_translate(view: pd.DataFrame, sel: set) -> None:
    """Перевод «всего, чего нет» по выбранным — с ходом по товарам.

    Не колбэк, а прямой вызов из отрисовки: здесь нет полей, которые
    надо пересоздать до рендера, зато есть что показать по ходу —
    двадцать товаров на четыре языка идут минуты, и молчащий экран
    не отличить от сломанного. Итог кладётся в session_state
    и рисуется после rerun, как у одиночного перевода.
    """
    todo = [r for _, r in view.iterrows()
            if int(r["id"]) in sel
            and any((r.get("lang_gaps") or {}).values())]
    total = {"done": 0, "fails": [], "prods": 0, "model": ""}
    with st.status(t("loc.bulk_running", n=len(todo)), expanded=True) as status:
        for i, r in enumerate(todo, 1):
            pid = int(r["id"])
            name = f'{r.get("name") or r.get("asin")} · {r.get("asin")}'
            status.update(label=t("loc.bulk_step", i=i, n=len(todo), name=name))
            plan, err = missing_plan(pid)
            if err:
                total["fails"].append(f"{r.get('asin')}: {err}")
                status.write(f"✗ {name} — {err}")
                continue
            res = _run_plan(pid, plan)
            if res["error"]:
                total["fails"].append(f"{r.get('asin')}: {res['error']}")
                status.write(f"✗ {name} — {res['error']}")
                continue
            total["done"] += res["done"]
            total["model"] = res["model"] or total["model"]
            if res["done"]:
                total["prods"] += 1
            for f in res["fails"]:
                total["fails"].append(f"{r.get('asin')} {f}")
            status.write(
                f"{'✓' if res['done'] and not res['fails'] else '△'} {name} — "
                + t("loc.bulk_line", n=res["done"],
                    langs=", ".join(l.upper() for l in res["ok_langs"]) or "—")
                + (f" · {' · '.join(res['fails'])}" if res["fails"] else ""))
        status.update(label=t("loc.bulk_finished", n=total["done"]),
                      state="error" if total["fails"] and not total["done"]
                      else "complete")
    st.session_state["loc-bulk-result"] = total
    _invalidate()
    st.rerun()


def _render_bulk_result() -> None:
    """Итог массового прогона — после rerun, чтобы список уже был свежим."""
    res = st.session_state.pop("loc-bulk-result", None)
    if not res:
        return
    if res["done"]:
        st.success("✓ " + t("loc.bulk_done", n=res["done"], p=res["prods"],
                            model=res["model"]))
    if res["fails"]:
        st.error("⚠ " + t("loc.bulk_fails", n=len(res["fails"])) + " · "
                 + " · ".join(res["fails"][:6])
                 + (" …" if len(res["fails"]) > 6 else ""))
    if not res["done"] and not res["fails"]:
        st.info(t("loc.bulk_nothing"))


def render_list(products: pd.DataFrame, demo: bool) -> None:
    render_sync_bar(products, demo)
    st.markdown(summary_html(summarize(products)), unsafe_allow_html=True)
    st.caption(t("loc.list_hint"))

    # без перевода — наверх: это и есть очередь работы
    view = products.copy()
    view["_o"] = view["langs_done"].map(
        lambda d: {"none": 0, "partial": 1, "all": 2}[product_state(set(d or ()))])
    view = view.sort_values(["_o", "name"])

    sel = render_bulk_bar(view, demo)
    gen = int(st.session_state.get("loc-sel-gen", 0))

    for _, r in view.iterrows():
        pid = int(r["id"])
        ck, c0, c1, c2 = st.columns([0.5, 1.1, 8, 2.6], gap="small",
                                    vertical_alignment="center")
        # Отметка живёт в НАБОРЕ `loc-sel`, а не в ключе галочки:
        # «Выбрать все» стоит выше галочек и переставить их напрямую
        # не может (правило 7б) — кнопка меняет набор и растит
        # поколение, галочки следующего прогона создаются заново.
        ck.checkbox("", key=f"loc-ck-{gen}-{pid}", value=pid in sel,
                    label_visibility="collapsed",
                    on_change=_toggle_sel, args=(pid, f"loc-ck-{gen}-{pid}"))
        render_thumb(c0, r, demo)
        c1.markdown(product_row_html(r), unsafe_allow_html=True)
        # Кнопка ведёт на первый язык, где ОСТАЛИСЬ непереведённые
        # строки, — он и есть работа. «Готов» здесь считается по
        # строкам, а не по факту «хоть одна переведена» (см.
        # load_products): раньше единственная строка, переведённая
        # кнопкой ↻, делала язык готовым, и кнопка звала «Перевести DE»
        # у товара, где DE значился законченным.
        # Когда переводить нечего, кнопка не обещает перевод —
        # она открывает товар, и зовётся так.
        gaps = r.get("lang_gaps") or {}
        missing = [lg for lg in TARGET_LANGS if gaps.get(lg, 0)]
        target = missing[0] if missing else TARGET_LANGS[0]
        label = (f'{t("loc.translate")} · {target.upper()}' if missing
                 else t("loc.open"))
        if c2.button(label, key=f"loc-open-{r['id']}",
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

    # Ряд собирается ФЛЕКСОМ, а не долями колонок (правило 0). Доли
    # делят ширину поровну и сжимают содержимое: пять контролов в узкой
    # колонке обрезали подписи языков до одной буквы — «D», «E», «I».
    head_key = "loc-head"
    st.markdown(
        f'<style>.st-key-{head_key} div[data-testid="stHorizontalBlock"]'
        '{gap:10px !important;align-items:center;flex-wrap:wrap;}'
        f'.st-key-{head_key} div[data-testid="stColumn"]'
        '{flex:0 0 auto !important;width:auto !important;'
        'min-width:0 !important;}'
        f'.st-key-{head_key} div[data-testid="stColumn"]:last-child'
        '{flex:1 1 auto !important;}'
        f'.st-key-{head_key} .stButton button'
        '{white-space:nowrap !important;width:auto !important;}'
        f'.st-key-{head_key} label{{white-space:nowrap !important;}}</style>',
        unsafe_allow_html=True)

    with st.container(key=head_key):
        # Языки выбираются НЕСКОЛЬКО сразу: перевод на четыре рынка —
        # одна работа, а не четыре захода. Подписи здесь коды (DE, ES…),
        # они не переводятся, поэтому правило 7 про sticky не нужно.
        done = set(row.get("langs_done") or ())
        back, langs_box = st.columns([1, 8], gap="small",
                                     vertical_alignment="center")
        if back.button("← " + t("loc.back"), key="loc-back"):
            for k in ("loc-product", "loc-lang"):
                st.session_state.pop(k, None)
            st.rerun()
        picked = pick_langs(langs_box, lang, done)
    lang = picked[0] if picked else lang
    st.session_state["loc-lang"] = lang

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

    # Слева макет, справа строки. Без картинки перевод — это список
    # фраз без контекста: не видно, что одна строка — крупный заголовок
    # на тёмном фоне, а соседняя — мелкая подпись под ней.
    # Действия — НАД таблицей, как массовые действия на Синтезе:
    # строк здесь три десятка, и кнопка под ними уезжает за экран.
    # Ровно поэтому «Перевести заново» и считали пропавшей.
    render_actions(layers, row, lang, demo)

    # Карточка — это девять слайдов, и текст живёт на них, а не
    # в главном фото. Одна таблица на 33 строки заставляла дизайнера
    # держать в голове, к какому слайду относится строка; теперь
    # рядом со строками стоит тот слайд, на котором они написаны.
    render_slides(layers, row, pid, lang, demo)
    render_notes()
    render_prompt_box()


def pick_langs(box, current: str, done: set) -> list:
    """Чекбоксы языков и кнопка «все, где нет перевода».

    Возвращает выбранные коды в порядке TARGET_LANGS. Первый из них —
    язык таблицы: смотреть на два языка одновременно всё равно нельзя,
    а переводить на несколько нужно одним нажатием.

    Кнопка НЕ пишет в ключи чекбоксов: Streamlit запрещает менять
    `session_state` ключа после того, как виджет создан, и падает
    с StreamlitWidgetAlreadyInstantiatedError — кнопка стоит ниже
    чекбоксов, то есть всегда «после». Поэтому она кладёт НАБОР
    и растит поколение, а чекбоксы следующего прогона создаются
    с новыми ключами и берут значения из набора. Тот же приём, что
    у полей перевода, и по той же причине (правило 7б).
    """
    gen = int(st.session_state.get("loc-langs-gen", 0))
    preset = st.session_state.get("loc-langs-preset")
    chosen = set(preset if preset is not None
                 else st.session_state.get("loc-langs") or [current])

    # последняя колонка-распорка забирает остаток, остальные жмутся
    # по содержимому — иначе «FR» и кнопка режутся так же, как раньше
    cols = box.columns([1] * len(TARGET_LANGS) + [3, 6], gap="small",
                       vertical_alignment="center")
    picked = []
    for i, lg in enumerate(TARGET_LANGS):
        if cols[i].checkbox(lg.upper(), key=f"loc-lang-{gen}-{lg}",
                            value=lg in chosen):
            picked.append(lg)

    # «все, где нет перевода» — это и есть очередь работы по товару
    if cols[-2].button(t("loc.langs_missing"), key="loc-langs-missing",
                       help=t("loc.langs_missing_help")):
        st.session_state["loc-langs-preset"] = [
            lg for lg in TARGET_LANGS if lg not in done]
        st.session_state["loc-langs-gen"] = gen + 1
        st.rerun()

    st.session_state.pop("loc-langs-preset", None)
    st.session_state["loc-langs"] = picked or [current]
    return st.session_state["loc-langs"]


def render_thumb(col, row, demo: bool) -> None:
    """Миниатюра главного изображения — чтобы различать товары.

    По названию они не различаются: «Blower DCB-201BC» и «Blower
    DVB-200» читаются одинаково, а на картинке видно сразу. Берётся
    ОДНО изображение на товар (узел `.MAIN`), а не все слои: каждая
    миниатюра стоит запроса ссылки, и при двадцати одном товаре это
    двадцать один запрос — по одному в сутки на товар, дальше из кэша.
    """
    node = cell_text(row, "figma_node_id")
    if demo or not node:
        return
    png, err = preview_png(node, figma.THUMB_SCALE)
    if err or not png:
        # молчим: миниатюра — удобство, и её отказ не должен
        # заслонять список, ради которого человек сюда пришёл
        return
    try:
        col.image(png, width="stretch")
    except Exception:
        # битые байты Streamlit отдаёт в PIL, и падает ВСЯ страница.
        # Список важнее картинки, поэтому здесь именно молчание.
        pass


def render_preview(row, demo: bool, lang: str,
                   part: str = "MAIN") -> None:
    """Картинка макета — только для ОТКРЫТОГО товара.

    Миниатюры в списке стоили бы по запросу Figma на строку при сотнях
    строк, а по названию там и так понятно, что за товар. Показывается
    английский макет: превью отвечает на вопрос «куда встанет текст»,
    и роль строки одинакова на всех языках.
    """
    node, shown = preview_node(row, lang, part)
    if demo or not node:
        st.caption(t("loc.preview_none"))
        return
    png, err = preview_png(node)
    if err or not png:
        # отказ рендера не должен выглядеть как «превью не бывает»
        st.caption("⚠ " + t("loc.preview_failed", e=err or "—"))
        return
    try:
        st.image(png, width="stretch")
    except Exception as e:
        # здесь, в отличие от списка, отказ называется вслух: человек
        # открыл товар ради контекста и должен знать, что его нет
        st.caption("⚠ " + t("loc.preview_failed", e=f"{type(e).__name__}"))
        return
    # какой макет на экране: свой или английский за неимением своего
    st.caption(t("loc.preview_lang", lang=shown.upper()) if shown == lang
               else t("loc.preview_fallback", lang=lang.upper()))


def human_mark(row) -> str:
    """Значок «строку правил человек после модели».

    Через месяц по этому полю будет видно, где перевод можно отдать
    автоматике, а где нет. Значок мелкий и стоит у ИСХОДНИКА, а не
    у перевода: он про историю строки, а не про её текущий текст.
    """
    flag = row.get("edited_after_model")
    if pd.isna(flag) or not bool(flag):
        return ""
    return (f'<span title="{t("loc.edited_by_human")}" style="color:{MUTED};'
            f'font-size:11px;margin-left:6px;">✎</span>')


def _store_edit(pid: int, slot: str, lang: str, key: str) -> None:
    """Правка уезжает в базу сразу, без кнопки «Сохранить».

    Кнопка означала бы, что часть работы живёт только в браузере:
    вкладку закрыли — правки нет. Здесь же строка мелкая, правок много,
    и подтверждать каждую бессмысленно.
    """
    err = save_translation(pid, slot, lang, st.session_state.get(key, ""))
    st.session_state["loc-save-error"] = err
    _invalidate()


def _translate_rows(pid: int, langs, rows: list) -> None:
    """Одни и те же строки на каждый из языков: строка по ↻ или
    «заново» по отмеченным языкам. Путь один — `_translate_plan`."""
    langs = [langs] if isinstance(langs, str) else list(langs)
    _translate_plan(pid, {lang: rows for lang in langs})


def _translate_plan(pid: int, plan: dict) -> None:
    """Перевод моделью по плану {язык: строки} — из редактора.

    Вызывается ИЗ КОЛБЭКА кнопки, а из колбэка `st.error` на экран
    не попадает — Streamlit рисует элементы позже. Поэтому всё, что
    надо сказать человеку, кладётся в `session_state` и выводится
    при отрисовке. Иначе выходит худший вид отказа: кнопка нажалась,
    счётчики остались нулями, объяснения нет.
    """
    st.session_state.pop("loc-save-error", None)
    st.session_state.pop("loc-model-note", None)
    r = _run_plan(pid, plan)
    if r["error"]:
        st.session_state["loc-save-error"] = r["error"]
        return
    if r["skipped"]:
        st.session_state["loc-model-note"] = t("loc.model_all_skipped")
        return
    # Отказ по одному языку не должен выглядеть отказом по всем: сказать
    # надо и про сделанное, и про несделанное, каждое своим числом.
    if r["fails"]:
        st.session_state["loc-save-error"] = " · ".join(r["fails"])
    if r["done"]:
        st.session_state["loc-model-note"] = t(
            "loc.model_done_langs", n=r["done"], model=r["model"],
            langs=", ".join(l.upper() for l in r["ok_langs"]))
    elif not r["fails"]:
        st.session_state["loc-model-note"] = t("loc.model_kept_human",
                                               n=r["n_work"])
    _invalidate()


def _invalidate() -> None:
    """Всё, что считает от переводов: строки, список, пробелы, выгрузка."""
    load_layers.clear()
    load_products.clear()
    lang_gaps.clear()
    export_rows.clear()


def _run_plan(pid: int, plan: dict) -> dict:
    """Перевод моделью по плану {язык: строки}. Возвращает, что вышло.

    План нужен потому, что у «всё, чего нет» строки на каждый язык
    СВОИ: у DE не хватает тридцати, у FR одной. Общий список на все
    языки переводил бы заново и то, что уже есть.

    Ничего не говорит человеку сам: зовётся и из колбэка редактора,
    и из массового прогона списка, а говорят они по-разному — один
    плашкой после перерисовки, другой строками хода по товарам.
    Возвращает: done (строк записано), model, fails (по языкам),
    ok_langs, n_work, skipped (нечего переводить), error (не начали).
    """
    out = {"done": 0, "model": "", "fails": [], "ok_langs": [],
           "n_work": 0, "skipped": False, "error": None}
    prompt_text, _ver, err = load_prompt()
    if err:
        out["error"] = err
        return out
    text = st.session_state.get("loc-prompt-draft") or prompt_text \
        or translate.DEFAULT_PROMPT

    # служебные строки отсеиваются на каждом языке отдельно: план
    # уже мог их не содержать, а мог и содержать — путь общий
    plan = {lang: translate.split_rows(rows)[0]
            for lang, rows in plan.items()}
    plan = {lang: rows for lang, rows in plan.items() if rows}
    if not plan:
        out["skipped"] = True
        return out
    out["n_work"] = max(len(v) for v in plan.values())

    for lang, work in plan.items():
        # глоссарий свой на каждый язык: словарь дизайнера у немецкого
        # и итальянского разный, и общий образец сбил бы оба
        pairs_df, _ = glossary(lang)
        pairs = pairs_df.to_dict("records") if not pairs_df.empty else []

        got, model = translate.run(text, lang, work, pairs)
        if not got:
            # три разных отказа, и все раньше выглядели одинаково —
            # пустотой: провайдер не ответил, ответ не разобрался, пусто
            out["fails"].append(f"{lang.upper()}: "
                                + (ai.last_call_error() or t("loc.model_empty")))
            continue

        # модель может ответить местами, которых мы не спрашивали: тогда
        # запись не найдёт строк и «успех» окажется нулём обновлённых
        known = {str(r["slot"]) for r in work}
        useful = {k: v for k, v in got.items() if k in known}
        if not useful:
            out["fails"].append(f"{lang.upper()}: " + t(
                "loc.model_slots_mismatch", n=len(got),
                got=", ".join(list(got)[:3])))
            continue

        n, err = save_model_translation(pid, lang, model, useful)
        if err:
            out["fails"].append(f"{lang.upper()}: {err}")
            continue
        out["done"] += n
        out["model"] = model
        out["ok_langs"].append(lang)

        # Поле ввода объявлено с key, и одного `pop` тут МАЛО: ключ из
        # session_state снимается, но состояние самого виджета живёт
        # в браузере — на следующем прогоне оттуда приезжает прежнее
        # пустое значение и ложится поверх `value=`. Видно это было по
        # счётчику: он считал от базы и показывал «50 / 56», а поле
        # рядом оставалось пустым. Поэтому меняется КЛЮЧ: поля
        # становятся новыми виджетами и берут текст из базы.
        gen_key = f"loc-gen-{pid}-{lang}"
        st.session_state[gen_key] = int(st.session_state.get(gen_key, 0)) + 1
    return out


def slide_title(name: str, part: pd.DataFrame) -> str:
    """Заголовок блока: «PT01», а у модуля A+ — вариант, номер и имя
    фрейма из Figma: «A+ десктоп 5 · carousel 3.1». Позиционное имя
    «A+d05» дизайнеру ничего не говорит, настоящее имя — говорит."""
    ap = aplus_part(name)
    if ap is None:
        return name
    real = ""
    if "frame_name" in part:
        real = next((cell_text(r, "frame_name") for _, r in part.iterrows()
                     if cell_text(r, "frame_name")), "")
    var, num = ap
    head = (t("loc.aplus_desktop", n=num) if var == "d"
            else t("loc.aplus_mobile", n=num) if var == "m"
            else t("loc.aplus_other"))
    return f"{head} · {real}" if real else head


def render_slides(layers: pd.DataFrame, row, pid: int, lang: str,
                  demo: bool) -> None:
    """Блок на слайд: заголовок, слева его превью, справа его строки."""
    slides = layers.assign(_slide=layers["slot"].map(slide_of)
                           if "slot" in layers else "")
    order = sorted({s for s in slides["_slide"] if s}, key=slide_order)
    if not order:                       # демо и старые данные без slot
        pane_img, pane_txt = st.columns([1, 1.9], gap="medium")
        with pane_img:
            render_preview(row, demo, lang)
        with pane_txt:
            render_rows(layers, pid, lang)
        return

    for name in order:
        part = slides[slides["_slide"] == name]
        # в заголовке — переводимые строки: служебные лежат внутри
        # свёрнутыми, и считать их работой значит завышать объём
        work_n = int((~part["source_text"].map(translate.is_boilerplate)).sum())
        st.markdown(eyebrow(f'{slide_title(name, part)} · {t("loc.slide_rows", n=work_n)}'),
                    unsafe_allow_html=True)
        pane_img, pane_txt = st.columns([1, 1.9], gap="medium")
        with pane_img:
            render_preview(row, demo, lang, part=name)
        with pane_txt:
            render_rows(part, pid, lang, header=False)


def render_rows(layers: pd.DataFrame, pid: int, lang: str,
                header: bool = True) -> None:
    # поколение данных: растёт после каждой записи модели, и поля
    # пересоздаются вместо того, чтобы показывать прошлое
    gen = int(st.session_state.get(f"loc-gen-{pid}-{lang}", 0))
    # Шапка таблицы: подписи колонок здесь, а не в каждой строке —
    # иначе на десяти строках они читаются как часть текста
    if header:
        st.markdown(
            f'<div style="display:flex;gap:10px;font-size:11px;'
            f'letter-spacing:.06em;text-transform:uppercase;color:{MUTED};'
            f'padding:0 2px 4px;"><div style="flex:1;">{t("loc.col_src")}</div>'
            f'<div style="flex:1;">{t("loc.col_dst")}</div>'
            f'<div style="flex:0 0 86px;text-align:right;">'
            f'{t("loc.col_chars")}</div></div>', unsafe_allow_html=True)

    if st.session_state.get("loc-save-error"):
        st.error("⚠ " + t("loc.save_row_failed",
                          e=st.session_state["loc-save-error"]))
    if st.session_state.get("loc-model-note"):
        st.success(st.session_state["loc-model-note"])

    work = layers[~layers["source_text"].map(translate.is_boilerplate)]
    skip = layers[layers["source_text"].map(translate.is_boilerplate)]

    edited: dict = {}
    for _, lr in work.iterrows():
        slot = cell_text(lr, "slot") or cell_text(lr, "layer_id")
        key = f"loc-txt-{pid}-{lang}-{gen}-{slot}"
        current = st.session_state.get(key, cell_text(lr, "translated_text"))
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
            c1, c2, c3, c4 = st.columns([1, 1, 0.34, 0.22], gap="small",
                                        vertical_alignment="center")
            c1.markdown(
                f'<div style="font-size:13px;color:{INK};padding-top:6px;">'
                f'{lr["source_text"]}{human_mark(lr)}</div>',
                unsafe_allow_html=True)
            c2.text_input(lr["layer_id"], value=current, key=key,
                          label_visibility="collapsed",
                          on_change=_store_edit, args=(pid, slot, lang, key))
            c3.markdown(counter_html(n, lim, state), unsafe_allow_html=True)
            # перевод ОДНОЙ строки: чаще всего переделать надо именно её,
            # а не весь товар — и это дешевле по времени и по деньгам
            c4.button("↻", key=f"loc-tr-{pid}-{lang}-{slot}",
                      help=t("loc.retranslate_row"),
                      on_click=_translate_rows,
                      args=(pid, st.session_state.get("loc-langs") or [lang],
                            [{"slot": slot,
                                         "source_text": lr["source_text"],
                                         "char_limit": lr.get("char_limit")}]))

    # Служебные строки — числа и коды моделей — свёрнуты: они одинаковы
    # на всех языках, и в общем списке это треть таблицы шума, в котором
    # теряется настоящая работа.
    if not skip.empty:
        with st.expander(t("loc.skip_rows_n", n=len(skip))):
            st.caption(t("loc.skip_rows_hint"))
            for _, lr in skip.iterrows():
                st.markdown(
                    f'<div class="ls-mono" style="font-size:12px;'
                    f'color:{MUTED};padding:1px 2px;">{lr["source_text"]}</div>',
                    unsafe_allow_html=True)

    check = work.copy()
    check["translated_text"] = check["layer_id"].map(edited)
    n_over = over_rows(check)
    if n_over:
        st.warning("⚠ " + t("loc.over_warning", n=n_over))


def render_prompt_box() -> None:
    """Промпт целиком на экране — то, что уйдёт модели, без добавок.

    Скрытый промпт — это чужие решения, которые нельзя оспорить.
    Дизайнер видит правила и дописывает своё («не переводить название
    модели») туда же, а не пишет о них в чат.
    """
    saved, ver, err = load_prompt()
    with st.expander(t("loc.prompt_open")):
        if err:
            st.error("⚠ " + t("loc.prompt_read_failed", e=err))
            return
        base = saved or translate.DEFAULT_PROMPT
        if not saved:
            # текст по умолчанию виден и назван таковым: подмены,
            # из-за которой мы теряли методологию тайтлов, тут нет
            st.caption(t("loc.prompt_default"))
        else:
            st.caption(t("loc.prompt_version", v=ver))
        st.text_area(t("loc.prompt_open"), value=base, height=260,
                     key="loc-prompt-draft", label_visibility="collapsed")
        if st.button(t("loc.prompt_save"), key="loc-prompt-save"):
            fail = save_prompt(st.session_state.get("loc-prompt-draft") or "")
            if fail:
                st.error("⚠ " + t("loc.prompt_save_failed", e=fail))
            else:
                st.success(t("loc.prompt_saved", v=ver + 1))
                st.rerun()


def rows_into(n_rows: int, langs) -> str:
    """«22 строки на французский» / «22 строки на 3 языка».

    Словами, а не «22 × 1»: произведение читалось как формула, и
    спрашивали, что там умножается. Один язык называется по имени,
    несколько — числом.
    """
    return f'{plural("loc.rows", n_rows)} {into_phrase(langs)}'


def into_phrase(langs) -> str:
    """«на французский» для одного языка, «на 3 языка» для нескольких."""
    langs = list(langs)
    if len(langs) == 1:
        return t(f"loc.into.{langs[0]}")
    return plural("loc.into_langs", len(langs))


def render_actions(layers: pd.DataFrame, row, lang: str, demo: bool) -> None:
    """Действия — НАД таблицей, первой строкой, и главное действие одно.

    Раньше кнопка перевода стояла под тремя десятками строк и уезжала
    за экран — её считали пропавшей и жали ↻ на каждой строке. Теперь
    первой и основной идёт «Перевести всё, чего нет»: она сама
    находит непереведённые строки на КАЖДОМ языке, где их нет, и
    переводит разом, без выбора языка и переключений. Галочки языков
    на неё не влияют — они для перевода заново и для просмотра.
    """
    pid = int(row["id"])
    rows = [{"slot": cell_text(lr, "slot") or cell_text(lr, "layer_id"),
             "source_text": lr["source_text"],
             "char_limit": lr.get("char_limit")}
            for _, lr in layers.iterrows()]
    langs = st.session_state.get("loc-langs") or [lang]
    work, _skip = translate.split_rows(rows)

    # Чего нет — по строкам на каждый язык. Демо-набор в базу не
    # ходит: план собирается из демо-строк той же формой, чтобы кнопка
    # на демо выглядела и считала так же, как на настоящих данных.
    if demo:
        plan, err = {}, None
        for lg in TARGET_LANGS:
            gap = [{"slot": cell_text(r, "slot") or cell_text(r, "layer_id"),
                    "source_text": r["source_text"],
                    "char_limit": r.get("char_limit")}
                   for _, r in demo_layers(pid, lg).iterrows()
                   if not cell_text(r, "translated_text").strip()]
            if gap:
                plan[lg] = gap
    else:
        plan, err = missing_plan(pid)
    if err:
        st.error("⚠ " + t("loc.load_failed", e=err))
    n_missing = sum(len(v) for v in plan.values())

    a1, a2, a3 = st.columns([3.6, 3.0, 2.4], gap="small")
    if n_missing:
        a1.button(f'{t("loc.translate_missing")} · '
                  f'{rows_into(n_missing, plan)}',
                  key="loc-fill", type="primary",
                  help=t("loc.translate_missing_help"),
                  on_click=_translate_plan, args=(pid, plan))
    else:
        a1.caption("✓ " + t("loc.nothing_missing"))
    # «Заново» — вторично: это переделка того, что уже есть, по
    # отмеченным языкам. Раньше подпись была «Перевести · 22 × 1».
    a2.button(t("loc.retranslate_n", rows=plural("loc.rows", len(work)),
                into=into_phrase(langs)),
              key="loc-retry", disabled=not work,
              help=t("loc.retranslate_help",
                     langs=", ".join(l.upper() for l in langs)),
              on_click=_translate_rows, args=(pid, langs, rows))
    # Запись в Figma через REST невозможна, поэтому «Применить» отдаёт
    # файл для плагина. Кнопка, которая ничего не делает и объясняет
    # почему, — хуже кнопки, которая делает половину дела.
    single = {
        "file_key": row.get("figma_file_key"),
        "asin": row.get("asin"), "lang": lang,
        "layers": [{"layer_id": lr["layer_id"],
                    "slot": cell_text(lr, "slot"),
                    "text": cell_text(lr, "translated_text")}
                   for _, lr in layers.iterrows()
                   if cell_text(lr, "translated_text").strip()],
    }
    a3.download_button(
        t("loc.apply_figma"), key="loc-apply",
        file_name=f"figma-{row.get('asin')}-{lang}.json", mime="application/json",
        data=json.dumps(single, ensure_ascii=False, indent=2))
    st.caption(t("loc.apply_json_note"))
    render_copy_box(single, "loc-copy", len(single["layers"]))


def render_notes() -> None:
    """Оговорки — под таблицей: они поясняют колонку длины."""
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
