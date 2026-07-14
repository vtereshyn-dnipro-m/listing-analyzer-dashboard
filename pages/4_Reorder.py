# pages/4_Reorder.py — Автозаказ: рекомендации по пополнению
import pandas as pd
import streamlit as st
import plotly.express as px

from db.connection import get_connection

st.markdown("""
<style>
[data-testid="stMetric"] {
    border: 1px solid rgba(128, 128, 128, 0.35);
    border-radius: 12px;
    padding: 14px 18px;
}
[data-testid="stMetricValue"] { font-size: 2rem; }
</style>
""", unsafe_allow_html=True)

st.title("Автозаказ")
st.caption("Что и сколько заказать: скорость продаж × остаток × срок поставки. "
           "Система считает точку заказа сама.")

@st.cache_data(ttl=300)
def load_reorder():
    conn = get_connection()
    df = pd.read_sql("""
        SELECT sku, product_name, current_stock, daily_velocity,
               days_of_cover, reorder_point, suggested_qty, urgency
        FROM kabinet_data.reorder_recommendations
        WHERE calc_date = (SELECT MAX(calc_date) FROM kabinet_data.reorder_recommendations)
    """, conn)
    conn.close()
    return df

df = load_reorder()

if df.empty:
    st.info("Рекомендации ещё не рассчитаны. Запусти ячейку автозаказа в пайплайне.")
    st.stop()

URG_ORDER = {"critical": 0, "warning": 1, "ok": 2}
URG_ICON = {"critical": "🔴", "warning": "🟡", "ok": "🟢"}
URG_LABEL = {"critical": "Заказать срочно", "warning": "Пора заказывать", "ok": "В норме"}

df["urg_rank"] = df["urgency"].map(URG_ORDER)

# ---------- KPI ----------
c1, c2, c3, c4 = st.columns(4)
crit = df[df["urgency"] == "critical"]
warn = df[df["urgency"] == "warning"]
c1.metric("🔴 Заказать срочно", len(crit),
          help="Кончатся раньше, чем приедет поставка")
c2.metric("🟡 Пора заказывать", len(warn))
c3.metric("Всего к заказу, шт",
          int(df.loc[df["urgency"] != "ok", "suggested_qty"].sum()))
c4.metric("SKU под контролем", len(df))

st.divider()

# ---------- срочные — крупно ----------
if not crit.empty:
    st.markdown("#### 🔴 Требуют заказа в первую очередь")
    top = crit.sort_values("days_of_cover").head(6)
    cols = st.columns(min(len(top), 3))
    for i, (_, r) in enumerate(top.iterrows()):
        with cols[i % 3]:
            st.metric(
                label=f"{str(r['sku'])[:16]}",
                value=f"заказать {int(r['suggested_qty'])}",
                delta=f"хватит на {r['days_of_cover']:.0f} дн",
                delta_color="inverse",
                help=f"{r['product_name'][:70]} · продаётся {r['daily_velocity']:.1f}/день",
            )
    st.divider()

# ---------- график: скорость vs запас ----------
left, right = st.columns([3, 2])
with left:
    st.markdown("##### Топ по срочности")
    plot = df[df["urgency"] != "ok"].sort_values("days_of_cover").head(15)
    if not plot.empty:
        plot["label"] = plot["product_name"].str.slice(0, 35) + "…"
        fig = px.bar(plot.sort_values("days_of_cover", ascending=False),
                     x="days_of_cover", y="label", orientation="h",
                     color="urgency",
                     color_discrete_map={"critical": "#e24b4a", "warning": "#f2b134"},
                     labels={"days_of_cover": "дней хватит", "label": ""},
                     text="suggested_qty")
        fig.update_traces(texttemplate="заказать %{text}", textposition="outside")
        fig.update_layout(height=480, showlegend=False,
                          margin=dict(l=10, r=60, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.markdown("##### Распределение")
    dist = df.groupby("urgency").size().reset_index(name="count")
    dist["label"] = dist["urgency"].map(URG_LABEL)
    fig = px.pie(dist, names="label", values="count", hole=0.55,
                 color="urgency",
                 color_discrete_map={"critical": "#e24b4a",
                                     "warning": "#f2b134", "ok": "#3aa"})
    fig.update_layout(height=260, showlegend=True,
                      legend=dict(orientation="h", y=-0.1),
                      margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---------- таблица + выбор для заказа ----------
st.markdown("##### Все рекомендации")
show = df.sort_values(["urg_rank", "days_of_cover"]).copy()
show["urgency_disp"] = show["urgency"].map(lambda u: f"{URG_ICON.get(u,'')} {URG_LABEL.get(u,u)}")

st.dataframe(
    show[["urgency_disp", "sku", "product_name", "current_stock",
          "daily_velocity", "days_of_cover", "suggested_qty"]],
    use_container_width=True, height=440, hide_index=True,
    column_config={
        "urgency_disp": st.column_config.TextColumn("Срочность", width="small"),
        "sku": st.column_config.TextColumn("SKU", width="small"),
        "product_name": st.column_config.TextColumn("Товар", width="large"),
        "current_stock": st.column_config.NumberColumn("Остаток", width="small"),
        "daily_velocity": st.column_config.NumberColumn("Продаж/день", format="%.1f", width="small"),
        "days_of_cover": st.column_config.NumberColumn("Хватит, дней", format="%.0f", width="small"),
        "suggested_qty": st.column_config.NumberColumn("Заказать, шт", width="small"),
    },
)

st.download_button(
    "⬇️ Скачать список заказа (CSV)",
    df[df["urgency"] != "ok"][["sku", "product_name", "current_stock",
                               "daily_velocity", "days_of_cover", "suggested_qty", "urgency"]]
      .to_csv(index=False).encode("utf-8-sig"),
    file_name="reorder_list.csv",
    mime="text/csv",
)

st.caption("Параметры расчёта (срок поставки, страховой запас, горизонт) пока фиксированы. "
           "Дальше вынесем в настройки — сможешь крутить сам. Товары в пути учтём, "
           "когда подключим раздел «Товары в пути».")
