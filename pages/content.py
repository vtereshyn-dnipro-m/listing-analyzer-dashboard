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

from i18n import t
from services import ai, figma, translate
from services.localization import (
    ALL_LANGS, TARGET_LANGS, SYNC_EVERY_HOURS,
    demo_layers, demo_products, fits, glossary, load_layers, load_products,
    load_prompt, needs_sync, over_rows, product_state,
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


def cell_text(row, col: str) -> str:
    """Значение ячейки строкой — с NaN вместо пустоты.

    Правило 4 проекта: NaN в Python ИСТИННЫЙ, поэтому `x or ""`
    возвращает не пустую строку, а сам NaN, и `.strip()` на нём падает
    с AttributeError. Непереведённые строки приходят из LEFT JOIN
    именно как NaN, а не как None, — на этом и упала страница.
    """
    val = row.get(col)
    return "" if pd.isna(val) else str(val)


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
                    "typo_frames": parsed.get("typo_frames", []),
                    "limited": bool(first_pass),
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
    # список из четырёх товаров не должен выглядеть как весь файл:
    # по нему начнут считать объём работы, как по демо-данным
    if rep.get("limited"):
        st.info("ℹ " + t("loc.first_pass_notice",
                         n=len(figma.FIRST_PASS_ASINS)))
    if rep.get("aplus_frames"):
        st.caption(t("loc.aplus_skipped", n=int(rep["aplus_frames"])))
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
        c0, c1, c2 = st.columns([1.1, 8, 2.6], gap="small",
                                vertical_alignment="center")
        render_thumb(c0, r, demo)
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
    # Языки выбираются НЕСКОЛЬКО сразу: перевод на четыре рынка — одна
    # работа, а не четыре захода. Подписи здесь коды (DE, ES…), они
    # не переводятся, поэтому правило 7 про sticky-виджеты не нужно.
    done = set(row.get("langs_done") or ())
    picked = pick_langs(b2, lang, done)
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
    render_actions(layers, row, lang)

    pane_img, pane_txt = st.columns([1, 1.9], gap="medium")
    with pane_img:
        render_preview(row, demo)
    with pane_txt:
        render_rows(layers, pid, lang)
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

    cols = box.columns(len(TARGET_LANGS) + 1, gap="small",
                       vertical_alignment="center")
    picked = []
    for i, lg in enumerate(TARGET_LANGS):
        if cols[i].checkbox(lg.upper(), key=f"loc-lang-{gen}-{lg}",
                            value=lg in chosen):
            picked.append(lg)

    # «все, где нет перевода» — это и есть очередь работы по товару
    if cols[-1].button(t("loc.langs_missing"), key="loc-langs-missing",
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


def render_preview(row, demo: bool) -> None:
    """Картинка макета — только для ОТКРЫТОГО товара.

    Миниатюры в списке стоили бы по запросу Figma на строку при сотнях
    строк, а по названию там и так понятно, что за товар. Показывается
    английский макет: превью отвечает на вопрос «куда встанет текст»,
    и роль строки одинакова на всех языках.
    """
    node = cell_text(row, "figma_node_id")
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
    st.caption(t("loc.preview_note"))


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
    load_layers.clear()
    load_products.clear()


def _translate_rows(pid: int, langs, rows: list) -> None:
    """Перевод моделью: строка или весь товар — путь один.

    Вызывается ИЗ КОЛБЭКА кнопки, а из колбэка `st.error` на экран
    не попадает — Streamlit рисует элементы позже. Поэтому всё, что
    надо сказать человеку, кладётся в `session_state` и выводится
    при отрисовке. Иначе выходит худший вид отказа: кнопка нажалась,
    счётчики остались нулями, объяснения нет.
    """
    st.session_state.pop("loc-save-error", None)
    st.session_state.pop("loc-model-note", None)
    langs = [langs] if isinstance(langs, str) else list(langs)

    prompt_text, _ver, err = load_prompt()
    if err:
        st.session_state["loc-save-error"] = err
        return
    text = st.session_state.get("loc-prompt-draft") or prompt_text \
        or translate.DEFAULT_PROMPT

    work, _skip = translate.split_rows(rows)
    if not work:
        st.session_state["loc-model-note"] = t("loc.model_all_skipped")
        return

    done_total, model_used, fails = 0, "", []
    for lang in langs:
        # глоссарий свой на каждый язык: словарь дизайнера у немецкого
        # и итальянского разный, и общий образец сбил бы оба
        pairs_df, _ = glossary(lang)
        pairs = pairs_df.to_dict("records") if not pairs_df.empty else []

        got, model = translate.run(text, lang, work, pairs)
        if not got:
            # три разных отказа, и все раньше выглядели одинаково —
            # пустотой: провайдер не ответил, ответ не разобрался, пусто
            fails.append(f"{lang.upper()}: "
                         + (ai.last_call_error() or t("loc.model_empty")))
            continue

        # модель может ответить местами, которых мы не спрашивали: тогда
        # запись не найдёт строк и «успех» окажется нулём обновлённых
        known = {str(r["slot"]) for r in work}
        useful = {k: v for k, v in got.items() if k in known}
        if not useful:
            fails.append(f"{lang.upper()}: " + t(
                "loc.model_slots_mismatch", n=len(got),
                got=", ".join(list(got)[:3])))
            continue

        n, err = save_model_translation(pid, lang, model, useful)
        if err:
            fails.append(f"{lang.upper()}: {err}")
            continue
        done_total += n
        model_used = model

        # Поле ввода объявлено с key, и одного `pop` тут МАЛО: ключ из
        # session_state снимается, но состояние самого виджета живёт
        # в браузере — на следующем прогоне оттуда приезжает прежнее
        # пустое значение и ложится поверх `value=`. Видно это было по
        # счётчику: он считал от базы и показывал «50 / 56», а поле
        # рядом оставалось пустым. Поэтому меняется КЛЮЧ: поля
        # становятся новыми виджетами и берут текст из базы.
        gen_key = f"loc-gen-{pid}-{lang}"
        st.session_state[gen_key] = int(st.session_state.get(gen_key, 0)) + 1

    # Отказ по одному языку не должен выглядеть отказом по всем: сказать
    # надо и про сделанное, и про несделанное, каждое своим числом.
    if fails:
        st.session_state["loc-save-error"] = " · ".join(fails)
    if done_total:
        st.session_state["loc-model-note"] = t(
            "loc.model_done_langs", n=done_total, model=model_used,
            langs=", ".join(l.upper() for l in langs if
                            f"{l.upper()}:" not in " ".join(fails)))
    elif not fails:
        st.session_state["loc-model-note"] = t("loc.model_kept_human",
                                               n=len(work))
    load_layers.clear()
    load_products.clear()


def render_rows(layers: pd.DataFrame, pid: int, lang: str) -> None:
    # поколение данных: растёт после каждой записи модели, и поля
    # пересоздаются вместо того, чтобы показывать прошлое
    gen = int(st.session_state.get(f"loc-gen-{pid}-{lang}", 0))
    # Шапка таблицы: подписи колонок здесь, а не в каждой строке —
    # иначе на десяти строках они читаются как часть текста
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


def render_actions(layers: pd.DataFrame, row, lang: str) -> None:
    """Действия и оговорки — под обеими колонками, а не внутри одной."""
    pid = int(row["id"])
    rows = [{"slot": cell_text(lr, "slot") or cell_text(lr, "layer_id"),
             "source_text": lr["source_text"],
             "char_limit": lr.get("char_limit")}
            for _, lr in layers.iterrows()]

    a1, a2, a3 = st.columns([3.0, 2.4, 3.6], gap="small")
    # Перевод — главное действие экрана, поэтому он основной и первый.
    # «Применить в Figma» вторично: применяют то, что уже переведено.
    langs = st.session_state.get("loc-langs") or [lang]
    work, _skip = translate.split_rows(rows)
    a1.button(f'{t("loc.retranslate")} · {len(work)} × {len(langs)}',
              key="loc-retry", type="primary",
              disabled=not work,
              help=t("loc.retranslate_help",
                     langs=", ".join(l.upper() for l in langs)),
              on_click=_translate_rows, args=(pid, langs, rows))
    # Запись в Figma через REST невозможна, поэтому «Применить» отдаёт
    # файл для плагина. Кнопка, которая ничего не делает и объясняет
    # почему, — хуже кнопки, которая делает половину дела.
    a2.download_button(
        t("loc.apply_figma"), key="loc-apply",
        file_name=f"figma-{row.get('asin')}-{lang}.json", mime="application/json",
        data=json.dumps({
            "file_key": row.get("figma_file_key"),
            "asin": row.get("asin"), "lang": lang,
            "layers": [{"layer_id": lr["layer_id"],
                        "slot": cell_text(lr, "slot"),
                        "text": cell_text(lr, "translated_text")}
                       for _, lr in layers.iterrows()
                       if cell_text(lr, "translated_text").strip()],
        }, ensure_ascii=False, indent=2))
    st.caption(t("loc.apply_json_note"))


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
