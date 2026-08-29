# -*- coding: utf-8 -*-
"""
pages/synthesis.py — Синтез: Split 75/125. v2.

Что нового в v2:
- Методология берётся из listing_data.synthesis_skill (активная версия,
  правится на странице «Методология» без коммитов кода).
- Защищённые фразы (protected_keywords): чипы + добавление/удаление
  прямо здесь; передаются в промпт, после генерации проверяются кодом.
- Пост-проверки по официальным правилам Amazon: длина, запрещённые
  символы, повторы слов, наличие must-keep фраз, отсутствие forbid-фраз.
- Черновик сохраняется в synthesis_drafts со skill_version.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from difflib import SequenceMatcher

import pandas as pd
import streamlit as st

from config import TITLE_LIMIT as _TL_DEFAULT, HIGHLIGHTS_LIMIT as _HL_DEFAULT
from i18n import t, mp_label
from services.db import get_conn, cfg, get_engine
from services.settings import get_setting, get_int
from services.ai import (
    generate_json, task_config, no_credit_banner, last_call_error,
    reset_usage, usage_totals,
)
from services.economics import econ_map, money_at_risk, fmt_money
from services.serp import (
    readability, facts_extracted, render_serp_row,
    render_first_glance, render_ai_view, load_competitors, esc,
    VISIBLE_MOBILE, VISIBLE_DESKTOP,
)
from services.seo import (
    build_keyword_table, coverage, compress_phrase, phrase_present,
    sqp_error, TIER_LABEL, TIER_COLOR, TIERS,
)
from services.flatfile import (
    load_accepted_titles, plan_export, plan_signature, build_flat_cached,
    build_csv_export,
)
from services.spapi import (
    missing_secrets, marketplace_meta, push_title, log_push, load_pushes,
    issues_text,
)
from services.history import (
    load_history, summary as history_summary, stamp as history_stamp,
    load_error as history_error,
)
from components.ui import inject_fonts, eyebrow, limit_ruler_html

inject_fonts()
st.title(t("nav.synthesis"))

# Провайдер и модель задачи «сплит тайтла» — из настроек, на каждой
# перерисовке. Раньше пара звалась GEMINI_MODEL, хотя задачу мог выполнять
# Anthropic: имя врало и мешало показать в интерфейсе, чем на самом деле
# сгенерирован черновик.
TITLE_PROVIDER, TITLE_MODEL = task_config("title_split")
TITLE_LIMIT = get_int("limit.title", _TL_DEFAULT)
HIGHLIGHTS_LIMIT = get_int("limit.highlights", _HL_DEFAULT)

FORBIDDEN_CHARS = set("!$?_{}^¬¦®©™")
ACCENT = "#E8590C"
INK = "#1A1815"
MUTED = "#57534A"

# Промпт разделён на постоянную и переменную часть намеренно.
#
# Постоянная (SYSTEM_PROMPT) — методология и правила: одинакова для всех
# товаров партии. Переменная (USER_PROMPT) — исходный тайтл, маркетплейс
# и фразы: своя у каждого товара.
#
# Кэш Anthropic — это совпадение ПРЕФИКСА в порядке tools → system →
# messages. Пока методология лежала внутри общего текста вперемешку
# с данными товара, префикс менялся на каждом товаре и кэшироваться было
# нечему: партия из 20 обрабатывала методологию 20 раз.
#
# Версия методологии подставляется в первую строку system осознанно: если
# скилл перевыпустят, байты префикса изменятся и старый кэш перестанет
# читаться сам собой. Без этой строки два разных скилла с совпадающим
# текстом дали бы один кэш.
SYSTEM_PROMPT = """Ты эксперт по Amazon-листингам бренда Dnipro-M.

МЕТОДОЛОГИЯ (версия {skill_version}, следуй ей строго):
{skill_text}

ЗАДАЧА — сплит с сохранением поискового веса, а не просто обрезка:
- title: целься в {title_target} символов. ЖЁСТКИЙ лимит {title_limit},
  два символа — запас, промах по лимиту делает результат непригодным
- highlights: целься в {highlights_target}, жёсткий лимит {highlights_limit}
- dropped — что выброшено на ревью человеку

ПОРЯДОК ПРИОРИТЕТОВ:
1. Фразы MUST KEEP обязаны попасть в title дословно — по ним идут реальные покупки.
2. Фразы PREFERRED — в title, если помещаются; иначе в highlights.
3. Фразы COMPRESS можно сокращать без потери смысла: 1500 mAh → 1,5 Ah,
   milímetros → mm, Newton-metros → Nm, voltios → V. Сокращай, а не выбрасывай.
4. Фразы FORBID не должны появиться ни в title, ни в highlights.
5. Всё, что не влезло, перечисли в dropped — человек решит.
6. КОНВЕРСИЯ ВАЖНЕЕ ПОКАЗОВ. У фраз в скобках указаны покупки за 4 недели
   и конверсия (покупки / клики). Когда две фразы близки по весу и обе
   не помещаются, оставляй ту, у которой есть покупки: она приводит деньги,
   а фраза без покупок только собирает показы. Фразу с покупками не сокращай
   и не выбрасывай в пользу фразы с нулём покупок.

7. ДЛИНА — ЖЁСТКОЕ ТРЕБОВАНИЕ. Прежде чем выдать ответ, посчитай длину
   title и highlights В СИМВОЛАХ (с пробелами). Если хоть одна больше
   лимита — сократи и пересчитай заново, и так пока не уложишься.
   Сокращай за счёт менее ценных слов, а не за счёт фраз MUST KEEP.

Ответь ТОЛЬКО валидным JSON без markdown:
{{"title": "...", "highlights": "...", "dropped": ["...", "..."]}}"""

# переменная часть: всё, что своё у каждого товара
USER_PROMPT = """{keywords_block}Исходный тайтл (маркетплейс {marketplace}):
{title}"""


def build_system(skill_text: str, skill_ver: int) -> str:
    """Постоянная часть промпта. Байты обязаны совпадать от товара к товару,
    иначе кэшировать нечего."""
    return SYSTEM_PROMPT.format(
        skill_version=skill_ver,
        skill_text=skill_text.replace("{title_limit}", str(TITLE_LIMIT))
                             .replace("{highlights_limit}", str(HIGHLIGHTS_LIMIT)),
        title_limit=TITLE_LIMIT,
        highlights_limit=HIGHLIGHTS_LIMIT,
        title_target=max(1, TITLE_LIMIT - LENGTH_MARGIN),
        highlights_target=max(1, HIGHLIGHTS_LIMIT - LENGTH_MARGIN),
    )


# ---------------------------------------------------------------- загрузка

@st.cache_data(ttl=300)
def load_candidates() -> pd.DataFrame:
    try:
        df = pd.read_sql(
            """
            SELECT DISTINCT ON (d.asin, d.marketplace)
                   d.asin, d.marketplace, s.title, s.fetched_at,
                   s.main_image, m.sku_group
            FROM diagnosis d
            JOIN LATERAL (
                SELECT title, fetched_at, raw->>'main_image' AS main_image
                FROM listing_snapshots s
                WHERE s.asin = d.asin AND s.marketplace = d.marketplace
                  AND s.ok = TRUE AND s.title <> ''
                ORDER BY s.fetched_at DESC LIMIT 1
            ) s ON TRUE
            LEFT JOIN product_matrix m
                   ON m.asin = d.asin AND m.marketplace = d.marketplace
            WHERE d.rule_id = 'title_over_limit'
            ORDER BY d.asin, d.marketplace, d.created_at DESC
            """,
            get_engine(),
        )
        return df
    except Exception:
        return pd.DataFrame()


SKILL_ERR_KEY = "synth.skill_error"


def skill_error() -> str | None:
    """Почему методология не прочиталась, если не прочиталась."""
    try:
        return st.session_state.get(SKILL_ERR_KEY)
    except Exception:
        return None


def _remember_skill_error(text: str | None) -> None:
    try:
        if text is None:
            st.session_state.pop(SKILL_ERR_KEY, None)
        else:
            st.session_state[SKILL_ERR_KEY] = text
    except Exception:
        pass


@st.cache_data(ttl=120)
def load_skill() -> tuple[str, int]:
    """Общая методология (common) + title_split, склеенные.
    Версия в подписи — от title_split.

    ЗАПАСНОЙ МЕТОДОЛОГИИ ЗДЕСЬ НЕТ И БЫТЬ НЕ ДОЛЖНО. Раньше при любом сбое
    возвращался зашитый текст «Бренд Dnipro-M первым» — то есть правило,
    ПРОТИВОПОЛОЖНОЕ действующей v8, где бренд в тайтле запрещён. Подмена шла
    молча, генерация выглядела нормальной, и в тайтлы возвращался бренд,
    который Amazon всё равно вырезает.

    Пустой текст и версия 0 означают «методологии нет». Генерация с таким
    ответом не запускается — см. generate_split.
    """
    try:
        df = pd.read_sql(
            """
            SELECT DISTINCT ON (scope) scope, skill_text, version
            FROM synthesis_skill
            WHERE is_active = TRUE AND scope IN ('common', 'title_split')
            ORDER BY scope, version DESC
            """,
            get_engine(),
        )
        if not df.empty:
            parts: list[str] = []
            version = 0
            common = df[df["scope"] == "common"]
            spec = df[df["scope"] == "title_split"]
            if not common.empty:
                parts.append(str(common.iloc[0]["skill_text"]))
            if not spec.empty:
                parts.append(str(spec.iloc[0]["skill_text"]))
                version = int(spec.iloc[0]["version"])
            if parts and version > 0:
                _remember_skill_error(None)
                return "\n\n".join(parts), version
            # строка есть, а активной версии title_split нет — это тоже
            # «методологии нет», а не «версия ноль»
            _remember_skill_error(t("synth.skill_missing"))
            return "", 0
    except Exception as e:
        _remember_skill_error(f"{type(e).__name__}: {e}")
        return "", 0
    _remember_skill_error(t("synth.skill_missing"))
    return "", 0


def load_keywords(asin: str, mp: str) -> pd.DataFrame:
    try:
        df = pd.read_sql(
            """
            SELECT id, phrase, phrase_type, source FROM protected_keywords
            WHERE asin = %(asin)s AND marketplace = %(mp)s
            ORDER BY phrase_type, phrase
            """,
            get_engine(), params={"asin": asin, "mp": mp},
        )
        return df
    except Exception:
        return pd.DataFrame()


# ---------------------------------------------------------------- генерация

def kw_metrics(kw_df: pd.DataFrame | None) -> dict:
    """фраза -> (покупки, клики). Таблица приходит в двух видах: как её
    отдаёт services.seo (search_query / purchases / clicks) и как её
    переименовал kw_editor для показа (phrase / pur / clk)."""
    if kw_df is None or kw_df.empty:
        return {}
    cols = kw_df.columns
    p_col = "search_query" if "search_query" in cols else "phrase"
    pur_col = "purchases" if "purchases" in cols else "pur"
    clk_col = "clicks" if "clicks" in cols else "clk"
    if p_col not in cols or pur_col not in cols:
        return {}
    out = {}
    for _, r in kw_df.iterrows():
        pur = r.get(pur_col)
        clk = r.get(clk_col)
        out[str(r[p_col])] = (
            0.0 if pd.isna(pur) else float(pur),
            0.0 if clk is None or pd.isna(clk) else float(clk),
        )
    return out


def phrase_line(phrase: str, metrics: dict) -> str:
    """«фраза (покупок 12, конверсия 8,0%)» — конверсионный сигнал модели.

    Конверсия = покупки / клики: фраза может собирать показы и клики, но
    не приводить заказы, и при равном весе она должна уступать."""
    m = metrics.get(phrase)
    if not m:
        return phrase
    pur, clk = m
    if pur <= 0:
        return f"{phrase} (покупок 0)"
    if clk > 0:
        conv = f"{pur / clk * 100:.1f}".replace(".", ",")
        return f"{phrase} (покупок {int(pur)}, конверсия {conv}%)"
    return f"{phrase} (покупок {int(pur)})"


TOP_PHRASES = 25


def _trim_phrases(keep: list[str], kw_df: pd.DataFrame | None) -> list[str]:
    """Топ-25 по весу + все must_keep, порядок исходного списка сохраняем.

    Без таблицы обрезаем просто по числу: длинный список фраз раздувает
    промпт и отъедает бюджет ответа."""
    if len(keep) <= TOP_PHRASES:
        return keep
    if kw_df is None or kw_df.empty:
        return keep[:TOP_PHRASES]
    cols = kw_df.columns
    p_col = "search_query" if "search_query" in cols else "phrase"
    w_col = "weight" if "weight" in cols else "w"
    if p_col not in cols or w_col not in cols or "tier" not in cols:
        return keep[:TOP_PHRASES]
    ranked = kw_df.sort_values(w_col, ascending=False)
    top = {str(p) for p in ranked[p_col].head(TOP_PHRASES)}
    must = {str(p) for p, tier in zip(ranked[p_col], ranked["tier"])
            if tier == "must_keep"}
    allowed = top | must
    return [p for p in keep if p in allowed]


def generate_split(title: str, marketplace: str,
                   skill_text: str, keep: list[str], forbid: list[str],
                   kw_df: pd.DataFrame | None = None,
                   retry_note: str = "",
                   skill_ver: int = 0) -> dict | None:
    """Генерация сплита. Провайдер и модель — из Настроек (задача title_split).

    kw_df — таблица фраз с фактами SQP: из неё в промпт уходят покупки
    и конверсия по каждой фразе, чтобы модель при выборе между фразами
    близкого веса предпочитала конвертирующие."""
    # Промпт держим компактным: в него уходит топ-25 фраз по весу плюс ВСЕ
    # must_keep (по ним идут покупки, терять нельзя даже если вес мал).
    # Раньше уходила вся таблица — это раздувало запрос и съедало бюджет.
    metrics = kw_metrics(kw_df)
    keep = _trim_phrases(keep, kw_df)
    kw_lines = []
    if keep:
        # про скобки говорим только когда метрики есть: без SQP их не будет,
        # и обещание в промпте оказалось бы ложным
        head = ("ОБЯЗАТЕЛЬНО сохрани дословно (в title или highlights); "
                "в скобках — покупки за 4 недели и конверсия (покупки/клики): "
                if metrics else
                "ОБЯЗАТЕЛЬНО сохрани дословно (в title или highlights): ")
        kw_lines.append(head + "; ".join(phrase_line(p, metrics) for p in keep))
    if forbid:
        kw_lines.append("ЗАПРЕЩЕНО использовать: " + "; ".join(forbid))
    keywords_block = ("\n".join(kw_lines) + "\n\n") if kw_lines else ""

    # Версия 0 или пустой текст — это «методологию не прочитали», а не
    # «методология такая». Генерировать в этом случае нельзя: раньше здесь
    # подставлялся зашитый текст с прямо противоположным правилом.
    if not str(skill_text or "").strip() or int(skill_ver or 0) <= 0:
        st.error("⚠ " + t("synth.skill_failed",
                          e=skill_error() or t("synth.skill_missing")))
        return None

    prompt = USER_PROMPT.format(keywords_block=keywords_block,
                                marketplace=marketplace, title=title)
    # автоповтор — тоже переменная часть: он свой у каждой попытки,
    # в system ему нельзя, там он ломал бы кэш всей партии
    if retry_note:
        prompt += "\n\n" + retry_note
    return generate_json("title_split", prompt, timeout=120,
                         system=build_system(skill_text, skill_ver))


LENGTH_MARGIN = 2      # запас к лимиту, который просим у модели
MAX_ATTEMPTS = 3       # первая попытка + два автоповтора


def trim_to_word(text: str, limit: int) -> str:
    """Обрезка строго по границе слова, никогда посреди слова.

    Хвостовую пунктуацию и разделители убираем: «…1650W ·» выглядит
    как обрыв, а не как законченный тайтл."""
    if len(text) <= limit:
        return text
    cut = text[:limit + 1]
    if " " in cut:
        cut = cut[:cut.rindex(" ")]
    else:
        cut = cut[:limit]           # одно слово длиннее лимита — режем как есть
    return cut.rstrip(" ,;·—–-|/")


def keeps_all(text: str, hl: str, keep: list[str]) -> bool:
    """Все must_keep-фразы по-прежнему на месте (в title или highlights)."""
    combined = f"{text} {hl}"
    return all(phrase_present(p, combined) for p in keep)


def enforce_limits(res: dict, must_keep: list[str]) -> tuple[dict, dict]:
    """Последний рубеж: режем сами, но только если не теряем must_keep.

    Возвращает (результат, отметки). Если обрезка убивает обязательную
    фразу — НЕ режем: пусть человек правит руками, это честнее, чем
    молча выбросить фразу, по которой идут покупки."""
    marks = {"trimmed": [], "over": []}
    out = dict(res)
    for field, limit, key in (("title", TITLE_LIMIT, "title"),
                              ("highlights", HIGHLIGHTS_LIMIT, "highlights")):
        val = str(out.get(field) or "")
        if len(val) <= limit:
            continue
        cand = trim_to_word(val, limit)
        probe = dict(out)
        probe[field] = cand
        if cand and keeps_all(str(probe.get("title") or ""),
                              str(probe.get("highlights") or ""), must_keep):
            out[field] = cand
            marks["trimmed"].append(key)
        else:
            marks["over"].append(key)
    return out, marks


def over_limits(res: dict) -> list[str]:
    """Какие поля не влезли в лимит — для решения о повторе."""
    bad = []
    if len(str(res.get("title") or "")) > TITLE_LIMIT:
        bad.append(f"title {len(str(res.get('title') or ''))}/{TITLE_LIMIT}")
    if len(str(res.get("highlights") or "")) > HIGHLIGHTS_LIMIT:
        bad.append("highlights "
                   f"{len(str(res.get('highlights') or ''))}/{HIGHLIGHTS_LIMIT}")
    return bad


def retry_note(res: dict) -> str:
    """Указание на повтор: насколько именно промахнулись и что делать."""
    lines = []
    for field, limit in (("title", TITLE_LIMIT),
                         ("highlights", HIGHLIGHTS_LIMIT)):
        n = len(str(res.get(field) or ""))
        if n > limit:
            lines.append(
                f"Предыдущий вариант {field} был {n} символов при лимите "
                f"{limit} — сократи РОВНО на {n - limit + LENGTH_MARGIN} "
                "символов. Не добавляй новых слов, только убирай лишние "
                "и сокращай единицы измерения.")
    return "ПОВТОР. " + " ".join(lines) if lines else ""


def generate_guarded(title: str, marketplace: str, skill_text: str,
                     keep: list[str], forbid: list[str],
                     kw_df: pd.DataFrame | None,
                     must_keep: list[str],
                     skill_ver: int = 0,
                     on_step=None) -> tuple[dict | None, dict]:
    """Генерация с гарантией длины: до трёх попыток, затем обрезка.

    Модель промахивается по длине (77 при лимите 75), и человеку
    приходилось жать «Перегенерировать» руками. Теперь: просим с запасом,
    при промахе повторяем с точным указанием на сколько сократить,
    и только после трёх неудач режем сами — по границе слова и не теряя
    must_keep. Возвращает (результат, статистика).

    on_step(kind, **kw) — необязательный обратный вызов для показа хода.
    Автоповторы дольше всего, и раньше они шли молча: человек видел
    замерший экран и не знал, работа идёт или подвисло.
    """
    stats = {"attempts": 0, "retried": 0, "trimmed": 0, "over": 0}
    res = None
    note = ""

    def step(kind: str, **kw) -> None:
        if on_step:
            try:
                on_step(kind, **kw)
            except Exception:
                pass    # показ хода не имеет права ронять генерацию

    for attempt in range(1, MAX_ATTEMPTS + 1):
        stats["attempts"] += 1
        step("generating", attempt=attempt)
        res = generate_split(title, marketplace, skill_text, keep, forbid,
                             kw_df=kw_df, retry_note=note,
                             skill_ver=skill_ver)
        if res is None:
            step("failed")
            return None, stats
        step("checking")
        if not over_limits(res):
            step("done")
            return res, stats
        if attempt < MAX_ATTEMPTS:
            stats["retried"] += 1
            note = retry_note(res)
            step("retry", attempt=attempt + 1, total=MAX_ATTEMPTS,
                 over=max(len(str(res.get("title") or "")) - TITLE_LIMIT,
                          len(str(res.get("highlights") or ""))
                          - HIGHLIGHTS_LIMIT))

    step("trimming")
    res, marks = enforce_limits(res, must_keep)
    if marks["trimmed"]:
        stats["trimmed"] = 1
        res["trimmed_fields"] = marks["trimmed"]
    if marks["over"]:
        stats["over"] = 1
        res["over_fields"] = marks["over"]
    step("done")
    return res, stats


def run_checks(new_title: str, new_hl: str,
               keep: list[str], forbid: list[str]) -> list[tuple[bool, str]]:
    """Пост-проверки кодом. Возвращает [(ok, сообщение), ...]."""
    checks: list[tuple[bool, str]] = []
    combined = f"{new_title} {new_hl}".lower()

    checks.append((len(new_title) <= TITLE_LIMIT,
                   t("chk.title_len", n=len(new_title), min=TITLE_LIMIT)))
    checks.append((len(new_hl) <= HIGHLIGHTS_LIMIT,
                   t("chk.hl_len", n=len(new_hl), min=HIGHLIGHTS_LIMIT)))

    bad_chars = sorted({c for c in new_title if c in FORBIDDEN_CHARS})
    checks.append((not bad_chars,
                   t("chk.forbidden_chars") + ": " + (" ".join(bad_chars)
                    if bad_chars else t("chk.none"))))

    words = re.findall(r"[a-zA-Zа-яА-ЯёЁáéíóúñüÁÉÍÓÚÑÜäöüßÄÖÜ0-9]+", new_title.lower())
    stop = {"de", "con", "para", "y", "el", "la", "und", "mit", "für", "et", "avec", "e", "con", "per"}
    over_words = sorted({w for w in words
                         if len(w) > 2 and w not in stop and words.count(w) > 2})
    checks.append((not over_words,
                   t("chk.word_repeats") + ": " + (", ".join(over_words)
                    if over_words else t("chk.none"))))

    for ph in keep:
        checks.append((ph.lower() in combined, f"{t('chk.phrase_kept')}: «{ph}»"))
    for ph in forbid:
        checks.append((ph.lower() not in combined, f"{t('chk.phrase_absent')}: «{ph}»"))

    return checks


def save_draft(asin: str, mp: str, original: str, result: dict, skill_version: int) -> bool:
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO synthesis_drafts
                    (asin, marketplace, original_title, new_title,
                     new_highlights, dropped_words, model, skill_version, raw)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (asin, mp, original,
                 result.get("title", ""),
                 result.get("highlights", ""),
                 ", ".join(result.get("dropped", [])),
                 TITLE_MODEL, skill_version,
                 json.dumps(result, ensure_ascii=False)),
            )
        conn.close()
        st.session_state.pop(f"save-err-{asin}-{mp}", None)
        return True
    except Exception as e:
        # текст кладём в session_state: st.warning не переживает st.rerun(),
        # а именно так провал сохранения и оставался незамеченным
        detail = f"{type(e).__name__}: {e}"
        st.session_state[f"save-err-{asin}-{mp}"] = detail
        st.warning(t("common.save_failed", e=detail))
        return False


# ---------------------------------------------------------------- UI


@st.cache_data(ttl=60)
def load_draft_stats() -> dict:
    """История работы по товару: черновики, Coverage и их место во времени
    относительно принятой правки.

    Голое «сгенерировано 7» не отвечает на единственный важный вопрос — принято
    или нет. Поэтому считаем ещё, сколько черновиков было ДО принятия и
    сколько появилось ПОСЛЕ: первое говорит, сколько заходов понадобилось,
    второе — что человек пересматривает уже принятое.

    Слова «отклонено» здесь быть не может: отказ мы нигде не пишем, в
    synthesis_changes попадает только принятое. Черновик, не ставший
    правкой, — это перегенерация или брошенная работа, а не отклонение.
    """
    try:
        df = pd.read_sql(
            """
            WITH acc AS (
                SELECT DISTINCT ON (asin, marketplace)
                       asin, marketplace, accepted_at, model
                FROM synthesis_changes
                WHERE status = 'accepted' AND change_type = 'title_split'
                ORDER BY asin, marketplace, accepted_at DESC
            )
            SELECT d.asin, d.marketplace, count(*) AS drafts,
                   max(c.coverage_score) AS coverage,
                   count(*) FILTER (WHERE a.accepted_at IS NOT NULL
                                      AND d.created_at < a.accepted_at)
                       AS before_accept,
                   count(*) FILTER (WHERE a.accepted_at IS NOT NULL
                                      AND d.created_at > a.accepted_at)
                       AS after_accept,
                   max(a.accepted_at) AS accepted_at,
                   max(d.model) AS last_model
            FROM synthesis_drafts d
            LEFT JOIN synthesis_coverage c
                   ON c.asin = d.asin AND c.marketplace = d.marketplace
            LEFT JOIN acc a
                   ON a.asin = d.asin AND a.marketplace = d.marketplace
            GROUP BY d.asin, d.marketplace
            """, get_engine())
        return {(r["asin"], r["marketplace"]): r.to_dict()
                for _, r in df.iterrows()}
    except Exception:
        return {}


@st.cache_data(ttl=60)
def load_accepted() -> dict:
    """Принятые правки: (asin, mp) -> дата и статус."""
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT DISTINCT ON (asin, marketplace)
                   asin, marketplace, accepted_at, status, after_len,
                   coverage_score, model, after_text, after_extra
            FROM synthesis_changes
            ORDER BY asin, marketplace, accepted_at DESC
            """, get_engine())
        conn.close()
        return {(r["asin"], r["marketplace"]): r.to_dict()
                for _, r in df.iterrows()}
    except Exception:
        return {}


def accept_change(asin: str, mp: str, before: str, result: dict,
                  coverage_score, skill_version: int, model: str,
                  source: str = "ai") -> bool:
    """Фиксирует принятый сплит — цикл замыкается здесь.

    Дальше эта запись используется экраном «До / после»: сравнение
    sessions и продаж до правки и после.

    source отделён от model намеренно: model говорит, чем СГЕНЕРИРОВАН
    черновик, и остаётся верным после ручной правки, а source — принят
    текст как есть или переписан человеком. Смешав их, мы бы либо врали
    про модель, либо потеряли долю ручных правок — а это и есть мера
    того, насколько методология попадает.
    """
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO synthesis_changes
                    (asin, marketplace, change_type, before_text, before_len,
                     after_text, after_len, after_extra, after_extra_len,
                     dropped, coverage_score, skill_version, model, status,
                     source)
                VALUES (%s,%s,'title_split',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                        'accepted',%s)
                """,
                (asin, mp, before, len(before or ""),
                 result.get("title", ""), len(result.get("title", "")),
                 result.get("highlights", ""), len(result.get("highlights", "")),
                 "; ".join(result.get("dropped", []) or []),
                 coverage_score, skill_version, model, source))
        conn.close()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(t("common.save_failed", e=e))
        return False


@st.cache_data(ttl=30)
def load_drafts_for_review() -> pd.DataFrame:
    """Черновики без принятой правки — очередь на разбор."""
    try:
        df = pd.read_sql(
            """
            SELECT DISTINCT ON (d.asin, d.marketplace)
                   d.id, d.asin, d.marketplace, d.created_at,
                   d.original_title AS title_before,
                   d.new_title      AS title_after,
                   d.new_highlights AS highlights_after,
                   d.dropped_words  AS dropped,
                   d.model, d.skill_version, c.coverage_score
            FROM synthesis_drafts d
            LEFT JOIN LATERAL (
                SELECT coverage_score FROM synthesis_coverage c
                WHERE c.asin = d.asin AND c.marketplace = d.marketplace
                ORDER BY c.created_at DESC LIMIT 1
            ) c ON TRUE
            WHERE NOT EXISTS (
                SELECT 1 FROM synthesis_changes sc
                WHERE sc.asin = d.asin AND sc.marketplace = d.marketplace
                  AND sc.change_type = 'title_split'
            )
            ORDER BY d.asin, d.marketplace, d.created_at DESC
            """, get_engine())
        return df
    except Exception:
        return pd.DataFrame()


def draft_quality(cov, checks_failed: int) -> tuple[str, str]:
    """Зелёный — принимать бегло, красный — смотреть глазами."""
    try:
        v = float(cov) if cov is not None and not pd.isna(cov) else None
    except (TypeError, ValueError):
        v = None
    if checks_failed:
        return "red", t("draft.checks_failed")
    if v is None:
        return "amber", t("draft.no_coverage")
    if v < 70:
        return "red", t("draft.low_coverage", n=int(v))
    if v >= 85:
        return "green", f"Coverage {v:.0f}%"
    return "amber", f"Coverage {v:.0f}%"


def save_coverage(asin: str, mp: str, cov: dict) -> None:
    if cov.get("score") is None:
        return
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO synthesis_coverage
                    (asin, marketplace, coverage_score, weight_total,
                     weight_kept, kept_phrases, lost_phrases)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (asin, mp, cov["score"], cov["weight_total"], cov["weight_kept"],
                 "; ".join(p for p, _, _ in cov["kept"][:30]),
                 "; ".join(p for p, _, _ in cov["lost"][:30])))
        conn.close()
    except Exception:
        pass


def batch_generate(items: list, skill_text: str, skill_version: int) -> dict:
    """Пакетная генерация: только черновики, ничего не применяется."""
    done, failed, unsaved = 0, 0, 0
    stats = {"attempts": 0, "retried": 0, "trimmed": 0, "over": 0}
    errors: list[str] = []
    # счётчик токенов обнуляем: иначе к цифрам этой партии прибавится
    # расход прошлой и «прочитано из кэша» будет выглядеть лучше, чем есть
    reset_usage()
    bar = st.progress(0.0, text=t("synth.batch_run"))
    line = st.empty()

    def _tick(i: int, asin: str, mp: str, sku: str) -> None:
        """Числа и текущий товар. Голое «[7/20]» не отвечало на вопрос,
        сколько из пройденных реально легло в базу."""
        bar.progress(i / len(items),
                     text=t("gen.batch", i=i, n=len(items), done=done,
                            skipped=failed + unsaved))
        line.caption(f"{sku + ' · ' if sku else ''}{asin} · {mp}")

    for i, x in enumerate(items, 1):
        r = x["r"]
        asin, mp, title = r["asin"], r["marketplace"], r["title"] or ""
        _tick(i, asin, mp, str(r.get("sku_group") or ""))
        kw = build_keyword_table(asin, mp, title)
        # Пустая таблица фраз бывает по двум причинам, и они требуют
        # разного: «SQP по товару нет» — генерируем по методологии,
        # «SQP не прочитался» — не генерируем вовсе. Во втором случае
        # ушла бы партия без единой must_keep фразы и без forbid,
        # а проверка keeps_all на пустом списке прошла бы сама собой.
        _sqp_err = sqp_error()
        if kw.empty and _sqp_err:
            failed += 1
            errors.append(f"{asin} ({mp}): " + t("synth.sqp_failed",
                                                 e=_sqp_err))
            continue
        keep, forbid = [], []
        if not kw.empty:
            keep = kw.loc[kw["tier"].isin(["must_keep", "preferred"]),
                          "search_query"].tolist()
            forbid = kw.loc[kw["tier"] == "forbid", "search_query"].tolist()
        must = (kw.loc[kw["tier"] == "must_keep", "search_query"].tolist()
                if not kw.empty else [])
        try:
            res, st_one = generate_guarded(title, mp, skill_text, keep, forbid,
                                           kw, must, skill_version)
            for k in stats:
                stats[k] += st_one.get(k, 0)
        except Exception as e:
            # раньше здесь было `except Exception: res = None` — причина
            # провала терялась без следа
            res = None
            errors.append(f"{asin} ({mp}): {type(e).__name__}: {e}")
        if res:
            # считаем именно сохранение: раньше done увеличивался после
            # генерации, и партия рапортовала «5 готово» при пустой таблице
            if save_draft(asin, mp, title, res, skill_version):
                if not kw.empty:
                    save_coverage(asin, mp, coverage(
                        kw, res.get("title", ""), res.get("highlights", "")))
                done += 1
            else:
                unsaved += 1
                err = st.session_state.get(f"save-err-{asin}-{mp}")
                errors.append(f"{asin} ({mp}): "
                              + t("synth.save_failed_short")
                              + (f" — {err}" if err else ""))
        else:
            failed += 1
            # ошибку уже показал слой ИИ, но st.rerun() её сотрёт —
            # забираем текст с собой, чтобы показать после перерисовки
            err = last_call_error()
            if err and (not errors or errors[-1] != f"{asin} ({mp}): {err}"):
                errors.append(f"{asin} ({mp}): {err}")
    bar.empty()
    line.empty()
    usage = usage_totals()
    st.cache_data.clear()
    return {"done": done, "failed": failed, "unsaved": unsaved,
            "errors": errors, "stats": stats, "usage": usage}


@st.cache_data(ttl=300)
def load_all_products() -> pd.DataFrame:
    """Все товары матрицы со свежим снапшотом — для работы с любым тайтлом,
    а не только с теми, у кого сработало правило title_over_limit."""
    try:
        df = pd.read_sql(
            """
            SELECT m.asin, m.marketplace, m.sku_group,
                   s.title, s.fetched_at, s.main_image
            FROM product_matrix m
            LEFT JOIN LATERAL (
                SELECT title, fetched_at, raw->>'main_image' AS main_image
                FROM listing_snapshots s
                WHERE s.asin = m.asin AND s.marketplace = m.marketplace
                  AND s.ok = TRUE AND s.title <> ''
                ORDER BY s.fetched_at DESC LIMIT 1
            ) s ON TRUE
            WHERE m.is_competitor = FALSE
            ORDER BY m.sku_group, m.asin, m.marketplace
            """, get_engine())
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_sqp_coverage() -> set:
    """Товары, по которым Brand Analytics реально загружен.

    Раньше состояние определялось по наличию трафика — из-за этого строка
    могла утверждать «SQP собран», а таблица фраз оказывалась пустой.
    """
    try:
        df = pd.read_sql(
            "SELECT DISTINCT asin, marketplace FROM sqp_reports", get_engine())
        return set(zip(df["asin"], df["marketplace"]))
    except Exception:
        return set()


# Колонки таблицы фраз: технические имена, подписи — в column_config.
# Иначе при переводе получаются дубли имён и pyarrow роняет страницу.
def kw_editor(kw_df: pd.DataFrame, key: str) -> pd.DataFrame:
    """Редактируемая таблица ключевых фраз с типами."""
    v = kw_df.rename(columns={
        "search_query": "phrase", "volume": "vol", "impressions": "imp",
        "clicks": "clk", "purchases": "pur", "weight": "w"})
    v["w"] = v["w"].round(1)
    return st.data_editor(
        v[["phrase", "vol", "imp", "clk", "pur", "w", "in_title", "tier"]],
        column_config={
            "phrase": st.column_config.TextColumn(
                "Query", width="large", disabled=True),
            "vol": st.column_config.NumberColumn("Volume", disabled=True),
            "imp": st.column_config.NumberColumn("Impressions", disabled=True),
            "clk": st.column_config.NumberColumn("Clicks", disabled=True),
            "pur": st.column_config.NumberColumn("Purchases", disabled=True),
            "w": st.column_config.NumberColumn("Weight", disabled=True),
            "in_title": st.column_config.CheckboxColumn(
                t("card.title"), disabled=True),
            "tier": st.column_config.SelectboxColumn(
                "Tier", options=TIERS, required=True),
        },
        hide_index=True, width="stretch", height=300, key=key)


def render_preview(new_title: str, new_hl: str, mp: str) -> None:
    """Превью выдачи: как увидят человек и ИИ.

    Смысл разделения 75/125: title читает человек за 1–2 фиксации взгляда,
    Item Highlights — в основном ИИ-ассистент, который парсит факты.
    """
    with st.expander(t("serp.preview"), expanded=False):
        r = readability(new_title)
        f = facts_extracted(new_title, new_hl)

        pc1, pc2 = st.columns(2)
        with pc1:
            st.markdown(
                render_serp_row(new_title, VISIBLE_MOBILE,
                                t("serp.mobile"), t("serp.fits")),
                unsafe_allow_html=True)
        with pc2:
            st.markdown(
                render_serp_row(new_title, VISIBLE_DESKTOP,
                                t("serp.desktop"), t("serp.fits")),
                unsafe_allow_html=True)

        st.markdown(render_first_glance(new_title, r), unsafe_allow_html=True)
        st.markdown(render_ai_view(f), unsafe_allow_html=True)

        comps = load_competitors("", mp)
        if not comps.empty:
            st.markdown(f"**{t('serp.side_by_side')}**")
            st.markdown(
                f'<div style="background:#FFF;border:1px solid #E8590C;'
                f'border-radius:8px;padding:8px 11px;font-size:12px;'
                f'margin-bottom:4px;"><b>{t("common.our")}:</b> '
                f'{new_title}</div>', unsafe_allow_html=True)
            for _, cp in comps.iterrows():
                st.markdown(
                    f'<div style="background:#FFF;border:1px solid #E7E4DD;'
                    f'border-radius:8px;padding:8px 11px;font-size:12px;'
                    f'color:#57534A;margin-bottom:4px;">'
                    f'{str(cp["title"])[:90]}… · {cp["rating"] or "—"} '
                    f'({cp["review_count"] or 0})</div>',
                    unsafe_allow_html=True)


# ================================================================ UI
SQP_MARKETPLACES = {"es", "de", "it"}
SQP_LABEL = {
    "ready": t("synth.sqp_ready"),
    "queued": t("synth.sqp_queued"),
    "off": t("synth.sqp_off"),
}
Q_COLOR = {"green": "#2F6B3A", "amber": "#854F0B", "red": "#A32D2D"}

st.caption(t("synth.caption"))
# баланс провайдера исчерпан — предупреждаем ДО кнопок генерации,
# сами кнопки не блокируем: счёт можно пополнить и нажать снова
no_credit_banner("title_split")

candidates = load_candidates()
if candidates.empty:
    st.info(t("synth.no_candidates"))
    st.stop()

skill_text, skill_version = load_skill()
ECON = econ_map()
DRAFTS = load_draft_stats()
ACCEPTED = load_accepted()
SQP_HAVE = load_sqp_coverage()
HISTORY = load_history()

rows = []
for _, r in candidates.iterrows():
    key = (r["asin"], r["marketplace"])
    e = ECON.get(key) or {}
    rows.append({
        "r": r,
        "risk": money_at_risk("title_over_limit", e.get("revenue_30d")),
        "over": max(0, len(r["title"] or "") - TITLE_LIMIT),
        "econ": e,
        "draft": DRAFTS.get(key) or {},
        "accepted": ACCEPTED.get(key),
        "sqp_state": ("ready" if (r["asin"], r["marketplace"]) in SQP_HAVE
                      else "queued" if r["marketplace"] in SQP_MARKETPLACES
                      else "off"),
    })

# ---- шапка: разрез по стране рядом с общим числом
# Разрез читаем из состояния фильтра, а не из переменной: сам фильтр живёт
# внутри вкладки «Очередь» и рисуется ниже, шапка — выше. Ключ виджета
# переживает перерисовку, поэтому число в шапке соответствует выбору.
# Смысл пары чисел — проверяемость: пока видно только общее, нельзя
# заметить, что разрез по стране считается неверно.
MP_FILTER_KEY = "syn-mp"
mp_head = list(st.session_state.get(MP_FILTER_KEY) or [])
head_rows = ([x for x in rows if x["r"]["marketplace"] in mp_head]
             if mp_head else rows)

total_risk = sum(x["risk"] for x in rows)
n_ready = sum(1 for x in rows if x["sqp_state"] == "ready")
head_risk = sum(x["risk"] for x in head_rows)
head_ready = sum(1 for x in head_rows if x["sqp_state"] == "ready")


def head_metric(before: str, value: str, after: str, total: str,
                color: str = INK) -> str:
    """«3 тайтлов сверх лимита · всего 5».

    «всего» стоит в КОНЦЕ своей метрики, а не сразу за числом: иначе
    «3 · всего 5 тайтлов сверх лимита» читается так, будто пять — это
    что-то другое. И показывается только при включённом фильтре: без него
    оба числа совпадают, и вторая половина строки была бы шумом.
    """
    tail = (f'<span style="color:{MUTED};font-weight:400;font-size:12.5px;">'
            f' · {t("synth.of_total", n=total)}</span>') if mp_head else ""
    lead = f"{before} " if before else ""
    return (f'{lead}<b style="color:{color}">{value}</b>'
            f'{" " + after if after else ""}{tail}')


_where = (f'<b>{" · ".join(mp_label(m) for m in sorted(mp_head))}</b>'
          f'<span style="color:{MUTED};"> — </span>') if mp_head else ""
_sep = f'<span style="color:{MUTED};">&nbsp;&nbsp;·&nbsp;&nbsp;</span>'
st.markdown(
    _where + _sep.join([
        head_metric(t("synth.at_risk_line"), fmt_money(head_risk, ""), "",
                    fmt_money(total_risk, ""), ACCENT),
        head_metric("", str(len(head_rows)), t("synth.over_limit_n"),
                    str(len(rows))),
        head_metric(t("synth.sqp_have"), str(head_ready), "", str(n_ready)),
    ]), unsafe_allow_html=True)

# Методология не прочиталась — генерация выключена целиком. Раньше в этом
# месте молча подставлялся зашитый текст с противоположным правилом
# («бренд первым» при v8, где бренд запрещён), и подмену было не увидеть.
if not skill_version:
    st.error("⚠ " + t("synth.skill_failed",
                      e=skill_error() or t("synth.skill_missing")))
    st.page_link("pages/methodology.py", label=t("nav.methodology"),
                 icon=":material/menu_book:")

pending = load_drafts_for_review()
# черновики по паре — чтобы в очереди показать «было/стало» без перехода
# на вкладку разбора; после перезагрузки страницы результат не теряется
PENDING_MAP = ({(r["asin"], r["marketplace"]): r for _, r in pending.iterrows()}
               if not pending.empty else {})
all_products = load_all_products()
tab_queue, tab_review, tab_any = st.tabs([
    f"{t('synth.tab_queue')} · {len(rows)}",
    f"{t('synth.tab_review')} · {len(pending)}",
    f"{t('synth.tab_any')} · {len(all_products)}",
])


def render_card_head(x: dict) -> None:
    """Строка товара: фото, ASIN, превышение, деньги, состояние работы."""
    r = x["r"]
    asin, mp = r["asin"], r["marketplace"]
    title = r["title"] or ""
    sku = r["sku_group"] if r["sku_group"] and r["sku_group"] != asin else ""
    img = None if pd.isna(r.get("main_image")) else r.get("main_image")
    thumb = (f'<div style="flex:0 0 42px;"><img src="{img}" '
             f'style="width:42px;height:42px;object-fit:contain;background:#fff;'
             f'border:1px solid #E7E4DD;border-radius:7px;"></div>') if img else ""
    sub = [SQP_LABEL[x["sqp_state"]]]
    hist = history_line(x["draft"], x["accepted"])
    if hist:
        sub.append(("✓ " if x["accepted"] else "") + hist)
    cov = x["draft"].get("coverage")
    if cov is not None and pd.notna(cov):
        sub.append(f"Coverage {int(cov)}%")
    edge = ACCENT if x["risk"] else "#E7E4DD"
    st.markdown(
        f'<div class="ls-card" style="background:#fff;border:1px solid #E7E4DD;'
        f'border-left:3px solid {edge};border-radius:0 10px 10px 0;'
        f'padding:11px 14px;margin-bottom:4px;display:flex;gap:12px;'
        f'align-items:center;">{thumb}'
        f'<div style="flex:1;min-width:0;">'
        f'<div style="font-size:13.5px;font-weight:700;">'
        f'{sku + " · " if sku else ""}'
        f'<a href="https://www.amazon.{mp}/dp/{asin}" target="_blank" '
        f'style="color:#1A1815;text-decoration:none;'
        f'border-bottom:1px dotted #57534A;">{asin}</a> '
        f'<span style="font-weight:400;color:#57534A;">· {mp} · '
        f'{len(title)}/{TITLE_LIMIT} · +{x["over"]} · {title[:58]}…</span></div>'
        f'<div style="font-size:11.5px;color:#57534A;">{" · ".join(sub)}</div>'
        f'</div><span class="ls-mono" style="font-size:13px;font-weight:700;'
        f'color:{ACCENT if x["risk"] else "#57534A"};">'
        f'{fmt_money(x["risk"]) if x["risk"] else "нет данных"}</span></div>',
        unsafe_allow_html=True)


DIFF_BG = "#DCEEE0"       # подсветка того, что модель изменила
OK_GREEN = "#2F6B3A"
ERR_RED = "#A32D2D"

# провайдер по префиксу имени модели: в базе лежит только id модели,
# а человеку нужен и вендор. Незнакомый префикс — показываем как есть,
# врать про вендора хуже, чем промолчать
MODEL_VENDOR = (("claude", "Anthropic"), ("gemini", "Google Gemini"),
                ("gpt", "OpenAI"))


def model_badge(model: str | None, provider: str | None = None) -> str:
    """«Anthropic · claude-sonnet-5» — чем сгенерирован черновик."""
    mid = "" if model is None or pd.isna(model) else str(model).strip()
    if not mid:
        return ""
    vendor = (provider or "").strip()
    for prefix, name in MODEL_VENDOR:
        if mid.lower().startswith(prefix):
            vendor = name
            break
    else:
        vendor = {"anthropic": "Anthropic", "gemini": "Google Gemini"}.get(
            vendor.lower(), vendor)
    label = f"{vendor} · {mid}" if vendor else mid
    return (f'<span style="background:#F1EFE9;color:#57534A;font-size:11px;'
            f'border-radius:5px;padding:2px 8px;white-space:nowrap;">'
            f'{esc(label)}</span>')


def history_line(draft: dict, accepted: dict | None) -> str:
    """«принят 28.08 · до этого черновиков: 6» вместо «черновиков 7».

    Слова «отклонено» здесь нет намеренно: отказ никуда не пишется, и
    назвать отклонённым черновик, который просто перегенерировали, —
    выдумать факт. Говорим то, что знаем: принято или нет и сколько
    заходов было.
    """
    n = int(draft.get("drafts") or 0)
    if not n and not accepted:
        return ""
    if not accepted:
        return t("synth.hist_none", n=n)
    day = pd.to_datetime(accepted["accepted_at"]).strftime("%d.%m")
    before = int(draft.get("before_accept") or 0)
    after = int(draft.get("after_accept") or 0)
    line = t("synth.hist_accepted", day=day)
    if before:
        line += " · " + t("synth.hist_before", n=before)
    if after:
        line += " · " + t("synth.hist_after", n=after)
    return line


def diff_html(before: str, after: str) -> str:
    """«Стало» с подсветкой отличий от «было», по словам.

    Пословно, а не посимвольно: посимвольный дифф в тайтле даёт рваную
    подсветку внутри слов, читать невозможно."""
    a = re.findall(r"\S+\s*", before)
    b = re.findall(r"\S+\s*", after)
    out = []
    for tag, _i1, _i2, j1, j2 in SequenceMatcher(None, a, b).get_opcodes():
        chunk = esc("".join(b[j1:j2]))
        if not chunk:
            continue
        out.append(chunk if tag == "equal" else
                   f'<span style="background:{DIFF_BG};border-radius:3px;">'
                   f"{chunk}</span>")
    return "".join(out)


def counter_html(n: int, limit: int) -> str:
    """Счётчик длины: красный при превышении, зелёный в пределах."""
    color = ERR_RED if n > limit else OK_GREEN
    return (f'<span class="ls-mono" style="color:{color};font-weight:700;">'
            f"{n}/{limit}</span>")


def field_html(label: str, counter: str, body: str, top_line: bool) -> str:
    """Поле карточки: подпись со счётчиком и текст. HTML одной строкой."""
    border = ("border-top:1px solid #E7E4DD;margin-top:10px;padding-top:10px;"
              if top_line else "")
    return (
        f'<div style="{border}">'
        f'<div style="font-size:11.5px;letter-spacing:.06em;color:#57534A;'
        f'text-transform:uppercase;margin-bottom:4px;">{label} {counter}</div>'
        f'<div class="ls-mono" style="font-size:13px;line-height:1.55;'
        f'color:#1A1815;white-space:pre-wrap;word-break:break-word;">'
        f"{body}</div></div>"
    )


@st.cache_data(ttl=60, show_spinner=False)
def single_plan(asin: str, mp: str) -> list[dict]:
    """План выгрузки по ОДНОМУ товару — та же раскладка, что у партии.

    Через plan_export, а не отдельной веткой: SKU, product_type и выбор
    шаблона обязаны совпадать с файлом на всю партию. Разойдутся —
    и человек получит два разных файла на один и тот же товар.
    """
    acc = load_accepted_titles((mp,))
    if acc.empty:
        return []
    sub = acc[(acc["asin"].astype(str) == str(asin))
              & (acc["marketplace"].astype(str) == str(mp))]
    if sub.empty:
        return []
    return plan_export(sub)[0]


def event_html(e: dict) -> str:
    """Одно событие истории. Раскрывается через <details>, а не через
    st.expander: вложенные expander Streamlit не разрешает, а весь блок
    истории и так лежит внутри одного."""
    if e["kind"] == "push":
        head = t("hist.push")
        tail = e.get("status") or ""
        color = OK_GREEN if e.get("ok") else ERR_RED
        extra = (f'<div style="font-size:11.5px;color:{MUTED};">'
                 f'submissionId {esc(e["submission_id"])}</div>'
                 if pd.notna(e.get("submission_id"))
                 and str(e.get("submission_id") or "").strip() else "")
        # pd.notna, а не `if`: у успешной отправки issues приходит NaN,
        # а NaN в Python истинный — в строке появлялось «nan»
        if pd.notna(e.get("detail")) and str(e.get("detail") or "").strip():
            extra += (f'<div style="font-size:11.5px;color:{ERR_RED};">'
                      f'{esc(str(e["detail"])[:300])}</div>')
    else:
        head = t("hist.accept")
        src = e.get("source") or "ai"
        tail = t("hist.manual") if src == "manual" else t("hist.ai")
        color = INK
        bits = []
        if pd.notna(e.get("skill_version")):
            bits.append(t("hist.skill", n=int(e["skill_version"])))
        if e.get("model") and pd.notna(e.get("model")):
            bits.append(esc(str(e["model"])))
        if e.get("tries"):
            bits.append(t("hist.tries", n=int(e["tries"])))
        extra = (f'<div style="font-size:11.5px;color:{MUTED};">'
                 f'{" · ".join(bits)}</div>') if bits else ""

    before = "" if pd.isna(e.get("before")) else str(e.get("before") or "")
    after = "" if pd.isna(e.get("after")) else str(e.get("after") or "")
    body = (f'<div style="font-size:12px;color:{MUTED};margin-top:4px;">'
            f'{t("synth.was")}: {esc(before)}</div>'
            f'<div style="font-size:12.5px;color:{INK};">'
            f'{t("synth.became")}: <b>{esc(after)}</b></div>{extra}')
    return (f'<details style="border-bottom:1px solid #E7E4DD;padding:6px 0;">'
            f'<summary style="cursor:pointer;font-size:12.5px;list-style:none;">'
            f'<span class="ls-mono" style="color:{MUTED};">'
            f'{history_stamp(e["at"])}</span>'
            f'<span style="color:{MUTED};"> · </span>{head}'
            f'<span style="color:{MUTED};"> · </span>'
            f'<b style="color:{color};">{esc(tail)}</b></summary>'
            f'<div style="padding:4px 0 6px 10px;">{body}</div></details>')


def render_history(asin: str, mp: str) -> None:
    """Блок «История» — что генерировали, принимали и отправляли.

    Свёрнутый показывает последнюю отправку: именно за ней сюда и лезут —
    дошла правка до Amazon или нет.
    """
    events = HISTORY.get((str(asin), str(mp).lower())) or []
    err = history_error()
    with st.expander(f'{t("hist.title")} · {history_summary(events)}',
                     expanded=False):
        if err:
            # пустая история и недоступная — разные вещи; молчать про вторую
            # значит показать «ничего не делали» вместо «не смогли прочитать»
            st.error("⚠ " + t("hist.load_failed", e=err))
        if not events:
            st.caption(t("hist.empty"))
            return
        st.markdown("".join(event_html(e) for e in events),
                    unsafe_allow_html=True)


def last_push(asin: str, mp: str) -> dict | None:
    """Последняя УДАЧНАЯ отправка пары — состояние карточки, а не история."""
    for e in HISTORY.get((str(asin), str(mp).lower())) or []:
        if e["kind"] == "push" and e.get("ok"):
            return e
    return None


def render_card_actions(asin: str, mp: str, is_accepted: bool,
                        pushed: dict | None) -> None:
    """Группа «выгрузка»: файл и отправка в Amazon.

    Отделена от группы решения по тексту чертой и отступом: там человек
    решает, каким быть тайтлу, здесь — выносит решение наружу. Смешанные
    в один ряд, эти действия читались как равные, хотя отправка правит
    ЖИВОЙ листинг клиента, а всё остальное — нет.

    Основная кнопка всегда одна и всегда показывает СЛЕДУЮЩИЙ шаг:
    пока не принято — «Принять» в первой группе; принято, но не
    отправлено — «Отправить в Amazon» здесь; отправлено — основной нет,
    следующего шага не осталось.

    Наверху страницы есть такие же по названию кнопки с другой областью
    действия (всё принятое по фильтру), у них в подписи «для всех
    принятых · N».
    """
    st.markdown(
        f'<div style="border-top:1px solid #E7E4DD;margin:10px 0 8px;"></div>'
        f'<div style="font-size:11px;letter-spacing:.06em;color:{MUTED};'
        f'text-transform:uppercase;margin-bottom:4px;">'
        f'{t("card.group_export")}</div>', unsafe_allow_html=True)

    st.markdown(
        f'<style>.st-key-exp-{asin}-{mp}'
        '{padding-left:14px;border-left:2px solid #F1EFE9;}</style>',
        unsafe_allow_html=True)
    box = st.container(key=f"exp-{asin}-{mp}")
    with box:
        b1, b2, b3 = st.columns([1.75, 1.75, 4.2], gap="small")
        plan = single_plan(asin, mp) if is_accepted else []
        if plan:
            name, mime, data = build_flat_cached(
                plan, plan_signature(plan),
                pd.Timestamp.now().strftime("%Y-%m-%d"))
            b1.download_button(f'⬇ {t("export.flat")}', data, file_name=name,
                               mime=mime, key=f"c-flat-{asin}-{mp}")
        else:
            b1.button(f'⬇ {t("export.flat")}', disabled=True,
                      key=f"c-flat-off-{asin}-{mp}",
                      help=(t("export.accept_this_first") if not is_accepted
                            else t("export.no_template")))

        state_key = f"push-confirm-{asin}-{mp}"
        rows = [dict(r, marketplace=i["marketplace"], tpl=i["tpl"])
                for i in plan for r in i["rows"]]
        miss = missing_secrets()
        # основная — только если отправка и есть следующий шаг
        push_primary = ("primary" if (rows and not miss and pushed is None)
                        else "secondary")
        if not rows or miss:
            b2.button(t("push.button"), disabled=True,
                      key=f"c-push-off-{asin}-{mp}",
                      help=(t("push.no_keys", keys=", ".join(miss)) if miss
                            else t("export.accept_this_first")
                            if not is_accepted else t("export.no_template")))
        elif b2.button(t("push.button"), type=push_primary,
                       key=f"c-push-{asin}-{mp}"):
            st.session_state[state_key] = True

        if pushed is not None:
            b3.caption("✓ " + t("card.pushed_at",
                                day=history_stamp(pushed["at"]),
                                status=t("hist.accepted_by_amazon")))

        if st.session_state.get(state_key) and rows:
            render_push_confirm(rows, state_key)
        render_push_result(state_key)
        # история — про отправку, поэтому под её кнопками, а не отдельным
        # блоком в конце карточки
        render_history(asin, mp)


def step_writer(status):
    """Обработчик шагов для st.status: превращает kind в строку человеку."""
    def on_step(kind: str, **kw) -> None:
        if kind == "generating":
            status.update(label=t("gen.generating"))
            status.write("· " + t("gen.generating"))
        elif kind == "checking":
            status.write("· " + t("gen.checking"))
        elif kind == "retry":
            # самый нужный шаг: автоповторы занимают больше всего времени,
            # и без него человек видит замерший экран без объяснения
            line = t("gen.retry", attempt=kw.get("attempt", 2),
                     total=kw.get("total", MAX_ATTEMPTS),
                     over=max(1, int(kw.get("over") or 1)))
            status.update(label=line)
            status.write("↻ " + line)
        elif kind == "trimming":
            status.write("✂ " + t("gen.trimming"))
        elif kind == "failed":
            status.update(label=t("gen.failed"), state="error")
        elif kind == "done":
            status.update(label=t("gen.done"), state="complete")
    return on_step


def render_result(asin: str, mp: str, before: str, draft) -> None:
    """Блок «было / стало» с длинами и кнопкой «Принять».

    Источник — свежий результат из session_state, иначе последний
    несогласованный черновик из synthesis_drafts: после перезагрузки
    страницы человек должен видеть то же, что видел до неё."""
    accepted = ACCEPTED.get((asin, mp))
    # Идёт перегенерация — показывать прошлый результат нельзя: он мелькает
    # перед новым, и выглядит так, будто генерация вернула старое.
    # Вместо него полоса хода, её рисует блок генерации ниже.
    if st.session_state.get(f"regen-{asin}-{mp}"):
        st.info("↻ " + t("gen.regenerating"))
        return
    res = st.session_state.get(f"res-{asin}-{mp}")
    if res:
        after = str(res.get("title") or "")
        hl = str(res.get("highlights") or "")
        dropped = res.get("dropped") or []
        trimmed = res.get("trimmed_fields") or []
        over = res.get("over_fields") or []
        cov = None
        skill_v = skill_version
        # свежий результат сгенерирован тем, что настроено сейчас
        model_id, model_prov = TITLE_MODEL, TITLE_PROVIDER
    elif draft is not None:
        after = str(draft.get("title_after") or "")
        hl = str(draft.get("highlights_after") or "")
        dropped = [d for d in str(draft.get("dropped") or "").split("; ") if d]
        cov = draft.get("coverage_score")
        skill_v = int(draft.get("skill_version") or 0)
        trimmed, over = [], []
        # у сохранённого черновика — та модель, которой его сделали, а не
        # та, что стоит в настройках сейчас: настройку могли поменять
        model_id, model_prov = draft.get("model"), None
    elif accepted is not None:
        # Третий источник — уже ПРИНЯТАЯ правка. Без него карточка исчезала
        # сразу после приёмки (принятый черновик выпадает из очереди
        # разбора), и кнопки «после приёмки» оказывались недостижимы:
        # скачать файл по этому товару было неоткуда.
        after = str(accepted.get("after_text") or "")
        hl = "" if pd.isna(accepted.get("after_extra")) \
            else str(accepted.get("after_extra") or "")
        dropped, trimmed, over = [], [], []
        cov = accepted.get("coverage_score")
        skill_v = int(accepted.get("skill_version") or 0
                      if not pd.isna(accepted.get("skill_version", 0)) else 0)
        model_id, model_prov = accepted.get("model"), None
    else:
        return
    if not after:
        return

    # ---- режим ручной правки
    # Человек правит поверх черновика, а не вместо него: исходный текст
    # модели остаётся в synthesis_drafts, в synthesis_changes уходит
    # отредактированный с пометкой источника. Иначе «принято» перестало бы
    # отличаться от «переписано руками», а доля ручных правок — это и есть
    # мера того, насколько методология попадает.
    edit_key = f"edit-{asin}-{mp}"
    editing = bool(st.session_state.get(edit_key))
    if editing:
        after = str(st.session_state.get(f"{edit_key}-title", after) or "")
        hl = str(st.session_state.get(f"{edit_key}-hl", hl) or "")

    checks = run_checks(after, hl, [], [])
    failed = [m for ok, m in checks if not ok]

    # Рамку рисуем контейнеру с ключом: кнопки и раскрывашка — обычные
    # виджеты Streamlit, внутрь HTML их не вставить, а внутрь контейнера —
    # можно, и тогда они оказываются в той же карточке.
    card_key = f"rescard-{asin}-{mp}"
    st.markdown(
        f'<style>.st-key-{card_key}{{background:#FFFFFF;'
        'border:1px solid #E7E4DD;border-left:3px solid #E8590C;'
        'border-radius:0 12px 12px 0;padding:14px 16px;margin-bottom:12px;}'
        f'.st-key-{card_key} div[data-testid="stExpander"]'
        '{border:none;box-shadow:none;}'
        '</style>',
        unsafe_allow_html=True)

    with st.container(key=card_key):
        # заголовок и плашка модели в одной строке: «чем сгенерировано» —
        # часть подписи результата, а не отдельная строка ниже
        st.markdown(
            '<div style="display:flex;align-items:center;gap:10px;'
            'flex-wrap:wrap;margin-bottom:2px;">'
            + eyebrow(t("synth.result"))
            + model_badge(model_id, model_prov) + '</div>',
            unsafe_allow_html=True)
        # повторное принятие: правка не ломается, но человек должен знать,
        # что перезаписывает свой же прошлый выбор — в выгрузку пойдёт
        # последняя принятая, предыдущая останется только в истории
        # Баннер про замену нужен, только когда на экране НЕ принятый текст:
        # иначе он сообщает «заменит предыдущий» про сам предыдущий.
        _prev = accepted if (res or draft is not None) else None
        if _prev is not None:
            st.info("↻ " + t("synth.already_accepted",
                             day=pd.to_datetime(
                                 _prev["accepted_at"]).strftime("%d.%m")))
        # «было» и «стало» — одним блоком, разделены линией; в «стало»
        # подсвечено то, что модель заменила или добавила
        body = field_html(
            t("synth.was"),
            f'<span class="ls-mono" style="color:#57534A;">'
            f'{len(before)}</span>', esc(before), False)
        if not editing:
            body += field_html(t("synth.became"),
                               counter_html(len(after), TITLE_LIMIT),
                               diff_html(before, after), True)
            if hl:
                body += field_html("item highlights",
                                   counter_html(len(hl), HIGHLIGHTS_LIMIT),
                                   esc(hl), True)
        st.markdown(body, unsafe_allow_html=True)

        if editing:
            # счётчики и проверки пересчитываются на каждой перерисовке,
            # то есть при уходе фокуса или Ctrl+Enter: у Streamlit нет
            # события на каждую букву, и обещать его в подписи нельзя
            st.markdown(
                f'<div style="font-size:11.5px;letter-spacing:.06em;'
                f'color:#57534A;text-transform:uppercase;margin:10px 0 2px;">'
                f'{t("synth.became")} {counter_html(len(after), TITLE_LIMIT)}'
                f'</div>', unsafe_allow_html=True)
            st.text_area(t("synth.became"), value=after, height=80,
                         key=f"{edit_key}-title", label_visibility="collapsed")
            st.markdown(
                f'<div style="font-size:11.5px;letter-spacing:.06em;'
                f'color:#57534A;text-transform:uppercase;margin:8px 0 2px;">'
                f'item highlights '
                f'{counter_html(len(hl), HIGHLIGHTS_LIMIT)}</div>',
                unsafe_allow_html=True)
            st.text_area("item highlights", value=hl, height=80,
                         key=f"{edit_key}-hl", label_visibility="collapsed")
            st.caption(t("synth.edit_hint"))
        else:
            st.caption(t("synth.diff_hint"))
        # обрезанный нами вариант помечаем явно: человек должен видеть,
        # что часть текста убрал код, а не модель
        if trimmed:
            st.warning("✂ " + t("synth.trimmed_note",
                                fields=", ".join(trimmed)))
        if over:
            st.error("⚠ " + t("synth.over_note", fields=", ".join(over)))
        # черновик не записался — на экране он есть, а в базе нет:
        # после перезагрузки страницы пропадёт
        _serr = st.session_state.get(f"save-err-{asin}-{mp}")
        if _serr:
            st.error("⚠ " + t("synth.not_saved", e=_serr))

        # выброшенное занимало три строки и оттесняло кнопки вниз
        if dropped:
            with st.expander(f"{t('synth.dropped')} · {len(dropped)}"):
                st.markdown(" · ".join(f"`{d}`" for d in dropped))

        st.markdown(" · ".join(("✅ " if ok else "❌ ") + m
                               for ok, m in checks))

        def _save(source: str) -> None:
            """Принять текущий текст. source различает «как сгенерировано»
            и «переписано руками»."""
            if accept_change(asin, mp, before,
                             {"title": after, "highlights": hl,
                              "dropped": dropped},
                             cov, skill_v, TITLE_MODEL, source):
                for k in (f"res-{asin}-{mp}", edit_key,
                          f"{edit_key}-title", f"{edit_key}-hl"):
                    st.session_state.pop(k, None)
                st.success(t("synth.accepted_ok"))
                st.rerun()

        # Кнопки жмём вплотную. Прошлая попытка (PR #42) не сработала и
        # сделала хуже: доли колонок подобрать можно, но КНОПКА внутри
        # растягивалась на всю долю (width:100%), поэтому между подписями
        # зияли пустые поля самих кнопок.
        #
        # Лечится не долями, а флексом: колонка перестаёт делить ширину
        # (flex:0 0 auto) и сжимается по содержимому, кнопка перестаёт
        # тянуться (width:auto). Тогда ряд собирается слева направо
        # с фиксированным зазором, а последняя колонка-распорка забирает
        # остаток. Доли при этом почти не важны — они лишь резерв
        # на случай, если css не доедет.
        st.markdown(
            f'<style>.st-key-{card_key} div[data-testid="stHorizontalBlock"]'
            '{gap:8px !important;align-items:center;flex-wrap:wrap;}'
            f'.st-key-{card_key} div[data-testid="stColumn"]'
            '{flex:0 0 auto !important;width:auto !important;'
            'min-width:0 !important;}'
            f'.st-key-{card_key} div[data-testid="stColumn"]:last-child'
            '{flex:1 1 auto !important;}'
            f'.st-key-{card_key} .stButton button,'
            f'.st-key-{card_key} .stDownloadButton button'
            '{white-space:nowrap !important;width:auto !important;'
            'padding-left:14px !important;padding-right:14px !important;}'
            f'.st-key-{card_key} div[data-testid="stCaptionContainer"] p'
            '{margin-bottom:0 !important;}'
            '</style>', unsafe_allow_html=True)
        if not editing:
            st.markdown(
                f'<div style="font-size:11px;letter-spacing:.06em;'
                f'color:{MUTED};text-transform:uppercase;margin:6px 0 4px;">'
                f'{t("card.group_text")}</div>', unsafe_allow_html=True)
        a1, a2, a3, a4 = st.columns([1.15, 1.45, 1.85, 3.55],
                                    gap="small")
        if editing:
            # источник считаем по факту, а не по тому, что открывали форму:
            # открыть и ничего не изменить — это всё ещё «как сгенерировано»
            changed = (after != str(res.get("title") if res else
                                    draft.get("title_after") or "")
                       or hl != str(res.get("highlights") if res else
                                    draft.get("highlights_after") or ""))
            if a1.button(t("synth.edit_save"), type="primary",
                         disabled=bool(failed),
                         help=None if not failed else t("synth.fix_first"),
                         key=f"q-save-{asin}-{mp}"):
                _save("manual" if changed else "ai")
            if a2.button(t("synth.edit_cancel"), key=f"q-ecancel-{asin}-{mp}"):
                for k in (edit_key, f"{edit_key}-title", f"{edit_key}-hl"):
                    st.session_state.pop(k, None)
                st.rerun()
            if changed:
                a4.caption(t("synth.edit_changed"))
        else:
            # Основная кнопка всегда одна и всегда показывает СЛЕДУЮЩИЙ шаг.
            # Пока не принято — это «Принять»; после приёмки следующий шаг
            # уже в группе выгрузки, и держать «Принять» оранжевой значит
            # предлагать сделать то, что сделано.
            if a1.button(t("synth.accept_short"),
                         type="secondary" if accepted is not None else "primary",
                         disabled=bool(failed),
                         help=None if not failed else t("synth.fix_first"),
                         key=f"q-acc-{asin}-{mp}"):
                _save("ai")
            if a2.button(t("synth.edit"), key=f"q-edit-{asin}-{mp}"):
                st.session_state[edit_key] = True
                st.rerun()
            if a3.button(t("synth.regenerate"), key=f"q-re-{asin}-{mp}"):
                # Кнопка только просит перегенерировать. Саму генерацию
                # делает блок ниже — тот же, что и у «Сгенерировать»:
                # вторая копия кода разошлась бы с первой. Раньше здесь
                # был только pop(res), то есть кнопка ничего не запускала,
                # а после появления третьего источника карточки (принятая
                # правка) выглядела вообще бездействующей.
                st.session_state.pop(f"res-{asin}-{mp}", None)
                st.session_state[f"regen-{asin}-{mp}"] = True
                st.rerun()
        _marks = []
        if accepted is not None and not editing:
            _marks.append("✓ " + t("card.accepted_at", day=pd.to_datetime(
                accepted["accepted_at"]).strftime("%d.%m")))
        if cov is not None and not pd.isna(cov):
            _marks.append(f"Coverage {float(cov):.0f}%")
        if _marks:
            a4.caption(" · ".join(_marks))

        if not editing:
            render_card_actions(asin, mp, accepted is not None,
                                last_push(asin, mp))


# ================================================================ очередь
def render_push_confirm(pushable: list[dict],
                        state_key: str = "push-confirm") -> None:
    """Подтверждение отправки в Amazon.

    Правил здесь три, и все три — про то, что это чужие живые листинги.

    1. Отправка возможна ТОЛЬКО из этого блока. Кнопка на панели лишь
       открывает подтверждение, сама ничего не шлёт.
    2. Товар ровно один. Пачка появится, когда единичная отправка
       подтвердится на проде, — до тех пор список одиночный намеренно.
    3. Повтор не запрещаем, но показываем дату и требуем отдельной
       галочки: «уже отправляли» — частая и дорогая ошибка.
    """
    st.markdown(
        f'<style>.st-key-push_box-{state_key}'
        '{background:#FFF9F4;border:1px solid #E7E4DD;'
        'border-left:3px solid #E8590C;border-radius:0 12px 12px 0;'
        'padding:14px 16px;margin:6px 0 12px;}</style>',
        unsafe_allow_html=True)
    with st.container(key=f"push_box-{state_key}"):
        st.markdown(eyebrow(t("push.confirm_title")), unsafe_allow_html=True)
        labels = {f'{r["sku"]} · {r["marketplace"]} · {r["asin"]}': r
                  for r in pushable}
        if len(labels) == 1:
            # из карточки товар уже выбран — выпадающий список из одного
            # пункта только притворялся бы выбором
            pick = next(iter(labels))
            st.markdown(f"**{esc(pick)}**")
        else:
            pick = st.selectbox(t("push.pick"), sorted(labels),
                                key=f"push-pick-{state_key}")
        row = labels[pick]
        meta = marketplace_meta([row["tpl"]])
        prev = load_pushes().get((row["asin"], row["marketplace"]))

        st.markdown(
            f'<div style="font-size:13px;line-height:1.7;">'
            f'<b>{esc(row["sku"])}</b>'
            f'<span style="color:#57534A;"> · {mp_label(row["marketplace"])}'
            f' · {esc(row["product_type"])}'
            f' · {t("push.count", n=1)}</span></div>'
            f'<div style="font-size:12.5px;color:#57534A;margin-top:6px;">'
            f'{t("synth.was")}: {esc(row["before"][:160])}</div>'
            f'<div style="font-size:13px;margin-top:2px;">'
            f'{t("synth.became")}: <b>{esc(row["title"])}</b> '
            f'<span class="ls-mono" style="color:#57534A;">'
            f'{len(row["title"])}/{TITLE_LIMIT}</span></div>',
            unsafe_allow_html=True)

        if meta is None:
            st.error(t("push.no_marketplace_id"))
            return
        mp_id, lang = meta
        st.caption(f"marketplaceId {mp_id} · {lang}")

        again = True
        if prev is not None:
            when = pd.to_datetime(prev["pushed_at"]).strftime("%d.%m %H:%M")
            st.warning("↻ " + t("push.already", day=when,
                                title=str(prev["after_text"])[:80]))
            again = st.checkbox(t("push.again_ok"),
                                key=f"push-again-{state_key}")

        c1, c2, c3 = st.columns([1.6, 1.2, 4])
        if c1.button(t("push.send", n=1), type="primary", disabled=not again,
                     key=f"push-send-{state_key}"):
            res = push_title(row["sku"], row["marketplace"],
                             row["product_type"], row["title"],
                             row.get("highlights", ""), mp_id, lang,
                             TITLE_LIMIT, HIGHLIGHTS_LIMIT)
            log_err = log_push(row["asin"], row["sku"], row["marketplace"],
                               row["before"], row["title"],
                               row.get("highlights", ""), res)
            st.session_state[f"push-result-{state_key}"] = dict(
                res, sku=row["sku"], marketplace=row["marketplace"],
                log_err=log_err)
            st.session_state.pop(state_key, None)
            st.cache_data.clear()
            st.rerun()
        if c2.button(t("push.cancel"), key=f"push-cancel-{state_key}"):
            st.session_state.pop(state_key, None)
            st.rerun()


def render_push_result(state_key: str = "push-confirm") -> None:
    """Итог отправки. Переживает rerun: иначе причина отказа пропадёт
    ровно тогда, когда она нужнее всего.

    Итог привязан к тому же ключу, что и подтверждение: иначе отправка
    из карточки показывала бы результат наверху страницы, где человек
    его не ищет."""
    res = st.session_state.pop(f"push-result-{state_key}", None)
    if not res:
        return
    accepted = 1 if res.get("ok") else 0
    st.markdown(t("push.result", ok=accepted, bad=1 - accepted))
    if res.get("ok"):
        st.success(f'✓ {res["sku"]} · {res.get("status")}'
                   + (f' · submissionId {res["submission_id"]}'
                      if res.get("submission_id") else ""))
    else:
        st.error(f'✗ {res["sku"]}: {res.get("error") or res.get("status")}')
        for line in (issues_text(res.get("issues")) or "").split(" · "):
            if line:
                st.code(line, language=None)
    for s in res.get("skipped") or []:
        st.caption("⚠ " + s)
    if res.get("log_err"):
        # отправили, но следа не осталось — хуже, чем неудачная отправка
        st.error("⚠ " + t("push.log_failed", e=res["log_err"]))


SMALL_MARKET = 5      # меньше товаров в матрице — страна уезжает в «Прочие»


def market_breakdown(queue: list, products: pd.DataFrame,
                     selected: list) -> str:
    """Таблица «строка на страну + итог».

    Смысл тот же, что у пары чисел в шапке, только подробнее: строки
    обязаны складываться в итог. Если разрез считается неверно, сумма
    не сойдётся с итогом, и это видно без всякой отладки.

    Полоса показывает долю товаров сверх лимита ВНУТРИ страны, а не долю
    страны в общей очереди: второе дублировало бы соседнюю колонку, первое
    отвечает на вопрос «где хуже всего» и сравнимо между строками.
    """
    stat: dict[str, dict] = {}
    for mp in (sorted(products["marketplace"].astype(str).str.lower().unique())
               if not products.empty else []):
        stat[mp] = {"products": 0, "over": 0, "risk": 0.0}
    if not products.empty:
        for mp, n in (products["marketplace"].astype(str).str.lower()
                      .value_counts().items()):
            stat.setdefault(mp, {"products": 0, "over": 0, "risk": 0.0})
            stat[mp]["products"] = int(n)
    for x in queue:
        mp = str(x["r"]["marketplace"]).lower()
        stat.setdefault(mp, {"products": 0, "over": 0, "risk": 0.0})
        stat[mp]["over"] += 1
        stat[mp]["risk"] += x["risk"] or 0.0
    if not stat:
        return ""

    sel = {str(m).lower() for m in selected}
    # «Прочие» собираем только из мелочи и никогда — из выбранной страны:
    # иначе подсвечивать нечего и разрез не проверить
    small = [m for m, v in stat.items()
             if v["products"] < SMALL_MARKET and m not in sel]
    small = small if len(small) > 1 else []
    big = [m for m in stat if m not in small]
    big.sort(key=lambda m: (-stat[m]["over"], -stat[m]["risk"], m))

    def bar(over: int, products_n: int) -> str:
        pct = (100.0 * over / products_n) if products_n else 0.0
        color = ACCENT if pct >= 50 else ("#B4763A" if pct >= 20 else OK_GREEN)
        return (f'<div style="display:flex;align-items:center;gap:7px;">'
                f'<div style="flex:1;min-width:44px;height:6px;'
                f'background:#EFEDE7;border-radius:3px;overflow:hidden;">'
                f'<div style="width:{min(100.0, pct):.1f}%;height:6px;'
                f'background:{color};border-radius:3px;"></div></div>'
                f'<span class="ls-mono" style="font-size:11.5px;'
                f'color:{MUTED};">{pct:.0f}%</span></div>')

    def cell(v: str, align: str = "right", extra: str = "") -> str:
        return (f'<td style="padding:6px 8px;text-align:{align};'
                f'border-bottom:1px solid #E7E4DD;{extra}">{v}</td>')

    def row(label: str, v: dict, highlight: bool, strong: bool = False,
            title: str = "") -> str:
        bg = "background:#FBF3EC;" if highlight else ""
        edge = (f"box-shadow:inset 3px 0 0 {ACCENT};" if highlight else "")
        weight = "font-weight:700;" if strong or highlight else ""
        top = "border-top:2px solid #E7E4DD;" if strong else ""
        name = (f'<span style="{weight}">{label}</span>'
                + (f'<span style="color:{MUTED};font-size:11.5px;"> · '
                   f'{title}</span>' if title else ""))
        return (f'<tr style="{bg}{edge}{top}">'
                + cell(name, "left", weight)
                + cell(f'<span class="ls-mono">{v["products"]}</span>',
                       "right", weight)
                + cell(f'<span class="ls-mono">{v["over"]}</span>',
                       "right", weight)
                + cell(bar(v["over"], v["products"]), "left")
                + cell(f'<span class="ls-mono" '
                       f'style="color:{ACCENT if v["risk"] else MUTED};">'
                       f'{fmt_money(v["risk"], "") if v["risk"] else "—"}'
                       f'</span>', "right", weight)
                + "</tr>")

    head = ("".join(
        f'<th style="padding:4px 8px;text-align:{a};font-size:11px;'
        f'letter-spacing:.06em;text-transform:uppercase;color:{MUTED};'
        f'font-weight:400;">{h}</th>'
        for h, a in ((t("synth.bd_market"), "left"),
                     (t("synth.bd_products"), "right"),
                     (t("synth.bd_over"), "right"),
                     (t("synth.bd_share"), "left"),
                     (t("synth.bd_risk"), "right"))))

    body = "".join(row(mp_label(m), stat[m], m in sel) for m in big)
    if small:
        agg = {k: sum(stat[m][k] for m in small)
               for k in ("products", "over", "risk")}
        body += row(t("synth.bd_other"), agg, False,
                    title=", ".join(sorted(small)))
    total = {k: sum(v[k] for v in stat.values())
             for k in ("products", "over", "risk")}
    body += row(t("synth.bd_total"), total, False, strong=True)
    return (f'<table style="width:100%;border-collapse:collapse;'
            f'font-size:13px;margin-bottom:10px;"><thead><tr>{head}</tr>'
            f'</thead><tbody>{body}</tbody></table>')


with tab_queue:
    st.markdown(market_breakdown(rows, all_products, mp_head),
                unsafe_allow_html=True)

    # Кнопки сегмента переносились на вторую строку — «принято» уезжало вниз
    # и выглядело сломанным элементом. Держим строку целой: запрещаем
    # перенос внутри группы кнопок и ужимаем отступы. Колонки Streamlit
    # при этом сжимаются по контенту, а не растягиваются на всю ширину.
    st.markdown(
        '<style>'
        '.st-key-syn_filters div[data-testid="stHorizontalBlock"]'
        '{flex-wrap:nowrap;gap:8px;align-items:center;}'
        # у группы кнопок display:block, поэтому одного flex-wrap мало —
        # переводим её во flex; сами кнопки лежат во ВЛОЖЕННОМ div, перенос
        # запрещаем и ему, иначе «принято» и «Таблица» уезжают на вторую строку
        '.st-key-syn_filters div[data-testid="stButtonGroup"]'
        '{display:flex !important;flex-wrap:nowrap !important;gap:2px;}'
        '.st-key-syn_filters div[data-testid="stButtonGroup"] > div'
        '{display:flex !important;flex-wrap:nowrap !important;}'
        '.st-key-syn_filters div[data-testid="stButtonGroup"] button'
        '{padding-left:10px !important;padding-right:10px !important;'
        'white-space:nowrap !important;}'
        '.st-key-syn_filters div[data-testid="stButtonGroup"] p'
        '{font-size:13px !important;white-space:nowrap !important;}'
        '</style>',
        unsafe_allow_html=True)

    # Фильтр «все / с SQP / без черновика / принято» убран: человек открывает
    # страницу работать, а его заставляли сначала выбрать режим. Путь теперь
    # один: открыл -> сгенерировал -> посмотрел было/стало -> принял -> выгрузил.
    with st.container(key="syn_filters"):
        f1, f2, f3 = st.columns([4.0, 1.8, 1.7])
        query = f1.text_input("q", label_visibility="collapsed",
                              placeholder=t("synth.search"))
        mps = sorted({x["r"]["marketplace"] for x in rows})
        # ключ обязателен: шапка страницы читает выбор из session_state,
        # она рисуется выше этого виджета
        mp_sel = f2.multiselect("MP", mps, default=[],
                                label_visibility="collapsed",
                                placeholder=t("list.all_mp"),
                                key=MP_FILTER_KEY)
        try:
            q_mode = f3.segmented_control(
                "вид", ["cards", "table"], default="cards",
                format_func=lambda k: t("list.cards") if k == "cards"
                else t("list.table"),
                selection_mode="single", label_visibility="collapsed",
                key="syn-mode")
        except AttributeError:
            q_mode = f3.radio("вид", ["cards", "table"], horizontal=True,
                              label_visibility="collapsed", key="syn-mode")
        q_mode = q_mode or "cards"

    # ---- выгрузка принятых тайтлов для загрузки в Amazon
    # Берём из synthesis_changes, а не из очереди: правку могли принять на
    # вкладке «любой товар», и в очередь title_over_limit такой товар
    # не попадает — иначе выгрузка молча теряла бы строки.
    _day = pd.Timestamp.now().strftime("%Y-%m-%d")
    _acc = load_accepted_titles(tuple(mp_sel) if mp_sel else None)
    # Та же природа, что в карточке: без флекса кнопки растягиваются
    # на всю долю колонки, и длинная подпись «для всех принятых · N»
    # переносится внутри кнопки на две строки.
    st.markdown(
        '<style>.st-key-exp_bar div[data-testid="stHorizontalBlock"]'
        '{gap:8px !important;align-items:center;flex-wrap:wrap;}'
        '.st-key-exp_bar div[data-testid="stColumn"]'
        '{flex:0 0 auto !important;width:auto !important;min-width:0 !important;}'
        '.st-key-exp_bar div[data-testid="stColumn"]:last-child'
        '{flex:1 1 auto !important;}'
        '.st-key-exp_bar .stButton button,'
        '.st-key-exp_bar .stDownloadButton button'
        '{white-space:nowrap !important;width:auto !important;'
        'padding-left:14px !important;padding-right:14px !important;}'
        '</style>', unsafe_allow_html=True)
    _bar = st.container(key="exp_bar")
    # третья колонка держит место под кнопку прямой отправки по API:
    # когда она появится, соседние не поедут и подписи не переверстаются
    with _bar:
        e1, e2, e3, e4 = st.columns([2.0, 1.6, 2.0, 3.4])
    if _acc.empty:
        # неактивны и с прямой подсказкой, что сделать: раньше две серые
        # кнопки просто терялись и было непонятно, почему они не нажимаются
        e1.button(t("export.flat"), disabled=True, key="exp-flat-none",
                  help=t("export.accept_first"))
        e2.button(t("export.csv"), disabled=True, key="exp-csv-none")
        e4.caption(f'{t("export.nothing")} — {t("export.accept_first")}')
    else:
        # раскладываем по шаблонам Amazon: один шаблон покрывает часть типов
        # товара, поэтому файлов может быть несколько, а часть строк может
        # не попасть никуда — про такие говорим прямо, а не молчим
        _plan, _bad = plan_export(_acc)
        _in = sum(len(i["rows"]) for i in _plan)
        _cname, _cmime, _cdata = build_csv_export(_acc, _day)
        if _plan:
            _fname, _fmime, _fdata = build_flat_cached(
                _plan, plan_signature(_plan), _day)
            e1.download_button(
                f'⬇ {t("export.flat")} · {t("export.for_all", n=_in)}', _fdata,
                               file_name=_fname, mime=_fmime, key="exp-flat",
                               type="primary")
        else:
            e1.button(t("export.flat"), disabled=True, key="exp-flat-notpl",
                      help=t("export.no_template"))
        e2.download_button(t("export.csv"), _cdata, file_name=_cname,
                           mime=_cmime, key="exp-csv")
        _mps_txt = ", ".join(sorted(_acc["marketplace"].unique())).upper()
        e4.caption(t("export.hint", n=_in, mps=_mps_txt,
                     files=len(_plan) or 1))
        if _bad:
            _why = Counter(b["reason"] for b in _bad)
            e4.caption("⚠ " + t("export.skipped", n=len(_bad)) + " — " +
                       ", ".join(f'{t("export.why_" + k)}: {v}'
                                 for k, v in _why.most_common()))
            with e4.expander(t("export.skipped_list"), expanded=False):
                st.dataframe(pd.DataFrame(_bad), hide_index=True,
                             width="stretch")

        # ---- прямая отправка в Amazon: третья кнопка, место под неё
        # держали с самого начала. Всё, что она делает по нажатию, —
        # открывает подтверждение. Отправку запускает только вторая кнопка,
        # внутри подтверждения: это запись в живые листинги клиента.
        _pushable = [dict(r, marketplace=i["marketplace"], tpl=i["tpl"])
                     for i in _plan for r in i["rows"]]
        _miss = missing_secrets()
        if not _pushable or _miss:
            e3.button(
                f'{t("push.button")} · {t("export.for_all", n=len(_pushable))}',
                disabled=True, key="push-open-off",
                      help=(t("push.no_keys", keys=", ".join(_miss)) if _miss
                            else t("export.accept_first")))
        elif e3.button(
                f'{t("push.button")} · {t("export.for_all", n=len(_pushable))}',
                key="push-open"):
            st.session_state["push-confirm"] = True
        if st.session_state.get("push-confirm") and _pushable:
            render_push_confirm(_pushable)

    render_push_result()

    view = rows
    if mp_sel:
        view = [x for x in view if x["r"]["marketplace"] in mp_sel]
    if query.strip():
        q = query.strip().lower()
        view = [x for x in view
                if q in str(x["r"]["asin"]).lower()
                or q in str(x["r"].get("sku_group") or "").lower()
                or q in str(x["r"]["title"] or "").lower()]

    # ---- пакетная генерация: партия берётся из ТЕКУЩЕЙ выборки, поэтому
    # блок стоит после фильтров. Раньше он был выше и молча работал по всей
    # очереди — «top-20» на отфильтрованном экране означал другие товары.
    # Товары с черновиком пропускаем: перегенерировать их незачем.
    _pending = [x for x in sorted(view, key=lambda z: -z["risk"])
                if not x["draft"].get("drafts")]
    b1, b2, b3 = st.columns([1.4, 2.2, 4])
    batch_n = b1.selectbox(
        "партия", [5, 10, 20, 50, 100, 0], index=2,
        format_func=lambda n: t("synth.batch_all") if n == 0 else f"top-{n}",
        label_visibility="collapsed", key="batch-n")
    _top = _pending if batch_n == 0 else _pending[:batch_n]
    if b2.button(f"{t('synth.batch_run')} ({len(_top)})", type="primary",
                 disabled=not _top or not skill_version,
                 help=(t("synth.skill_missing") if not skill_version
                       else None if _top else t("synth.batch_none"))):
        res = batch_generate(_top, skill_text, skill_version)
        # st.rerun() стирает всё, что нарисовал этот прогон, включая
        # st.error слоя ИИ — поэтому итог кладём в session_state
        # и показываем уже ПОСЛЕ перерисовки
        st.session_state["batch_outcome"] = res
        st.rerun()
    # итог прошлой партии — переживает st.rerun(), поэтому ошибки видны
    _out = st.session_state.pop("batch_outcome", None)
    if _out:
        if _out.get("unsaved"):
            # сгенерировано, но не легло в базу — самый обидный случай:
            # раньше он выглядел как успех
            st.error(t("synth.batch_unsaved", n=_out["unsaved"]))
        if _out["done"]:
            st.success(t("synth.batch_done", done=_out["done"],
                         failed=_out["failed"]))
            _s = _out.get("stats") or {}
            if _s.get("attempts"):
                st.caption(t("synth.guard_stats", att=_s["attempts"],
                             n=_out["done"] + _out["failed"],
                             retried=_s.get("retried", 0),
                             trimmed=_s.get("trimmed", 0),
                             over=_s.get("over", 0)))
        else:
            st.error(t("synth.batch_all_failed", failed=_out["failed"]))
        # расход токенов — единственная проверка, что кэш реально сработал:
        # метка cache_control ничего не гарантирует, короткий префикс
        # не кэшируется молча. Ноль прочитанного при непустой записи —
        # значит префикс менялся между товарами
        _u = _out.get("usage") or {}
        if _u.get("calls"):
            _read = int(_u.get("cache_read_input_tokens", 0))
            _write = int(_u.get("cache_creation_input_tokens", 0))
            _fresh = int(_u.get("input_tokens", 0))
            st.caption(t("synth.usage_line", calls=_u["calls"],
                         fresh=f"{_fresh:,}".replace(",", " "),
                         write=f"{_write:,}".replace(",", " "),
                         read=f"{_read:,}".replace(",", " ")))
            if _write and not _read:
                st.caption("⚠ " + t("synth.cache_miss"))
        for _line in _out.get("errors", [])[:5]:
            st.code(_line, language=None)
        if len(_out.get("errors", [])) > 5:
            st.caption(f"… ещё {len(_out['errors']) - 5}")

    b3.caption(t("synth.batch_hint") + " · "
               + t("synth.batch_pending", n=len(_pending)))

    if not view:
        st.caption(t("catalog.nothing"))
    else:
        view.sort(key=lambda z: (-z["risk"], -z["over"]))

        if q_mode == "table":
            _c = {
                "img": t("metric.photos"), "sku": "SKU", "asin": "ASIN",
                "mp": "MP", "len": t("metric.title"),
                "over": t("ruler.excess"), "risk": t("synth.at_risk_line"),
                "sqp": "SQP", "drafts": t("synth.drafts_n"),
                "cov": "Coverage", "acc": t("work.accepted"),
                "title": t("card.title"), "link": t("matrix.collect"),
            }
            _sqp_txt = {"ready": t("metric.yes"), "queued": t("work.no_draft"),
                        "off": t("metric.no")}
            # имена колонок технические, подписи — в column_config
            _sqp_txt = {"ready": t("metric.yes"), "queued": t("work.no_draft"),
                        "off": t("metric.no")}
            tv = pd.DataFrame([{
                "img": (None if pd.isna(z["r"].get("main_image"))
                        else z["r"].get("main_image")),
                "sku": z["r"]["sku_group"],
                "asin": z["r"]["asin"],
                "mp": z["r"]["marketplace"],
                "len": len(z["r"]["title"] or ""),
                "over": z["over"],
                "risk": round(z["risk"]) if z["risk"] else None,
                "sqp": _sqp_txt[z["sqp_state"]],
                "drafts": (int(z["draft"]["drafts"])
                           if z["draft"].get("drafts") else 0),
                "cov": (int(z["draft"]["coverage"])
                        if z["draft"].get("coverage") is not None
                        and not pd.isna(z["draft"].get("coverage")) else None),
                "acc": ("✓" if z["accepted"] else ""),
                "title": (z["r"]["title"] or "")[:70],
                "link": f"https://www.amazon.{z['r']['marketplace']}"
                        f"/dp/{z['r']['asin']}",
            } for z in view])
            st.dataframe(
                tv,
                column_config={
                    "img": st.column_config.ImageColumn(
                        t("metric.photos"), width="small"),
                    "sku": st.column_config.TextColumn("SKU", width="small"),
                    "asin": st.column_config.TextColumn("ASIN", width="small"),
                    "mp": st.column_config.TextColumn("MP", width="small"),
                    "len": st.column_config.NumberColumn(
                        t("metric.title"), width="small"),
                    "over": st.column_config.NumberColumn(
                        t("ruler.excess"), width="small"),
                    "risk": st.column_config.NumberColumn(
                        f"{t('synth.at_risk_line')}, EUR", format="%.0f",
                        width="small"),
                    "sqp": st.column_config.TextColumn("SQP", width="small"),
                    "drafts": st.column_config.NumberColumn(
                        t("synth.drafts_n"), width="small"),
                    "cov": st.column_config.NumberColumn(
                        "Coverage, %", format="%.0f", width="small"),
                    "acc": st.column_config.TextColumn(
                        t("work.accepted"), width="small"),
                    "title": st.column_config.TextColumn(
                        t("card.title"), width="large"),
                    "link": st.column_config.LinkColumn(
                        t("matrix.collect"), display_text="→"),
                },
                hide_index=True, width="stretch", height=520)
            st.caption(t("list.sort_hint"))
            st.stop()

        for x in view[:30]:
            r = x["r"]
            asin, mp = r["asin"], r["marketplace"]
            title = r["title"] or ""
            render_card_head(x)

            with st.expander(f"{t('synth.work_with')} · {asin} · {mp}"):
                fetched = (pd.to_datetime(r["fetched_at"]).strftime("%d.%m %H:%M")
                           if pd.notna(r["fetched_at"]) else "—")
                st.markdown(
                    eyebrow(f"{t('synth.original')} · {len(title)} симв. · "
                            f"{t('matrix.collected_at')} {fetched} · "
                            f"{t('synth.methodology')} v{skill_version}"),
                    unsafe_allow_html=True)
                st.code(title, language=None)
                st.markdown(
                    limit_ruler_html(len(title), TITLE_LIMIT,
                                     left_label=f"{TITLE_LIMIT} {t('ruler.limit')}",
                                     right_label=f"+{x['over']} {t('ruler.cut')}"),
                    unsafe_allow_html=True)

                # Результат — СРАЗУ под оригиналом, до таблицы фраз: раньше
                # черновик уезжал на другую вкладку, за 25 строк SQP.
                render_result(asin, mp, title, PENDING_MAP.get((asin, mp)))

                st.markdown(eyebrow(t("synth.keywords")),
                            unsafe_allow_html=True)
                kw = build_keyword_table(asin, mp, title)
                kw_edit = pd.DataFrame()
                if kw.empty and sqp_error():
                    # «данных нет» — утверждение о данных; при сбое чтения
                    # оно ложное, и генерация пойдёт без защищённых фраз
                    st.error("⚠ " + t("synth.sqp_failed", e=sqp_error()))
                elif kw.empty:
                    st.caption(SQP_LABEL[x["sqp_state"]] + " · "
                               + t("synth.no_sqp"))
                else:
                    kw_edit = kw_editor(kw, f"kw-{asin}-{mp}")
                    cnt = kw_edit["tier"].value_counts().to_dict()
                    st.markdown(" · ".join(f"{TIER_LABEL[k]} {cnt.get(k, 0)}"
                                           for k in TIERS))

                keep_list, forbid_list = [], []
                if not kw_edit.empty:
                    o = kw_edit.sort_values("w", ascending=False)
                    keep_list = o.loc[o["tier"].isin(["must_keep", "preferred"]),
                                      "phrase"].tolist()
                    forbid_list = o.loc[o["tier"] == "forbid", "phrase"].tolist()

                _regen = st.session_state.pop(f"regen-{asin}-{mp}", False)
                if st.button(t("synth.generate"), type="primary",
                             key=f"gen-{asin}-{mp}",
                             disabled=not skill_version) or _regen:
                    with st.status(f"{t('gen.title')} · v{skill_version}",
                                   expanded=True) as _status:
                        _status.write("· " + t("gen.phrases"))
                        _must = (kw.loc[kw["tier"] == "must_keep",
                                        "search_query"].tolist()
                                 if not kw.empty else [])
                        res, _st = generate_guarded(
                            title, mp, skill_text, keep_list, forbid_list,
                            kw_edit if not kw_edit.empty else kw, _must,
                            skill_version, on_step=step_writer(_status))
                    if res:
                        save_draft(asin, mp, title, res, skill_version)
                        if not kw.empty:
                            save_coverage(asin, mp, coverage(
                                kw, res.get("title", ""),
                                res.get("highlights", "")))
                        st.session_state[f"res-{asin}-{mp}"] = res
                        st.cache_data.clear()
                        st.rerun()

    if len(view) > 30:
        st.caption(f"показано 30 из {len(view)} — уточни фильтры")


# ================================================================ разбор
with tab_review:
    if pending.empty:
        st.info(t("synth.no_drafts"))
    else:
        st.caption(t("synth.review_hint"))
        econ_sorted = []
        for _, d in pending.iterrows():
            e = ECON.get((d["asin"], d["marketplace"])) or {}
            econ_sorted.append((money_at_risk("title_over_limit",
                                              e.get("revenue_30d")), d))
        econ_sorted.sort(key=lambda z: -z[0])

        for risk, d in econ_sorted:
            asin, mp = d["asin"], d["marketplace"]
            before = d["title_before"] or ""
            after = d["title_after"] or ""
            hl = d["highlights_after"] or ""
            checks = run_checks(after, hl, [], [])
            n_failed = sum(1 for ok, _ in checks if not ok)
            qual, qtext = draft_quality(d.get("coverage_score"), n_failed)
            color = Q_COLOR[qual]

            st.markdown(
                f'<div class="ls-card" style="background:#fff;'
                f'border:1px solid #E7E4DD;border-left:3px solid {color};'
                f'border-radius:0 10px 10px 0;padding:10px 14px;'
                f'margin-bottom:4px;">'
                f'<div style="display:flex;justify-content:space-between;">'
                f'<span style="font-size:13px;font-weight:700;">{asin} · {mp}'
                f'<span style="font-weight:400;color:#57534A;"> · '
                f'{len(before)} → {len(after)} симв.</span></span>'
                f'<span class="ls-mono" style="font-size:12.5px;color:{color};">'
                f'{qtext}{" · " + fmt_money(risk) if risk else ""}</span></div>'
                f'<div style="font-size:12.5px;color:#1A1815;margin-top:4px;'
                f'font-family:var(--ls-mono);">{after}</div></div>',
                unsafe_allow_html=True)

            with st.expander(f"{t('synth.details')} · {asin} · {mp}"):
                st.markdown(f"**{t('synth.was')}**")
                st.code(before, language=None)
                st.markdown(f"**title** · {len(after)}/{TITLE_LIMIT}")
                st.code(after, language=None)
                st.markdown(f"**item highlights** · {len(hl)}/{HIGHLIGHTS_LIMIT}")
                st.code(hl, language=None)
                render_preview(after, hl, mp)
                if d.get("dropped"):
                    st.markdown(f"**{t('synth.dropped')}:** {d['dropped']}")
                st.markdown(" · ".join(("✅ " if ok else "❌ ") + m
                                       for ok, m in checks))

            c1, c2, c3 = st.columns([1.3, 1.2, 4])
            if c1.button(t("synth.accept_short"), type="primary",
                         disabled=bool(n_failed),
                         key=f"acc-{asin}-{mp}-{d['id']}"):
                if accept_change(asin, mp, before,
                                 {"title": after, "highlights": hl,
                                  "dropped": (d.get("dropped") or "").split("; ")},
                                 d.get("coverage_score"),
                                 int(d.get("skill_version") or 0),
                                 TITLE_MODEL):
                    st.success(t("synth.accepted_ok"))
                    st.rerun()
            if c2.button(t("synth.regenerate"), key=f"re-{asin}-{mp}-{d['id']}"):
                kw = build_keyword_table(asin, mp, before)
                keep = forbid = []
                if not kw.empty:
                    keep = kw.loc[kw["tier"].isin(["must_keep", "preferred"]),
                                  "search_query"].tolist()
                    forbid = kw.loc[kw["tier"] == "forbid",
                                    "search_query"].tolist()
                with st.spinner(t("synth.regenerate")):
                    _rmust = (kw.loc[kw["tier"] == "must_keep",
                                     "search_query"].tolist()
                              if not kw.empty else [])
                    res, _rst = generate_guarded(before, mp, skill_text, keep,
                                                 forbid, kw, _rmust,
                                                 skill_version)
                if res:
                    save_draft(asin, mp, before, res, skill_version)
                    if not kw.empty:
                        save_coverage(asin, mp, coverage(
                            kw, res.get("title", ""), res.get("highlights", "")))
                    st.cache_data.clear()
                    st.rerun()


# ================================================================ любой товар
with tab_any:
    st.caption(t("synth.any_hint"))
    if all_products.empty:
        st.info(t("common.no_data"))
    else:
        aq1, aq2 = st.columns([3, 2])
        any_query = aq1.text_input(
            "q", label_visibility="collapsed", key="any-q",
            placeholder=t("catalog.search"))
        any_mps = sorted(all_products["marketplace"].dropna().unique())
        any_mp = aq2.multiselect("MP", any_mps, default=[],
                                 label_visibility="collapsed",
                                 placeholder=t("list.all_mp"), key="any-mp")

        av = all_products
        if any_mp:
            av = av[av["marketplace"].isin(any_mp)]
        if any_query.strip():
            q = any_query.strip().lower()
            av = av[
                av["asin"].astype(str).str.lower().str.contains(q, na=False)
                | av["sku_group"].astype(str).str.lower().str.contains(q, na=False)
                | av["title"].astype(str).str.lower().str.contains(q, na=False)
            ]

        st.caption(f"{t('matrix.found')} {len(av)}")
        if av.empty:
            st.caption(t("catalog.nothing"))
        else:
            with st.expander(f"{t('list.table')} ({len(av)})"):
                # имена колонок технические, подписи — в column_config,
                # иначе на разных языках возникают дубли и pyarrow падает
                atv = av.copy()
                atv["len"] = atv["title"].astype(str).str.len().where(
                    atv["title"].notna(), None)
                atv["over"] = (atv["len"] - TITLE_LIMIT).clip(lower=0)
                atv["got"] = pd.to_datetime(
                    atv["fetched_at"], errors="coerce").dt.strftime("%d.%m %H:%M")
                atv["link"] = atv.apply(
                    lambda z: f"https://www.amazon.{z['marketplace']}"
                              f"/dp/{z['asin']}", axis=1)
                st.dataframe(
                    atv[["main_image", "sku_group", "asin", "marketplace",
                         "len", "over", "got", "title", "link"]],
                    column_config={
                        "main_image": st.column_config.ImageColumn(
                            t("metric.photos"), width="small"),
                        "sku_group": st.column_config.TextColumn(
                            "SKU", width="small"),
                        "asin": st.column_config.TextColumn("ASIN", width="small"),
                        "marketplace": st.column_config.TextColumn(
                            "MP", width="small"),
                        "len": st.column_config.NumberColumn(
                            t("metric.title"), width="small"),
                        "over": st.column_config.NumberColumn(
                            t("ruler.excess"), width="small"),
                        "got": st.column_config.TextColumn(
                            t("matrix.collected_at"), width="small"),
                        "title": st.column_config.TextColumn(
                            t("card.title"), width="large"),
                        "link": st.column_config.LinkColumn(
                            t("matrix.collect"), display_text="→"),
                    },
                    hide_index=True, width="stretch", height=420)
                st.caption(t("list.sort_hint"))

            opts = {}
            for _, r in av.head(300).iterrows():
                # NaN истинный в Python: без pd.isna() len(NaN) уронит страницу
                raw_title = r.get("title")
                title_s = "" if raw_title is None or pd.isna(raw_title) else str(raw_title)
                raw_sku = r.get("sku_group")
                sku_s = "" if raw_sku is None or pd.isna(raw_sku) else str(raw_sku)
                sku = f"{sku_s} · " if sku_s and sku_s != r["asin"] else ""
                ln = f" · {len(title_s)}" if title_s else ""
                ttl = title_s[:60] if title_s else t("matrix.not_collected")
                opts[f"{sku}{r['asin']} · {r['marketplace']}{ln} · {ttl}"] = (
                    r["asin"], r["marketplace"])

            pick = st.selectbox(t("photo.product"), list(opts.keys()), key="any-pick")
            a_asin, a_mp = opts[pick]
            arow = av[(av["asin"] == a_asin)
                      & (av["marketplace"] == a_mp)].iloc[0]
            a_title = arow["title"] or ""

            if not a_title:
                st.warning(t("synth.no_snapshot"))
            else:
                over = max(0, len(a_title) - TITLE_LIMIT)
                fetched = (pd.to_datetime(arow["fetched_at"]).strftime("%d.%m %H:%M")
                           if pd.notna(arow["fetched_at"]) else "—")
                st.markdown(
                    eyebrow(f"{t('synth.original')} · {len(a_title)} симв. · "
                            f"{t('matrix.collected_at')} {fetched} · "
                            f"{t('synth.methodology')} v{skill_version}"),
                    unsafe_allow_html=True)
                st.code(a_title, language=None)
                st.markdown(
                    limit_ruler_html(
                        len(a_title), TITLE_LIMIT,
                        left_label=f"{TITLE_LIMIT} {t('ruler.limit')}",
                        right_label=(f"+{over} {t('ruler.cut')}" if over
                                     else f"{t('ruler.free')} "
                                          f"{TITLE_LIMIT - len(a_title)}")),
                    unsafe_allow_html=True)
                if not over:
                    st.caption(t("synth.in_limit"))

                st.markdown(eyebrow(t("synth.keywords")),
                            unsafe_allow_html=True)
                a_kw = build_keyword_table(a_asin, a_mp, a_title)
                a_edit = pd.DataFrame()
                if a_kw.empty:
                    st.caption(t("synth.no_sqp"))
                else:
                    a_edit = kw_editor(a_kw, f"any-kw-{a_asin}-{a_mp}")
                    cnt = a_edit["tier"].value_counts().to_dict()
                    st.markdown(" · ".join(f"{TIER_LABEL[k]} {cnt.get(k, 0)}"
                                           for k in TIERS))

                a_keep, a_forbid = [], []
                if not a_edit.empty:
                    o = a_edit.sort_values("w", ascending=False)
                    a_keep = o.loc[o["tier"].isin(["must_keep", "preferred"]),
                                   "phrase"].tolist()
                    a_forbid = o.loc[o["tier"] == "forbid", "phrase"].tolist()

                if st.button(t("synth.generate"), type="primary",
                             key=f"any-gen-{a_asin}-{a_mp}",
                             disabled=not skill_version):
                    with st.status(f"{t('gen.title')} · v{skill_version}",
                                   expanded=True) as _astatus:
                        _astatus.write("· " + t("gen.phrases"))
                        _amust = (a_kw.loc[a_kw["tier"] == "must_keep",
                                          "search_query"].tolist()
                                  if not a_kw.empty else [])
                        ares, _ast = generate_guarded(
                            a_title, a_mp, skill_text, a_keep, a_forbid,
                            a_edit if not a_edit.empty else a_kw, _amust,
                            skill_version, on_step=step_writer(_astatus))
                    if ares:
                        save_draft(a_asin, a_mp, a_title, ares, skill_version)
                        if not a_kw.empty:
                            save_coverage(a_asin, a_mp, coverage(
                                a_kw, ares.get("title", ""),
                                ares.get("highlights", "")))
                        st.session_state[f"any-res-{a_asin}-{a_mp}"] = ares
                        st.cache_data.clear()
                        st.rerun()

                ares = st.session_state.get(f"any-res-{a_asin}-{a_mp}")
                if ares:
                    a_new = ares.get("title", "")
                    a_hl = ares.get("highlights", "")
                    st.divider()
                    a_cov = None
                    if not a_edit.empty:
                        cdf = a_kw.copy()
                        tmap = dict(zip(a_edit["phrase"], a_edit["tier"]))
                        cdf["tier"] = cdf["search_query"].map(tmap).fillna("compress")
                        cv = coverage(cdf, a_new, a_hl)
                        a_cov = cv["score"]
                        if a_cov is not None:
                            col = ("#2F6B3A" if a_cov >= 85
                                   else "#854F0B" if a_cov >= 65 else "#A32D2D")
                            st.markdown(
                                f'<div style="font-size:19px;font-weight:700;">'
                                f'SEO Coverage <span style="color:{col};'
                                f'font-family:var(--ls-mono);">{a_cov}%</span>'
                                f'</div>', unsafe_allow_html=True)
                            if cv["lost"]:
                                st.markdown(f"**{t('synth.lost')}:** "
                                            + " · ".join(
                                    f"`{p}`" for p, _, _ in cv["lost"][:6]))

                    st.markdown(f"**title** · {len(a_new)}/{TITLE_LIMIT}")
                    st.code(a_new, language=None)
                    st.markdown(f"**item highlights** · {len(a_hl)}/{HIGHLIGHTS_LIMIT}")
                    st.code(a_hl, language=None)
                    render_preview(a_new, a_hl, a_mp)
                    if ares.get("dropped"):
                        st.markdown(f"**{t('synth.dropped')}:** "
                                    + " · ".join(f"`{w}`"
                                                 for w in ares["dropped"]))

                    a_checks = run_checks(a_new, a_hl, a_keep, a_forbid)
                    a_failed = [m for ok, m in a_checks if not ok]
                    st.markdown(" · ".join(("✅ " if ok else "❌ ") + m
                                           for ok, m in a_checks))

                    ac1, ac2 = st.columns([1.4, 1])
                    if ac1.button(t("synth.accept"), type="primary",
                                  disabled=bool(a_failed),
                                  key=f"any-acc-{a_asin}-{a_mp}"):
                        if accept_change(a_asin, a_mp, a_title, ares, a_cov,
                                         skill_version, TITLE_MODEL):
                            st.success(t("synth.accepted_ok"))
                            st.rerun()
                    if ac2.button(t("synth.regenerate"),
                                  key=f"any-re-{a_asin}-{a_mp}"):
                        st.session_state.pop(f"any-res-{a_asin}-{a_mp}", None)
                        st.rerun()
