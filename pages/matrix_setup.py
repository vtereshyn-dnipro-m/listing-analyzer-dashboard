# -*- coding: utf-8 -*-
"""
pages/matrix_setup.py — Настройка: Матрица товаров.
Единственная страница с записью в БД (product_matrix) — разрешённые
INSERT/UPDATE, никакого DDL. Ввод пачкой в любом формате:
    GS-98, B0DKFVFT29, es
    GS-98, B0XXXXXXXX, es, конкурент
    B0YYYYYYYY
    https://www.amazon.es/dp/B0ZZZZZZZZ
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from i18n import t
from services.db import get_conn, add_matrix_rows, parse_asin_lines

st.header(t("nav.matrix"))

st.markdown(
    "Формат — построчно, любой из вариантов вперемешку:  \n"
    "`SKU, ASIN, маркетплейс[, конкурент]` · голый `ASIN` · ссылка amazon"
)

text = st.text_area(
    "ASIN пачкой",
    height=180,
    placeholder="GS-98, B0DKFVFT29, es\nGS-98, B0XXXXXXXX, es, конкурент\nB0YYYYYYYY",
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

# ---- текущая матрица
try:
    conn = get_conn()
    df = pd.read_sql(
        "SELECT sku_group, asin, marketplace, is_competitor, added_at "
        "FROM product_matrix ORDER BY sku_group, is_competitor, marketplace, asin",
        conn,
    )
    conn.close()
except Exception:
    df = pd.DataFrame()

if df.empty:
    st.caption(t("common.no_data"))
else:
    df["кто"] = df["is_competitor"].map(
        {True: t("common.competitor"), False: t("common.our")}
    )
    st.dataframe(
        df[["sku_group", "asin", "marketplace", "кто", "added_at"]],
        use_container_width=True,
        hide_index=True,
    )
    ours = int((~df.is_competitor).sum())
    comps = int(df.is_competitor.sum())
    st.caption(f"Всего: {len(df)} · наших {ours} · конкурентов {comps}")

st.divider()
st.markdown("### Прогнать пайплайн вручную")
st.caption(
    "Временно, пока ноутбук в Databricks не может импортировать services/* "
    "(репозиторий не склонирован в Repos). Гоняет batch_fetch → analyze → "
    "diagnose прямо отсюда для одного sku_group."
)

pipeline_sku = st.text_input(
    "sku_group для прогона", placeholder="Например: GS-98", key="pipeline_sku"
)

if st.button("Прогнать batch_fetch → analyze → diagnose", type="secondary"):
    if not pipeline_sku.strip():
        st.warning("Укажи sku_group.")
    else:
        import requests
        import json
        from services.db import cfg

        SCRAPINGDOG_KEY = cfg("SCRAPINGDOG_API_KEY")
        if not SCRAPINGDOG_KEY:
            st.error("SCRAPINGDOG_API_KEY не найден в секретах.")
        else:
            MP_DOMAIN = {
                "com": "amazon.com", "de": "amazon.de", "es": "amazon.es",
                "fr": "amazon.fr", "it": "amazon.it", "co.uk": "amazon.co.uk",
            }
            MP_COUNTRY = {
                "com": "us", "de": "de", "es": "es",
                "fr": "fr", "it": "it", "co.uk": "gb",
            }

            try:
                conn = get_conn()
                cur = conn.cursor()
                cur.execute(
                    "SELECT asin, marketplace, is_competitor FROM product_matrix "
                    "WHERE sku_group = %s",
                    (pipeline_sku.strip(),),
                )
                rows = cur.fetchall()

                if not rows:
                    st.warning(f"В матрице нет строк для {pipeline_sku}. Сначала добавь ASIN выше.")
                else:
                    with st.status("Прогоняю пайплайн...", expanded=True) as status:
                        for asin, mp, is_competitor in rows:
                            st.write(f"Fetch {asin} ({mp})...")
                            params = {
                                "api_key": SCRAPINGDOG_KEY,
                                "domain": MP_DOMAIN.get(mp, "amazon.com"),
                                "asin": asin,
                                "country": MP_COUNTRY.get(mp, "us"),
                            }
                            resp = requests.get(
                                "https://api.scrapingdog.com/amazon/product",
                                params=params, timeout=30,
                            )
                            ok = resp.status_code == 200
                            data = resp.json() if ok else {}

                            availability = (
                                data.get("availability_status")
                                or data.get("availability") or ""
                            ).lower()
                            in_stock = (
                                "unavailable" not in availability
                                and "out of stock" not in availability
                            )
                            title = data.get("title") or ""
                            bullets = (
                                data.get("feature_bullets")
                                or data.get("about_this_item") or []
                            )
                            review_count = (
                                data.get("total_reviews")
                                or data.get("review_count")
                            )

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
                                (asin, mp, title_len,
                                 max(0, title_len - 75), highlights_len),
                            )

                            if not is_competitor:
                                if not in_stock:
                                    cur.execute(
                                        """
                                        INSERT INTO diagnosis
                                            (sku_group, asin, marketplace, severity,
                                             pain, cause, action, rule_id)
                                        VALUES (%s, %s, %s, 'red', %s, %s, %s, 'out_of_stock')
                                        """,
                                        (pipeline_sku, asin, mp,
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
                                        (pipeline_sku, asin, mp,
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
                                        (pipeline_sku, asin, mp,
                                         f"{review_count} отзывов при пороге 50+",
                                         "листинг молодой / без Vine",
                                         "запустить Vine (30 юнитов)"),
                                    )

                            st.write(f"   → {asin} готово (ok={ok}, in_stock={in_stock})")

                        conn.commit()
                        status.update(label="Готово", state="complete")

                    st.success(f"Пайплайн для {pipeline_sku} прогнан. Открой Диагноз или Каталог 75/125.")

                cur.close()
                conn.close()
            except Exception as e:
                st.error(f"Ошибка пайплайна: {e}")
