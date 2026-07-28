# -*- coding: utf-8 -*-
"""
pages/photo.py — Фото: аудит галереи листинга через Gemini Vision.

Берёт URL фото из последнего снапшота, отправляет их в Gemini вместе
с методологией photo_brief (scope='photo_brief' + common), получает
JSON с чек-пунктами, считает грейд КОДОМ, показывает ТЗ дизайнеру.
Результат сохраняется в photo_analysis.
"""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from i18n import t
from services.db import get_conn, cfg
from components.ui import inject_fonts, eyebrow

inject_fonts()

INK = "#1A1815"
MUTED = "#8A8578"
BORDER = "#E7E4DD"
CARD = "#FFFFFF"
ACCENT = "#E8590C"
OK_TEXT = "#2F6B3A"
MONO = '"JetBrains Mono","SFMono-Regular",Consolas,monospace'

VISION_MODEL = "gemini-3.5-flash"
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{VISION_MODEL}:generateContent"
)
MAX_IMAGES = 10

MAIN_CHECKS = [
    ("main_white_bg", "фон чисто белый"),
    ("main_product_share", "товар ≥85% кадра"),
    ("main_no_packaging_dominance", "упаковка не доминирует"),
    ("main_no_overlays", "нет надписей и плашек"),
    ("main_readable_thumb", "читаемо в миниатюре"),
]
GALLERY_CHECKS = [
    ("role_specs", "инфографика характеристик"),
    ("role_feature", "фича крупным планом"),
    ("role_kit", "комплектация"),
    ("role_lifestyle", "применение"),
    ("role_scale", "масштаб / габариты"),
    ("role_compat", "совместимость платформы"),
]

PROMPT = """{skill}

Проанализируй фото листинга Amazon (маркетплейс {mp}, товар: {title}).
Первое изображение — ГЛАВНОЕ фото, остальные — галерея.

Ответь ТОЛЬКО валидным JSON:
{{
  "main": {{{main_keys}}},
  "gallery": {{{gallery_keys}}},
  "notes": {{"<ключ_чекпункта>": "короткое замечание по-русски"}},
  "designer_brief": "ТЗ дизайнеру: что переснять и как, по пунктам"
}}
Значения всех чек-пунктов — true или false."""


st.header("Фото")
st.caption("Аудит галереи по методологии photo_brief. Грейд считает код, ИИ только смотрит.")


@st.cache_data(ttl=300)
def load_candidates() -> pd.DataFrame:
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT DISTINCT ON (s.asin, s.marketplace)
                   s.asin, s.marketplace, s.title, s.raw, m.sku_group
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
def load_skill() -> tuple[str, int]:
    """common + photo_brief, склеенные."""
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT DISTINCT ON (scope) scope, skill_text, version
            FROM synthesis_skill
            WHERE is_active = TRUE AND scope IN ('common', 'photo_brief')
            ORDER BY scope, version DESC
            """,
            conn,
        )
        conn.close()
        parts, ver = [], 0
        for sc in ("common", "photo_brief"):
            row = df[df["scope"] == sc]
            if not row.empty:
                parts.append(str(row.iloc[0]["skill_text"]))
                if sc == "photo_brief":
                    ver = int(row.iloc[0]["version"])
        if parts:
            return "\n\n".join(parts), ver
    except Exception:
        pass
    return "", 0


def extract_images(raw) -> list[str]:
    try:
        data = raw if isinstance(raw, dict) else json.loads(raw or "{}")
    except Exception:
        return []
    imgs = data.get("images") or data.get("images_of_specified_asin") or []
    main = data.get("main_image")
    out: list[str] = []
    if main:
        out.append(main)
    for u in imgs:
        if isinstance(u, str) and u not in out:
            out.append(u)
    return out[:MAX_IMAGES]


def analyze(images: list[str], title: str, mp: str, skill: str) -> dict | None:
    api_key = cfg("GEMINI_API_KEY")
    if not api_key:
        st.error("GEMINI_API_KEY не найден в секретах.")
        return None
    try:
        import requests as _rq

        parts: list[dict] = []
        for url in images:
            r = _rq.get(url, timeout=30)
            if r.status_code != 200:
                continue
            import base64
            parts.append({
                "inline_data": {
                    "mime_type": r.headers.get("Content-Type", "image/jpeg"),
                    "data": base64.b64encode(r.content).decode(),
                }
            })
        if not parts:
            st.error("Не удалось загрузить ни одного изображения.")
            return None

        prompt = PROMPT.format(
            skill=skill or "Оцени фото листинга Amazon по здравому смыслу.",
            mp=mp, title=title[:120],
            main_keys=", ".join(f'"{k}": true' for k, _ in MAIN_CHECKS),
            gallery_keys=", ".join(f'"{k}": true' for k, _ in GALLERY_CHECKS),
        )
        parts.append({"text": prompt})

        resp = _rq.post(
            GEMINI_URL,
            headers={"x-goog-api-key": str(api_key).strip()},
            json={
                "contents": [{"parts": parts}],
                "generationConfig": {"responseMimeType": "application/json"},
            },
            timeout=180,
        )
        if resp.status_code != 200:
            st.error(f"Gemini HTTP {resp.status_code}: {resp.text[:300]}")
            return None
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except Exception as e:
        st.error(f"Ошибка анализа: {e}")
        return None


def compute_grade(main: dict, gallery: dict) -> tuple[str, int, int]:
    """Грейд считает код, не ИИ."""
    m = sum(1 for k, _ in MAIN_CHECKS if main.get(k) is True)
    g = sum(1 for k, _ in GALLERY_CHECKS if gallery.get(k) is True)
    total = m / len(MAIN_CHECKS) * 0.6 + g / len(GALLERY_CHECKS) * 0.4
    grade = "A" if total >= 0.9 else "B" if total >= 0.75 else "C" if total >= 0.5 else "D"
    return grade, m, g


def save(asin, mp, res, grade, m, g, n_img, ver) -> None:
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO photo_analysis
                    (asin, marketplace, grade, score_main, score_gallery,
                     checks, designer_brief, images_analyzed, model, skill_version, raw)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (asin, mp, grade, m, g,
                 json.dumps({"main": res.get("main"), "gallery": res.get("gallery")},
                            ensure_ascii=False),
                 res.get("designer_brief", ""), n_img, VISION_MODEL, ver,
                 json.dumps(res, ensure_ascii=False)),
            )
        conn.close()
    except Exception as e:
        st.warning(f"Анализ выполнен, но не сохранён: {e}")


# ---------------------------------------------------------------- UI
cands = load_candidates()
if cands.empty:
    st.info("Нет собранных листингов — прогони сбор в Матрице товаров.")
    st.stop()

skill, skill_ver = load_skill()
if not skill:
    st.warning("Методология photo_brief пуста — заполни её на странице Методологии.")

opts = {f"{r['sku_group'] or r['asin']} · {r['asin']} · {r['marketplace']}": i
        for i, r in cands.iterrows()}
choice = st.selectbox("Товар", list(opts.keys()))
row = cands.loc[opts[choice]]
asin, mp, title = row["asin"], row["marketplace"], row["title"]
images = extract_images(row["raw"])

st.markdown(
    eyebrow(f"{asin} · {mp} · фото: {len(images)} · методология v{skill_ver}"),
    unsafe_allow_html=True)

if images:
    cols = st.columns(min(len(images), 6))
    for i, url in enumerate(images[:6]):
        cols[i].image(url, use_container_width=True)
else:
    st.warning("В снапшоте нет URL изображений — пересобери товар.")

if st.button("Проанализировать галерею", type="primary", disabled=not images):
    with st.spinner(f"Gemini смотрит {len(images)} фото..."):
        res = analyze(images, title, mp, skill)
    if res:
        st.session_state["photo_res"] = res
        st.session_state["photo_key"] = (asin, mp)
        main, gallery = res.get("main", {}), res.get("gallery", {})
        grade, m, g = compute_grade(main, gallery)
        save(asin, mp, res, grade, m, g, len(images), skill_ver)

res = st.session_state.get("photo_res")
if res and st.session_state.get("photo_key") == (asin, mp):
    main, gallery = res.get("main", {}), res.get("gallery", {})
    notes = res.get("notes", {}) or {}
    grade, m, g = compute_grade(main, gallery)
    color = OK_TEXT if grade in ("A", "B") else ACCENT

    st.divider()
    st.markdown(
        f"<div style='font-size:22px;font-weight:700;color:{INK};'>Грейд "
        f"<span style='color:{color};font-family:{MONO};'>{grade}</span>"
        f"<span style='font-size:13px;color:{MUTED};font-weight:400;'>"
        f" · главное {m}/{len(MAIN_CHECKS)} · галерея {g}/{len(GALLERY_CHECKS)}</span></div>",
        unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Главное фото**")
        for k, label in MAIN_CHECKS:
            ok = main.get(k) is True
            note = notes.get(k, "")
            st.markdown(("✅ " if ok else "❌ ") + label
                        + (f" — {note}" if note and not ok else ""))
    with c2:
        st.markdown("**Роли галереи**")
        for k, label in GALLERY_CHECKS:
            ok = gallery.get(k) is True
            note = notes.get(k, "")
            st.markdown(("✅ " if ok else "❌ ") + label
                        + (f" — {note}" if note and not ok else ""))

    brief = res.get("designer_brief", "")
    if brief:
        st.markdown("**ТЗ дизайнеру**")
        st.code(brief, language=None)
