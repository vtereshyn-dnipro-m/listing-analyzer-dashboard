# -*- coding: utf-8 -*-
"""
pages/matrix_setup.py — Матрица товаров. v3 (дизайн макета B).

Строки-карточки с кнопкой «Собрать» в каждой, чипы Наши/Конкуренты,
поиск, фильтры, пагинация, групповые действия, расписание автосбора.
"""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from i18n import t
from services import cache
from services.db import get_conn, add_matrix_rows, parse_asin_lines, cfg, get_engine
from services.worklog import worklog_map, work_badges, has_work
from services.marketplaces import (product_url, asin_link,
                                   img_or_stub, ASIN_IN_URL)
from components.ui import inject_fonts, eyebrow

inject_fonts()
st.title(t("nav.matrix"))

INK = "#1A1815"
MUTED = "#8A8578"
BORDER = "#E7E4DD"
CARD = "#FFFFFF"
OK_BG = "#DCEEE0"
OK_TEXT = "#2F6B3A"
ERR_BG = "#FCEBEB"
ERR_TEXT = "#A32D2D"
MONO = "var(--ls-mono)"   # переменная из inject_fonts(): без кавычек в атрибутах

PAGE_SIZE = 25
# Страна для ScrapingDog. Пропуск здесь не безобиден: фолбэк "us" уводит
# сбор на amazon.com, и снапшот приезжает от ЧУЖОГО листинга. Так молча
# собирались ie и be — коды были в матрице, а в карте их не было.
MP_COUNTRY = {
    "com": "us", "de": "de", "es": "es", "fr": "fr",
    "it": "it", "co.uk": "gb", "nl": "nl", "se": "se", "pl": "pl",
    "ie": "ie", "be": "be", "com.be": "be",
}
# язык страницы: без него ScrapingDog иногда отдаёт EN-версию amazon.es,
# и длина тайтла считается по чужому языку
MP_LANGUAGE = {
    "es": "es", "de": "de", "fr": "fr", "it": "it",
    "com": "en", "co.uk": "en", "nl": "nl", "se": "sv", "pl": "pl",
    # Ирландия англоязычная; для Бельгии Amazon даёт нидерландский,
    # французский и английский — взят нидерландский как основной язык
    # каталога. Если клиент ведёт be на французском, менять здесь.
    "ie": "en", "be": "nl", "com.be": "nl",
}

st.caption(t("matrix.caption"))


@st.cache_data(ttl=120)
def load_matrix() -> pd.DataFrame:
    try:
        df = pd.read_sql(
            """
            SELECT m.sku_group, m.asin, m.marketplace, m.is_competitor, m.added_at,
                   s.fetched_at AS last_fetch, s.ok AS last_ok, s.title,
                   s.main_image,
                   d.red, d.amber, d.yellow
            FROM product_matrix m
            LEFT JOIN LATERAL (
                SELECT fetched_at, ok, title,
                       COALESCE(raw->>'main_image',
                                raw->'images'->>0) AS main_image
                FROM listing_snapshots s
                WHERE s.asin = m.asin AND s.marketplace = m.marketplace
                ORDER BY s.fetched_at DESC LIMIT 1
            ) s ON TRUE
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(*) FILTER (WHERE severity = 'red')    AS red,
                    COUNT(*) FILTER (WHERE severity = 'amber')  AS amber,
                    COUNT(*) FILTER (WHERE severity = 'yellow') AS yellow
                FROM (
                    SELECT DISTINCT ON (rule_id) severity
                    FROM diagnosis dd
                    WHERE dd.asin = m.asin AND dd.marketplace = m.marketplace
                      AND dd.resolved_at IS NULL
                    ORDER BY rule_id, created_at DESC
                ) latest
            ) d ON TRUE
            ORDER BY m.sku_group, m.marketplace, m.asin
            """,
            get_engine(),
        )
        return df
    except Exception:
        return pd.DataFrame()


# ================================================================ ввод пачкой
st.markdown(
    t("matrix.format_hint") + "  \n" + t("matrix.format_example")
)

text = st.text_area(
    "ASIN пачкой",
    height=120,
    placeholder=(
        "GS-98, B0DKFVFT29, es\n"
        "GS-98, https://www.amazon.es/dp/B0DKFVFT29\n"
        "https://www.amazon.de/dp/B0XXXXXXXX\n"
        "GS-98, B0XXXXXXXX, es, конкурент"
    ),
    label_visibility="collapsed",
)

if st.button(t("matrix.add"), type="primary", disabled=not text.strip()):
    rows = parse_asin_lines(text)
    if not rows:
        st.warning(t("matrix.no_asin"))
    else:
        try:
            conn = get_conn()
            n = add_matrix_rows(conn, rows)
            conn.close()
            st.success(f"{t('matrix.added')} {n}")
            cache.after_matrix_change()
            load_matrix.clear()
        except Exception as e:
            st.error(f"БД недоступна: {e}")

st.divider()

# ================================================================ импорт из каталога
@st.cache_data(ttl=120)
def load_catalog_source() -> pd.DataFrame:
    """Зеркало каталога Amazon (синхронизируется ноутбуком)."""
    try:
        df_c = pd.read_sql(
            "SELECT asin, marketplace, sku_group, fulfillment, report_date, "
            "synced_at FROM catalog_source", get_engine())
        return df_c
    except Exception:
        return pd.DataFrame()


src = load_catalog_source()

with st.expander(f"{t('matrix.import_header')} ({len(src)})",
                 expanded=False):
    if src.empty:
        st.caption(t("matrix.import_empty"))
    else:
        synced = pd.to_datetime(src["synced_at"].max()).strftime("%d.%m %H:%M")
        rep = pd.to_datetime(src["report_date"].max()).strftime("%d.%m.%Y")
        st.caption(f"{t('matrix.report_from')} {rep} · "
                   f"{t('matrix.synced_at')} {synced}")

        # что уже в матрице
        try:
            in_matrix = pd.read_sql(
                "SELECT asin, marketplace FROM product_matrix", get_engine())
        except Exception:
            in_matrix = pd.DataFrame(columns=["asin", "marketplace"])
        have = set(zip(in_matrix["asin"], in_matrix["marketplace"])) \
            if not in_matrix.empty else set()

        src = src.copy()
        src["_new"] = ~src.apply(
            lambda r: (r["asin"], r["marketplace"]) in have, axis=1)

        # сводка по маркетплейсам
        stat = (src.groupby("marketplace")
                .agg(total=("asin", "size"), new=("_new", "sum"))
                .reset_index())
        st.dataframe(
            stat,
            column_config={
                "marketplace": st.column_config.TextColumn("MP", width="small"),
                "total": st.column_config.NumberColumn(t("catalog.products"),
                                                       width="small"),
                "new": st.column_config.NumberColumn(t("matrix.import_new"),
                                                     width="small"),
            },
            hide_index=True, width="stretch")

        ic1, ic2 = st.columns([3, 2])
        mps_all = sorted(src["marketplace"].unique())
        mp_pick = ic1.multiselect(
            t("list.all_mp"), mps_all, default=mps_all)
        fba_only = ic2.checkbox("FBA", value=False)

        pick = src[src["marketplace"].isin(mp_pick)]
        if fba_only:
            pick = pick[pick["fulfillment"].astype(str)
                        .str.upper().str.startswith("AMAZON")]
        new_rows = pick[pick["_new"]]

        st.markdown(
            f"{t('matrix.import_new')}: **{len(new_rows)}** · "
            f"{t('matrix.import_existing')}: {len(pick) - len(new_rows)}")

        if st.button(f"{t('matrix.import_button')} ({len(new_rows)})",
                     type="primary", disabled=new_rows.empty):
            try:
                conn = get_conn()
                added = 0
                with conn, conn.cursor() as cur:
                    for _, r in new_rows.iterrows():
                        cur.execute(
                            """
                            INSERT INTO product_matrix
                                (sku_group, asin, marketplace, is_competitor)
                            VALUES (%s, %s, %s, FALSE)
                            ON CONFLICT (asin, marketplace) DO NOTHING
                            """,
                            (r["sku_group"] or r["asin"], r["asin"],
                             r["marketplace"]))
                        added += cur.rowcount
                conn.close()
                cache.after_matrix_change()
                load_matrix.clear()
                st.success(f"{t('matrix.import_button')}: {added}")
                st.rerun()
            except Exception as e:
                st.error(f"Ошибка импорта: {e}")

        st.caption(t("matrix.import_note"))

# ================================================================ данные


# ================================================================ пайплайн
def collect_rows(rows: pd.DataFrame) -> None:
    import requests

    key = cfg("SCRAPINGDOG_API_KEY")
    if not key:
        st.error("SCRAPINGDOG_API_KEY не найден в секретах.")
        return

    skipped: list[tuple] = []
    try:
        conn = get_conn()
        cur = conn.cursor()
        with st.status(t("matrix.collecting"), expanded=True) as status:
            for _, row in rows.iterrows():
                asin, mp = row["asin"], row["marketplace"]
                sku = row["sku_group"]
                is_comp = bool(row["is_competitor"])

                # Фолбэка на "us" здесь больше нет: он уводил сбор
                # на amazon.com, и снапшот приезжал от ЧУЖОГО листинга —
                # молча, так собирались ie, be и pl. Но и падать нельзя:
                # один непокрытый рынок положил бы всю партию, а собирают
                # сотнями. Поэтому строка пропускается с причиной, а список
                # пропущенных показывается в конце.
                if mp not in MP_COUNTRY or mp not in MP_LANGUAGE:
                    skipped.append((asin, mp, t("matrix.skip_unknown_mp")))
                    st.write(f"   ⚠ {asin} ({mp}): "
                             + t("matrix.skip_unknown_mp"))
                    continue

                st.write(f"Fetch {asin} ({mp})...")
                try:
                    resp = requests.get(
                        "https://api.scrapingdog.com/amazon/product",
                        params={"api_key": key, "domain": mp, "asin": asin,
                                "country": MP_COUNTRY[mp],
                                "language": MP_LANGUAGE[mp]},
                        timeout=60,
                    )
                except Exception as e:
                    # сеть отвалилась на одном товаре — остальные всё равно
                    # собираем, иначе партия из четырёхсот гибнет на седьмом
                    skipped.append((asin, mp, f"{type(e).__name__}: {e}"))
                    st.write(f"   ⚠ {asin} ({mp}): {type(e).__name__}: {e}")
                    continue
                ok = resp.status_code == 200
                data = resp.json() if ok else {
                    "_error_status": resp.status_code,
                    "_error_body": resp.text[:500],
                }

                availability = str(
                    data.get("availability_status") or data.get("availability") or ""
                ).lower()
                in_stock = ("unavailable" not in availability
                            and "out of stock" not in availability)
                title = data.get("title") or ""
                bullets = (data.get("feature_bullets")
                           or data.get("about_this_item") or [])
                raw_reviews = data.get("total_reviews") or data.get("review_count")
                try:
                    review_count = int(str(raw_reviews).replace(",", "").replace(".", ""))
                except (TypeError, ValueError):
                    review_count = None

                images = data.get("images") or []
                image_count = len(images) if isinstance(images, list) else 0
                has_video = bool(data.get("videos") or data.get("video")
                                 or data.get("has_video"))
                raw_aplus = bool(data.get("aplus"))

                cur.execute(
                    """
                    INSERT INTO listing_snapshots
                        (asin, marketplace, ok, title, in_stock,
                         review_count, bullet_points, raw)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (asin, mp, ok, title, in_stock, review_count,
                     bullets, json.dumps(data)),
                )
                # Признак A+ для правила берём СТАБИЛИЗИРОВАННЫЙ по трём
                # последним снимкам, и только после записи свежего снапшота —
                # вью считает по ним. Сырое поле врёт примерно на 15%
                # запросов ScrapingDog (на .it по отдельным товарам чаще),
                # и боль «нет A+» заводилась на товарах, где A+ есть.
                # Если строки во вью ещё нет (первый сбор) — сырое поле.
                cur.execute(
                    "SELECT has_aplus FROM listing_latest "
                    "WHERE asin = %s AND marketplace = %s", (asin, mp))
                _st_aplus = cur.fetchone()
                has_aplus = (bool(_st_aplus[0])
                             if _st_aplus and _st_aplus[0] is not None
                             else raw_aplus)

                title_len = len(title)
                cur.execute(
                    """
                    INSERT INTO listing_analysis
                        (asin, marketplace, title_len, title_over, highlights_len)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (asin, mp, title_len, max(0, title_len - 75),
                     len(" ".join(bullets))),
                )

                if ok and not is_comp:
                    if not in_stock:
                        cur.execute(
                            """
                            INSERT INTO diagnosis (sku_group, asin, marketplace,
                                severity, pain, cause, action, rule_id)
                            VALUES (%s, %s, %s, 'red', %s, %s, %s, 'out_of_stock')
                            """,
                            (sku, asin, mp,
                             "товар мёртв: недоступен к покупке",
                             "сток/поставка, не контент",
                             "пополнить сток или переключить вариацию"),
                        )
                    if title_len > 75:
                        cur.execute(
                            """
                            INSERT INTO diagnosis (sku_group, asin, marketplace,
                                severity, pain, cause, action, rule_id)
                            VALUES (%s, %s, %s, 'amber', %s, %s, %s, 'title_over_limit')
                            """,
                            (sku, asin, mp,
                             f"тайтл {title_len} симв. при лимите 75",
                             "Amazon обрежет после 27.07",
                             "сплит на title 75 + highlights"),
                        )
                    if review_count is not None and review_count < 50:
                        cur.execute(
                            """
                            INSERT INTO diagnosis (sku_group, asin, marketplace,
                                severity, pain, cause, action, rule_id)
                            VALUES (%s, %s, %s, 'yellow', %s, %s, %s, 'low_reviews')
                            """,
                            (sku, asin, mp,
                             f"{review_count} отзывов при пороге 50+",
                             "листинг молодой / без Vine",
                             "запустить Vine (30 юнитов)"),
                        )

                    if 0 < image_count < 7:
                        cur.execute(
                            """
                            INSERT INTO diagnosis (sku_group, asin, marketplace,
                                severity, pain, cause, action, rule_id)
                            VALUES (%s, %s, %s, 'yellow', %s, %s, %s, 'few_images')
                            """,
                            (sku, asin, mp,
                             f"{image_count} фото при норме 7+ для Tools",
                             "галерея слабее нормы категории",
                             "доснять фото: комплект, применение, размеры"),
                        )
                    if not has_video:
                        cur.execute(
                            """
                            INSERT INTO diagnosis (sku_group, asin, marketplace,
                                severity, pain, cause, action, rule_id)
                            VALUES (%s, %s, %s, 'yellow', %s, %s, %s, 'no_video')
                            """,
                            (sku, asin, mp,
                             "нет видео на листинге",
                             "конверсия инструментов растёт с видео-демо",
                             "снять 30-сек демо работы инструмента"),
                        )
                    if not has_aplus:
                        cur.execute(
                            """
                            INSERT INTO diagnosis (sku_group, asin, marketplace,
                                severity, pain, cause, action, rule_id)
                            VALUES (%s, %s, %s, 'amber', %s, %s, %s, 'no_aplus')
                            """,
                            (sku, asin, mp,
                             "нет A+ контента",
                             "A+ поднимает конверсию и защищает бренд-зону",
                             "собрать A+ из готовых модулей бренда"),
                        )

                st.write(f"   → {asin}: ok={ok}, тайтл {title_len} симв.")

            conn.commit()
            status.update(label=t("matrix.done"), state="complete")
        cur.close()
        conn.close()
        # Сбор меняет снапшоты и диагнозы — их читают ВСЕ страницы,
        # поэтому здесь глобальный сброс честнее точечного.
        st.cache_data.clear()
        # список пропущенных переживает st.rerun(): без этого он исчезал бы
        # ровно в тот момент, когда нужен
        if skipped:
            st.session_state["collect-skipped"] = skipped
        st.success(t("matrix.collected"))
        st.rerun()
    except Exception as e:
        st.error(f"Ошибка сбора: {e}")
        if skipped:
            st.session_state["collect-skipped"] = skipped


def render_collect_skipped() -> None:
    """Что не собралось и почему. Молча потерянная строка выглядит как
    собранная — до следующего взгляда на дату снапшота."""
    rows = st.session_state.pop("collect-skipped", None)
    if not rows:
        return
    st.warning("⚠ " + t("matrix.skipped_n", n=len(rows)))
    st.dataframe(
        pd.DataFrame(rows, columns=["asin", "mp", "reason"]),
        hide_index=True, width="stretch",
        column_config={
            "asin": st.column_config.TextColumn("ASIN"),
            "mp": st.column_config.TextColumn(t("matrix.c_mp")),
            "reason": st.column_config.TextColumn(t("matrix.c_reason")),
        })


# ================================================================ список
render_collect_skipped()

WORK = worklog_map()
df = load_matrix()

if df.empty:
    st.caption(t("common.no_data"))
else:
    ours_n = int((~df.is_competitor).sum())
    comp_n = int(df.is_competitor.sum())

    seg_key = "matrix-seg"
    seg = st.segmented_control(
        "Группа",
        options=["ours", "comp"],
        format_func=lambda v: f"{t('matrix.tab_ours')} · {ours_n}" if v == "ours" else f"{t('matrix.tab_comp')} · {comp_n}",
        default="ours",
        key=seg_key,
        label_visibility="collapsed",
    ) or "ours"

    data = df[~df.is_competitor] if seg == "ours" else df[df.is_competitor]

    f1, f2, f3, f4, f5 = st.columns([2.6, 1.8, 1.8, 2.2, 1.4])
    query = f1.text_input("Поиск", key="matrix-q", label_visibility="collapsed",
                          placeholder=t("matrix.search_placeholder"))
    mps = sorted(data["marketplace"].unique()) if not data.empty else []
    mp_sel = f2.multiselect("MP", mps, default=[], key="matrix-mp",
                            placeholder=t("matrix.all_mp"),
                            label_visibility="collapsed")
    only_stale = f3.checkbox(t("matrix.only_stale"), key="matrix-stale")
    try:
        work_scope = f4.segmented_control(
            "работа", ["all", "done", "todo", "pains"], default="all",
            format_func=lambda k: {"all": t("work.all"),
                                   "done": t("work.in_progress"),
                                   "todo": t("work.untouched"),
                                   "pains": t("work.with_pains")}[k],
            selection_mode="single", label_visibility="collapsed",
            key="matrix-work")
    except AttributeError:
        work_scope = f4.radio(
            "работа", ["all", "done", "todo", "pains"], horizontal=True,
            format_func=lambda k: {"all": t("work.all"),
                                   "done": t("work.in_progress"),
                                   "todo": t("work.untouched"),
                                   "pains": t("work.with_pains")}[k],
            label_visibility="collapsed", key="matrix-work")
    work_scope = work_scope or "all"
    try:
        view_mode = f5.segmented_control(
            "Вид", ["cards", "table"], default="cards",
            format_func=lambda k: t("list.cards") if k == "cards" else t("list.table"),
            selection_mode="single", label_visibility="collapsed", key="matrix-mode")
    except AttributeError:
        view_mode = f4.radio(
            "Вид", ["cards", "table"], horizontal=True,
            format_func=lambda k: t("list.cards") if k == "cards" else t("list.table"),
            label_visibility="collapsed", key="matrix-mode")
    view_mode = view_mode or "cards"

    view = data
    if query.strip():
        q = query.strip().upper()
        view = view[
            view["asin"].str.upper().str.contains(q, na=False)
            | view["sku_group"].str.upper().str.contains(q, na=False)
        ]
    if mp_sel:
        view = view[view["marketplace"].isin(mp_sel)]
    if only_stale:
        cutoff = pd.Timestamp.utcnow() - pd.Timedelta(hours=48)
        lf = pd.to_datetime(view["last_fetch"], utc=True, errors="coerce")
        view = view[lf.isna() | (lf < cutoff) | (view["last_ok"] == False)]  # noqa: E712

    if work_scope == "done":
        view = view[view.apply(
            lambda r: has_work(WORK.get((r["asin"], r["marketplace"]))), axis=1)]
    elif work_scope == "todo":
        view = view[~view.apply(
            lambda r: has_work(WORK.get((r["asin"], r["marketplace"]))), axis=1)]
    elif work_scope == "pains":
        def _has_pain(r) -> bool:
            return any(
                (r.get(k) is not None and not pd.isna(r.get(k)) and r.get(k))
                for k in ("red", "amber", "yellow"))
        view = view[view.apply(_has_pain, axis=1)]

    _in_work = sum(1 for _, r in view.iterrows()
                   if has_work(WORK.get((r["asin"], r["marketplace"]))))
    st.caption(f"{t('matrix.found')} {len(view)} · "
               f"{t('work.in_work_count')} {_in_work} · "
               f"{t('work.untouched_count')} {len(view) - _in_work}")

    pages = max(1, (len(view) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(st.session_state.get("matrix-page", 1), pages)
    chunk = view.iloc[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]

    # ---- табличный режим (с выбором строк)
    if view_mode == "table":
        tv = chunk.copy()
        tv["main_image"] = tv["main_image"].map(img_or_stub)
        tv["status"] = tv.apply(
            lambda x: "✓" if x["last_ok"] is True
            else ("✗" if x["last_ok"] is False else "—"), axis=1)
        tv["got"] = pd.to_datetime(
            tv["last_fetch"], errors="coerce").dt.strftime("%d.%m %H:%M").fillna("—")
        tv["pains"] = tv.apply(
            lambda x: int(0 if pd.isna(x["red"]) else x["red"])
            + int(0 if pd.isna(x["amber"]) else x["amber"])
            + int(0 if pd.isna(x["yellow"]) else x["yellow"]), axis=1)
        # ASIN показываем ССЫЛКОЙ, но ключи для сбора и удаления берём
        # не из таблицы, а по индексу строки (ниже): подменив здесь ASIN
        # на URL и оставив прежний способ, мы бы получили кнопку
        # «Удалить выбранные», которая молча не удаляет ничего
        tv["asin"] = tv.apply(
            lambda x: product_url(x["asin"], x["marketplace"]), axis=1)
        tv.insert(0, "pick", False)

        edited = st.data_editor(
            tv[["pick", "main_image", "sku_group", "asin", "marketplace",
                "status", "got", "pains", "title"]],
            column_config={
                "pick": st.column_config.CheckboxColumn("", width="small"),
                "main_image": st.column_config.ImageColumn(
                    t("metric.photos"), width="small"),
                "sku_group": st.column_config.TextColumn("SKU", width="small",
                                                         disabled=True),
                "asin": st.column_config.LinkColumn(
                    "ASIN", display_text=ASIN_IN_URL, width="small",
                    disabled=True),
                "marketplace": st.column_config.TextColumn("MP", width="small",
                                                           disabled=True),
                "status": st.column_config.TextColumn("OK", width="small",
                                                      disabled=True),
                "got": st.column_config.TextColumn(t("matrix.collected_at"),
                                                   disabled=True),
                "pains": st.column_config.NumberColumn(t("card.pain"),
                                                       width="small",
                                                       disabled=True),
                "title": st.column_config.TextColumn(t("card.title"),
                                                     width="large",
                                                     disabled=True),
            },
            hide_index=True, width="stretch", height=460,
            key=f"matrix-table-{page}",
        )
        # выбор — по ИНДЕКСУ строки, а не по её содержимому: в колонке
        # asin теперь ссылка, и пара (asin, marketplace) из таблицы
        # больше не совпадает с парой из базы
        sel_idx = list(edited[edited["pick"]].index)
        sel_rows = chunk.loc[sel_idx]
        sel_keys = [(r["asin"], r["marketplace"]) for _, r in sel_rows.iterrows()]

        ta1, ta2, _ = st.columns([2, 2, 3])
        if ta1.button(f"{t('matrix.collect_selected')} ({len(sel_keys)})",
                      type="primary", disabled=not sel_keys, key="tbl-collect"):
            collect_rows(sel_rows)
        if ta2.button(f"{t('matrix.delete_selected')} ({len(sel_keys)})",
                      disabled=not sel_keys, key="tbl-delete"):
            try:
                conn = get_conn()
                with conn, conn.cursor() as cur:
                    for a, m in sel_keys:
                        cur.execute(
                            "DELETE FROM product_matrix "
                            "WHERE asin = %s AND marketplace = %s", (a, m))
                conn.close()
                cache.after_matrix_change()
                load_matrix.clear()
                st.success(f"{t('matrix.deleted')} {len(sel_keys)}")
                st.rerun()
            except Exception as e:
                st.error(f"{e}")

        st.caption(t("list.sort_hint"))
        st.stop()

    # ---- строки-карточки
    selected_keys: list[tuple[str, str]] = []
    for _, r in chunk.iterrows():
        asin, mp = r["asin"], r["marketplace"]
        row_key = f"{asin}-{mp}"

        has_red = (0 if pd.isna(r["red"]) else int(r["red"])) > 0
        fetch_failed = (r["last_ok"] is not None) and (not r["last_ok"])
        edge = ERR_TEXT if (has_red or fetch_failed) else OK_TEXT

        title = "" if pd.isna(r["title"]) else str(r["title"])[:90]
        title_line = f"«{title}…»" if title else t("matrix.no_data_yet")
        if pd.notna(r["last_fetch"]):
            fetch_str = pd.to_datetime(r["last_fetch"]).strftime("%d.%m %H:%M")
            fetch_line = (f"{t('matrix.collected_at')} {fetch_str}" if r["last_ok"]
                          else f"{t('matrix.fetch_error_at')} {fetch_str}")
        else:
            fetch_line = t("matrix.not_collected")
        def _n(v) -> int:
            return 0 if pd.isna(v) else int(v)

        pains = " ".join(filter(None, [
            f"🔴{_n(r['red'])}" if _n(r["red"]) else "",
            f"🟠{_n(r['amber'])}" if _n(r["amber"]) else "",
            f"🟡{_n(r['yellow'])}" if _n(r["yellow"]) else "",
        ]))

        badge_bg, badge_fg, badge_txt = (
            (OK_BG, OK_TEXT, "✓ ok") if r["last_ok"]
            else ((ERR_BG, ERR_TEXT, "✗ err") if fetch_failed else ("#F0EFEA", MUTED, "—"))
        )

        sku_val = r["sku_group"]
        sku_part = f"{sku_val} · " if sku_val and sku_val != asin else ""
        name_html = (
            f"{sku_part}"
            f"<span style='font-family:{MONO};font-weight:400;color:{MUTED};"
            f"font-size:12px;'>"
            f"{asin_link(asin, mp)} · {mp}</span>"
        )
        badges = work_badges(WORK.get((asin, mp)))
        # заглушка вместо пустоты: без неё строки без фото сдвигались
        # влево и список выглядел рваным
        thumb_html = (
            f"<img src='{img_or_stub(r.get('main_image'))}' "
            f"style='width:40px;height:40px;object-fit:contain;"
            f"background:#fff;border:1px solid {BORDER};border-radius:8px;"
            f"margin-right:12px;vertical-align:middle;'>"
        )
        c_check, c_card, c_badge, c_btn = st.columns([0.4, 7, 1, 1.3])
        if c_check.checkbox("", key=f"sel-{row_key}", label_visibility="collapsed"):
            selected_keys.append((asin, mp))
        pains_part = f" · {pains}" if pains else ""
        badges_html = (f'<div style="margin-top:3px;">{badges}</div>'
                       if badges else "")
        c_card.markdown(
            f'<div style="background:{CARD};border:1px solid {BORDER};'
            f'border-left:3px solid {edge};border-radius:0 10px 10px 0;'
            f'padding:10px 14px;">'
            f'<div style="display:flex;align-items:center;">{thumb_html}<div>'
            f'<div style="font-size:14px;font-weight:600;color:{INK};">'
            f"{name_html}</div>"
            f'<div style="font-size:12px;color:{MUTED};">'
            f"{title_line} · {fetch_line}{pains_part}</div>"
            f"{badges_html}</div></div></div>",
            unsafe_allow_html=True,
        )
        c_badge.markdown(
            f"<div style='margin-top:12px;'><span style='font-family:{MONO};font-size:11px;"
            f"color:{badge_fg};background:{badge_bg};border-radius:6px;padding:3px 8px;'>"
            f"{badge_txt}</span></div>",
            unsafe_allow_html=True,
        )
        if c_btn.button(t("matrix.collect"), key=f"collect-{row_key}"):
            collect_rows(chunk[(chunk["asin"] == asin) & (chunk["marketplace"] == mp)])

    # ---- пагинация
    if pages > 1:
        pc1, pc2, pc3 = st.columns([1, 2, 1])
        if pc1.button(t("matrix.prev"), disabled=page <= 1):
            st.session_state["matrix-page"] = page - 1
            st.rerun()
        pc2.markdown(
            f"<div style='text-align:center;color:{MUTED};'>{t('matrix.page')} {page} / {pages}</div>",
            unsafe_allow_html=True,
        )
        if pc3.button(t("matrix.next"), disabled=page >= pages):
            st.session_state["matrix-page"] = page + 1
            st.rerun()

    # ---- групповые действия
    a1, a2, _ = st.columns([2, 2, 3])
    if a1.button(f"{t('matrix.collect_selected')} ({len(selected_keys)})",
                 type="primary", disabled=not selected_keys):
        mask = chunk.apply(
            lambda r: (r["asin"], r["marketplace"]) in selected_keys, axis=1)
        collect_rows(chunk[mask])
    if a2.button(f"{t('matrix.delete_selected')} ({len(selected_keys)})",
                 disabled=not selected_keys):
        try:
            conn = get_conn()
            with conn, conn.cursor() as cur:
                for asin, mp in selected_keys:
                    cur.execute(
                        "DELETE FROM product_matrix WHERE asin = %s AND marketplace = %s",
                        (asin, mp),
                    )
            conn.close()
            cache.after_matrix_change()
            load_matrix.clear()
            st.success(f"{t('matrix.deleted')} {len(selected_keys)}")
            st.rerun()
        except Exception as e:
            st.error(f"Не удалилось: {e}")

# ================================================================ расписание
st.divider()


@st.cache_data(ttl=60)
def load_schedule() -> dict:
    try:
        df_s = pd.read_sql("SELECT * FROM collection_schedule WHERE id = 1", get_engine())
        if not df_s.empty:
            return dict(df_s.iloc[0])
    except Exception:
        pass
    return {"enabled": True, "run_time": "13:00",
            "days": "mon,tue,wed,thu,fri,sat,sun"}


DAY_LABELS = {d: t(f"matrix.day_{d}")
              for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]}

sched = load_schedule()
sched_days = [d for d in str(sched.get("days", "")).split(",") if d in DAY_LABELS]
status_chip = (
    f"<span style='background:{OK_BG};color:{OK_TEXT};border-radius:999px;"
    f"padding:4px 12px;font-size:12px;font-weight:600;'>{t('matrix.schedule_enabled')}</span>"
    if sched.get("enabled", True) else
    f"<span style='background:#F0EFEA;color:{MUTED};border-radius:999px;"
    f"padding:4px 12px;font-size:12px;font-weight:600;'>{t('matrix.schedule_disabled')}</span>"
)

st.markdown(
    f'<div style="background:{CARD};border:1px solid {BORDER};'
    f'border-radius:10px;padding:16px 20px;margin-bottom:10px;">'
    f"{eyebrow(t('matrix.schedule_header'))}"
    f'<div style="display:flex;gap:16px;align-items:center;margin-top:10px;">'
    f"{status_chip}"
    f'<span style="font-family:{MONO};font-size:14px;color:{INK};">'
    f"{sched.get('run_time', '13:00')} Kyiv</span>"
    f'<span style="font-size:13px;color:{INK};">'
    f"{' '.join(DAY_LABELS[d] for d in sched_days)}</span></div></div>",
    unsafe_allow_html=True,
)

with st.expander(t("matrix.schedule_edit")):
    sc1, sc2, sc3 = st.columns([1, 2, 3])
    enabled = sc1.toggle(t("matrix.schedule_enabled_label"), value=bool(sched.get("enabled", True)))
    run_time = sc2.time_input(
        t("matrix.schedule_time"),
        value=pd.to_datetime(str(sched.get("run_time", "13:00"))).time(),
    )
    days_sel = sc3.multiselect(
        t("matrix.schedule_days"), list(DAY_LABELS.keys()), default=sched_days,
        format_func=lambda d: DAY_LABELS[d],
    )
    if st.button(t("matrix.schedule_save"), type="primary"):
        try:
            conn = get_conn()
            with conn, conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO collection_schedule
                        (id, enabled, run_time, days, updated_at)
                    VALUES (1, %s, %s, %s, now())
                    ON CONFLICT (id) DO UPDATE SET
                        enabled = EXCLUDED.enabled,
                        run_time = EXCLUDED.run_time,
                        days = EXCLUDED.days,
                        updated_at = now()
                    """,
                    (enabled, run_time.strftime("%H:%M"), ",".join(days_sel)),
                )
            conn.close()
            load_schedule.clear()
            st.success(t("matrix.schedule_saved"))
            st.rerun()
        except Exception as e:
            st.error(f"Не сохранилось: {e}")
