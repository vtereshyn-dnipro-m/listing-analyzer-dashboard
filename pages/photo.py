# -*- coding: utf-8 -*-
"""
pages/photo.py — Фото и A+ : аудит визуала листинга через Gemini Vision.

Вкладка «Галерея» — главное фото + галерея (методология photo_brief).
Вкладка «A+ контент» — модули A+ из снапшота (методология aplus).
Грейд в обоих случаях считает КОД, ИИ только отвечает по чек-пунктам.
Результаты пишутся в photo_analysis (analysis_type = gallery | aplus).
"""
from __future__ import annotations

import base64
import json

import pandas as pd
import streamlit as st

from i18n import t
from services.db import get_conn, cfg
from services.settings import get_setting
from services.ai import generate_json, task_config
from components.ui import inject_fonts, eyebrow

inject_fonts()

INK = "#1A1815"
MUTED = "#8A8578"
ACCENT = "#E8590C"
OK_TEXT = "#2F6B3A"
MONO = '"JetBrains Mono","SFMono-Regular",Consolas,monospace'

VISION_MODEL = task_config("photo_audit")[1]
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{VISION_MODEL}:generateContent"
)
MAX_IMAGES = 10
MAX_APLUS = 8

MP_LANGUAGE = {
    "es": "испанский", "de": "немецкий", "fr": "французский",
    "it": "итальянский", "nl": "нидерландский", "se": "шведский",
    "pl": "польский", "com": "английский", "co.uk": "английский",
}

MAIN_CHECKS = [
    ("main_white_bg", "фон чисто белый"),
    ("main_product_share", "товар ≥85% кадра"),
    ("main_no_packaging_dominance", "упаковка не доминирует"),
    ("main_no_overlays", "нет надписей и плашек"),
    ("main_readable_thumb", "читаемо в миниатюре"),
    ("main_language_match", "текст на языке маркетплейса"),
]
GALLERY_CHECKS = [
    ("role_specs", "инфографика характеристик"),
    ("role_feature", "фича крупным планом"),
    ("role_kit", "комплектация"),
    ("role_lifestyle", "применение"),
    ("role_scale", "масштаб / габариты"),
    ("role_compat", "совместимость платформы"),
    ("gallery_language_match", "инфографика на языке маркетплейса"),
]
APLUS_CHECKS = [
    ("aplus_brand_story", "есть блок о бренде"),
    ("aplus_benefits", "выгоды, а не только характеристики"),
    ("aplus_comparison", "сравнение моделей линейки"),
    ("aplus_usecases", "сценарии применения"),
    ("aplus_readable_mobile", "текст читаем на мобильном"),
    ("aplus_no_claims_risk", "нет запрещённых утверждений и чужих брендов"),
    ("aplus_consistent_style", "единый стиль с брендом"),
    ("aplus_language_match", "тексты на языке маркетплейса"),
]

PROMPT_TPL = """{skill}

Проанализируй изображения листинга Amazon (маркетплейс {mp}, товар: {title}).
Ожидаемый язык всех текстов на изображениях — {lang} (язык маркетплейса {mp}).
Английские или иные надписи для этого маркетплейса считаются нарушением,
кроме модели, бренда и единиц измерения (20V, 50 Nm, mm).
{context}

Ответь ТОЛЬКО валидным JSON:
{{
  "{block}": {{{keys}}},
  "notes": {{"<ключ_чекпункта>": "короткое замечание по-русски"}},
  "designer_brief": "ТЗ дизайнеру: что переснять/переделать, по пунктам"
}}
Значения всех чек-пунктов — true или false."""


# ---------------------------------------------------------------- данные
@st.cache_data(ttl=300)
def load_candidates() -> pd.DataFrame:
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT DISTINCT ON (s.asin, s.marketplace)
                   s.asin, s.marketplace, s.title, s.raw, s.fetched_at,
                   m.sku_group
            FROM listing_snapshots s
            LEFT JOIN product_matrix m
                ON m.asin = s.asin AND m.marketplace = s.marketplace
            WHERE s.ok = TRUE AND s.title <> ''
            ORDER BY s.asin, s.marketplace, s.fetched_at DESC
            """,
            conn,
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=120)
def load_skill(scope: str) -> tuple[str, int]:
    """common + указанная область, склеенные."""
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT DISTINCT ON (scope) scope, skill_text, version
            FROM synthesis_skill
            WHERE is_active = TRUE AND scope IN ('common', %(scope)s)
            ORDER BY scope, version DESC
            """,
            conn, params={"scope": scope},
        )
        conn.close()
        parts, ver = [], 0
        for sc in ("common", scope):
            row = df[df["scope"] == sc]
            if not row.empty:
                parts.append(str(row.iloc[0]["skill_text"]))
                if sc == scope:
                    ver = int(row.iloc[0]["version"])
        if parts:
            return "\n\n".join(parts), ver
    except Exception:
        pass
    return "", 0


def _img_id(url: str) -> str:
    """ID картинки Amazon: .../I/{ID}._SIZE_.jpg -> {ID} (для дедупа размеров)."""
    try:
        tail = url.rsplit("/I/", 1)[-1]
        return tail.split(".")[0]
    except Exception:
        return url


def _raw_dict(raw) -> dict:
    try:
        return raw if isinstance(raw, dict) else json.loads(raw or "{}")
    except Exception:
        return {}


def extract_images(raw) -> list[str]:
    data = _raw_dict(raw)
    imgs = data.get("images") or data.get("images_of_specified_asin") or []
    main = data.get("main_image")
    out, seen = [], set()
    for u in ([main] if main else []) + list(imgs):
        if not isinstance(u, str):
            continue
        uid = _img_id(u)
        if uid in seen:
            continue
        seen.add(uid)
        out.append(u)
    return out[:MAX_IMAGES]


def extract_aplus(raw) -> list[str]:
    data = _raw_dict(raw)
    imgs = data.get("aplus_images") or []
    out, seen = [], set()
    for u in imgs:
        if not isinstance(u, str):
            continue
        uid = _img_id(u)
        if uid in seen:
            continue
        seen.add(uid)
        out.append(u)
    return out[:MAX_APLUS]


# ---------------------------------------------------------------- анализ
def analyze(images: list[str], title: str, mp: str, skill: str,
            checks: list[tuple[str, str]], block: str, context: str) -> dict | None:
    """Аудит визуала. Провайдер и модель — из Настроек (задача photo_audit)."""
    prompt = PROMPT_TPL.format(
        skill=skill or "Оцени визуал листинга Amazon по здравому смыслу.",
        mp=mp, lang=MP_LANGUAGE.get(mp, "язык маркетплейса"),
        title=title[:120], context=context, block=block,
        keys=", ".join(f'"{k}": true' for k, _ in checks),
    )
    return generate_json("photo_audit", prompt, images=images, timeout=300)


def grade_from(score: float) -> str:
    return "A" if score >= 0.9 else "B" if score >= 0.75 else "C" if score >= 0.5 else "D"


def save(asin, mp, res, grade, m, g, n_img, ver, atype) -> None:
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO photo_analysis
                    (asin, marketplace, grade, score_main, score_gallery, checks,
                     designer_brief, images_analyzed, model, skill_version,
                     analysis_type, raw)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (asin, mp, grade, m, g,
                 json.dumps(res, ensure_ascii=False),
                 res.get("designer_brief", ""), n_img, VISION_MODEL, ver,
                 atype, json.dumps(res, ensure_ascii=False)),
            )
        conn.close()
    except Exception as e:
        st.warning(f"Анализ выполнен, но не сохранён: {e}")


def render_checks(res: dict, block: str, checks: list[tuple[str, str]],
                  title: str) -> None:
    data = res.get(block, {}) or {}
    notes = res.get("notes", {}) or {}
    st.markdown(f"**{title}**")
    for k, label in checks:
        ok = data.get(k) is True
        note = notes.get(k, "")
        st.markdown(("✅ " if ok else "❌ ") + label
                    + (f" — {note}" if note and not ok else ""))


def show_grade(grade: str, detail: str) -> None:
    color = OK_TEXT if grade in ("A", "B") else ACCENT
    st.markdown(
        f"<div style='font-size:22px;font-weight:700;color:{INK};'>{t('photo.grade')} "
        f"<span style='color:{color};font-family:{MONO};'>{grade}</span>"
        f"<span style='font-size:13px;color:{MUTED};font-weight:400;'> · {detail}"
        f"</span></div>", unsafe_allow_html=True)


# ---------------------------------------------------------------- UI
st.header(t("photo.title"))
st.caption(t("photo.caption"))

cands = load_candidates()
if cands.empty:
    st.info("Нет собранных листингов — прогони сбор в Матрице товаров.")
    st.stop()

opts = {f"{r['sku_group'] or r['asin']} · {r['asin']} · {r['marketplace']}": i
        for i, r in cands.iterrows()}
choice = st.selectbox(t("photo.product"), list(opts.keys()))
row = cands.loc[opts[choice]]
asin, mp, title = row["asin"], row["marketplace"], row["title"]
_f = row.get("fetched_at")
fetched_part = (
    f" · {t('matrix.collected_at')} "
    f"{pd.to_datetime(_f).strftime('%d.%m %H:%M')}"
    if _f is not None and not pd.isna(_f) else ""
)

tab_gallery, tab_aplus = st.tabs([t("photo.tab_gallery"), t("photo.tab_aplus")])

# ---- галерея
with tab_gallery:
    skill, ver = load_skill("photo_brief")
    if not skill:
        st.warning(t("photo.skill_empty"))
    images = extract_images(row["raw"])
    st.markdown(
        eyebrow(f"{asin} · {mp}{fetched_part} · "
                f"{t('metric.photos')}: {len(images)} · "
                f"{t('synth.methodology')} v{ver}"),
        unsafe_allow_html=True)
    if images:
        cols = st.columns(min(len(images), 6))
        for i, url in enumerate(images[:6]):
            cols[i].image(url, use_container_width=True)
    else:
        st.warning(t("photo.no_images"))

    if st.button(t("photo.analyze_gallery"), type="primary",
                 disabled=not images, key="btn-gallery"):
        with st.spinner(f"{t('photo.looking')} {len(images)}..."):
            res = analyze(
                images, title, mp, skill, MAIN_CHECKS + GALLERY_CHECKS, "main",
                "Первое изображение — ГЛАВНОЕ фото, остальные — галерея. "
                "Ключи main_* относятся к главному фото, role_* — к галерее в целом.",
            )
        if res:
            main = {k: v for k, v in (res.get("main", {}) or {}).items()}
            m = sum(1 for k, _ in MAIN_CHECKS if main.get(k) is True)
            g = sum(1 for k, _ in GALLERY_CHECKS if main.get(k) is True)
            score = m / len(MAIN_CHECKS) * 0.6 + g / len(GALLERY_CHECKS) * 0.4
            grade = grade_from(score)
            st.session_state["res_gallery"] = (asin, mp, res, grade, m, g)
            save(asin, mp, res, grade, m, g, len(images), ver, "gallery")

    saved = st.session_state.get("res_gallery")
    if saved and saved[0] == asin and saved[1] == mp:
        _, _, res, grade, m, g = saved
        st.divider()
        show_grade(grade, f"главное {m}/{len(MAIN_CHECKS)} · "
                          f"галерея {g}/{len(GALLERY_CHECKS)}")
        c1, c2 = st.columns(2)
        with c1:
            render_checks(res, "main", MAIN_CHECKS, t("photo.main_photo"))
        with c2:
            render_checks(res, "main", GALLERY_CHECKS, t("photo.gallery_roles"))
        if res.get("designer_brief"):
            st.markdown(f"**{t('photo.designer_brief')}**")
            st.code(res["designer_brief"], language=None)

# ---- A+ контент
with tab_aplus:
    skill_a, ver_a = load_skill("aplus")
    if not skill_a:
        st.warning(t("photo.skill_empty"))
    aplus = extract_aplus(row["raw"])
    st.markdown(
        eyebrow(f"{asin} · {mp}{fetched_part} · "
                f"A+: {len(aplus)} · {t('synth.methodology')} v{ver_a}"),
        unsafe_allow_html=True)
    if aplus:
        for url in aplus[:4]:
            st.image(url, use_container_width=True)
    else:
        st.info(t("photo.no_aplus"))

    if st.button(t("photo.analyze_aplus"), type="primary",
                 disabled=not aplus, key="btn-aplus"):
        with st.spinner(f"{t('photo.looking')} {len(aplus)} A+..."):
            res_a = analyze(
                aplus, title, mp, skill_a, APLUS_CHECKS, "aplus",
                "Это модули A+ контента листинга, по порядку сверху вниз.",
            )
        if res_a:
            block = res_a.get("aplus", {}) or {}
            a = sum(1 for k, _ in APLUS_CHECKS if block.get(k) is True)
            grade_a = grade_from(a / len(APLUS_CHECKS))
            st.session_state["res_aplus"] = (asin, mp, res_a, grade_a, a)
            save(asin, mp, res_a, grade_a, a, 0, len(aplus), ver_a, "aplus")

    saved_a = st.session_state.get("res_aplus")
    if saved_a and saved_a[0] == asin and saved_a[1] == mp:
        _, _, res_a, grade_a, a = saved_a
        st.divider()
        show_grade(grade_a, f"{a}/{len(APLUS_CHECKS)} пунктов")
        render_checks(res_a, "aplus", APLUS_CHECKS, t("photo.tab_aplus"))
        if res_a.get("designer_brief"):
            st.markdown(f"**{t('photo.designer_brief')}**")
            st.code(res_a["designer_brief"], language=None) 
