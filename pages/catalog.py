# -*- coding: utf-8 -*-
"""
pages/catalog.py — Каталог: паспорт каждого товара.

Одна карточка = один товар со всеми метриками разом: тайтл, фото, видео,
A+, отзывы, рейтинг, цена, BSR, сток, продавец. Здоровье считает код.
Показываются ВСЕ товары (включая здоровых и конкурентов) — в отличие от
Диагноза, который показывает только проблемные.
"""
from __future__ import annotations

import json
import re

import pandas as pd
import streamlit as st

from config import TITLE_LIMIT as _TL_DEFAULT
from i18n import t, plural
from services import collector
from services.bsr import parse_bsr
from services.buybox import buy_box_of, OWN, AMAZON, OTHER, NONE
from services.cells import cell_text
from services.db import get_conn, get_engine, missing_columns, safe_read
from services.settings import get_int, get_float
from services.economics import (
    econ_map, fmt_money, fmt_conversion, money_at_risk, num, risk_coef,
    unknown_rules, RULE_RISK,
)
from services.worklog import worklog_map, work_badges
from services.attributes import (
    attrs_map, missing_critical, fill_state, node_short,
)
from services.search import (
    search_map, fmt_int, fmt_pct, ctr_state,
)
from services.issues import (
    issues_map, asin_index, family_map, extract_deadline, action_hint,
    MONITORED, cause_label, code_label, fmt_issue_date,
)
from services.marketplaces import (product_url, asin_link,
                                   img_or_stub, ASIN_IN_URL)
from components.ui import inject_fonts, eyebrow, limit_ruler_html

inject_fonts()
st.title(t("nav.catalog"))

INK = "#1A1815"
MUTED = "#8A8578"
BORDER = "#E7E4DD"
CARD = "#FFFFFF"
ACCENT = "#E8590C"
OK_BG = "#DCEEE0"
OK_TEXT = "#2F6B3A"
WARN_BG = "#FAEEDA"
WARN_TEXT = "#854F0B"
ERR_BG = "#FCEBEB"
ERR_TEXT = "#A32D2D"
MONO = "var(--ls-mono)"   # переменная из inject_fonts(): без кавычек в атрибутах

TITLE_LIMIT = get_int("limit.title", _TL_DEFAULT)
MIN_REVIEWS = get_int("threshold.min_reviews", 50)
CRIT_REVIEWS = 10
RATING_RED = get_float("threshold.rating_red", 4.3)
RATING_GREEN = get_float("threshold.rating_green", 4.4)
MIN_IMAGES = get_int("threshold.min_images", 7)
PAGE_SIZE = 20


@st.cache_data(ttl=300)
def load_catalog() -> tuple[pd.DataFrame, str | None]:
    """Каталог и ПРИЧИНА, если прочитать не удалось.

    Пустой ответ здесь означает «товаров нет», и страница советует
    собрать их в Матрице. При сбое чтения тот же совет становится
    указанием завести заново почти тысячу товаров, которые в базе
    лежат — поэтому причина возвращается отдельно.
    """
    # Колонки сборщика (Buy Box, BSR) читаются, только если миграция
    # 2026-09-18 уже применена. Код в main приезжает на Cloud раньше,
    # чем .sql в Databricks, и жёсткий SELECT ронял Каталог целиком:
    # «column buy_box_owner does not exist». Без колонок страница
    # работает по raw и говорит, какой миграции не хватает.
    cols = ["buy_box_owner", "buy_box_seller", "bsr_rank", "bsr_category"]
    missing = missing_columns("listing_snapshots", cols)
    have = [c for c in cols if not missing or c not in missing]
    extra = "".join(f", s.{c}" for c in have)
    extra_inner = "".join(f", {c}" for c in have)
    df, err = safe_read(
            f"""
            SELECT m.sku_group, m.asin, m.marketplace, m.is_competitor,
                   m.status, m.collection_tier,
                   COALESCE(m.weekly_day,
                            MOD(ABS(HASHTEXT(m.asin || m.marketplace)), 7)) AS weekly_day,
                   s.fetched_at, s.ok, s.title, s.in_stock, s.review_count,
                   s.is_amazon_choice, s.raw{extra},
                   ll.has_aplus
            FROM product_matrix m
            LEFT JOIN listing_latest ll
                   ON ll.asin = m.asin AND ll.marketplace = m.marketplace
            LEFT JOIN LATERAL (
                SELECT fetched_at, ok, title, in_stock, review_count,
                       is_amazon_choice, raw{extra_inner}
                FROM listing_snapshots s
                WHERE s.asin = m.asin AND s.marketplace = m.marketplace
                  AND s.ok = TRUE
                ORDER BY s.fetched_at DESC LIMIT 1
            ) s ON TRUE
            ORDER BY m.is_competitor, m.sku_group, m.asin
            """)
    if err is None and not df.empty:
        for c in cols:
            if c not in df.columns:
                df[c] = None
    df.attrs["missing_columns"] = missing or []
    return df, err


def _raw(v) -> dict:
    try:
        return v if isinstance(v, dict) else json.loads(v or "{}")
    except Exception:
        return {}


def metrics(row: pd.Series) -> dict:
    """Все метрики товара из последнего снапшота.

    ВАЖНО: у товара, который ещё ни разу не собирался, LEFT JOIN LATERAL
    в load_catalog() отдаёт NULL по всем полям снапшота -> в pandas это
    NaN (float). `row.get("x") or ""` NaN не ловит, потому что bool(NaN)
    равен True — поэтому все "сырые" поля явно проверяются через pd.isna().
    """
    d = _raw(row.get("raw"))
    info = d.get("product_information") or {}

    collected = pd.notna(row.get("fetched_at"))

    imgs = d.get("images") or d.get("images_of_specified_asin") or []
    ids = set()
    for u in imgs:
        if isinstance(u, str):
            ids.add(u.rsplit("/I/", 1)[-1].split(".")[0])

    # BSR — из колонки, которую пишет сборщик; у снапшотов до 18.09
    # колонки нет, и для них тот же парсер (services/bsr.py) читает raw.
    # Один парсер на сборщик и экран: раньше здесь была своя регулярка,
    # которая брала ПЕРВЫЙ подходящий ключ и на ES/IT ловила соседей.
    bsr = None
    _rank = row.get("bsr_rank")
    if pd.notna(_rank):
        bsr = (int(_rank), cell_text(row, "bsr_category"))
    else:
        _r, _c = parse_bsr(info)
        if _r:
            bsr = (_r, _c or "")

    # Buy Box — так же: колонка, иначе из raw той же функцией
    _owner = cell_text(row, "buy_box_owner")
    if _owner:
        buy_box = (_owner, cell_text(row, "buy_box_seller") or None)
    else:
        buy_box = buy_box_of(d) if collected else (None, None)

    main_img = d.get("main_image") or (imgs[0] if imgs else "")

    price = d.get("price") or ""
    try:
        rating = float(str(d.get("average_rating") or "").replace(",", "."))
    except ValueError:
        rating = None

    raw_title = row.get("title")
    title = "" if pd.isna(raw_title) else str(raw_title)

    raw_reviews = row.get("review_count")
    reviews = None if pd.isna(raw_reviews) else int(raw_reviews)

    raw_stock = row.get("in_stock")
    in_stock = False if pd.isna(raw_stock) else bool(raw_stock)

    # у несобранного товара поле придёт NaN, а NaN в Python истинный —
    # bool(NaN) дал бы «бейдж есть» там, где данных нет вообще
    raw_choice = row.get("is_amazon_choice")
    amazon_choice = False if pd.isna(raw_choice) else bool(raw_choice)

    # A+ берём СТАБИЛИЗИРОВАННЫЙ по трём снимкам (listing_latest.has_aplus),
    # а не из последнего снапшота: ScrapingDog врёт примерно на 15% запросов,
    # а на .it по отдельным товарам на половине, и карточка показывала
    # «A+ нет» там, где A+ есть. Сырое поле остаётся запасным — для товара,
    # которого во вью ещё нет (первый сбор).
    stable_aplus = row.get("has_aplus")
    aplus = (bool(d.get("aplus")) if pd.isna(stable_aplus)
             else bool(stable_aplus))

    return {
        "title": title,
        "title_len": len(title),
        "images": len(ids),
        "video": int(d.get("number_of_videos") or 0),
        "aplus": aplus,
        "reviews": reviews,
        "rating": rating,
        "price": price,
        "bsr": bsr,
        "in_stock": in_stock,
        "seller": d.get("sold_by") or "",
        "buy_box": buy_box,
        "econ": {},
        "main_img": main_img,
        "coupon": bool(d.get("is_coupon_exists")),
        "amazon_choice": amazon_choice,
        "collected": collected,
    }


def health(mx: dict, is_comp: bool) -> tuple[str, str, str]:
    """Итоговое здоровье товара: (уровень, цвет, подпись)."""
    if is_comp:
        return "comp", MUTED, t("common.competitor")
    if not mx["collected"]:
        return "gray", MUTED, t("catalog.h_not_collected")
    if not mx["in_stock"]:
        return "red", ERR_TEXT, t("catalog.h_nostock")
    problems = 0
    if mx["title_len"] > TITLE_LIMIT:
        problems += 1
    if mx["images"] and mx["images"] < MIN_IMAGES:
        problems += 1
    if not mx["video"]:
        problems += 1
    if not mx["aplus"]:
        problems += 1
    if mx["reviews"] is not None and mx["reviews"] < MIN_REVIEWS:
        problems += 1
    if mx["rating"] is not None and mx["rating"] < RATING_RED:
        problems += 1
    if problems >= 3:
        return "amber", ACCENT, f"{problems} {t('catalog.h_problems')}"
    if problems:
        return "yellow", WARN_TEXT, f"{problems} {t('catalog.h_notes')}"
    return "ok", OK_TEXT, t("catalog.h_ok")


def chip(label: str, value: str, state: str) -> str:
    bg, fg = {
        "ok": (OK_BG, OK_TEXT),
        "warn": (WARN_BG, WARN_TEXT),
        "err": (ERR_BG, ERR_TEXT),
        "neutral": ("#F1EFE8", MUTED),
    }[state]
    return (
        f"<span style='display:inline-block;background:{bg};color:{fg};"
        f"border-radius:8px;padding:4px 10px;margin:0 6px 6px 0;font-size:12px;'>"
        f"<span style='opacity:.7;'>{label}</span> "
        f"<b style='font-family:{MONO};'>{value}</b></span>"
    )


st.caption(t("catalog.caption"))

ECON = econ_map()
WORK = worklog_map()
SEARCH = search_map()
ATTRS = attrs_map()
ISSUES = issues_map()
AIDX = asin_index(ISSUES)
FAMILY = family_map(ISSUES)
df, catalog_error = load_catalog()
if catalog_error:
    # сбой чтения — это НЕ «товаров нет»: совет «соберите товары
    # в Матрице» отправил бы заводить заново то, что уже в базе
    st.error("⚠ " + t("common.read_failed", e=catalog_error))
    st.stop()
if df.empty:
    st.caption(t("common.no_data"))
    st.stop()
if df.attrs.get("missing_columns"):
    # схема отстала от кода: Buy Box и BSR идут из raw, а не из колонок
    st.warning("⚠ " + t("catalog.schema_behind",
                        cols=", ".join(df.attrs["missing_columns"]),
                        file="migrations/2026-09-18_snapshots_buybox_bsr.sql"))


def age_days(ts) -> int | None:
    """Полных дней с момента снапшота; None — снапшота нет."""
    if pd.isna(ts):
        return None
    return int((pd.Timestamp.now("UTC") - pd.to_datetime(ts, utc=True)).days)


# Как job собирает пары — проверено по его ноутбуку 17.09 («Listing
# Suite Auto Collector», 13:00 Kyiv). Ярус `daily` — пары с заказами
# за 30 дней, собираются каждый прогон; `weekly` — остальное, день
# недели закреплён хэшем asin||marketplace (0 = понедельник). Свёрнутые
# (`status = 'wound_down'`) не собираются вовсе — это не отставание,
# а решение, и подписывать их надо словом, не возрастом. Пара, ещё не
# собранная ни разу, ждёт свой день: до семи дней по замыслу, а не
# «не собиралась».
WOUND = "wound_down"
STALE_AFTER = {"daily": 2, "weekly": 7}     # дней, после которых пара ОТСТАЁТ


def pair_status(row) -> str:
    return cell_text(row, "status") or "active"


def pair_tier(row) -> str:
    return "daily" if cell_text(row, "collection_tier") == "daily" else "weekly"


def pair_day(row) -> int | None:
    v = row.get("weekly_day")
    return None if pd.isna(v) else int(v)


def is_stale(row, age: int | None) -> bool:
    """Отстаёт от СВОЕГО графика: ежедневная — больше двух дней, недельная —
    больше семи. Свёрнутая не отстаёт никогда."""
    if age is None or pair_status(row) == WOUND:
        return False
    return age > STALE_AFTER[pair_tier(row)]


def cadence_text(row) -> str:
    """«обновляется ежедневно» / «по четвергам»."""
    if pair_tier(row) == "daily":
        return t("catalog.tier_daily")
    d = pair_day(row)
    return t(f"day.on.{d}") if d is not None else t("catalog.tier_weekly_unknown")


def collect_text(row) -> str:
    """Подпись сбора на карточке: дата, возраст, график — или статус словом."""
    age = age_days(row.get("fetched_at"))
    if pair_status(row) == WOUND:
        when = ("" if age is None else " · " + t("catalog.last_collect",
                date=pd.to_datetime(row["fetched_at"]).strftime("%d.%m")))
        return f'<span style="color:{MUTED};">{t("catalog.wound_down")}{when}</span>'
    if age is None:
        if pair_tier(row) == "daily":
            return t("catalog.first_collect_daily")
        d = pair_day(row)
        return (t("catalog.first_collect", day=t(f"day.in.{d}")) if d is not None
                else t("catalog.first_collect_soon"))
    when = pd.to_datetime(row["fetched_at"]).strftime("%d.%m %H:%M")
    ago = t("catalog.age_today") if age == 0 else plural("catalog.age_ago", age)
    col = WARN_TEXT if is_stale(row, age) else MUTED
    return f'{when} · <span style="color:{col};">{ago}</span> · {cadence_text(row)}'


def market_freshness(cat: pd.DataFrame) -> list[dict]:
    """Возраст данных по рынку — по ПРАВИЛАМ сбора, а не по календарю.

    Считаются не «старше недели», а ОТСТАЮЩИЕ от своего графика:
    ежедневная пара старше двух дней, недельная старше семи. Свёрнутые
    исключены из отставания и названы отдельно — они не отстают, их
    не собирают. Не собранные ни разу — «ждут первого сбора», а не
    «не собирались»: у новой пары слот наступает в течение недели.
    """
    out = []
    for mp, g in cat.groupby("marketplace", sort=True):
        wound = g[g.apply(pair_status, axis=1) == WOUND]
        live = g.drop(wound.index)
        ages = live["fetched_at"].map(age_days)
        have = ages.dropna()
        stale_rows = [r for _, r in live.iterrows() if is_stale(r, age_days(r.get("fetched_at")))]
        out.append({
            "mp": str(mp), "pairs": int(len(g)),
            "wound": int(len(wound)),
            "waiting": int(ages.isna().sum()),
            "stale": len(stale_rows),
            "median": int(have.median()) if len(have) else None,
            "oldest": (max(age_days(r.get("fetched_at")) for r in stale_rows)
                       if stale_rows else None),
            "last": (pd.to_datetime(live["fetched_at"], utc=True).max()
                     if len(have) else None),
        })
    return out


def freshness_html(rows: list[dict]) -> str:
    """Чипы по рынкам: одна строка HTML (правило 1)."""
    chips = []
    for r in rows:
        col = WARN_TEXT if r["stale"] else OK_TEXT
        med = (t("catalog.age_median", n=r["median"]) if r["median"] is not None
               else t("catalog.age_waiting_all"))
        parts = [med]
        if r["stale"]:
            parts.append(t("catalog.age_stale", n=r["stale"], days=r["oldest"]))
        if r["waiting"]:
            parts.append(t("catalog.age_waiting", n=r["waiting"]))
        tail = (f' · <span style="color:{MUTED};">{t("catalog.age_wound", n=r["wound"])}</span>'
                if r["wound"] else "")
        chips.append(
            f'<span style="display:inline-block;margin:0 8px 6px 0;padding:4px 10px;'
            f'border:1px solid {BORDER};border-radius:8px;font-size:12px;">'
            f'<b style="font-family:{MONO};">{r["mp"].upper()}</b> · {r["pairs"]} · '
            f'<span style="color:{col};">{" · ".join(parts)}</span>{tail}</span>')
    return "<div>" + "".join(chips) + "</div>"


# Возраст данных — до фильтров и списка, потому что относится ко всему
# экрану: цифры четырёхдневной давности выглядят как сегодняшние, и
# без этой строки читатель считает их сегодняшними.
FRESH = market_freshness(df)
st.markdown(freshness_html(FRESH), unsafe_allow_html=True)
st.caption(t("catalog.age_note"))


# ---- сбор по выбранным рынкам
# Кнопка запускает тот же job Databricks, что идёт в 13:00, но только
# по отмеченным рынкам. Три правила — см. services/collector.py:
# не поверх идущего, свёрнутые не считаются, ход — по базе.
@st.cache_data(ttl=20, show_spinner=False)
def _active_run():
    return collector.active_run()


def collect_plan_text(plan: pd.DataFrame) -> str:
    """«ES, DE · 566 товаров» и разбивка по рынкам, если их больше одного."""
    by = {str(r["marketplace"]): int(r["pairs"]) for _, r in plan.iterrows()}
    total = sum(by.values())
    head = f'{", ".join(m.upper() for m in by)} · {plural("catalog.products_n", total)}'
    if len(by) > 1:
        head += f' <span style="color:{MUTED};">({", ".join(f"{m.upper()} {n}" for m, n in by.items())})</span>'
    return f'<div style="font-size:14px;white-space:nowrap;">{head}</div>'


def render_collect(all_markets: list[str]) -> tuple:
    """Полоса действий. Возвращает два места под кнопки выгрузки:
    они стоят в этом же ряду, но что выгружать — известно только после
    фильтров ниже, поэтому заполняются позже (`st.empty`)."""
    key = "cat-collect"
    st.markdown(
        f'<style>.st-key-{key} div[data-testid="stHorizontalBlock"]'
        '{gap:10px !important;align-items:center;flex-wrap:wrap;}'
        f'.st-key-{key} div[data-testid="stColumn"]'
        '{flex:0 0 auto !important;width:auto !important;min-width:0 !important;}'
        f'.st-key-{key} div[data-testid="stColumn"]:last-child'
        '{flex:1 1 auto !important;}'
        f'.st-key-{key} .stButton button,.st-key-{key} .stDownloadButton button'
        '{white-space:nowrap !important;width:auto !important;}'
        f'.st-key-{key} label{{white-space:nowrap !important;}}</style>',
        unsafe_allow_html=True)

    run = st.session_state.get("collect-run")
    if run is None:
        # сбор мог начаться не отсюда — утренний прогон тоже «идёт»
        found, err = _active_run()
        if found:
            run = dict(found, markets=all_markets, external=True)
            st.session_state["collect-run"] = run
    no_client = collector.client() is None

    with st.container(key=key):
        # ряд галочек без подписи читался как список кодов — непонятно,
        # зачем он; заголовок говорит, что это действие и что выбирать
        st.markdown(eyebrow(t("catalog.collect_title")), unsafe_allow_html=True)
        # ряд: галочки · «Собрать» · что уйдёт · CSV · Excel — выгрузка
        # рядом со сбором, а не под фильтрами: это два действия над
        # каталогом, и искать их в разных местах не нужно
        cols = st.columns([1] * len(all_markets) + [4, 4, 1, 1], gap="small",
                          vertical_alignment="center")
        picked = [mp for i, mp in enumerate(all_markets)
                  if cols[i].checkbox(mp.upper(), key=f"collect-mp-{mp}")]
        plan, perr = collector.planned(picked)
        n_plan = int(plan["pairs"].sum()) if not plan.empty else 0
        export_slots = (cols[-2].empty(), cols[-1].empty())
        cols = cols[:-2]
        if cols[-2].button(t("catalog.collect_btn"), key="collect-go", type="primary",
                           disabled=not picked or not n_plan or run is not None or no_client,
                           help=t("catalog.collect_help")):
            started, serr = collector.start(picked)
            if started:
                st.session_state["collect-run"] = dict(started, planned=n_plan)
                _active_run.clear()
                st.rerun()
            st.session_state["collect-error"] = serr
        # что уйдёт в сбор — видно ДО нажатия и не зависит от кнопки:
        # «ES, DE · 566 товаров» — это число запросов, а не «выбрано 2».
        # Свёрнутые не в счёт: job их не собирает (planned считает так же).
        if no_client:
            cols[-1].caption(t("catalog.collect_no_client"))
        elif perr:
            cols[-1].caption("⚠ " + t("common.read_failed", e=perr))
        elif not picked:
            cols[-1].caption(t("catalog.collect_pick"))
        elif not n_plan:
            cols[-1].caption(t("catalog.collect_nothing"))
        else:
            cols[-1].markdown(collect_plan_text(plan), unsafe_allow_html=True)

    err = st.session_state.pop("collect-error", None)
    if err == "already-running":
        st.warning(t("catalog.collect_busy"))
    elif err and err != "no-client":
        st.error("⚠ " + t("catalog.collect_failed", e=err))

    render_collect_outcome()
    if run is not None:
        render_collect_progress()
    return export_slots


@st.fragment(run_every="10s" if st.session_state.get("collect-run") else None)
def render_collect_progress() -> None:
    """Ход сбора: состояние run'а и сколько снапшотов уже в базе.

    Фрагмент перерисовывает только себя раз в десять секунд, пока
    run идёт; страница целиком не дёргается. Число «собрано» — из
    базы, поэтому честно только при коммите по паре в ноутбуке;
    пока он коммитит одной транзакцией, здесь будет «0 из N» до
    самого финала — и об этом сказано словами, а не полоской.
    """
    run = st.session_state.get("collect-run")
    if not run:
        return
    state, err = collector.run_state(run["run_id"])
    if state:
        run.update({k: v for k, v in state.items() if v is not None})
    markets = run.get("markets") or []
    got, _ = collector.collected_since(run.get("started_at"), markets) \
        if run.get("started_at") else (0, None)
    planned_n = run.get("planned")
    since = (pd.Timestamp(run["started_at"]).tz_convert("Europe/Kyiv").strftime("%H:%M")
             if run.get("started_at") else "—")
    live = run.get("state") in ("PENDING", "RUNNING", "TERMINATING", "QUEUED", "BLOCKED")

    if live:
        head = t("catalog.collect_running", since=since,
                 mps=", ".join(m.upper() for m in markets))
        if planned_n:
            st.progress(min(1.0, got / planned_n),
                        text=f'{head} · {t("catalog.collect_got", got=got, n=planned_n)}')
            if got == 0:
                st.caption(t("catalog.collect_zero_note"))
        else:
            st.info(f'{head} · {t("catalog.collect_got_only", got=got)}')
        return

    # Завершился. Итог кладётся в session_state и рисуется страницей
    # после ПОЛНОГО rerun: фрагмент перерисовывает только себя, а
    # кнопка выше уже отрисована неактивной — без rerun она осталась бы
    # такой, пока человек не тронет экран.
    exit_value = run.get("exit") or ""
    st.session_state["collect-outcome"] = {
        "got": got, "exit": exit_value, "err": err,
        "result": run.get("result") or run.get("state"),
    }
    st.session_state.pop("collect-run", None)
    _active_run.clear()
    load_catalog.clear()
    st.rerun(scope="app")


def render_collect_outcome() -> None:
    """Итог последнего сбора — один раз, после перерисовки."""
    o = st.session_state.pop("collect-outcome", None)
    if not o:
        return
    exit_value = str(o.get("exit") or "")
    if o.get("result") == "SUCCESS" and "skipped" not in exit_value.lower():
        st.success(f'✓ {t("catalog.collect_done", got=o["got"])}'
                   + (f" · {exit_value}" if exit_value else ""))
    elif "skipped" in exit_value.lower():
        st.warning(t("catalog.collect_skipped"))
    else:
        st.error("⚠ " + t("catalog.collect_ended_badly",
                          state=o.get("result"), e=exit_value or "—"))
    if o.get("err"):
        st.caption("⚠ " + t("catalog.collect_failed", e=o["err"]))


_export_slots = render_collect(sorted(df["marketplace"].unique()))

# ---- группы фильтра: по ИСТОЧНИКУ проблемы, а не по конкретной причине.
# Amazon — состояние пары из listing_issues; Контент и Поиск — правила
# Диагноза из diagnosis (те же rule_id, что на дашборде).
CONTENT_RULES = {"title_over_limit", "few_images", "no_video", "no_aplus",
                 "low_reviews", "few_attributes", "out_of_stock"}
SEARCH_RULES = {"low_ctr", "hard_to_scan"}
_STATE_RULE = {"blocked": "amazon_blocked", "fba_out": "amazon_fba_out",
               "warning": "amazon_warning"}


@st.cache_data(ttl=300)
def load_rule_pairs() -> dict:
    """(asin, marketplace) -> множество rule_id из diagnosis."""
    try:
        d = pd.read_sql(
            "SELECT DISTINCT asin, marketplace, rule_id FROM diagnosis "
            "WHERE resolved_at IS NULL", get_engine())
    except Exception:
        return {}
    out: dict = {}
    for _, rr in d.iterrows():
        out.setdefault((str(rr["asin"]), str(rr["marketplace"])),
                       set()).add(str(rr["rule_id"]))
    return out


@st.cache_data(ttl=300)
def load_lost_choice() -> dict:
    """(asin, marketplace) -> когда потерян бейдж Amazon's Choice.

    Отдельным запросом, а не через load_rule_pairs: там только набор
    rule_id, а здесь важна дата — «потерян» без даты не говорит, вчера
    это случилось или полгода назад.
    """
    try:
        d = pd.read_sql(
            """
            SELECT DISTINCT ON (asin, marketplace)
                   asin, marketplace, created_at
            FROM diagnosis
            WHERE rule_id = 'lost_amazon_choice'
              AND resolved_at IS NULL
            ORDER BY asin, marketplace, created_at DESC
            """, get_engine())
    except Exception:
        return {}
    return {(str(rr["asin"]), str(rr["marketplace"])): rr["created_at"]
            for _, rr in d.iterrows()}


RULE_PAIRS = load_rule_pairs()
LOST_CHOICE = load_lost_choice()


def buy_box_chip(mx: dict) -> list[str]:
    """«Buy Box: наш / Amazon / чужой · имя / нет предложения».

    Показывается всегда, когда снапшот есть: отсутствие предложения —
    состояние, а не пустота, и оно объясняет продажи не хуже цены.
    Правила Диагноза под это пока нет — см. services/buybox.py.
    """
    owner, seller = mx.get("buy_box") or (None, None)
    if not owner:
        return []
    if owner == OWN:
        return [chip(t("metric.buy_box"), t("metric.bb_own"), "ok")]
    if owner == AMAZON:
        return [chip(t("metric.buy_box"), t("metric.bb_amazon"), "warn")]
    if owner == OTHER:
        return [chip(t("metric.buy_box"),
                     f'{t("metric.bb_other")} · {str(seller or "")[:18]}', "err")]
    return [chip(t("metric.buy_box"), t("metric.bb_none"), "warn")]


def choice_chips(mx: dict, asin: str, mp: str) -> list[str]:
    """Плашки Amazon's Choice: зелёная «есть», красная «потерян».

    Отсутствие бейджа плашкой НЕ показываем: он есть у 19 товаров из всех,
    и «нет» на каждой второй карточке — это шум, а не сигнал. Значимы два
    события: бейдж есть и бейдж был, но пропал.

    Когда бейдж на месте, показываем только зелёную, даже если боль
    lost_amazon_choice ещё висит в diagnosis: боль живёт до следующего
    сбора, и «потерян» рядом с живым бейджем — прямое враньё.
    """
    if mx.get("amazon_choice"):
        return [chip(t("metric.choice"), t("metric.yes"), "ok")]
    lost = LOST_CHOICE.get((str(asin), str(mp)))
    if lost is None or pd.isna(lost):
        return []
    return [chip(t("metric.choice_lost"),
                 pd.to_datetime(lost).strftime("%d.%m.%Y"), "err")]


def _pair_state(asin: str, mp: str) -> str:
    """Состояние конкретной пары товар × рынок — не худшее по всем рынкам."""
    return (ISSUES.get((str(asin), str(mp).lower()))
            or {"state": "none"})["state"]


def _pair_rules(asin: str, mp: str) -> set:
    return RULE_PAIRS.get((str(asin), str(mp)), set())


def in_group(asin: str, mp: str, group: str) -> bool:
    if group == "amazon":
        return _pair_state(asin, mp) != "none"
    target = CONTENT_RULES if group == "content" else SEARCH_RULES
    return bool(_pair_rules(asin, mp) & target)


def group_risk(asin: str, mp: str, group: str) -> float:
    """Деньги под риском пары в рамках группы — для сортировки, как
    в Диагнозе: выручка × худший коэффициент правила группы."""
    e = ECON.get((asin, mp)) or {}
    rev = e.get("revenue_30d")
    if group == "amazon":
        s = ISSUES.get((asin, mp))
        if not s or s["state"] == "none":
            return 0.0
        fam = FAMILY.get((asin, mp))
        family_alive = (fam["blocked"] < fam["total"]) if fam else False
        return money_at_risk(_STATE_RULE[s["state"]], rev,
                             had_sales=s["had_sales"],
                             family_alive=family_alive)
    hit = _pair_rules(asin, mp) & (CONTENT_RULES if group == "content"
                                   else SEARCH_RULES)
    if not hit:
        return 0.0
    try:
        # NaN истинный: float(rev or 0) вернул бы NaN. Правило без
        # коэффициента денег не приносит, а не «примерно три процента»
        coefs = [c for c in (risk_coef(r_) for r_ in hit) if c is not None]
        return num(rev) * max(coefs) if coefs else 0.0
    except (TypeError, ValueError):
        return 0.0


_pairs_all = set(zip(df["asin"].astype(str), df["marketplace"].astype(str)))
N_GRP = {g: sum(1 for a, m in _pairs_all if in_group(a, m, g))
         for g in ("amazon", "content", "search")}

# ---- фильтры
f1, f2, f3, f4 = st.columns([1.8, 1.6, 1.4, 2.4])
_who_opts = ["all", "ours", "comp"]
_who_lbl = {"all": t("catalog.all"), "ours": t("catalog.ours"),
            "comp": t("catalog.competitors")}
who = f1.segmented_control(
    "кто", _who_opts, default="all", format_func=lambda k: _who_lbl[k],
    selection_mode="single", label_visibility="collapsed", key="cat_who") or "all"
mps = sorted(df["marketplace"].unique())
mp_sel = f2.multiselect("MP", mps, default=[], label_visibility="collapsed",
                        placeholder=t("list.all_mp"))
only_problems = f3.checkbox(t("catalog.only_problems"))

# фильтр по источнику проблемы, счётчики — по парам (asin, marketplace).
# «С проблемами» отдавал 850 из 922 — не фильтр, а почти весь каталог;
# «Не продаются» и «FBA кончился» — подвиды одного источника (Amazon).
_grp_opts = ["all", "amazon", "content", "search"]
_grp_lbl = {"all": t("issue.f_all"),
            "amazon": f'{t("issue.f_amazon")} {N_GRP["amazon"]}',
            "content": f'{t("issue.f_content")} {N_GRP["content"]}',
            "search": f'{t("issue.f_search")} {N_GRP["search"]}'}
try:
    iss_f = f4.segmented_control(
        "группа", _grp_opts, default="all",
        format_func=lambda k: _grp_lbl[k], selection_mode="single",
        label_visibility="collapsed", key="cat_group")
except AttributeError:
    iss_f = f4.radio("группа", _grp_opts, horizontal=True,
                     format_func=lambda k: _grp_lbl[k],
                     label_visibility="collapsed", key="cat_group")
iss_f = iss_f or "all"

qc, vc = st.columns([4, 1.6])
q = qc.text_input("Поиск", label_visibility="collapsed",
                  placeholder=t("catalog.search"))
try:
    mode = vc.segmented_control(
        "Вид", ["cards", "table"], default="cards",
        format_func=lambda k: t("list.cards") if k == "cards" else t("list.table"),
        selection_mode="single", label_visibility="collapsed", key="cat_mode")
except AttributeError:
    mode = vc.radio("Вид", ["cards", "table"], horizontal=True,
                    format_func=lambda k: t("list.cards") if k == "cards" else t("list.table"),
                    label_visibility="collapsed", key="cat_mode")
mode = mode or "cards"

view = df
if who == "ours":
    view = view[~view["is_competitor"]]
elif who == "comp":
    view = view[view["is_competitor"]]
if mp_sel:
    view = view[view["marketplace"].isin(mp_sel)]
if q.strip():
    ql = q.strip().lower()
    view = view[
        view["asin"].str.lower().str.contains(ql, na=False)
        | view["sku_group"].astype(str).str.lower().str.contains(ql, na=False)
        | view["title"].astype(str).str.lower().str.contains(ql, na=False)
    ]
if iss_f != "all":
    view = view[[in_group(str(a), str(m), iss_f)
                 for a, m in zip(view["asin"], view["marketplace"])]]

rows = []
for _, r in view.iterrows():
    mx = metrics(r)
    lvl, color, label = health(mx, bool(r["is_competitor"]))
    rows.append({"r": r, "mx": mx, "lvl": lvl, "color": color, "label": label})

if only_problems:
    rows = [x for x in rows if x["lvl"] in ("red", "amber", "yellow")]

if not rows:
    st.caption(t("catalog.nothing"))
    st.stop()

order = {"red": 0, "amber": 1, "yellow": 2, "ok": 3, "gray": 4, "comp": 5}
def _rev(x) -> float:
    e = ECON.get((x["r"]["asin"], x["r"]["marketplace"])) or {}
    try:
        return num(e.get("revenue_30d"))
    except (TypeError, ValueError):
        return 0.0


if iss_f == "all":
    rows.sort(key=lambda x: (order[x["lvl"]], -_rev(x),
                             -num(x["mx"]["title_len"])))
else:
    # внутри группы — по деньгам под риском, как в Диагнозе: в «Amazon»
    # это даёт красные блокировки сверху, затем fba_out, затем жёлтые
    rows.sort(key=lambda x: (
        -group_risk(str(x["r"]["asin"]), str(x["r"]["marketplace"]), iss_f),
        order[x["lvl"]], -_rev(x)))

healthy = sum(1 for x in rows if x["lvl"] == "ok")
st.markdown(
    f"<div style='font-size:14px;color:{INK};margin-bottom:12px;'>"
    f"{len(rows)} {t('catalog.products')} · <span style='color:{OK_TEXT};'>"
    f"{t('catalog.healthy')} {healthy}</span>"
    f"</div>", unsafe_allow_html=True)

# ---- экспорт
exp = pd.DataFrame([{
    "sku": x["r"]["sku_group"], "asin": x["r"]["asin"],
    "mp": x["r"]["marketplace"],
    "who": ("competitor" if x["r"]["is_competitor"] else "own"),
    "health": x["label"], "title_len": x["mx"]["title_len"],
    "photos": x["mx"]["images"], "video": x["mx"]["video"],
    "aplus": x["mx"]["aplus"], "reviews": x["mx"]["reviews"],
    "rating": x["mx"]["rating"], "price": x["mx"]["price"],
    "bsr": x["mx"]["bsr"][0] if x["mx"]["bsr"] else None,
    "bsr_cat": x["mx"]["bsr"][1] if x["mx"]["bsr"] else None,
    "buy_box": (x["mx"].get("buy_box") or (None, None))[0],
    "buy_box_seller": (x["mx"].get("buy_box") or (None, None))[1],
    "in_stock": x["mx"]["in_stock"], "name": x["mx"]["title"],
    # сбор: статус, график и возраст — ровно то, что подписано на карточке
    "status": pair_status(x["r"]), "tier": pair_tier(x["r"]),
    "weekly_day": pair_day(x["r"]),
    "fetched_at": (pd.to_datetime(x["r"]["fetched_at"]).strftime("%Y-%m-%d %H:%M")
                   if pd.notna(x["r"]["fetched_at"]) else None),
    "age_days": age_days(x["r"]["fetched_at"]),
    "revenue_30d": (ECON.get((x["r"]["asin"], x["r"]["marketplace"])) or {}
                    ).get("revenue_30d"),
    "sessions_30d": (ECON.get((x["r"]["asin"], x["r"]["marketplace"])) or {}
                     ).get("sessions_30d"),
    "shipping_template": (ECON.get((x["r"]["asin"], x["r"]["marketplace"]))
                          or {}).get("shipping_template"),
    "sqp_queries": (SEARCH.get((x["r"]["asin"], x["r"]["marketplace"])) or {}
                    ).get("queries"),
    "sqp_demand": (SEARCH.get((x["r"]["asin"], x["r"]["marketplace"])) or {}
                   ).get("demand"),
    "sqp_imp_share": (SEARCH.get((x["r"]["asin"], x["r"]["marketplace"])) or {}
                      ).get("imp_share"),
    "sqp_ctr": (SEARCH.get((x["r"]["asin"], x["r"]["marketplace"])) or {}
                ).get("ctr"),
    "category": (ATTRS.get((x["r"]["asin"], x["r"]["marketplace"])) or {}
                 ).get("browse_node_name"),
    "category_path": (ATTRS.get((x["r"]["asin"], x["r"]["marketplace"])) or {}
                      ).get("browse_path"),
    "attrs_filled": (ATTRS.get((x["r"]["asin"], x["r"]["marketplace"])) or {}
                     ).get("attrs_filled"),
    "attrs_empty": (ATTRS.get((x["r"]["asin"], x["r"]["marketplace"])) or {}
                    ).get("attrs_empty"),
} for x in rows])
# Выгружается ТО, ЧТО НА ЭКРАНЕ: `rows` уже прошли фильтры рынка,
# группы проблем, поиска и «только проблемные», и в файле ровно они —
# в подписи кнопок стоит число строк, чтобы это было видно до нажатия.
# Два формата: CSV — для скриптов и pandas, XLSX — для людей: Excel
# открывает CSV с кириллицей и разделителями по-своему на каждой машине.
def _xlsx_bytes(frame: pd.DataFrame) -> bytes:
    """XLSX с ASIN-гиперссылкой на карточку Amazon.

    Ссылка — через product_url, не шаблоном по коду рынка: у Бельгии
    витрина amazon.com.be, и шаблон дал бы несуществующий домен
    (см. services/marketplaces.py и test_marketplace_maps). В ячейке остаётся сам ASIN — по нему
    фильтруют и ищут; ссылка живёт в свойстве ячейки. В CSV ссылок нет.
    """
    import io
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        frame.to_excel(xw, index=False, sheet_name="catalog")
        ws = xw.sheets["catalog"]
        cols = list(frame.columns)
        if "asin" in cols and "mp" in cols:
            c_asin, c_mp = cols.index("asin") + 1, cols.index("mp") + 1
            for i in range(len(frame)):
                cell = ws.cell(row=i + 2, column=c_asin)
                url = product_url(cell.value, ws.cell(row=i + 2, column=c_mp).value)
                if url:
                    cell.hyperlink = url
                    cell.style = "Hyperlink"
    return buf.getvalue()


_stamp = pd.Timestamp.now(tz="Europe/Kyiv").strftime("%Y-%m-%d")
# Кнопки стоят в ряду со сбором (места отданы render_collect), но число
# в подписи — от строк ПОСЛЕ фильтров: файл «всего каталога» вместо
# отфильтрованного был бы тихой подменой. Пояснение — в подсказке.
_export_slots[0].download_button(
    f'{t("catalog.export_csv")} · {len(exp)}',
    exp.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"catalog-{_stamp}.csv", mime="text/csv",
    key="cat-export-csv", type="primary", help=t("catalog.export_note"))
_export_slots[1].download_button(
    f'{t("catalog.export_xlsx")} · {len(exp)}',
    _xlsx_bytes(exp),
    file_name=f"catalog-{_stamp}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    key="cat-export-xlsx", type="primary", help=t("catalog.export_note"))

# ---- пагинация
pages = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
page = min(st.session_state.get("cat_page", 1), pages)
chunk = rows[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]

# ---- таблица
if mode == "table":
    tv = exp.copy()
    tv["img"] = [img_or_stub(x["mx"]["main_img"]) for x in rows]
    # ASIN сам ведёт на карточку Amazon — отдельная колонка-стрелка
    # говорила то же самое и занимала место
    tv["asin"] = [product_url(x["r"]["asin"], x["r"]["marketplace"])
                  for x in rows]
    tv = tv.rename(columns={"title_len": "len", "in_stock": "stock",
                            "revenue_30d": "rev", "sessions_30d": "sess",
                            "shipping_template": "ship"})
    cols = [c for c in ["img", "sku", "asin", "mp", "who", "health", "len",
                        "photos", "video", "aplus", "reviews", "rating",
                        "price", "bsr", "bsr_cat", "stock", "rev", "sess",
                        "ship", "name"] if c in tv.columns]
    st.dataframe(
        tv[cols],
        column_config={
            "img": st.column_config.ImageColumn(t("metric.photos"),
                                                width="small"),
            "sku": st.column_config.TextColumn("SKU", width="small"),
            "asin": st.column_config.LinkColumn(
                "ASIN", display_text=ASIN_IN_URL, width="small"),
            "mp": st.column_config.TextColumn("MP", width="small"),
            "who": st.column_config.TextColumn(t("common.our"), width="small"),
            "health": st.column_config.TextColumn(t("catalog.h_ok"),
                                                  width="small"),
            "len": st.column_config.NumberColumn(t("metric.title"),
                                                 width="small"),
            "photos": st.column_config.NumberColumn(t("metric.photos"),
                                                    width="small"),
            "video": st.column_config.TextColumn(t("metric.video"),
                                                 width="small"),
            "aplus": st.column_config.TextColumn(t("metric.aplus"),
                                                 width="small"),
            "reviews": st.column_config.NumberColumn(t("metric.reviews"),
                                                     width="small"),
            "rating": st.column_config.NumberColumn(t("metric.rating"),
                                                    width="small"),
            "price": st.column_config.TextColumn(t("metric.price"),
                                                 width="small"),
            "bsr": st.column_config.NumberColumn("BSR", width="small"),
            "bsr_cat": st.column_config.TextColumn("BSR cat", width="small"),
            "stock": st.column_config.TextColumn(t("metric.stock"),
                                                 width="small"),
            "rev": st.column_config.NumberColumn(
                f"{t('metric.revenue')}, EUR", format="%.0f", width="small"),
            "sess": st.column_config.NumberColumn(t("metric.sessions"),
                                                  width="small"),
            "ship": st.column_config.TextColumn(t("metric.shipping"),
                                                width="medium"),
            "name": st.column_config.TextColumn(t("card.title"), width="large"),
        },
        hide_index=True, width="stretch", height=560,
    )
    st.caption(t("list.sort_hint"))
    st.stop()

# ---- плашка Amazon Issues
def issue_details(entries: list, group_sku: str = "") -> None:
    """Раскрытие плашки: по каждому рынку — ASIN-ссылка на листинг,
    состояние, коды, тексты Amazon. ASIN обязателен: у одного SKU на
    разных рынках он может отличаться. SKU рынка показывается, когда
    отличается от группового — чинить в Seller Central придётся по нему."""
    for m, s in entries:
        asin_link = (
            f'<a href="{product_url(s["asin"], m)}" target="_blank" '
            f'style="font-family:{MONO};color:{INK};">{s["asin"]}</a>'
        ) if s.get("asin") else ""
        if s["state"] == "blocked":
            state_txt = "🔴 " + t("issue.blocked_since",
                                  date=fmt_issue_date(s["first_seen"],
                                                      with_year=True))
        elif s["state"] == "fba_out":
            state_txt = "🟠 " + t("issue.fba_out")
        else:
            state_txt = f"🟡 {t('issue.mp_selling')}"
        head = f"<b>{str(m).upper()}</b>"
        if asin_link:
            head += f" · {asin_link}"
        head += f" — {state_txt}"
        if s["stock"] is not None:
            head += " · " + t("issue.stock_n", n=s["stock"])
        mkt_sku = s.get("sku") or ""
        if mkt_sku and mkt_sku != group_sku:
            head += f' · SKU <span class="ls-mono">{mkt_sku}</span>'
        if not s["had_sales"]:
            head += " · " + t("issue.never_sold")
        st.markdown(head, unsafe_allow_html=True)

        # состояние семейства вариантов: покупатель на странице Amazon
        # видит живые соседние варианты и может решить, что система ошиблась
        if s["state"] == "blocked":
            fam = FAMILY.get((s.get("asin", ""), m))
            if fam and fam["total"] >= 2:
                fam_txt = (t("issue.family_all_blocked")
                           if fam["blocked"] >= fam["total"]
                           else t("issue.family_partial",
                                  blocked=fam["blocked"], total=fam["total"]))
                st.markdown(
                    f'<div style="font-size:12.5px;color:{WARN_TEXT};'
                    f'margin:-4px 0 6px;">↳ {fam_txt}</div>',
                    unsafe_allow_html=True)
        for row in s["rows"]:
            line = (f"`{row['code']}` **{code_label(row['code'])}** · "
                    + t("issue.since_date",
                        date=fmt_issue_date(row["first_seen"], with_year=True)))
            if row["attributes"]:
                line += f" · {t('issue.attributes')}: {row['attributes']}"
            st.markdown(line)
            if row["message"]:
                st.caption(row["message"])

    # пояснение один раз под раскрытием — только когда у какого-то из
    # заблокированных рынков есть живые варианты: иначе «они продаются» — ложь
    def _fam(m: str, s: dict) -> dict:
        return FAMILY.get((s.get("asin", ""), m)) or {}

    if any(s["state"] == "blocked"
           and 0 < _fam(m, s).get("blocked", 0) < _fam(m, s).get("total", 0)
           for m, s in entries):
        st.caption(t("issue.family_note"))


def issue_plate(asin: str, mp: str,
                group_sku: str = "") -> tuple[str, str | None, dict | None]:
    """Плашка Amazon Issues ВНУТРЬ карточки: (html, цвет кромки, сводка).

    Состояние — только СВОЕГО рынка (заблокированный на IT не красит живой
    ES). Первая строка — состояние и причина, жирная; вторая — контекст
    серым: остаток, SKU рынка (если отличается от группового), семейство
    вариантов, дедлайн из текста Amazon и что на других рынках. Серая
    плашка на немониторимом рынке обязательна: без неё отсутствие проблем
    неотличимо от отсутствия данных."""
    own = ISSUES.get((asin, mp))
    entries = AIDX.get(asin) or []

    # «также: FR (там продаётся), IT (там снят)» — состояние каждой пары
    def _also(m: str, s: dict) -> str:
        mpu = str(m).upper()
        if s["state"] == "blocked":
            return t("issue.also_blocked", mp=mpu)
        if s["state"] == "fba_out":
            return t("issue.also_fba", mp=mpu)
        return t("issue.also_alive", mp=mpu)

    others = [(str(m).upper(), _also(m, s))
              for m, s in entries if s["state"] != "none" and m != mp]
    also = (t("issue.also_markets",
              mps=", ".join(txt for _, txt in sorted(others)))
            if others else "")

    if not own or own["state"] == "none":
        if mp not in MONITORED:
            html = (
                f'<div style="background:#F1EFE8;border-radius:8px;'
                f'padding:6px 12px;margin:6px 0 8px;font-size:12px;'
                f'color:{MUTED};">◦ {t("issue.not_monitored")}</div>'
            )
            return html, None, None
        return "", None, None

    ctx: list[str] = []
    if own["state"] == "fba_out":
        ctx.append(t("issue.fba_out_ctx"))
    # «Нет товара» скрыло более раннюю блокирующую причину — говорим о ней,
    # иначе Каталог советует пополнить сток, а листинг лежит из-за EPR
    if own.get("masked"):
        ctx.append(t("issue.masked_by",
                     cause=cause_label(own["masked"][0]),
                     date=fmt_issue_date(own["masked"][1])))
    if own["state"] == "warning":
        dl = extract_deadline(own)
        if dl:
            what, ts = dl
            part = t("issue.deadline_until", what=what,
                     date=ts.strftime("%d.%m"))
            if ts < pd.Timestamp.now(tz="UTC"):
                part += " · " + t("issue.deadline_passed")
            ctx.append(part)
    if own["stock"] is not None:
        ctx.append(t("issue.stock_n", n=own["stock"]))
    mkt_sku = own.get("sku") or ""
    if mkt_sku and mkt_sku != group_sku:
        ctx.append(f'SKU <span class="ls-mono">{mkt_sku}</span>')
    fam = FAMILY.get((asin, mp))
    if fam and fam["total"] >= 2:
        ctx.append(t("issue.family_short_all")
                   if fam["blocked"] >= fam["total"]
                   else t("issue.family_short_partial",
                          blocked=fam["blocked"], total=fam["total"]))
    if not own["had_sales"]:
        ctx.append(t("issue.never_sold"))
    if also:
        ctx.append(also)

    # цвет — по asin_state Кабинета (агрегат всех SKU этого ASIN),
    # а не по is_buyable одного SKU: FBA-SKU может быть не-buyable
    # при живом FBM того же ASIN
    if own["state"] == "blocked":
        bg, fg = ERR_BG, ERR_TEXT
        line1 = ("🔴 " + t("issue.blocked_since",
                           date=fmt_issue_date(own["first_seen"]))
                 + " · " + cause_label(own["cause"] or None))
        edge = ERR_TEXT
    elif own["state"] == "fba_out":
        bg, fg = "#FCE8DC", ACCENT
        line1 = "🟠 " + t("issue.fba_out")
        edge = ACCENT
    else:
        bg, fg = WARN_BG, WARN_TEXT
        line1 = "🟡 " + t("issue.selling_warnings", n=len(own["rows"]))
        edge = "#EF9F27"   # жёлтая кромка под жёлтую плашку;
        # оранжевая (#E8590C) теперь занята fba_out

    # третья строка — что ДЕЛАТЬ; вторая и третья не рендерятся пустыми:
    # пустая подстановка одна на строке закрывает HTML-блок (правило 1)
    act = action_hint(own)
    line2 = (f'<div style="font-size:12px;color:#57534A;margin-top:2px;">'
             f'{" · ".join(ctx)}</div>') if ctx else ""
    line3 = (f'<div style="font-size:12.5px;color:{INK};font-weight:600;'
             f'margin-top:3px;">→ {act}</div>') if act else ""
    html = (
        f'<div style="background:{bg};border-radius:8px;padding:8px 12px;'
        f'margin:6px 0 8px;font-size:13px;">'
        f'<div style="font-weight:700;color:{fg};">{line1}</div>'
        f"{line2}{line3}</div>"
    )
    return html, edge, own


# ---- карточки
for x in chunk:
    r, mx, color, label = x["r"], x["mx"], x["color"], x["label"]
    asin, mp = r["asin"], r["marketplace"]
    sku = r["sku_group"] if r["sku_group"] and r["sku_group"] != asin else ""
    head = f"{sku} · " if sku else ""
    who_lbl = t("common.competitor") if r["is_competitor"] else t("common.our")

    _ec = ECON.get((asin, mp)) or {}
    _badges = work_badges(WORK.get((asin, mp)))
    _sr = SEARCH.get((asin, mp)) or {}
    _at = ATTRS.get((asin, mp)) or {}
    _fill_st, _fill_label = fill_state(_at)
    _miss = missing_critical(_at)
    chips = "".join([
        chip(t("metric.title"), f"{mx['title_len']}/{TITLE_LIMIT}",
             "err" if mx["title_len"] > TITLE_LIMIT else "ok"),
        chip(t("metric.photos"), str(mx["images"]),
             "ok" if mx["images"] >= MIN_IMAGES else "warn"),
        chip(t("metric.video"), t("metric.yes") if mx["video"] else t("metric.no"),
             "ok" if mx["video"] else "warn"),
        chip(t("metric.aplus"), t("metric.yes") if mx["aplus"] else t("metric.no"),
             "ok" if mx["aplus"] else "warn"),
        chip(t("metric.reviews"), str(mx["reviews"] if mx["reviews"] is not None else "—"),
             "ok" if num(mx["reviews"]) >= MIN_REVIEWS
             else ("err" if num(mx["reviews"]) < CRIT_REVIEWS else "warn")),
        chip(t("metric.rating"),
             (f"{mx['rating']:.1f}".replace(".", ",") if mx["rating"] else "—"),
             "neutral" if not mx["rating"]
             else ("err" if mx["rating"] < RATING_RED
                   else ("ok" if mx["rating"] >= RATING_GREEN else "warn"))),
        chip(t("metric.price"), str(mx["price"] or "—"), "neutral"),
        chip(t("metric.bsr"), (f"#{mx['bsr'][0]} · {mx['bsr'][1][:22]}"
                     if mx["bsr"] else "—"), "neutral"),
        chip(t("metric.stock"), t("metric.in_stock") if mx["in_stock"] else t("metric.no"),
             "ok" if mx["in_stock"] else "err"),
    ] + buy_box_chip(mx) + choice_chips(mx, asin, mp) + ([
        chip(t("metric.revenue"), fmt_money(_ec.get("revenue_30d"), ""),
             "neutral"),
        chip(t("metric.sessions"), str(int(num(_ec.get("sessions_30d")))),
             "neutral"),
        chip(t("metric.conversion"), fmt_conversion(_ec.get("conversion_rate")),
             "ok" if num(_ec.get("conversion_rate")) > 0 else "neutral"),
        chip(t("metric.shipping"),
             str(_ec.get("shipping_template") or t("metric.no_template"))[:22],
             "ok" if _ec.get("shipping_template") else "warn"),
    ] if _ec else []) + ([
        chip(t("search.queries"), fmt_int(_sr.get("queries")), "neutral"),
        chip(t("search.demand"), fmt_int(_sr.get("demand")), "neutral"),
        chip(t("search.imp_share"), fmt_pct(_sr.get("imp_share")),
             "ok" if num(_sr.get("imp_share")) >= 1 else "warn"),
        chip("CTR", fmt_pct(_sr.get("ctr")),
             {"ok": "ok", "warn": "err", "none": "neutral"}[ctr_state(_sr)]),
        chip(t("search.purchases"), fmt_int(_sr.get("purchases")),
             "ok" if num(_sr.get("purchases")) > 0 else "warn"),
    ] if _sr else []) + ([
        chip(t("attr.category"), node_short(_at), "neutral"),
        chip(t("attr.filled"), _fill_label,
             {"ok": "ok", "warn": "warn", "err": "err",
              "none": "neutral"}[_fill_st]),
    ] + ([chip(t("attr.missing"), ", ".join(_miss[:3]), "warn")]
         if _miss else []) if _at else []))

    ruler = limit_ruler_html(
        mx["title_len"], TITLE_LIMIT, left_label=f"{TITLE_LIMIT}",
        right_label=(f"+{mx['title_len'] - TITLE_LIMIT} {t('ruler.cut')}"
                     if mx["title_len"] > TITLE_LIMIT
                     else f"{t('ruler.free')} {TITLE_LIMIT - mx['title_len']}"),
    ) if mx["title_len"] else ""

    fetched = collect_text(r)
    short = (mx["title"][:130] + "…") if len(mx["title"]) > 130 else mx["title"]

    thumb = (
        f'<img src="{mx["main_img"]}" style="width:92px;height:92px;'
        f'object-fit:contain;background:#fff;border:1px solid {BORDER};'
        f'border-radius:10px;">'
    ) if mx["main_img"] else ""
    head_html = eyebrow(
        f'{head}{asin_link(asin, mp)} · {mp} · {who_lbl}'
    )
    badges_html = (f'<div style="margin-top:6px;">{_badges}</div>'
                   if _badges else "")

    # Amazon Issues — только свои товары: реплика идёт из аккаунта продавца,
    # по конкурентам этих данных не бывает. Плашка внутри карточки, кромка
    # перекрашивается: blocked/warning ловятся глазом при прокрутке.
    plate_html, edge, own_issues = ("", None, None)
    if not r["is_competitor"]:
        plate_html, edge, own_issues = issue_plate(
            asin, mp, cell_text(r, "sku_group"))

    # HTML одной строкой: у карточки может не быть линейки, значков или
    # плашки, и на переносах пустые участки превращаются в блок кода markdown.
    st.markdown(
        f'<div class="ls-card" style="background:{CARD};'
        f'border:1px solid {BORDER};border-left:4px solid {edge or color};'
        f'border-radius:0 12px 12px 0;padding:14px 18px;margin-bottom:10px;'
        f'display:flex;gap:16px;">'
        f'<div style="flex:0 0 92px;">{thumb}</div>'
        f'<div style="flex:1;min-width:0;">'
        f'<div class="ls-head" style="display:flex;'
        f'justify-content:space-between;align-items:baseline;">{head_html}'
        f'<span style="font-family:{MONO};font-size:12px;color:{color};">'
        f"{label} · {fetched}</span></div>"
        f'<div style="font-size:13px;color:{INK};margin:6px 0 8px;">'
        f'{short or t("catalog.no_data_row")}</div>'
        f"{plate_html}"
        f"{ruler}"
        f'<div style="margin-top:6px;">{chips}</div>'
        f"{badges_html}</div></div>",
        unsafe_allow_html=True,
    )

    # раскрытие с деталями — под карточкой (st.expander внутрь HTML
    # не вставить), подписано ASIN'ом, чтобы не терялась связь в списке
    if own_issues:
        with st.expander(t("issue.details_title", asin=asin)):
            issue_details(AIDX.get(asin) or [], cell_text(r, "sku_group"))

if pages > 1:
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    def _page_list(cur: int, total: int) -> list:
        """Номера страниц с многоточием: 1 … 4 5 [6] 7 8 … 37"""
        if total <= 7:
            return list(range(1, total + 1))
        pages_set = {1, total, cur, cur - 1, cur + 1}
        pages_set = {p for p in pages_set if 1 <= p <= total}
        out, prev = [], 0
        for p in sorted(pages_set):
            if prev and p - prev > 1:
                out.append("…")
            out.append(p)
            prev = p
        return out

    nav = _page_list(page, pages)

    # Колонки Streamlit размазывают узкие кнопки на всю ширину контейнера
    # (широкий дашборд) — отсюда рваные зазоры. Заворачиваем блок в
    # container(key=...) и таргетируем его CSS: колонки сжимаются по
    # контенту и центрируются, кнопки одной высоты и без лишних полей.
    st.markdown(
        f"""
        <style>
        .st-key-cat_pager div[data-testid="stHorizontalBlock"] {{
            justify-content: center;
            gap: 6px;
            flex-wrap: wrap;
        }}
        .st-key-cat_pager div[data-testid="column"] {{
            width: auto !important;
            flex: 0 0 auto !important;
            min-width: 0 !important;
        }}
        .st-key-cat_pager button {{
            min-width: 40px !important;
            padding: 4px 12px !important;
        }}
        .st-key-cat_pager button:disabled {{
            color: {ACCENT} !important;
            border-color: {BORDER} !important;
            font-weight: 700 !important;
            opacity: 1 !important;
            background: {CARD} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container(key="cat_pager"):
        cols = st.columns(len(nav) + 2)

        if cols[0].button(t("list.prev"), disabled=page <= 1, key="cat_prev"):
            st.session_state["cat_page"] = page - 1
            st.rerun()

        for i, p in enumerate(nav):
            with cols[i + 1]:
                if p == "…":
                    st.button("…", disabled=True, key=f"cat_dots_{i}")
                elif p == page:
                    st.button(str(p), disabled=True, key=f"cat_pg_{p}")
                else:
                    if st.button(str(p), key=f"cat_pg_{p}"):
                        st.session_state["cat_page"] = p
                        st.rerun()

        if cols[-1].button(t("list.next"), disabled=page >= pages, key="cat_next"):
            st.session_state["cat_page"] = page + 1
            st.rerun()
