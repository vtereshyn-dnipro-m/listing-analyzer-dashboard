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
from components.ui import inject_fonts, eyebrow

inject_fonts()
st.header(t("meth.title"))
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
        st.error(f"Не сохранилось: {e}")

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
                        st.error(f"Откат не удался: {e}")

# ================================================================ источники
st.divider()
st.markdown(eyebrow("Официальные источники Amazon"), unsafe_allow_html=True)
st.caption(
    "Документы, на которых основаны правила методологий. "
    "Проверяй при изменениях политик Amazon — открой ссылку, сверь, отметь."
)

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
    st.caption("Источники не заведены — прогони DDL-ячейку policy_sources.")
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
            f"⚠ проверено {checked_str}</span>"
            if stale else
            f"<span style='font-family:{_MONO};font-size:11px;color:{_MUTED};'>"
            f"проверено {checked_str}</span>"
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
                     style="font-family:{_MONO};font-size:11px;color:{_MUTED};">↗ открыть</a>
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
        if c_btn.button("✓ проверено", key=f"src-check-{src['id']}"):
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
                st.error(f"Не сохранилось: {e}")
