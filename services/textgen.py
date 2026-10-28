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
с проверками правил кодом: правила тайтла (`services/title_rules.py`) и правки
Ярослава 21.10.2026 (`run_checks`). У каждого черновика — штамп версии: номер
методологии, модель, `prompt_sha256` (ровно то, что ушло в модель) и
`rules_version` (коммит кода правил) — после обновления правил видно, почему
старый текст отличается от нового. Модель и деньги — только по нажатию человека
с правом `ls.textgen.accept`; право проверяет страница.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
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

# Цена, USD за миллион токенов (вход, выход) — по справочнику Anthropic на 06.10.2026
# (проверка #167). Переопределяется настройкой `price.<модель>` = «вход/выход» в
# app_settings. Запись в кэш стоит до 2× входа (кэш на час), чтение — 0,1×: в счёт
# идёт запись по 2×, чтение — по полной цене входа. Оценка сверху, лимит не занижается.
DEFAULT_PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5": (2.0, 10.0)}
CACHE_WRITE_FACTOR = 2.0
# Только Anthropic: расход размышления у Gemini (`thoughtsTokenCount`) слой ai не
# считает, и цена вызова вышла бы заниженной — лимит в долларах врал бы.
PROVIDERS = ("anthropic",)

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
    stamped: bool = False               # колонки штампа есть и записаны (миграция применена)
    rules_version: str | None = None    # что записано в rules_version; None при stamped — коммит не прочитан


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
    """Оценка сверху: токен входа — не меньше знака (на деле 2–4 знака) и весь вход
    по цене записи в кэш; выход — весь бюджет ответа вместе с размышлением."""
    tin = int(math.ceil((prompt_chars + 1) * CACHE_WRITE_FACTOR))
    return round(math.ceil(cost(p, tin, max_tokens) * 10_000) / 10_000, 4)


def usage_cost(p: tuple[float, float], usage: dict) -> tuple[int, int, float]:
    tin = sum(int(usage.get(k) or 0) for k in
              ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    billable_in = (int(usage.get("input_tokens") or 0) + int(usage.get("cache_read_input_tokens") or 0)
                   + CACHE_WRITE_FACTOR * int(usage.get("cache_creation_input_tokens") or 0))
    tout = int(usage.get("output_tokens") or 0)
    return tin, tout, cost(p, int(math.ceil(billable_in)), tout)


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


# ------------------------------------------------------------------ правила 21.10.2026
# Правки Ярослава по 99601000-B, по слову владельца общие для генерации всех
# товаров (docs/textgen.md). Код ловит то, что видно по тексту; смысл заголовка
# («ценность, а не название функции») по тексту не проверить — его держат
# методология и человек при приёмке. Бренд первым — `title_rules` (BRAND_NOT_FIRST).

# Заголовок буллета — капсом и через двоеточие: «CAMBIA DE ASPIRAR A SOPLAR SIN
# DESMONTAR: …». Двоеточие между цифрами («TRITURA 15:1 LAS HOJAS: …») заголовок
# не обрывает. Число с единицей («4Ah», «20V», «245 km/h», «3,5 m³/min») в заголовке
# капсом нарушением не считается: единицы пишутся со строчными (проверка #175).
_BULLET_HEAD = re.compile(r"^\s*((?:[^:\n]|(?<=\d):(?=\d))+?)\s*:\s+\S")
_UNIT_TOKEN = re.compile(r"\d[\d.,:]*\s?(?:km/h|m[³3]/(?:min|h)|mAh|Ah|Nm|kW|W|V|L|J|mm|cm|kg|rpm|bpm|spm|"
                         r"min|bar|dB|Pa|s|h)?(?![A-Za-z])")

# Первый буллет — главная ценность. Ценность товара коду не известна; где её
# решил человек, ожидание записано по (SKU, площадка): у 99601000-B — переключение
# между всасыванием и выдуванием без разборки (правка Ярослава 21.10.2026).
# Все шаблоны должны найтись в ЗАГОЛОВКЕ первого буллета (без учёта регистра): ценность
# — то, что стоит капсом; упоминание в тексте ниже заголовка её не делает первой.
# «Без разборки» — «sin desmontar/desmontaje»; «sin herramientas» — другое
# (проверка #175).
FIRST_BULLET = {
    ("99601000-B", "es"): ("aspirar ↔ soplar sin desmontar",
                           (r"aspir", r"sopl", r"sin\s+desmont")),
}

# Цифра в тайтле подписана тем, что она значит: «Aire 245km/h», «Bolsa 45L»,
# «Tritura 15:1». Подпись ищется в той же части тайтла (между запятыми). Единицы,
# которые говорят сами за себя (W, Nm, Ø…mm, rpm, Ah, J), сюда не входят. Слова
# подписей — на языке площадки; есть только испанские (пилот — ES). На других
# площадках правило молчит, а не ругает верные «Luft 245km/h» (проверка #175).
VALUE_LABELS = (
    ("km/h", re.compile(r"(?<![\d.,])\d+(?:[.,]\d+)?\s*km/h", re.I), ("aire", "velocidad")),
    ("m³", re.compile(r"(?<![\d.,])\d+(?:[.,]\d+)?\s*m(?:³|3)/(?:min|h)\b", re.I),
     ("aire", "caudal", "aspiración", "aspiracion", "succión", "succion")),
    ("L", re.compile(r"(?<![\d.,])\d+(?:[.,]\d+)?\s*L\b"),
     ("bolsa", "depósito", "deposito", "capacidad", "saco", "tanque")),
    ("N:1", re.compile(r"(?<![\d.,])\d+\s*:\s*1\b"), ("tritura",)),
)
LABELS_BY_MARKETPLACE = {"es": VALUE_LABELS}

# Одиночное значение паспорта (N) не превращается в диапазон «0 - N»: у DTW-205BC
# «2800» обороты стали «0 - 2800» (dnipro-m.ua и правка Алексея 21.10.2026).
# Одиночное — число, которое в паспорте не конец диапазона и не часть соотношения
# («15:1»). Диапазон паспорта узнаётся в любой записи: «0-2800», «0…45», «0...45»,
# «від 0 до 2800», «de 0 a 2800» (проверка #175).
_NUM = re.compile(r"(?<![\d.,:])\d+(?:[.,]\d+)*(?![\d.,]*:\d)")
_RANGE = re.compile(r"(?<![\d.,])(\d+(?:[.,]\d+)*)\s*(?:[-–—…]|\.\.\.|\s(?:до|по|to|a|hasta|bis)\s)\s*"
                    r"(\d+(?:[.,]\d+)*)", re.I)
_ZERO_RANGE = re.compile(r"(?<![\d.,])0\s*[-–—]\s*(\d+(?:[.,]\d+)*)")
_THOUSANDS = re.compile(r"^\d{1,3}(?:[.,]\d{3})+$")


def _num(x: str) -> str:
    """«2.800» и «2,800» — тысячи, то же, что «2800»; «3,9» — «3.9»."""
    return re.sub(r"[.,]", "", x) if _THOUSANDS.match(x) else x.replace(",", ".")


def passport_values(facts: pf.Facts | None) -> tuple[set[str], set[tuple[str, str]]]:
    """Одиночные числа фактов паспорта и диапазоны «a - b» среди них. Концы
    диапазонов и соотношения одиночными не считаются. Колонка ID и источники не в
    счёт: «FACT-99601000-B-010» и «SRC-…-0003» — не значения."""
    nums, ranges = set(), set()
    for s in (facts.sections if facts else []):
        if not s.rows:
            continue
        head = s.rows[0]
        for r in s.rows[1:]:
            for i, (h, v) in enumerate(zip(head, r)):
                hl = h.strip().lower()
                if i == 0 or not v or hl.startswith(pf.SOURCE_COLS) or pf.SOURCE_MARK in hl:
                    continue
                found = _RANGE.findall(v)
                ranges |= {(_num(a), _num(b)) for a, b in found}
                ends = {_num(x) for pair in found for x in pair}
                nums |= {_num(m.group(0)) for m in _NUM.finditer(v)} - ends
    return nums, ranges


def run_checks(texts: dict, model: str | None, conflict_tokens: set[str] = frozenset(), *,
               facts: pf.Facts | None = None, sku: str | None = None,
               marketplace: str | None = None) -> list[dict]:
    # kind=TOOL: тип товара (инструмент или аккумулятор/зарядка) паспорт не даёт
    # машинно; для аккумулятора правило вольтажа сработает лишним — это видно.
    found = tr.check(texts["title"], texts["highlight"], kind=tr.TOOL, model=model)
    out = [{"code": v.code, "field": "highlight" if v.field == "highlights" else v.field, "detail": v.detail}
           for v in found]
    # Заголовок буллета капсом через двоеточие.
    for f in FIELDS:
        if not f.startswith("bullet_"):
            continue
        m = _BULLET_HEAD.match(texts[f])
        head = m.group(1) if m else ""
        letters = [c for c in _UNIT_TOKEN.sub("", head) if c.isalpha()]
        if not (m and len(letters) >= 2 and all(c.isupper() for c in letters)):
            out.append({"code": "BULLET_HEAD", "field": f, "detail": (head or texts[f])[:40]})
    # Первый буллет — решённая человеком главная ценность товара.
    exp = FIRST_BULLET.get((sku, marketplace))
    head1 = _BULLET_HEAD.match(texts["bullet_1"])
    if exp and not (head1 and all(re.search(pat, head1.group(1), re.I) for pat in exp[1])):
        out.append({"code": "FIRST_BULLET", "field": "bullet_1", "detail": exp[0]})
    # Цифра в тайтле подписана. Части — по запятой, но не по десятичной («3,5 m³/min»).
    for part in re.split(r"(?<!\d),|,(?!\d)", texts["title"]):
        low = part.lower()
        for _, rx, labels in LABELS_BY_MARKETPLACE.get(marketplace, ()):
            for m in rx.finditer(part):
                if not any(re.search(rf"(?<!\w){re.escape(lb)}", low) for lb in labels):
                    out.append({"code": "UNLABELED_VALUE", "field": "title", "detail": m.group(0).strip()})
    # Одиночное значение паспорта — не диапазон «0 - N».
    nums, ranges = passport_values(facts)
    for f in FIELDS:
        for m in _ZERO_RANGE.finditer(texts[f]):
            n = _num(m.group(1))
            if n in nums and ("0", n) not in ranges:
                out.append({"code": "RANGE_FROM_SINGLE", "field": f, "detail": f"{m.group(0)} → {m.group(1)}"})
    # Значение конфликта всё-таки попало в текст (из названия товара, из знаний
    # модели) — нарушение, которое видит человек до приёмки.
    for f in FIELDS:
        hits = pf.has_tokens(texts[f], conflict_tokens)
        if hits:
            out.append({"code": "CONFLICT_VALUE", "field": f, "detail": ", ".join(hits)})
    if not model:
        out.append({"code": "NO_MODEL_PREFIX_CHECK", "field": "highlight", "detail": ""})
    return out


# ------------------------------------------------------------------ генерация
ASIN_RE = re.compile(r"B0[A-Z0-9]{8}")        # тот же CHECK, что у content_versions.asin — fullmatch
ASIN_CODES = ("ASIN_UNREAD", "ASIN_UNKNOWN", "ASIN_AMBIGUOUS")   # пометки, а не нарушения тайтла


def pick_asin(asins: list[str] | None) -> tuple[str | None, dict | None]:
    """ASIN для черновиков (решение владельца 23.10.2026): ровно один на площадке —
    он; иначе пусто и причина. `asins` = None — связь SKU ↔ ASIN не прочиталась."""
    if asins is None:
        return None, {"code": "ASIN_UNREAD", "field": "title", "detail": ""}
    # fullmatch и только строки: «$» в re.match пропускает хвостовой перевод строки,
    # а NaN из pandas — float (правило 4); обе ошибки всплыли бы ПОСЛЕ оплаты вызова.
    ok = sorted({a for a in asins if isinstance(a, str) and ASIN_RE.fullmatch(a)})
    if len(ok) == 1:
        return ok[0], None
    if not ok:
        return None, {"code": "ASIN_UNKNOWN", "field": "title", "detail": ""}
    return None, {"code": "ASIN_AMBIGUOUS", "field": "title", "detail": ", ".join(ok)}


# ------------------------------------------------------------------ штамп версии
STAMP_MIGRATION = "2026-10-27_content_versions_stamp.sql"
STAMP_COLUMNS = ("prompt_sha256", "rules_version")
_COMMIT = re.compile(r"[0-9a-f]{40}")


def prompt_sha256(system: str, prompt: str) -> str:
    """Отпечаток ровно того, что ушло в модель: методология (system) и запрос.
    Тот же отпечаток — тот же вход; другой — изменились правила, промпт или факты."""
    return hashlib.sha256((system or "").encode("utf-8") + b"\x00" + (prompt or "").encode("utf-8")).hexdigest()


def generate(*, sku: str, marketplace: str, copy: dict, actor: str, store, conn, method: tuple[str, int],
             provider: str, model: str, max_tokens: int, setting, ai_call, ai_usage, ai_reset,
             asins: list[str] | None, ai_error=lambda: None, rules_version: str | None = None) -> Result:
    """Один вызов модели и черновики. `copy` — строка `passport_source_artifacts`
    (source_artifact_id, passport_id, archived_locator, sha256). Вызов модели и
    его учёт — через переданные функции: страница отдаёт `services/ai`, тест —
    подмену. `rules_version` — коммит кода правил (полный sha, 40 знаков); не
    такой — пишется пусто: CHECK в базе отверг бы вставку уже ПОСЛЕ платного
    вызова."""
    m_text, m_ver = method
    if not (m_text or "").strip() or not m_ver:
        return Result("BLOCKED", "NO_METHOD", SCOPE)
    # ASIN и штамп решаются ДО платного вызова: ничего, что может упасть, после него нет.
    asin, why_no_asin = pick_asin(asins)
    rules_ver = rules_version if isinstance(rules_version, str) and _COMMIT.fullmatch(rules_version) else None
    if provider not in PROVIDERS:
        return Result("BLOCKED", "PROVIDER", provider)
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
    if header["passport_id"] != copy["passport_id"]:
        return Result("FAILED", "COPY_OTHER_PASSPORT", f"{header['passport_id']} ≠ {copy['passport_id']}")
    facts = pf.read(data)
    prompt = build_prompt(sku, marketplace, header, facts)
    p_sha = prompt_sha256(m_text, prompt)
    est = estimate(p, len(prompt) + len(m_text), max_tokens)

    with conn, conn.cursor() as cur:
        # Одна блокировка на весь пилот: лимит пилота общий, проверка и резерв —
        # одним шагом, иначе два нажатия разом прошли бы оба.
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('textgen_limits'))")
        # Черновикам должно быть куда лечь ДО траты денег (проверка #167).
        cur.execute("SELECT to_regclass('listing_data.content_versions') IS NOT NULL")
        if not cur.fetchone()[0]:
            return Result("BLOCKED", "NO_CONTENT_TABLE", "content_versions")
        # Код и миграция едут порознь: без колонок штампа черновик пишется как
        # раньше, а страница называет миграцию.
        cur.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema = 'listing_data'"
                    " AND table_name = 'content_versions' AND column_name = ANY(%s)", (list(STAMP_COLUMNS),))
        stamped = int(cur.fetchone()[0]) == len(STAMP_COLUMNS)
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

    checks = run_checks(texts, model_code(facts), pf.conflict_tokens(facts.conflicts),
                        facts=facts, sku=sku, marketplace=marketplace)
    # ASIN товара на этой площадке: один — во все черновики; иначе пусто, причина —
    # пометкой в checks тайтла (ASIN_CODES — не нарушение, экран показывает отдельно).
    if why_no_asin:
        checks.append(why_no_asin)
    with conn, conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"content:{sku}:{marketplace}",))
        for f in FIELDS:
            cur.execute("SELECT COALESCE(max(version), 0) FROM content_versions"
                        " WHERE sku = %s AND marketplace = %s AND field = %s", (sku, marketplace, f))
            ver = int(cur.fetchone()[0]) + 1
            mine = [c for c in checks if c["field"] == f]
            stamp_cols, stamp_vals = ((", prompt_sha256, rules_version", ", %s, %s"), (p_sha, rules_ver)) \
                if stamped else (("", ""), ())
            cur.execute(
                "INSERT INTO content_versions (sku, marketplace, field, text, version, proposal_id, created_by,"
                " passport_id, passport_version, passport_sha256, passport_artifact_id, origin, model,"
                f" skill_version, checks, asin{stamp_cols[0]}) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,"
                f" 'model', %s, %s, %s, %s{stamp_cols[1]})",
                (sku, marketplace, f, texts[f], ver, proposal, actor, header["passport_id"],
                 str(header["passport_version"]), copy["sha256"], copy["source_artifact_id"], model, m_ver,
                 json.dumps(mine, ensure_ascii=False), asin) + stamp_vals)
    return Result("OK", "", "", call_id, proposal, texts, checks, real, stamped=stamped,
                  rules_version=rules_ver if stamped else None)


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
        "SELECT field, text, text_len, version, proposal_id, status, model, checks, created_at, asin"
        " FROM content_versions WHERE sku = %(s)s AND marketplace = %(m)s AND proposal_id = ("
        " SELECT proposal_id FROM content_versions WHERE sku = %(s)s AND marketplace = %(m)s"
        " AND proposal_id LIKE 'TG-%%' ORDER BY id DESC LIMIT 1)", {"s": sku, "m": marketplace})


# ------------------------------------------------------------------ SKU ↔ ASIN
# Связь товара сверху (ASIN пилота) и товара генерации (SKU паспорта). Два
# источника: справочник SKU Кабинета (`passport.sku_directory`, точный код и
# наблюдаемые листинги) и матрица (`product_matrix.sku_group` на рынке ES).
# В матрице у варианта бывает базовый код: у 99601000-B там «99601000» — поэтому
# по ТОЧНОМУ коду сначала справочник, матрица — вторым источником, без угадывания
# базового кода по суффиксу.
def _split(row, col: str) -> list[str]:
    from services.cells import cell_text      # NaN — пусто, не «nan» (правило 4)
    return [a for a in cell_text(row, col).split() if a]


def asins_for_sku(sku: str, directory, matrix_es) -> list[str]:
    """ASIN ES товара. Рынок знает только матрица: без неё (не прочиталась) ES не
    проверить, и ответ пустой — справочник отдаёт ASIN всех рынков (проверка #168).
    Из справочника — только ASIN, что стоят на ES в матрице; из матрицы — по
    точному SKU."""
    if matrix_es is None:
        return []
    es = set(matrix_es["asin"]) if not matrix_es.empty else set()
    out = set()
    if directory is not None and not directory.empty:
        for _, r in directory[directory["sku"] == sku].iterrows():
            out |= {a for a in _split(r, "asins") if a in es}
    if not matrix_es.empty:
        from services.cells import cell_text
        out |= {cell_text(r, "asin") for _, r in matrix_es.iterrows() if cell_text(r, "sku_group") == sku}
    return sorted(a for a in out if a)


def skus_for_asin(asin: str, directory, matrix_es) -> list[str]:
    from services.cells import cell_text
    out = set()
    if directory is not None and not directory.empty:
        out |= {cell_text(r, "sku") for _, r in directory.iterrows() if asin in _split(r, "asins")}
    if matrix_es is not None and not matrix_es.empty:
        out |= {cell_text(r, "sku_group") for _, r in matrix_es.iterrows() if cell_text(r, "asin") == asin}
    return sorted(x for x in out if x)
