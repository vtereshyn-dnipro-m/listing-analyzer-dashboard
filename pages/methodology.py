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
from services.db import get_conn, get_engine
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
def load_versions(scope_: str) -> tuple[pd.DataFrame, str | None]:
    """Версии области и ПРИЧИНА, если прочитать не удалось.

    Причину возвращаем отдельно намеренно. Пока функция отдавала пустую
    таблицу на любой сбой, страница говорила «для этой области методологии
    ещё нет» — то есть утверждала про данные то, чего не знала. Именно так
    30.08 живая v8 выглядела отсутствующей: в этом блоке стоял
    `conn.close()` при том, что переменной `conn` здесь уже не было, и
    NameError уходил в общий except.
    """
    try:
        df = pd.read_sql(
            """
            SELECT id, version, marketplace, skill_text, created_at, is_active
            FROM synthesis_skill
            WHERE scope = %(scope)s
            ORDER BY version DESC
            """,
            get_engine(), params={"scope": scope_},
        )
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"{type(e).__name__}: {e}"


versions, load_err = load_versions(scope)

if load_err:
    # Редактор и сохранение заперты, пока методология не прочитана.
    # Пустой редактор при сбое — это заряженная кнопка: «Сохранить как v1»
    # деактивировала бы действующую версию и подменила её пустой.
    st.error("⚠ " + t("meth.load_failed", e=load_err))
    current_text = ""
    current_version = 0
elif versions.empty:
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
    disabled=bool(load_err),
)

save = st.button(
    f"{t('meth.save_as')} v{current_version + 1}",
    type="primary",
    disabled=(bool(load_err) or edited.strip() == current_text.strip()
              or not edited.strip()),
    help=t("meth.load_blocked") if load_err else None,
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
        # Глобальный сброс здесь ОСОЗНАННО: методологию читают Синтез
        # и Фото своими кэшами внутри страниц, дотянуться до них
        # отсюда нельзя, а работать по старой методологии после
        # сохранение — ровно тот инцидент, который мы уже разбирали.
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
                        # Глобальный сброс здесь ОСОЗНАННО: методологию читают Синтез
                        # и Фото своими кэшами внутри страниц, дотянуться до них
                        # отсюда нельзя, а работать по старой методологии после
                        # откат — ровно тот инцидент, который мы уже разбирали.
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

_p7, _, _ = st.columns(3)
# порог из практики Amazon: ниже 0.3% при заметных показах — карточка
# не убеждает; читает services/search.py (ctr_state)
_min_ctr = _p7.number_input(
    t("meth.min_ctr"), 0.0, 10.0, get_float("threshold.min_ctr", 0.3), 0.1,
    help=t("meth.min_ctr_hint"))

if st.button(t("meth.save_thresholds"), type="primary", key="save-thresholds"):
    try:
        save_setting("limit.title", _title_limit)
        save_setting("limit.highlights", _hl_limit)
        save_setting("threshold.min_reviews", _min_reviews)
        save_setting("threshold.min_images", _min_images)
        save_setting("threshold.rating_red", _rating_red)
        save_setting("threshold.rating_green", _rating_green)
        save_setting("threshold.min_ctr", _min_ctr)
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
_MONO = "var(--ls-mono)"   # переменная из inject_fonts(): без кавычек в атрибутах
_STALE_DAYS = 30


@st.cache_data(ttl=120)
def load_sources() -> pd.DataFrame:
    try:
        df_src = pd.read_sql(
            "SELECT * FROM policy_sources ORDER BY id", get_engine())
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
            f'<div style="background:{_CARD};border:1px solid {edge};{left}'
            f'border-radius:10px;padding:12px 16px;margin-bottom:8px;">'
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:baseline;gap:10px;">'
            f'<div style="font-size:14px;font-weight:600;color:{_INK};">'
            f"{src['title']} "
            f'<a href="{src["url"]}" target="_blank" '
            f'style="font-family:{_MONO};font-size:11px;color:{_MUTED};">'
            f'{t("meth.open_link")}</a>'
            f'<span style="font-size:11px;color:{_MUTED};">{note}</span></div>'
            f"{checked_html}</div>"
            f'<div style="font-size:12px;color:{_MUTED};margin-top:4px;">'
            f'{t("meth.grounds")}: {src["grounds"]} {chips}</div></div>',
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
                load_sources.clear()
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
        df_a = pd.read_sql(
            """
            SELECT a.*, s.title AS source_title, s.url AS source_url
            FROM policy_alerts a
            LEFT JOIN policy_sources s ON s.id = a.source_id
            WHERE a.status = 'new'
            ORDER BY a.detected_at DESC
            """, get_engine())
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
        detected = pd.to_datetime(a["detected_at"]).strftime("%d.%m.%Y")
        st.markdown(
            f'<div style="background:{_CARD};border:1px solid {_BORDER};'
            f'border-left:3px solid {fg};border-radius:0 10px 10px 0;'
            f'padding:14px 18px;margin-bottom:8px;">'
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:baseline;">'
            f'<div style="font-size:14px;font-weight:600;color:{_INK};">'
            f"{a['source_title']} "
            f'<a href="{a["source_url"]}" target="_blank" '
            f'style="font-family:{_MONO};font-size:11px;color:{_MUTED};">'
            f'{t("meth.open_link")}</a></div>'
            f'<span style="background:{bg};color:{fg};border-radius:999px;'
            f'padding:2px 10px;font-size:11px;font-weight:600;">{lbl}</span>'
            f"</div>"
            f'<div style="font-size:13px;color:{_INK};margin-top:6px;">'
            f"{a['summary']}</div>"
            f'<div style="font-size:12px;color:{_MUTED};margin-top:4px;">'
            f'{t("meth.affected")}: {scopes_chips or "—"} · '
            f'{t("meth.detected")} {detected}</div></div>',
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
                load_alerts.clear()
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
                load_alerts.clear()
                st.rerun()
            except Exception as e:
                st.error(f"{e}")
