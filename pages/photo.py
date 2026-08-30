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
import time

import pandas as pd
import streamlit as st

from i18n import t, current_lang
from services import cache
from services.db import get_conn, cfg, get_engine
from services.settings import get_setting
from services.ai import generate_json, task_config, no_credit_banner
from components.ui import inject_fonts, eyebrow

inject_fonts()
st.title(t("photo.title"))
# баланс провайдера исчерпан — предупреждаем до кнопок генерации
no_credit_banner("photo_audit")

INK = "#1A1815"
MUTED = "#57534A"
ACCENT = "#E8590C"
OK_TEXT = "#2F6B3A"
CARD = "#FFFFFF"
BORDER = "#E7E4DD"
MONO = "var(--ls-mono)"

VISION_MODEL = task_config("photo_audit")[1]
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{VISION_MODEL}:generateContent"
)
MAX_IMAGES = 10
MAX_APLUS = 8

MP_FLAG = {"com": "🇺🇸", "es": "🇪🇸", "de": "🇩🇪", "fr": "🇫🇷", "it": "🇮🇹",
           "co.uk": "🇬🇧", "nl": "🇳🇱", "be": "🇧🇪", "ie": "🇮🇪", "se": "🇸🇪",
           "pl": "🇵🇱", "ca": "🇨🇦"}
PROVIDER_ICON = {"gemini": "✦ Gemini", "anthropic": "⚡ Claude"}

MP_LANGUAGE = {
    "es": "испанский", "de": "немецкий", "fr": "французский",
    "it": "итальянский", "nl": "нидерландский", "se": "шведский",
    "pl": "польский", "com": "английский", "co.uk": "английский",
}

MAIN_CHECKS = [
    ("main_white_bg", "chk.main_white_bg"),
    ("main_product_share", "chk.main_product_share"),
    ("main_no_packaging_dominance", "chk.main_no_packaging_dominance"),
    ("main_no_overlays", "chk.main_no_overlays"),
    ("main_readable_thumb", "chk.main_readable_thumb"),
    ("main_language_match", "chk.main_language_match"),
]
GALLERY_CHECKS = [
    ("role_specs", "chk.role_specs"),
    ("role_feature", "chk.role_feature"),
    ("role_kit", "chk.role_kit"),
    ("role_lifestyle", "chk.role_lifestyle"),
    ("role_scale", "chk.role_scale"),
    ("role_compat", "chk.role_compat"),
    ("gallery_language_match", "chk.gallery_language_match"),
]
APLUS_CHECKS = [
    ("aplus_brand_story", "chk.aplus_brand_story"),
    ("aplus_benefits", "chk.aplus_benefits"),
    ("aplus_comparison", "chk.aplus_comparison"),
    ("aplus_usecases", "chk.aplus_usecases"),
    ("aplus_readable_mobile", "chk.aplus_readable_mobile"),
    ("aplus_no_claims_risk", "chk.aplus_no_claims_risk"),
    ("aplus_consistent_style", "chk.aplus_consistent_style"),
    ("aplus_language_match", "chk.aplus_language_match"),
]

UI_LANG_NAME = {"ru": "русском", "uk": "украинском", "en": "английском"}

PROMPT_TPL = """{skill}

ЯЗЫК ОТВЕТА: все текстовые поля ответа (notes, designer_brief) пиши строго
на {answer_lang} языке. Названия чек-пунктов и ключи JSON не переводи.

Проанализируй изображения листинга Amazon (маркетплейс {mp}, товар: {title}).
Ожидаемый язык всех текстов на изображениях — {lang} (язык маркетплейса {mp}).
Английские или иные надписи для этого маркетплейса считаются нарушением,
кроме модели, бренда и единиц измерения (20V, 50 Nm, mm).
{context}

Ответь ТОЛЬКО валидным JSON:
{{
  "{block}": {{{keys}}},
  "notes": {{"<ключ_чекпункта>": "короткое замечание"}},
  "per_photo": [
    {{
      "index": 1,
      "role": "роль кадра: главное фото / инфографика / фича / комплект / применение / масштаб / совместимость / другое",
      "score": 7,
      "good": "что работает на продажу в этом кадре, конкретно",
      "issue": "что мешает: чего не видно, что снижает доверие или понимание",
      "fix": "что переснять или добавить, конкретным действием",
      "conversion": "какое возражение покупателя кадр снимает или НЕ снимает",
      "emotion": "какую эмоцию вызывает кадр и почему (доверие, желание, сомнение, безразличие)"
    }}
  ],
  "designer_brief": "ТЗ дизайнеру: что переснять/переделать, по пунктам"
}}
Значения всех чек-пунктов — true или false.
В per_photo дай объект НА КАЖДОЕ изображение по порядку, score от 1 до 10.
Оценивай как ИИ-ассистент покупателя (Amazon Rufus), который смотрит на фото
и решает, отвечает ли оно на вопрос «подойдёт ли мне этот товар»."""


# ---------------------------------------------------------------- данные
@st.cache_data(ttl=300)
def load_candidates() -> pd.DataFrame:
    try:
        df = pd.read_sql(
            """
            SELECT DISTINCT ON (s.asin, s.marketplace)
                   s.asin, s.marketplace, s.title, s.raw, s.fetched_at,
                   m.sku_group, m.is_competitor, ll.has_aplus
            FROM listing_snapshots s
            LEFT JOIN product_matrix m
                ON m.asin = s.asin AND m.marketplace = s.marketplace
            LEFT JOIN listing_latest ll
                ON ll.asin = s.asin AND ll.marketplace = s.marketplace
            WHERE s.ok = TRUE AND s.title <> ''
            ORDER BY s.asin, s.marketplace, s.fetched_at DESC
            """,
            get_engine(),
        )
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=120)
def load_skill(scope: str) -> tuple[str, int]:
    """common + указанная область, склеенные."""
    try:
        df = pd.read_sql(
            """
            SELECT DISTINCT ON (scope) scope, skill_text, version
            FROM synthesis_skill
            WHERE is_active = TRUE AND scope IN ('common', %(scope)s)
            ORDER BY scope, version DESC
            """,
            get_engine(), params={"scope": scope},
        )
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
    """ID картинки по имени файла — работает и для галереи, и для A+ модулей.

    .../I/81EcKIG6LhL._AC_SL1500_.jpg              -> 81EcKIG6LhL
    .../aplus-media-library-service-media/644f...__CR0,0.jpg -> 644f...
    Раньше ID брался по пути /I/, из-за чего ВСЕ модули A+ получали
    одинаковый ключ и схлопывались в один при дедупе.
    """
    try:
        name = url.split("?")[0].rstrip("/").split("/")[-1]
        return name.split(".")[0]
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
        answer_lang=UI_LANG_NAME.get(current_lang(), "русском"),
        title=title[:120], context=context, block=block,
        keys=", ".join(f'"{k}": true' for k, _ in checks),
    )
    return generate_json("photo_audit", prompt, images=images, timeout=300)


def run_meta(task: str, elapsed: float) -> str:
    """Строка метаданных прогона: провайдер, модель, длительность."""
    prov, model = task_config(task)
    icon = PROVIDER_ICON.get(prov, prov)
    mins, secs = divmod(int(elapsed), 60)
    dur = f"{mins}м {secs}с" if mins else f"{secs}с"
    return f"{icon} · {model} · ⏱ {dur}"


def render_per_photo(res: dict, images: list[str]) -> None:
    """Разбор каждого кадра: оценка, что работает, что мешает, что делать."""
    items = res.get("per_photo") or []
    if not items:
        return
    st.divider()
    st.markdown(f"**{t('photo.per_photo')}**")
    for it in items:
        try:
            idx = int(it.get("index", 0))
        except (TypeError, ValueError):
            idx = 0
        url = images[idx - 1] if 0 < idx <= len(images) else None
        try:
            sc = float(it.get("score") or 0)
        except (TypeError, ValueError):
            sc = 0.0
        color = OK_TEXT if sc >= 8 else (ACCENT if sc < 6 else "#854F0B")
        verdict = "A" if sc >= 8 else ("C" if sc < 6 else "B")

        c1, c2 = st.columns([1, 4])
        if url:
            c1.image(url, width="stretch")
        with c2:
            st.markdown(
                f"<div style='font-size:15px;font-weight:700;'>Фото #{idx} — "
                f"{it.get('role','')}</div>"
                f"<div style='font-family:{MONO};font-size:20px;font-weight:700;"
                f"color:{color};'>{sc:.0f}/10 "
                f"<span style='font-size:13px;font-weight:400;'>{verdict}</span></div>",
                unsafe_allow_html=True)
            if it.get("good"):
                st.markdown(f"✅ {it['good']}")
            if it.get("issue"):
                st.markdown(f"⚠️ {it['issue']}")
            if it.get("fix"):
                st.markdown(f"🛠 {it['fix']}")
            if it.get("conversion"):
                st.markdown(f"🎯 {it['conversion']}")
            if it.get("emotion"):
                st.markdown(f"😶 {it['emotion']}")
        st.markdown("---")


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
        st.markdown(("✅ " if ok else "❌ ") + t(label)
                    + (f" — {note}" if note and not ok else ""))


def show_grade(grade: str, detail: str, score: int | None = None) -> None:
    color = OK_TEXT if grade in ("A", "B") else ACCENT
    score_part = (f"<span style='font-family:{MONO};color:{color};'> {score}/100</span>"
                  if score is not None else "")
    st.markdown(
        f"<div style='font-size:22px;font-weight:700;color:{INK};'>{t('photo.grade')} "
        f"<span style='color:{color};font-family:{MONO};'>{grade}</span>{score_part}"
        f"<span style='font-size:13px;color:{MUTED};font-weight:400;'> · {detail}"
        f"</span></div>", unsafe_allow_html=True)


def failed_reasons(res: dict, block: str,
                   checks: list[tuple[str, str]]) -> list[str]:
    data = res.get(block, {}) or {}
    return [t(label) for k, label in checks if data.get(k) is not True]



# ---------------------------------------------------------------- аудиты
@st.cache_data(ttl=120)
def load_audits() -> pd.DataFrame:
    """Последний аудит по каждому товару и типу — с полным результатом.

    Раньше результат жил только в session_state и пропадал при перезагрузке,
    из-за чего анализ приходилось гонять заново. Теперь читаем сохранённый.
    """
    try:
        df_a = pd.read_sql(
            """
            SELECT DISTINCT ON (asin, marketplace, analysis_type)
                   asin, marketplace, analysis_type, grade,
                   score_main, score_gallery, created_at, model,
                   designer_brief, images_analyzed, skill_version, raw
            FROM photo_analysis
            ORDER BY asin, marketplace, analysis_type, created_at DESC
            """,
            get_engine(),
        )
        return df_a
    except Exception:
        return pd.DataFrame()


def saved_result(audits: pd.DataFrame, asin: str, mp: str,
                 kind: str) -> tuple[dict | None, dict | None]:
    """Возвращает (результат анализа, метаданные) из сохранённого аудита."""
    row = audit_of(audits, asin, mp, kind)
    if row is None:
        return None, None
    raw = row.get("raw")
    try:
        res = raw if isinstance(raw, dict) else json.loads(raw or "{}")
    except Exception:
        return None, None
    if not res:
        return None, None
    meta = {
        "grade": row.get("grade"),
        "created_at": row.get("created_at"),
        "model": row.get("model"),
        "images": row.get("images_analyzed"),
        "skill_version": row.get("skill_version"),
    }
    return res, meta


def audit_of(audits: pd.DataFrame, asin: str, mp: str, kind: str):
    if audits.empty:
        return None
    row = audits[(audits["asin"] == asin) & (audits["marketplace"] == mp)
                 & (audits["analysis_type"] == kind)]
    return None if row.empty else row.iloc[0]


def grade_chip(g: str | None) -> str:
    if not g:
        return f'<span style="background:#F1EFE8;color:{MUTED};border-radius:7px;padding:2px 8px;font-size:11px;">без аудита</span>'
    color = OK_TEXT if g in ("A", "B") else ACCENT
    bg = "#DCEEE0" if g in ("A", "B") else "#FCE8DC"
    return (f'<span style="background:{bg};color:{color};border-radius:7px;'
            f'padding:2px 8px;font-size:11px;font-weight:600;">{g}</span>')


# ---------------------------------------------------------------- UI
st.caption(t("photo.caption"))

cands = load_candidates()
if cands.empty:
    st.info(t("common.no_data"))
    st.stop()

audits = load_audits()
skill_g, ver_g = load_skill("photo_brief")
skill_a, ver_a = load_skill("aplus")
gallery_ready = bool(skill_g) and ver_g > 0
aplus_ready = bool(skill_a) and ver_a > 0

if not gallery_ready or not aplus_ready:
    miss = []
    if not gallery_ready:
        miss.append("«Фото · ТЗ дизайнеру»")
    if not aplus_ready:
        miss.append("«A+ контент»")
    st.warning(f"{t('photo.methodology_missing')}: " + ", ".join(miss))
    st.page_link("pages/methodology.py", label=t("photo.goto_methodology"),
                 icon=":material/menu_book:")

# ---- фильтры
f1, f2, f3 = st.columns([2, 2, 1.6])
who = f1.segmented_control(
    "кто", ["all", "ours", "comp"], default="all",
    format_func=lambda k: {"all": t("catalog.all"), "ours": t("catalog.ours"),
                           "comp": t("catalog.competitors")}[k],
    selection_mode="single", label_visibility="collapsed", key="ph-who") or "all"
mps = sorted(cands["marketplace"].unique())
mp_sel = f2.multiselect("MP", mps, default=[], label_visibility="collapsed",
                        placeholder=t("list.all_mp"))
try:
    mode = f3.segmented_control(
        "вид", ["cards", "table"], default="cards",
        format_func=lambda k: t("list.cards") if k == "cards" else t("list.table"),
        selection_mode="single", label_visibility="collapsed", key="ph-mode")
except AttributeError:
    mode = f3.radio("вид", ["cards", "table"], horizontal=True,
                    label_visibility="collapsed", key="ph-mode")
mode = mode or "cards"

q1, q2 = st.columns([4, 2])
query = q1.text_input("Поиск", label_visibility="collapsed",
                      placeholder=t("catalog.search"))
only_new = q2.checkbox(t("work.untouched"))

view = cands.copy()
if who == "ours":
    view = view[~view["is_competitor"].fillna(False)]
elif who == "comp":
    view = view[view["is_competitor"].fillna(False)]
if mp_sel:
    view = view[view["marketplace"].isin(mp_sel)]
if query.strip():
    ql = query.strip().lower()
    view = view[
        view["asin"].str.lower().str.contains(ql, na=False)
        | view["sku_group"].astype(str).str.lower().str.contains(ql, na=False)
        | view["title"].astype(str).str.lower().str.contains(ql, na=False)
    ]

rows = []
for _, r in view.iterrows():
    imgs = extract_images(r["raw"])
    apl = extract_aplus(r["raw"])
    ag = audit_of(audits, r["asin"], r["marketplace"], "gallery")
    aa = audit_of(audits, r["asin"], r["marketplace"], "aplus")
    rows.append({"r": r, "imgs": imgs, "apl": apl,
                 "g_grade": None if ag is None else ag["grade"],
                 "a_grade": None if aa is None else aa["grade"],
                 "g_at": None if ag is None else ag["created_at"],
                 "a_at": None if aa is None else aa["created_at"]})

if only_new:
    rows = [x for x in rows if x["g_grade"] is None and x["a_grade"] is None]

if not rows:
    st.caption(t("catalog.nothing"))
    st.stop()

order = {"D": 0, "C": 1, "B": 2, "A": 3, None: 4}
rows.sort(key=lambda x: (order.get(x["g_grade"], 4), -len(x["imgs"])))
st.markdown(f"{len(rows)} {t('catalog.products')}")

# ---- таблица
if mode == "table":
    tv = pd.DataFrame([{
        "фото": (x["imgs"][0] if x["imgs"] else None),
        "SKU": x["r"]["sku_group"], "ASIN": x["r"]["asin"],
        "MP": x["r"]["marketplace"],
        "фото, шт": len(x["imgs"]), "A+, модулей": len(x["apl"]),
        "грейд галереи": x["g_grade"] or "—",
        "грейд A+": x["a_grade"] or "—",
        "аудит": (pd.to_datetime(x["g_at"]).strftime("%d.%m %H:%M")
                  if x["g_at"] is not None else "—"),
        "название": (x["r"]["title"] or "")[:70],
        "ссылка": f"https://www.amazon.{x['r']['marketplace']}/dp/{x['r']['asin']}",
    } for x in rows])
    st.dataframe(
        tv,
        column_config={
            "фото": st.column_config.ImageColumn("Фото", width="small"),
            "ссылка": st.column_config.LinkColumn("Листинг", display_text="открыть"),
        },
        hide_index=True, width="stretch", height=520)
    st.caption(t("list.sort_hint"))
    st.stop()

# ---- карточки
for x in rows:
    r, imgs, apl = x["r"], x["imgs"], x["apl"]
    asin, mp = r["asin"], r["marketplace"]
    sku = r["sku_group"] if r["sku_group"] and r["sku_group"] != asin else ""
    title = (r["title"] or "")[:70]
    fetched = (pd.to_datetime(r["fetched_at"]).strftime("%d.%m %H:%M")
               if pd.notna(r["fetched_at"]) else t("catalog.not_collected"))
    thumb = (
        f'<div style="flex:0 0 64px;"><img src="{imgs[0]}" '
        f'style="width:64px;height:64px;object-fit:contain;background:#fff;'
        f'border:1px solid {BORDER};border-radius:10px;"></div>'
    ) if imgs else ""
    edge = ("#A32D2D" if x["g_grade"] == "D"
            else ACCENT if x["g_grade"] == "C"
            else OK_TEXT if x["g_grade"] in ("A", "B") else BORDER)
    head_line = (
        f'{sku + " · " if sku else ""}'
        f'<a href="https://www.amazon.{mp}/dp/{asin}" target="_blank">{asin}</a>'
        f' · {MP_FLAG.get(mp, "")} {mp} · {t("matrix.collected_at")} {fetched}'
    )
    st.markdown(
        f'<div class="ls-card" style="background:{CARD};border:1px solid {BORDER};'
        f'border-left:3px solid {edge};border-radius:0 12px 12px 0;'
        f'padding:12px 16px;margin-bottom:4px;display:flex;gap:14px;'
        f'align-items:center;">'
        f'{thumb}'
        f'<div style="flex:1;min-width:0;">'
        f'{eyebrow(head_line)}'
        f'<div style="font-size:14px;color:{INK};margin:3px 0 6px;">{title}</div>'
        f'<span style="font-size:12px;color:{MUTED};">'
        f'{t("metric.photos")} {len(imgs)} · A+ {len(apl)}</span> '
        f'{grade_chip(x["g_grade"])} {grade_chip(x["a_grade"])}'
        f'</div></div>',
        unsafe_allow_html=True)

    with st.expander(f"Аудит · {asin}"):
        st.markdown(
            eyebrow(f"{t('synth.methodology')} v{ver_g} / v{ver_a}"),
            unsafe_allow_html=True)

        tab_g, tab_a = st.tabs([t("photo.tab_gallery"), t("photo.tab_aplus")])

        with tab_g:
            if imgs:
                per_row = 5
                for start in range(0, len(imgs), per_row):
                    cols = st.columns(per_row)
                    for i, url in enumerate(imgs[start:start + per_row]):
                        cols[i].image(url, width="stretch",
                                      caption=f"{start + i + 1}")
            else:
                st.warning(t("photo.no_images"))

            saved_g, meta_g = saved_result(audits, asin, mp, "gallery")
            has_saved_g = saved_g is not None
            btn_label_g = (t("photo.reanalyze_gallery") if has_saved_g
                           else t("photo.analyze_gallery"))
            if has_saved_g:
                st.caption(
                    f"{t('photo.audit_from')} "
                    f"{pd.to_datetime(meta_g['created_at']).strftime('%d.%m %H:%M')}"
                    f" · {meta_g.get('model') or ''}"
                    f" · методология v{meta_g.get('skill_version') or 0}"
                    f" · {meta_g.get('images') or 0} фото. "
                    + t("photo.audit_hint")
                )

            if st.button(btn_label_g, type="primary" if not has_saved_g else "secondary",
                         disabled=not imgs or not gallery_ready,
                         key=f"g-{asin}-{mp}"):
                _t0 = time.time()
                with st.spinner(f"{t('photo.looking')} {len(imgs)}..."):
                    res = analyze(
                        imgs, r["title"], mp, skill_g,
                        MAIN_CHECKS + GALLERY_CHECKS, "main",
                        "Первое изображение — ГЛАВНОЕ фото, остальные — галерея. "
                        "Ключи main_* относятся к главному фото, role_* и "
                        "gallery_* — к галерее в целом.")
                if res:
                    main = res.get("main", {}) or {}
                    m = sum(1 for k, _ in MAIN_CHECKS if main.get(k) is True)
                    g = sum(1 for k, _ in GALLERY_CHECKS if main.get(k) is True)
                    score = m / len(MAIN_CHECKS) * 0.6 + g / len(GALLERY_CHECKS) * 0.4
                    grade = grade_from(score)
                    save(asin, mp, res, grade, m, g, len(imgs), ver_g, "gallery")
                    st.session_state[f"res-g-{asin}-{mp}"] = (
                        res, grade, m, g, run_meta("photo_audit", time.time() - _t0))
                    cache.after_photo_audit()
                    load_audits.clear()

            saved = st.session_state.get(f"res-g-{asin}-{mp}")
            if not saved and has_saved_g:
                _main = saved_g.get("main", {}) or {}
                _m = sum(1 for k, _ in MAIN_CHECKS if _main.get(k) is True)
                _g = sum(1 for k, _ in GALLERY_CHECKS if _main.get(k) is True)
                saved = (saved_g, meta_g.get("grade") or grade_from(
                    _m / len(MAIN_CHECKS) * 0.6 + _g / len(GALLERY_CHECKS) * 0.4),
                    _m, _g,
                    f"{meta_g.get('model') or ''} · "
                    f"{pd.to_datetime(meta_g['created_at']).strftime('%d.%m %H:%M')}")
            if saved:
                res, grade, m, g, meta = saved
                st.divider()
                st.markdown(
                    eyebrow(f"{MP_FLAG.get(mp,'')} {mp} · {asin} · {meta}"),
                    unsafe_allow_html=True)
                show_grade(grade, f"{t('photo.main_photo')} {m}/{len(MAIN_CHECKS)} · "
                                  f"{t('photo.gallery_roles')} {g}/{len(GALLERY_CHECKS)}",
                           round((m / len(MAIN_CHECKS) * 0.6
                                  + g / len(GALLERY_CHECKS) * 0.4) * 100))
                fails = failed_reasons(res, "main", MAIN_CHECKS + GALLERY_CHECKS)
                if fails:
                    st.markdown(f"{t('photo.not_done')}: " + " · ".join(fails))
                c1, c2 = st.columns(2)
                with c1:
                    render_checks(res, "main", MAIN_CHECKS, t("photo.main_photo"))
                with c2:
                    render_checks(res, "main", GALLERY_CHECKS, t("photo.gallery_roles"))
                if res.get("designer_brief"):
                    st.markdown(f"**{t('photo.designer_brief')}**")
                    st.code(res["designer_brief"], language=None)
                render_per_photo(res, imgs)

        with tab_a:
            if apl:
                for i, url in enumerate(apl, 1):
                    st.image(url, width="stretch", caption=f"A+ {i}")
            else:
                # Модулей в снапшоте нет — но значит ли это, что A+ нет?
                # Стабилизированный признак отвечает точнее сырого: именно
                # здесь глюк ScrapingDog и виден — A+ есть, а модули
                # не пришли, и человеку надо пересобрать, а не рисовать A+.
                _sa = r.get("has_aplus")
                _has = (bool(_raw_dict(r.get("raw")).get("aplus"))
                        if pd.isna(_sa) else bool(_sa))
                if _has:
                    st.warning(t("photo.no_aplus_modules"))
                else:
                    st.info(t("photo.no_aplus"))

            saved_a_db, meta_a = saved_result(audits, asin, mp, "aplus")
            has_saved_a = saved_a_db is not None
            btn_label_a = (t("photo.reanalyze_aplus") if has_saved_a
                           else t("photo.analyze_aplus"))
            if has_saved_a:
                st.caption(
                    f"{t('photo.audit_from')} "
                    f"{pd.to_datetime(meta_a['created_at']).strftime('%d.%m %H:%M')}"
                    f" · {meta_a.get('model') or ''}"
                    f" · методология v{meta_a.get('skill_version') or 0}"
                )

            if st.button(btn_label_a,
                         type="primary" if not has_saved_a else "secondary",
                         disabled=not apl or not aplus_ready,
                         key=f"a-{asin}-{mp}"):
                _ta = time.time()
                with st.spinner(f"{t('photo.looking')} {len(apl)} A+..."):
                    res_a = analyze(apl, r["title"], mp, skill_a, APLUS_CHECKS,
                                    "aplus",
                                    "Это модули A+ контента листинга, "
                                    "по порядку сверху вниз.")
                if res_a:
                    block = res_a.get("aplus", {}) or {}
                    a = sum(1 for k, _ in APLUS_CHECKS if block.get(k) is True)
                    grade_a = grade_from(a / len(APLUS_CHECKS))
                    save(asin, mp, res_a, grade_a, a, 0, len(apl), ver_a, "aplus")
                    st.session_state[f"res-a-{asin}-{mp}"] = (
                        res_a, grade_a, a, run_meta("photo_audit", time.time() - _ta))
                    cache.after_photo_audit()
                    load_audits.clear()

            saved_a = st.session_state.get(f"res-a-{asin}-{mp}")
            if not saved_a and has_saved_a:
                _blk = saved_a_db.get("aplus", {}) or {}
                _n = sum(1 for k, _ in APLUS_CHECKS if _blk.get(k) is True)
                saved_a = (saved_a_db,
                           meta_a.get("grade") or grade_from(_n / len(APLUS_CHECKS)),
                           _n,
                           f"{meta_a.get('model') or ''} · "
                           f"{pd.to_datetime(meta_a['created_at']).strftime('%d.%m %H:%M')}")
            if saved_a:
                res_a, grade_a, a, meta_a_txt = saved_a
                st.divider()
                st.markdown(
                    eyebrow(f"{MP_FLAG.get(mp,'')} {mp} · {asin} · {meta_a_txt}"),
                    unsafe_allow_html=True)
                show_grade(grade_a, f"{a}/{len(APLUS_CHECKS)}",
                           round(a / len(APLUS_CHECKS) * 100))
                fails_a = failed_reasons(res_a, "aplus", APLUS_CHECKS)
                if fails_a:
                    st.markdown(f"{t('photo.not_done')}: " + " · ".join(fails_a))
                render_checks(res_a, "aplus", APLUS_CHECKS, t("photo.tab_aplus"))
                if res_a.get("designer_brief"):
                    st.markdown(f"**{t('photo.designer_brief')}**")
                    st.code(res_a["designer_brief"], language=None)
                render_per_photo(res_a, apl) 
