"""Генерация текстов по паспорту SKU (решение владельца 21.10.2026).

«Сгенерировать» на странице генератора: тайтл, Item Highlight, 5 буллетов и
описание — из фактов сохранённой копии паспорта, по методологии области
`textgen` (`synthesis_skill`; `title_split` и `bullets` не трогаются).

Лимиты — решение владельца: 10 вызовов на товар в сутки, $1 на товар в сутки,
$10 в сутки на весь пилот; сутки — по Киеву. Считаются по журналу
`textgen_calls` (миграция 2026-10-21_textgen_calls.sql), а не по сессии. Перед
вызовом под блокировкой резервируется ОЦЕНКА СВЕРХУ (максимум токенов ответа по
цене модели), после вызова она заменяется фактической ценой по расходу токенов.
Цена модели неизвестна — генерации нет: лимит в долларах без цены не проверить.

Результат — черновики `content_versions` (8 полей одним предложением `TG-<id>`)
с проверками правил тайтла кодом. Модель и деньги — только по нажатию человека
с правом `ls.textgen.accept`; право проверяет страница.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field

from services import passport_copies as pc
from services import passport_facts as pf
from services import title_rules as tr

SCOPE = "textgen"
TASK = "textgen"
FIELDS = ("title", "highlight", "bullet_1", "bullet_2", "bullet_3", "bullet_4", "bullet_5", "description")

LIMIT_CALLS_SKU_DAY = 10
LIMIT_USD_SKU_DAY = 1.0
LIMIT_USD_PILOT_DAY = 10.0

# Цена, USD за миллион токенов (вход, выход). Переопределяется настройкой
# `price.<модель>` = «вход/выход» в app_settings. Вход-кэш считается по полной цене
# входа — оценка сверху, лимит не занижается.
DEFAULT_PRICES = {"claude-sonnet-5": (3.0, 15.0)}

LANGUAGE = {"es": "español", "de": "Deutsch", "it": "italiano", "fr": "français", "nl": "Nederlands",
            "pl": "polski", "se": "svenska", "be": "français", "co.uk": "English (UK)", "ie": "English (UK)"}

DAY_START = "(date_trunc('day', now() AT TIME ZONE 'Europe/Kyiv') AT TIME ZONE 'Europe/Kyiv')"


@dataclass
class Usage:
    calls_sku: int = 0
    usd_sku: float = 0.0
    usd_pilot: float = 0.0


@dataclass
class Result:
    status: str                         # OK | BLOCKED | FAILED
    code: str = ""                      # причина для BLOCKED / FAILED → i18n tg.gen.err.<code>
    detail: str = ""
    call_id: int | None = None
    proposal_id: str = ""
    texts: dict = field(default_factory=dict)
    checks: list = field(default_factory=list)
    cost_usd: float = 0.0


# ------------------------------------------------------------------ цена
def price(model: str, setting=None) -> tuple[float, float] | None:
    """(вход, выход) USD за миллион токенов; None — цена неизвестна."""
    raw = (setting(f"price.{model}", "") if setting else "") or ""
    try:
        a, b = (float(x) for x in str(raw).replace(",", ".").split("/"))
        if a >= 0 and b >= 0:
            return a, b
    except ValueError:
        pass
    return DEFAULT_PRICES.get(model)


def cost(p: tuple[float, float], input_tokens: int, output_tokens: int) -> float:
    return round((input_tokens * p[0] + output_tokens * p[1]) / 1_000_000, 4)


def estimate(p: tuple[float, float], prompt_chars: int, max_tokens: int) -> float:
    """Оценка сверху: токен входа — не меньше двух знаков (кириллица дороже
    латиницы), выход — весь бюджет ответа вместе с размышлением."""
    return round(math.ceil(cost(p, prompt_chars // 2 + 1, max_tokens) * 10_000) / 10_000, 4)


def usage_cost(p: tuple[float, float], usage: dict) -> tuple[int, int, float]:
    tin = sum(int(usage.get(k) or 0) for k in
              ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    tout = int(usage.get("output_tokens") or 0)
    return tin, tout, cost(p, tin, tout)


# ------------------------------------------------------------------ лимиты
def day_usage(cur, sku: str) -> Usage:
    """Расход за сутки по Киеву: вызовы и деньги товара, деньги всего пилота."""
    cur.execute(
        "SELECT count(*) FILTER (WHERE sku = %s), COALESCE(sum(cost_usd) FILTER (WHERE sku = %s), 0),"
        " COALESCE(sum(cost_usd), 0) FROM textgen_calls WHERE started_at >= " + DAY_START, (sku, sku))
    n, a, b = cur.fetchone()
    return Usage(int(n or 0), float(a or 0), float(b or 0))


def block_reason(u: Usage, est: float) -> tuple[str, str] | None:
    """Причина выключить кнопку или отказать в момент нажатия; None — можно."""
    if u.calls_sku >= LIMIT_CALLS_SKU_DAY:
        return "LIMIT_CALLS", f"{u.calls_sku}/{LIMIT_CALLS_SKU_DAY}"
    if u.usd_sku + est > LIMIT_USD_SKU_DAY:
        return "LIMIT_USD_SKU", f"${u.usd_sku:.2f} + ${est:.2f} > ${LIMIT_USD_SKU_DAY:.0f}"
    if u.usd_pilot + est > LIMIT_USD_PILOT_DAY:
        return "LIMIT_USD_PILOT", f"${u.usd_pilot:.2f} + ${est:.2f} > ${LIMIT_USD_PILOT_DAY:.0f}"
    return None


# ------------------------------------------------------------------ промпт
def build_prompt(sku: str, marketplace: str, header: dict, facts: pf.Facts) -> str:
    lang = LANGUAGE.get(marketplace, "English")
    return (f"Площадка: Amazon {marketplace.upper()}. Язык всех текстов: {lang}.\n"
            f"SKU: {sku}. Паспорт {header.get('passport_id')} v{header.get('passport_version')}, "
            f"состояние {header.get('state') or '—'}.\n\n"
            f"ФАКТЫ ПАСПОРТА\n{facts.prompt_text()}\n\n"
            "Ответ — только JSON, без пояснений:\n"
            '{"title": "…", "highlight": "…", "bullets": ["…", "…", "…", "…", "…"], "description": "…"}')


def parse_answer(data) -> dict | None:
    """Ответ модели → {поле: текст} для всех восьми полей; иначе None."""
    if not isinstance(data, dict):
        return None
    b = data.get("bullets")
    if not (isinstance(b, list) and len(b) == 5 and all(isinstance(x, str) and x.strip() for x in b)):
        return None
    out = {"title": data.get("title"), "highlight": data.get("highlight"), "description": data.get("description")}
    if not all(isinstance(v, str) and v.strip() for v in out.values()):
        return None
    out.update({f"bullet_{i}": x for i, x in enumerate(b, 1)})
    return {k: str(out[k]).strip() for k in FIELDS}


def model_code(facts: pf.Facts) -> str | None:
    for s in facts.sections:
        if not s.rows:
            continue
        head = [h.strip().lower() for h in s.rows[0]]
        for r in s.rows[1:]:
            row = dict(zip(head, r))
            name = row.get("поле") or row.get("характеристика") or ""
            if name.strip().lower() == "модель" and row.get("значення"):
                return row["значення"].strip()
    return None


def run_checks(texts: dict, model: str | None) -> list[dict]:
    found = tr.check(texts["title"], texts["highlight"], kind=tr.TOOL, model=model)
    out = [{"code": v.code, "field": "highlight" if v.field == "highlights" else v.field, "detail": v.detail}
           for v in found]
    if not model:
        out.append({"code": "NO_MODEL_PREFIX_CHECK", "field": "highlight", "detail": ""})
    return out


# ------------------------------------------------------------------ генерация
def generate(*, sku: str, marketplace: str, copy: dict, actor: str, store, conn, method: tuple[str, int],
             provider: str, model: str, max_tokens: int, setting, ai_call, ai_usage, ai_reset,
             ai_error=lambda: None) -> Result:
    """Один вызов модели и черновики. `copy` — строка `passport_source_artifacts`
    (source_artifact_id, passport_id, archived_locator, sha256). Вызов модели и
    его учёт — через переданные функции: страница отдаёт `services/ai`, тест —
    подмену."""
    m_text, m_ver = method
    if not (m_text or "").strip() or not m_ver:
        return Result("BLOCKED", "NO_METHOD", SCOPE)
    p = price(model, setting)
    if p is None:
        return Result("BLOCKED", "NO_PRICE", model)
    try:
        data = store.get(copy["archived_locator"])
    except Exception as e:  # noqa: BLE001 — причина уходит на экран
        return Result("FAILED", "COPY_UNREADABLE", f"{type(e).__name__}: {str(e)[:160]}")
    if hashlib.sha256(data).hexdigest() != copy["sha256"]:
        return Result("FAILED", "COPY_CHANGED", copy["source_artifact_id"])
    header = pc.read_header(data)
    if header["sku_id"] != sku:
        return Result("FAILED", "COPY_OTHER_SKU", f"{header['sku_id']} ≠ {sku}")
    facts = pf.read(data)
    prompt = build_prompt(sku, marketplace, header, facts)
    est = estimate(p, len(prompt) + len(m_text), max_tokens)

    with conn, conn.cursor() as cur:
        # Одна блокировка на весь пилот: лимит пилота общий, проверка и резерв —
        # одним шагом, иначе два нажатия разом прошли бы оба.
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('textgen_limits'))")
        why = block_reason(day_usage(cur, sku), est)
        if why:
            return Result("BLOCKED", why[0], why[1])
        cur.execute("INSERT INTO textgen_calls (sku, marketplace, actor, provider, model, cost_usd)"
                    " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id", (sku, marketplace, actor, provider, model, est))
        call_id = cur.fetchone()[0]

    ai_reset()
    answer = None
    err = ""
    try:
        answer = ai_call(TASK, prompt, system=m_text)
    except Exception as e:  # noqa: BLE001 — вызов уже учтён резервом, итог запишем
        err = f"{type(e).__name__}: {str(e)[:200]}"
    usage = ai_usage() or {}
    tin, tout, real = usage_cost(p, usage)
    if not usage:
        real = est        # расход неизвестен — списываем оценку, не ноль
    texts = parse_answer(answer)
    if texts is None and not err:
        err = ai_error() or "ответ модели не в формате (title, highlight, 5 bullets, description)"
    proposal = f"TG-{call_id}"
    with conn, conn.cursor() as cur:
        cur.execute("UPDATE textgen_calls SET status = %s, finished_at = now(), input_tokens = %s,"
                    " output_tokens = %s, cost_usd = %s, proposal_id = %s, error = %s WHERE id = %s",
                    ("ok" if texts else "failed", tin or None, tout or None, real,
                     proposal if texts else None, err or None, call_id))
    if texts is None:
        return Result("FAILED", "MODEL", err, call_id, cost_usd=real)

    checks = run_checks(texts, model_code(facts))
    with conn, conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"content:{sku}:{marketplace}",))
        for f in FIELDS:
            cur.execute("SELECT COALESCE(max(version), 0) FROM content_versions"
                        " WHERE sku = %s AND marketplace = %s AND field = %s", (sku, marketplace, f))
            ver = int(cur.fetchone()[0]) + 1
            mine = [c for c in checks if c["field"] == f]
            cur.execute(
                "INSERT INTO content_versions (sku, marketplace, field, text, version, proposal_id, created_by,"
                " passport_id, passport_version, passport_sha256, passport_artifact_id, origin, model,"
                " skill_version, checks) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'model', %s, %s, %s)",
                (sku, marketplace, f, texts[f], ver, proposal, actor, header["passport_id"],
                 str(header["passport_version"]), copy["sha256"], copy["source_artifact_id"], model, m_ver,
                 json.dumps(mine, ensure_ascii=False)))
    return Result("OK", "", "", call_id, proposal, texts, checks, real)


# ------------------------------------------------------------------ чтение для экрана
def active_copies():
    """Действующие копии паспортов docx: (df, причина), как `safe_read`."""
    from services.db import safe_read
    return safe_read(
        "SELECT source_artifact_id, sku_id, passport_id, archived_locator, sha256, recorded_at"
        " FROM passport_source_artifacts WHERE lifecycle = 'ACTIVE' AND mime_type = %(m)s"
        " AND archived_locator LIKE %(r)s ORDER BY sku_id", {"m": pc.MIME, "r": pc.ROOT + "/%"})


def usage_now(sku: str):
    """Расход за сегодня для подписи у кнопки: (Usage, причина-сбоя)."""
    from services.db import safe_read
    df, err = safe_read(
        "SELECT count(*) FILTER (WHERE sku = %(s)s) AS n, COALESCE(sum(cost_usd) FILTER (WHERE sku = %(s)s), 0) AS a,"
        " COALESCE(sum(cost_usd), 0) AS b FROM textgen_calls WHERE started_at >= " + DAY_START, {"s": sku})
    if err:
        return None, err
    r = df.iloc[0]
    return Usage(int(r["n"]), float(r["a"]), float(r["b"])), None


def latest(sku: str, marketplace: str):
    """Последнее предложение генератора по SKU × рынку: (df, причина)."""
    from services.db import safe_read
    return safe_read(
        "SELECT field, text, text_len, version, proposal_id, status, model, checks, created_at"
        " FROM content_versions WHERE sku = %(s)s AND marketplace = %(m)s AND proposal_id = ("
        " SELECT proposal_id FROM content_versions WHERE sku = %(s)s AND marketplace = %(m)s"
        " AND proposal_id LIKE 'TG-%%' ORDER BY id DESC LIMIT 1)", {"s": sku, "m": marketplace})
