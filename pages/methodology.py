# -*- coding: utf-8 -*-
"""
pages/methodology.py — Методологии: библиотека скиллов с версиями.

Каждая область (scope) — своя методология: title_split (Синтез),
дальше bullets, photo_brief, ai_grade и т.д. Правки без коммитов кода:
новая версия при каждом сохранении, откат в один клик.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from i18n import t
from services.db import get_conn
from services.settings import get_int, get_float, save_setting
from components.ui import inject_fonts, eyebrow

inject_fonts()
st.title(t("meth.title"))
st.caption(t("meth.caption"))

# Подписи областей — в i18n (meth.scope.<id>), здесь только id
SCOPE_IDS = [
    "common", "title_split", "bullets", "highlights", "description",
    "aplus", "photo_brief", "video_brief", "ai_grade",
    "keyword_research", "review_analysis", "competitor_teardown",
    "ppc_negatives",
]

scope = st.selectbox(
    t("meth.scope"),
    SCOPE_IDS,
    format_func=lambda s: t(f"meth.scope.{s}"),
)


@st.cache_data(ttl=60)
def load_versions(scope_: str) -> pd.DataFrame:
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT id, version, marketplace, skill_text, created_at, is_active
            FROM synthesis_skill
            WHERE scope = %(scope)s
            ORDER BY version DESC
            """,
            conn, params={"scope": scope_},
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


versions = load_versions(scope)

if versions.empty:
    st.info(t("meth.empty_scope"))
    current_text = ""
    current_version = 0
else:
    active = versions[versions["is_active"]]
    if active.empty:
        current_text = ""
        current_version = int(versions["version"].max())
        st.warning(t("meth.no_active"))
    else:
        current_text = active.iloc[0]["skill_text"]
        current_version = int(active.iloc[0]["version"])
        st.markdown(
            eyebrow(
                f"{t('meth.active_version')} v{current_version} · "
                f"{pd.to_datetime(active.iloc[0]['created_at']).strftime('%d.%m %H:%M')}"
            ),
            unsafe_allow_html=True,
        )

edited = st.text_area(
    t("meth.title"),
    value=current_text,
    height=420,
    label_visibility="collapsed",
    placeholder=t("meth.editor_placeholder"),
)

save = st.button(
    f"{t('meth.save_as')} v{current_version + 1}",
    type="primary",
    disabled=(edited.strip() == current_text.strip() or not edited.strip()),
)

if save:
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE synthesis_skill SET is_active = FALSE "
                "WHERE scope = %s AND is_active = TRUE",
                (scope,),
            )
            cur.execute(
                """
                INSERT INTO synthesis_skill
                    (version, marketplace, scope, skill_text, is_active)
                VALUES (%s, 'all', %s, %s, TRUE)
                """,
                (current_version + 1, scope, edited.strip()),
            )
        conn.close()
        st.cache_data.clear()
        st.success(t("meth.saved"))
        st.rerun()
    except Exception as e:
        st.error(t("common.save_failed", e=e))

# ---- история версий и откат
if not versions.empty:
    st.divider()
    st.markdown(f"### {t('meth.history')}")

    for _, v in versions.iterrows():
        label = (
            f"v{int(v['version'])} · "
            f"{pd.to_datetime(v['created_at']).strftime('%d.%m.%Y %H:%M')}"
            + (f" · **{t('meth.active_label')}**" if v["is_active"] else "")
        )
        with st.expander(label):
            st.text(v["skill_text"][:2000])
            if not v["is_active"]:
                if st.button(f"{t('meth.rollback')} v{int(v['version'])}",
                             key=f"rollback-{v['id']}"):
                    try:
                        conn = get_conn()
                        with conn, conn.cursor() as cur:
                            cur.execute(
                                "UPDATE synthesis_skill SET is_active = FALSE "
                                "WHERE scope = %s AND is_active = TRUE",
                                (scope,),
                            )
                            cur.execute(
                                "UPDATE synthesis_skill SET is_active = TRUE "
                                "WHERE id = %s",
                                (int(v["id"]),),
                            )
                        conn.close()
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(t("common.save_failed", e=e))

# ================================================================ пороги правил
st.divider()
st.markdown(eyebrow(t("meth.thresholds")), unsafe_allow_html=True)
st.caption(t("meth.thresholds_hint"))

_p1, _p2, _p3 = st.columns(3)
_title_limit = _p1.number_input(
    t("meth.limit_title"), 20, 300, get_int("limit.title", 75), 1)
_hl_limit = _p2.number_input(
    t("meth.limit_highlights"), 20, 500, get_int("limit.highlights", 125), 1)
_min_reviews = _p3.number_input(
    t("meth.min_reviews"), 0, 1000, get_int("threshold.min_reviews", 50), 1)

_p4, _p5, _p6 = st.columns(3)
_min_images = _p4.number_input(
    t("meth.min_images"), 1, 20, get_int("threshold.min_images", 7), 1)
_rating_red = _p5.number_input(
    t("meth.rating_red"), 1.0, 5.0, get_float("threshold.rating_red", 4.3), 0.1)
_rating_green = _p6.number_input(
    t("meth.rating_green"), 1.0, 5.0, get_float("threshold.rating_green", 4.4), 0.1)

if st.button(t("meth.save_thresholds"), type="primary", key="save-thresholds"):
    try:
        save_setting("limit.title", _title_limit)
        save_setting("limit.highlights", _hl_limit)
        save_setting("threshold.min_reviews", _min_reviews)
        save_setting("threshold.min_images", _min_images)
        save_setting("threshold.rating_red", _rating_red)
        save_setting("threshold.rating_green", _rating_green)
        st.success(t("meth.thresholds_saved"))
    except Exception as e:
        st.error(t("common.save_failed", e=e))


# ================================================================ источники
st.divider()
st.markdown(eyebrow(t("meth.sources")), unsafe_allow_html=True)
st.caption(t("meth.sources_hint"))

_INK = "#1A1815"
_MUTED = "#8A8578"
_BORDER = "#E7E4DD"
_CARD = "#FFFFFF"
_ACCENT = "#E8590C"
_MONO = '"JetBrains Mono","SFMono-Regular",Consolas,monospace'
_STALE_DAYS = 30


@st.cache_data(ttl=120)
def load_sources() -> pd.DataFrame:
    try:
        conn = get_conn()
        df_src = pd.read_sql(
            "SELECT * FROM policy_sources ORDER BY id", conn)
        conn.close()
        return df_src
    except Exception:
        return pd.DataFrame()


sources = load_sources()

if sources.empty:
    st.caption(t("meth.sources_empty"))
else:
    today = pd.Timestamp.now().normalize()
    for _, src in sources.iterrows():
        checked = pd.to_datetime(src["last_checked"]) if src["last_checked"] else None
        stale = checked is None or (today - checked).days > _STALE_DAYS
        edge = _ACCENT if stale else _BORDER
        left = f"border-left:3px solid {_ACCENT};" if stale else ""
        checked_str = checked.strftime("%d.%m.%Y") if checked is not None else "—"
        checked_html = (
            f"<span style='font-family:{_MONO};font-size:11px;color:#993C1D;'>"
            f"⚠ {t('meth.checked_at')} {checked_str}</span>"
            if stale else
            f"<span style='font-family:{_MONO};font-size:11px;color:{_MUTED};'>"
            f"{t('meth.checked_at')} {checked_str}</span>"
        )
        note = f" · {src['url_note']}" if src.get("url_note") else ""
        chips = "".join(
            f"<span style='background:#F1EFE8;border-radius:6px;padding:1px 8px;"
            f"margin-left:4px;font-size:11px;'>{s.strip()}</span>"
            for s in str(src.get("scopes") or "").split(",") if s.strip()
        )

        c_card, c_btn = st.columns([8, 1.4])
        c_card.markdown(
            f"""
            <div style="background:{_CARD};border:1px solid {edge};{left}
                        border-radius:10px;padding:12px 16px;margin-bottom:8px;">
              <div style="display:flex;justify-content:space-between;align-items:baseline;gap:10px;">
                <div style="font-size:14px;font-weight:600;color:{_INK};">
                  {src['title']}
                  <a href="{src['url']}" target="_blank"
                     style='font-family:{_MONO};font-size:11px;color:{_MUTED};'>↗ открыть</a>
                  <span style="font-size:11px;color:{_MUTED};">{note}</span>
                </div>
                {checked_html}
              </div>
              <div style="font-size:12px;color:{_MUTED};margin-top:4px;">
                Обосновывает: {src['grounds']} {chips}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if c_btn.button(t("meth.checked"), key=f"src-check-{src['id']}"):
            try:
                conn = get_conn()
                with conn, conn.cursor() as cur:
                    cur.execute(
                        "UPDATE policy_sources SET last_checked = CURRENT_DATE "
                        "WHERE id = %s",
                        (int(src["id"]),),
                    )
                conn.close()
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(t("common.save_failed", e=e))

# ================================================================ изменения правил
st.divider()
st.markdown(eyebrow(t("meth.policy_changes")), unsafe_allow_html=True)
st.caption(t("meth.policy_hint"))

_SEV = {"critical": ("#FCEBEB", "#A32D2D", "sev.red"),
        "important": ("#FCE8DC", "#E8590C", "sev.amber"),
        "info": ("#F1EFE8", "#57534A", "sev.yellow")}


@st.cache_data(ttl=60)
def load_alerts() -> pd.DataFrame:
    try:
        conn = get_conn()
        df_a = pd.read_sql(
            """
            SELECT a.*, s.title AS source_title, s.url AS source_url
            FROM policy_alerts a
            LEFT JOIN policy_sources s ON s.id = a.source_id
            WHERE a.status = 'new'
            ORDER BY a.detected_at DESC
            """, conn)
        conn.close()
        return df_a
    except Exception:
        return pd.DataFrame()


alerts = load_alerts()

if alerts.empty:
    st.caption(t("meth.policy_none"))
else:
    for _, a in alerts.iterrows():
        bg, fg, _lk = _SEV.get(str(a["severity"]), _SEV["info"])
        lbl = t(_lk)
        scopes_chips = "".join(
            f"<span style='background:#F1EFE8;border-radius:6px;padding:1px 8px;"
            f"margin-left:4px;font-size:11px;'>{s.strip()}</span>"
            for s in str(a["affected_scopes"] or "").split(",") if s.strip())
        st.markdown(
            f"""
            <div style="background:{_CARD};border:1px solid {_BORDER};
                        border-left:3px solid {fg};border-radius:0 10px 10px 0;
                        padding:14px 18px;margin-bottom:8px;">
              <div style="display:flex;justify-content:space-between;align-items:baseline;">
                <div style="font-size:14px;font-weight:600;color:{_INK};">
                  {a['source_title']}
                  <a href="{a['source_url']}" target="_blank"
                     style='font-family:{_MONO};font-size:11px;color:{_MUTED};'>↗ открыть</a>
                </div>
                <span style="background:{bg};color:{fg};border-radius:999px;
                             padding:2px 10px;font-size:11px;font-weight:600;">{lbl}</span>
              </div>
              <div style="font-size:13px;color:{_INK};margin-top:6px;">{a['summary']}</div>
              <div style="font-size:12px;color:{_MUTED};margin-top:4px;">
                Затронуто: {scopes_chips or '—'} ·
                обнаружено {pd.to_datetime(a['detected_at']).strftime('%d.%m.%Y')}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if a["proposed_changes"]:
            with st.expander(t("meth.policy_changes")):
                st.text(a["proposed_changes"])
        ac1, ac2, _ = st.columns([1.4, 1.4, 4])
        if ac1.button(t("meth.applied"), key=f"alert-ok-{a['id']}"):
            try:
                conn = get_conn()
                with conn, conn.cursor() as cur:
                    cur.execute(
                        "UPDATE policy_alerts SET status = 'applied' WHERE id = %s",
                        (int(a["id"]),))
                conn.close()
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"{e}")
        if ac2.button(t("meth.dismiss"), key=f"alert-no-{a['id']}"):
            try:
                conn = get_conn()
                with conn, conn.cursor() as cur:
                    cur.execute(
                        "UPDATE policy_alerts SET status = 'dismissed' WHERE id = %s",
                        (int(a["id"]),))
                conn.close()
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"{e}")
