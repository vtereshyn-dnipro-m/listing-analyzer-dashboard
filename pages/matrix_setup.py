# -*- coding: utf-8 -*-
"""
pages/matrix_setup.py — Настройка: Матрица товаров. v2 (на 100+ ASIN).

- Ввод пачкой (SKU, ASIN, маркетплейс[, конкурент] / голый ASIN / ссылка).
- Вкладки Наши / Конкуренты, поиск, фильтр по маркетплейсу, пагинация.
- Выбор строк -> «Собрать сейчас» (точечный прогон) / «Удалить из матрицы».
- Блок «Расписание сбора» — настройка в collection_schedule (исполнитель —
  Databricks Job, подключается отдельно и читает это расписание).

DDL (один раз, через ноутбук или SQL Editor):
    CREATE TABLE IF NOT EXISTS listing_data.collection_schedule (
        id SMALLINT PRIMARY KEY DEFAULT 1,
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        run_time TEXT NOT NULL DEFAULT '13:00',
        days TEXT NOT NULL DEFAULT 'mon,tue,wed,thu,fri,sat,sun',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    INSERT INTO listing_data.collection_schedule (id) VALUES (1)
        ON CONFLICT (id) DO NOTHING;
"""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from i18n import t
from services.db import get_conn, add_matrix_rows, parse_asin_lines, cfg

PAGE_SIZE = 25

st.header(t("nav.matrix"))

# ================================================================ ввод пачкой
st.markdown(
    "Формат — построчно, любой из вариантов вперемешку:  \n"
    "`SKU, ASIN, маркетплейс[, конкурент]` · голый `ASIN` · ссылка amazon"
)

text = st.text_area(
    "ASIN пачкой",
    height=140,
    placeholder=(
        "GS-98, B0DKFVFT29, es\n"
        "GS-98, https://www.amazon.es/dp/B0DKFVFT29\n"
        "https://www.amazon.de/dp/B0XXXXXXXX\n"
        "GS-98, B0XXXXXXXX, es, конкурент"
    ),
    label_visibility="collapsed",
)

if st.button("Добавить в матрицу", type="primary", disabled=not text.strip()):
    rows = parse_asin_lines(text)
    if not rows:
        st.warning("Не нашёл ни одного ASIN — проверь формат")
    else:
        try:
            conn = get_conn()
            n = add_matrix_rows(conn, rows)
            conn.close()
            st.success(f"Добавлено/обновлено: {n}")
            st.cache_data.clear()
        except Exception as e:
            st.error(f"БД недоступна: {e}")

st.divider()

# ================================================================ загрузка матрицы
@st.cache_data(ttl=120)
def load_matrix() -> pd.DataFrame:
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT m.sku_group, m.asin, m.marketplace, m.is_competitor, m.added_at,
                   s.fetched_at AS last_fetch, s.ok AS last_ok
            FROM product_matrix m
            LEFT JOIN LATERAL (
                SELECT fetched_at, ok FROM listing_snapshots s
                WHERE s.asin = m.asin AND s.marketplace = m.marketplace
                ORDER BY s.fetched_at DESC LIMIT 1
            ) s ON TRUE
            ORDER BY m.sku_group, m.marketplace, m.asin
            """,
            conn,
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


df = load_matrix()

if df.empty:
    st.caption(t("common.no_data"))
else:
    ours_df = df[~df.is_competitor].copy()
    comp_df = df[df.is_competitor].copy()

    tab_ours, tab_comp = st.tabs(
        [f"Наши · {len(ours_df)}", f"Конкуренты · {len(comp_df)}"]
    )

    def render_table(data: pd.DataFrame, tab_key: str) -> None:
        if data.empty:
            st.caption(t("common.no_data"))
            return

        # ---- поиск и фильтры
        f1, f2, f3 = st.columns([3, 2, 2])
        query = f1.text_input(
            "Поиск", key=f"q-{tab_key}", label_visibility="collapsed",
            placeholder="Поиск: ASIN или SKU...",
        )
        mps = sorted(data["marketplace"].unique())
        mp_sel = f2.multiselect(
            "Маркетплейс", mps, default=[], key=f"mp-{tab_key}",
            placeholder="Все маркетплейсы",
        )
        only_stale = f3.checkbox(
            "Только без свежих данных", key=f"stale-{tab_key}",
            help="Нет успешного снапшота за последние 48 часов",
        )

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

        st.caption(f"Найдено: {len(view)}")

        # ---- пагинация
        pages = max(1, (len(view) + PAGE_SIZE - 1) // PAGE_SIZE)
        page_key = f"page-{tab_key}"
        page = st.session_state.get(page_key, 1)
        page = min(page, pages)
        start = (page - 1) * PAGE_SIZE
        chunk = view.iloc[start:start + PAGE_SIZE].copy()

        # ---- таблица с выбором
        chunk["last_fetch_str"] = pd.to_datetime(
            chunk["last_fetch"], errors="coerce"
        ).dt.strftime("%d.%m %H:%M").fillna("—")
        chunk["status"] = chunk.apply(
            lambda r: "✓" if r["last_ok"] else ("—" if pd.isna(r["last_ok"]) else "✗"),
            axis=1,
        )

        edited = st.data_editor(
            chunk[["sku_group", "asin", "marketplace", "status", "last_fetch_str"]]
            .assign(выбрать=False)[["выбрать", "sku_group", "asin", "marketplace",
                                    "status", "last_fetch_str"]],
            column_config={
                "выбрать": st.column_config.CheckboxColumn("", width="small"),
                "sku_group": st.column_config.TextColumn("SKU", disabled=True),
                "asin": st.column_config.TextColumn("ASIN", disabled=True),
                "marketplace": st.column_config.TextColumn("MP", disabled=True, width="small"),
                "status": st.column_config.TextColumn("OK", disabled=True, width="small"),
                "last_fetch_str": st.column_config.TextColumn("Последний сбор", disabled=True),
            },
            hide_index=True,
            use_container_width=True,
            key=f"editor-{tab_key}-{page}",
        )
        selected = edited[edited["выбрать"]]

        # ---- пагинация: контролы
        if pages > 1:
            pc1, pc2, pc3 = st.columns([1, 2, 1])
            if pc1.button("← Назад", key=f"prev-{tab_key}", disabled=page <= 1):
                st.session_state[page_key] = page - 1
                st.rerun()
            pc2.markdown(
                f"<div style='text-align:center;color:#8A8578;'>стр. {page} / {pages}</div>",
                unsafe_allow_html=True,
            )
            if pc3.button("Вперёд →", key=f"next-{tab_key}", disabled=page >= pages):
                st.session_state[page_key] = page + 1
                st.rerun()

        # ---- действия над выбранными
        a1, a2, _ = st.columns([2, 2, 3])
        collect_btn = a1.button(
            f"↻ Собрать сейчас ({len(selected)})",
            key=f"collect-{tab_key}", type="primary", disabled=selected.empty,
        )
        delete_btn = a2.button(
            f"Удалить из матрицы ({len(selected)})",
            key=f"delete-{tab_key}", disabled=selected.empty,
        )

        if delete_btn and not selected.empty:
            try:
                conn = get_conn()
                with conn, conn.cursor() as cur:
                    for _, r in selected.iterrows():
                        cur.execute(
                            "DELETE FROM product_matrix WHERE asin = %s AND marketplace = %s",
                            (r["asin"], r["marketplace"]),
                        )
                conn.close()
                st.cache_data.clear()
                st.success(f"Удалено: {len(selected)}")
                st.rerun()
            except Exception as e:
                st.error(f"Не удалилось: {e}")

        if collect_btn and not selected.empty:
            run_pipeline(selected)

    # ---------------------------------------------------------- пайплайн
    def run_pipeline(selected: pd.DataFrame) -> None:
        import requests

        SCRAPINGDOG_KEY = cfg("SCRAPINGDOG_API_KEY")
        if not SCRAPINGDOG_KEY:
            st.error("SCRAPINGDOG_API_KEY не найден в секретах.")
            return

        MP_COUNTRY = {
            "com": "us", "de": "de", "es": "es", "fr": "fr",
            "it": "it", "co.uk": "gb", "nl": "nl", "se": "se", "pl": "pl",
        }

        try:
            conn = get_conn()
            cur = conn.cursor()
            with st.status("Собираю данные...", expanded=True) as status:
                for _, row in selected.iterrows():
                    asin, mp, sku = row["asin"], row["marketplace"], row["sku_group"]
                    cur.execute(
                        "SELECT is_competitor FROM product_matrix "
                        "WHERE asin = %s AND marketplace = %s",
                        (asin, mp),
                    )
                    res = cur.fetchone()
                    is_competitor = bool(res[0]) if res else False

                    st.write(f"Fetch {asin} ({mp})...")
                    resp = requests.get(
                        "https://api.scrapingdog.com/amazon/product",
                        params={
                            "api_key": SCRAPINGDOG_KEY,
                            "domain": mp,
                            "asin": asin,
                            "country": MP_COUNTRY.get(mp, "us"),
                        },
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
                    highlights_len = len(" ".join(bullets))
                    cur.execute(
                        """
                        INSERT INTO listing_analysis
                            (asin, marketplace, title_len, title_over, highlights_len)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (asin, mp, title_len, max(0, title_len - 75), highlights_len),
                    )

                    if ok and not is_competitor:
                        if not in_stock:
                            cur.execute(
                                """
                                INSERT INTO diagnosis
                                    (sku_group, asin, marketplace, severity,
                                     pain, cause, action, rule_id)
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
                                INSERT INTO diagnosis
                                    (sku_group, asin, marketplace, severity,
                                     pain, cause, action, rule_id)
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
                                INSERT INTO diagnosis
                                    (sku_group, asin, marketplace, severity,
                                     pain, cause, action, rule_id)
                                VALUES (%s, %s, %s, 'yellow', %s, %s, %s, 'low_reviews')
                                """,
                                (sku, asin, mp,
                                 f"{review_count} отзывов при пороге 50+",
                                 "листинг молодой / без Vine",
                                 "запустить Vine (30 юнитов)"),
                            )

                    st.write(f"   → {asin}: ok={ok}, тайтл {title_len} симв.")

                conn.commit()
                status.update(label="Готово", state="complete")

            cur.close()
            conn.close()
            st.cache_data.clear()
            st.success("Сбор завершён. Открой Диагноз или Каталог.")
        except Exception as e:
            st.error(f"Ошибка сбора: {e}")

    with tab_ours:
        render_table(ours_df, "ours")
    with tab_comp:
        render_table(comp_df, "comp")

# ================================================================ расписание
st.divider()
st.markdown("### Расписание автосбора")


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


DAY_LABELS = {"mon": "Пн", "tue": "Вт", "wed": "Ср", "thu": "Чт",
              "fri": "Пт", "sat": "Сб", "sun": "Вс"}

sched = load_schedule()
sc1, sc2, sc3 = st.columns([1, 2, 3])
enabled = sc1.toggle("Включено", value=bool(sched.get("enabled", True)))
run_time = sc2.time_input(
    "Время (Kyiv)",
    value=pd.to_datetime(str(sched.get("run_time", "13:00"))).time(),
)
days_current = str(sched.get("days", "")).split(",")
days_sel = sc3.multiselect(
    "Дни", list(DAY_LABELS.keys()),
    default=[d for d in days_current if d in DAY_LABELS],
    format_func=lambda d: DAY_LABELS[d],
)

if st.button("Сохранить расписание"):
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO collection_schedule (id, enabled, run_time, days, updated_at)
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
        st.success("Расписание сохранено.")
    except Exception as e:
        st.error(f"Не сохранилось: {e}")

st.caption(
    "Автосбор выполняется фоновым заданием по этому расписанию. "
    "Точечный сбор — кнопкой «↻ Собрать сейчас» в таблице выше."
)
