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
from services.db import get_conn, add_matrix_rows, parse_asin_lines, cfg
from components.ui import inject_fonts, eyebrow

inject_fonts()

INK = "#1A1815"
MUTED = "#8A8578"
BORDER = "#E7E4DD"
CARD = "#FFFFFF"
OK_BG = "#DCEEE0"
OK_TEXT = "#2F6B3A"
ERR_BG = "#FCEBEB"
ERR_TEXT = "#A32D2D"
MONO = '"JetBrains Mono","SFMono-Regular",Consolas,monospace'

PAGE_SIZE = 25
MP_COUNTRY = {
    "com": "us", "de": "de", "es": "es", "fr": "fr",
    "it": "it", "co.uk": "gb", "nl": "nl", "se": "se", "pl": "pl",
}
# язык страницы: без него ScrapingDog иногда отдаёт EN-версию amazon.es,
# и длина тайтла считается по чужому языку
MP_LANGUAGE = {
    "es": "es", "de": "de", "fr": "fr", "it": "it",
    "com": "en", "co.uk": "en", "nl": "nl", "se": "sv", "pl": "pl",
}

st.header(t("nav.matrix"))
st.caption(t("matrix.caption"))

# ================================================================ ввод пачкой
st.markdown(
    t("matrix.format_hint") + "  \n"
    "`SKU, ASIN, маркетплейс[, конкурент]` · `SKU, ссылка` · голый `ASIN` · ссылка amazon"
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
            st.cache_data.clear()
        except Exception as e:
            st.error(f"БД недоступна: {e}")

st.divider()

# ================================================================ данные
@st.cache_data(ttl=120)
def load_matrix() -> pd.DataFrame:
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT m.sku_group, m.asin, m.marketplace, m.is_competitor, m.added_at,
                   s.fetched_at AS last_fetch, s.ok AS last_ok, s.title,
                   s.main_image,
                   d.red, d.amber, d.yellow
            FROM product_matrix m
            LEFT JOIN LATERAL (
                SELECT fetched_at, ok, title, raw->>'main_image' AS main_image
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
                    ORDER BY rule_id, created_at DESC
                ) latest
            ) d ON TRUE
            ORDER BY m.sku_group, m.marketplace, m.asin
            """,
            conn,
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


# ================================================================ пайплайн
def collect_rows(rows: pd.DataFrame) -> None:
    import requests

    key = cfg("SCRAPINGDOG_API_KEY")
    if not key:
        st.error("SCRAPINGDOG_API_KEY не найден в секретах.")
        return

    try:
        conn = get_conn()
        cur = conn.cursor()
        with st.status(t("matrix.collecting"), expanded=True) as status:
            for _, row in rows.iterrows():
                asin, mp = row["asin"], row["marketplace"]
                sku = row["sku_group"]
                is_comp = bool(row["is_competitor"])

                st.write(f"Fetch {asin} ({mp})...")
                resp = requests.get(
                    "https://api.scrapingdog.com/amazon/product",
                    params={"api_key": key, "domain": mp, "asin": asin,
                            "country": MP_COUNTRY.get(mp, "us"),
                            "language": MP_LANGUAGE.get(mp, "en")},
                    timeout=60,
                )
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
                has_aplus = bool(data.get("aplus"))

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
        st.cache_data.clear()
        st.success(t("matrix.collected"))
        st.rerun()
    except Exception as e:
        st.error(f"Ошибка сбора: {e}")


# ================================================================ список
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

    f1, f2, f3, f4 = st.columns([3, 2, 2, 1.6])
    query = f1.text_input("Поиск", key="matrix-q", label_visibility="collapsed",
                          placeholder=t("matrix.search_placeholder"))
    mps = sorted(data["marketplace"].unique()) if not data.empty else []
    mp_sel = f2.multiselect("MP", mps, default=[], key="matrix-mp",
                            placeholder=t("matrix.all_mp"),
                            label_visibility="collapsed")
    only_stale = f3.checkbox(t("matrix.only_stale"), key="matrix-stale")
    try:
        view_mode = f4.segmented_control(
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

    st.caption(f"{t('matrix.found')} {len(view)}")

    pages = max(1, (len(view) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(st.session_state.get("matrix-page", 1), pages)
    chunk = view.iloc[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]

    # ---- табличный режим
    if view_mode == "table":
        tv = chunk.copy()
        tv["статус"] = tv.apply(
            lambda x: "✓ ok" if x["last_ok"] is True
            else ("✗ err" if x["last_ok"] is False else "—"), axis=1)
        tv["последний сбор"] = pd.to_datetime(
            tv["last_fetch"], errors="coerce").dt.strftime("%d.%m %H:%M").fillna("—")
        tv["боли"] = tv.apply(
            lambda x: int(0 if pd.isna(x["red"]) else x["red"])
            + int(0 if pd.isna(x["amber"]) else x["amber"])
            + int(0 if pd.isna(x["yellow"]) else x["yellow"]), axis=1)
        tv["ссылка"] = tv.apply(
            lambda x: f"https://www.amazon.{x['marketplace']}/dp/{x['asin']}", axis=1)
        st.dataframe(
            tv[["main_image", "sku_group", "asin", "marketplace", "статус",
                "последний сбор", "боли", "title", "ссылка"]],
            column_config={
                "main_image": st.column_config.ImageColumn("Фото", width="small"),
                "sku_group": st.column_config.TextColumn("SKU", width="small"),
                "asin": st.column_config.TextColumn("ASIN", width="small"),
                "marketplace": st.column_config.TextColumn("MP", width="small"),
                "статус": st.column_config.TextColumn("Статус", width="small"),
                "боли": st.column_config.NumberColumn("Болей", width="small"),
                "title": st.column_config.TextColumn("Название", width="large"),
                "ссылка": st.column_config.LinkColumn("Листинг", display_text="открыть"),
            },
            hide_index=True, use_container_width=True, height=460,
        )
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
        sku_part = (f"{sku_val} ·" if sku_val and sku_val != asin else "")
        img = None if pd.isna(r.get("main_image")) else r.get("main_image")
        thumb_html = (
            f"<img src='{img}' style='width:40px;height:40px;object-fit:contain;"
            f"background:#fff;border:1px solid {BORDER};border-radius:8px;"
            f"margin-right:12px;vertical-align:middle;'>" if img else ""
        )
        c_check, c_card, c_badge, c_btn = st.columns([0.4, 7, 1, 1.3])
        if c_check.checkbox("", key=f"sel-{row_key}", label_visibility="collapsed"):
            selected_keys.append((asin, mp))
        c_card.markdown(
            f"""
            <div style="background:{CARD};border:1px solid {BORDER};
                        border-left:3px solid {edge};border-radius:0 10px 10px 0;
                        padding:10px 14px;">
              <div style="display:flex;align-items:center;">
              {thumb_html}
              <div>
              <div style="font-size:14px;font-weight:600;color:{INK};">
                {sku_part}
                <span style='font-family:{MONO};font-weight:400;color:{MUTED};font-size:12px;'>
                  <a href="https://www.amazon.{mp}/dp/{asin}" target="_blank"
                     style="color:{MUTED};text-decoration:none;
                            border-bottom:1px dotted {MUTED};">{asin}</a> · {mp}</span>
              </div>
              <div style="font-size:12px;color:{MUTED};">{title_line} · {fetch_line} {('· ' + pains) if pains else ''}</div>
              </div>
              </div>
            </div>
            """,
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
            st.cache_data.clear()
            st.success(f"{t('matrix.deleted')} {len(selected_keys)}")
            st.rerun()
        except Exception as e:
            st.error(f"Не удалилось: {e}")

# ================================================================ расписание
st.divider()


@st.cache_data(ttl=60)
def load_schedule() -> dict:
    try:
        conn = get_conn()
        df_s = pd.read_sql("SELECT * FROM collection_schedule WHERE id = 1", conn)
        conn.close()
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
    f"""
    <div style="background:{CARD};border:1px solid {BORDER};border-radius:10px;
                padding:16px 20px;margin-bottom:10px;">
      {eyebrow(t('matrix.schedule_header'))}
      <div style="display:flex;gap:16px;align-items:center;margin-top:10px;">
        {status_chip}
        <span style='font-family:{MONO};font-size:14px;color:{INK};'>
          {sched.get('run_time', '13:00')} Kyiv</span>
        <span style="font-size:13px;color:{INK};">
          {' '.join(DAY_LABELS[d] for d in sched_days)}</span>
      </div>
    </div>
    """,
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
            st.cache_data.clear()
            st.success(t("matrix.schedule_saved"))
            st.rerun()
        except Exception as e:
            st.error(f"Не сохранилось: {e}")
