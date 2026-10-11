# -*- coding: utf-8 -*-
"""
services/passport.py — «Контент → Паспорт SKU»: чтение и правила показа.

Здесь нет ни одной записи: этап 1 — область только на чтение. Изменяющие
действия (создание, новые данные, ответы Верификатору) появятся на этапах
3–5 и до своих квитанций включения отвечают FEATURE_DISABLED (ТЗ §13).

Нормативы — снимок канона в canon/ai_design_conveyor: «Функциональное ТЗ
Listing Suite → Контент → Паспорт SKU» v1.0, 00A v2.13, 06E MVP-14,
Listing_Suite_UI_Message_Mapping v1.1, каталог сообщений v1.0. Слова и
коды статусов взяты оттуда дословно, своих здесь нет.

**Реестр не сводит разные состояния к одному цветному ярлыку** (ТЗ 9.6).
У строки четыре независимые оси, и порядок их применения закреплён
(9.6.5): идентичность товара → актуальность данных → каноническое
состояние Паспорта → нужно ли действие пользователя. Следующее действие
считается только после всех четырёх (`next_action`).

Две ловушки, ради которых правила вынесены в чистые функции и заперты
тестом `test_passport_registry.py`:

- `BLOCKED` показывается ТОЛЬКО при действующем блокере BLK-<RUN>-<NNN> с
  причиной, ответственным и условием возобновления (ТЗ 3.1, 9.6.3).
  Отправленный вопрос сам по себе Паспорт не блокирует: без блокера это
  «В работе» и отдельное «Требуется ответ»;
- «Паспорт отсутствует» — не пятое состояние Паспорта, а результат поиска
  (9.6.2). Поэтому машинный статус для него не выдумывается: в строке
  `state` пустой, а наличие — отдельная колонка.

Справочник товаров — база Кабинета (`kabinet_data.sku_master` и
наблюдаемые листинги Amazon), решение владельца 07.10.2026. Модели в
справочнике нет: поиск по модели идёт по названию, а у товара с Паспортом —
и по модели из самого Паспорта.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from services import kdb
from services.cells import cell_text
from services.db import safe_read, table_exists


def txt(v) -> str:
    """Значение строкой; None, NaN и NaT — пусто (правило 4, `services/cells.py`)."""
    return cell_text({"v": v}, "v")

CANON = pathlib.Path(__file__).resolve().parent.parent / "canon" / "ai_design_conveyor"
PASSPORT_DIR = CANON / "02_SKU_Passport"
MIGRATION = "migrations/2026-10-07_passport_sku_core.sql"

# Канонические состояния Паспорта (00A «Допустимые состояния Паспорта»).
STATES = ("READY", "READY_WITH_LIMITATIONS", "NOT_READY", "BLOCKED")

# Актуальность данных Реестра (ТЗ 9.6.4) — отдельная ось, не состояние.
CURRENT, UPDATING, STALE, LOAD_ERROR = "CURRENT", "UPDATING", "STALE", "LOAD_ERROR"

# Следующее действие (ТЗ 9.7). Одно на строку, универсальной кнопки нет.
COMPARE = "COMPARE"                 # возможный дубликат — выбрать точный SKU
DO_REQUIRED = "DO_REQUIRED"         # блокер назначен пользователю
ANSWER = "ANSWER"                   # вопрос Верификатора со статусом SENT
OPEN_LIMITATIONS = "OPEN_LIMITATIONS"
OPEN_PASSPORT = "OPEN_PASSPORT"     # read-only просмотр
OPEN_WORK = "OPEN_WORK"             # NOT_READY без адресного запроса: «Действие не требуется»
CREATE = "CREATE"
WAIT = "WAIT"                       # данные устарели/обновляются — изменяющих действий нет

# Флаги функций (Integration Contract «Feature flags») плюс флаг первичного
# создания — в Integration Contract его нет, потому что нет и typed request
# для первичного создания (canon/REFERENCE_DRIFT.md уходит владельцу). Все
# выключены до своей квитанции включения на этапе 7; включить «настройкой»
# нельзя намеренно: OFF → ON по контракту — это receipt, а не галочка.
FLAGS = (
    "listing_suite.passport_create",
    "listing_suite.source_evidence_delta",
    "listing_suite.folder_snapshot_v1",
    "listing_suite.passport_recreate",
    "listing_suite.passport_restore",
    "listing_suite.verifier_answers",     # ответы Верификатору — этап 4, тоже наш
)
FEATURE_DISABLED = "FEATURE_DISABLED"

# Наши четыре роли → канонические роли Listing_Suite_Authority_Mapping_Contract.
# Предложение 07.10.2026, ждёт подтверждения владельца процесса. Пересоздание
# (PRODUCT_OWNER_WITH_RECREATE_AUTHORITY) по контракту — отдельная явная
# привязка, а не следствие PRODUCT_OWNER, поэтому утверждающему его нет.
CANONICAL_ROLES = {
    "viewer": ("AUDITOR",),
    "content_manager": ("DATA_CONTRIBUTOR",),
    "approver": ("PRODUCT_OWNER",),
    "admin": ("PASSPORT_ADMIN",),
}

ASIN_RE = r"^B0[0-9A-Z]{8}$"
SEARCH_LIMIT = 50


# ---------------------------------------------------------------- справочник
@st.cache_data(ttl=600, show_spinner=False)
def sku_directory() -> tuple[pd.DataFrame, str | None]:
    """Справочник SKU из базы Кабинета: код, название, EAN и ASIN Amazon.

    ASIN — из наблюдаемых листингов (`product_entity_listings`), только
    вида B0…: v1 — только Amazon, а у других площадок идентификатор свой
    (model id ManoMano, product_sku Leroy Merlin). EAN пуст, где его нет, —
    поиск от этого не ломается."""
    sql = f"""
        SELECT m.sku, m.name, m.ean, m.is_active,
               COALESCE(string_agg(DISTINCT l.peid, ' ' ORDER BY l.peid)
                        FILTER (WHERE l.peid ~ '{ASIN_RE}'), '') AS asins
          FROM kabinet_data.sku_master m
          LEFT JOIN kabinet_data.product_entity_listings l ON l.sku = m.sku
         GROUP BY m.sku, m.name, m.ean, m.is_active
         ORDER BY m.sku
    """
    try:
        conn = kdb.get_conn()
    except Exception as e:
        return pd.DataFrame(), f"{type(e).__name__}: {e}"
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            cols = [d[0] for d in cur.description]
            df = pd.DataFrame(cur.fetchall(), columns=cols)
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"{type(e).__name__}: {e}"
    finally:
        conn.close()


# ---------------------------------------------------------------- реестр
@st.cache_data(ttl=60, show_spinner=False)
def load_registry() -> dict:
    """Всё, что Реестру нужно из базы Listing Suite, одним набором.

    `error` — прочитать не удалось (ТЗ 9.6.4 «Ошибка загрузки»); `missing` —
    миграции ещё нет. Это разные вещи и говорятся по-разному: первое —
    сбой, второе — шаг, который надо сделать (код и миграция едут порознь)."""
    out = {"objects": pd.DataFrame(), "questions": pd.DataFrame(), "blocks": pd.DataFrame(),
           "runs": pd.DataFrame(), "error": None, "missing": False,
           "read_at": datetime.now(timezone.utc)}
    exists = table_exists("listing_data.passport_objects")
    if exists is False:
        out["missing"] = True
        return out
    queries = {
        "objects": """SELECT passport_id, lineage_id, sku_id, product_version, product_name, model,
                             state, passport_version, sha256, storage_path, materials_url, limitations,
                             last_event_type, last_event_at, readback_sha256, readback_at
                        FROM passport_objects WHERE status = 'ACTIVE'""",
        "questions": """SELECT question_id, run_id, sku_id, question_type, status, impact, block_id,
                               responsible_role, responsible_user, question_text, created_at, updated_at
                          FROM passport_questions
                         WHERE status IN ('SENT', 'ANSWER_RECEIVED')""",
        "blocks": """SELECT block_id, run_id, sku_id, reason, responsible_party, responsible_role,
                            responsible_user, resume_condition, created_at
                       FROM passport_blocks WHERE resolved_at IS NULL""",
        "runs": """SELECT run_id, sku_id, requested_action, lifecycle_state, current_node_id, created_at
                     FROM ai_runs WHERE route = 'SKU_PASSPORT' AND terminal_status = 'NOT_TERMINAL'""",
    }
    return _read_all(out, queries)


def _read_all(out: dict, queries: dict) -> dict:
    """Читает набор запросов; первый сбой — ошибка всего набора. Ответ без
    колонок, которые запрос перечислил, — тоже сбой, а не пустота: иначе
    чужой ответ (другая схема, подмена) выглядел бы «Паспортов нет»."""
    for key, sql in queries.items():
        df, err = safe_read(sql)
        if not err and not df.empty:
            want = _columns_of(sql)
            lost = [c for c in want if c not in df.columns]
            if lost:
                err = f"{key}: нет колонок {lost}"
        if err:
            out["error"] = err
            return out
        out[key] = df
    return out


def _columns_of(sql: str) -> list[str]:
    head = re.search(r"SELECT\s+(.*?)\s+FROM\s", sql, re.S | re.I).group(1)
    return [c.strip().split()[-1] for c in head.split(",")]


@st.cache_data(ttl=60, show_spinner=False)
def known_artifacts(sku: str) -> dict[str, str]:
    """SHA уже зарегистрированных материалов SKU → их ID: точный повтор
    новой редакции не создаёт (политика приёма, п. 8). Сбой чтения — пусто:
    тогда повтор будет пойман при регистрации, а не здесь."""
    df, err = safe_read("""SELECT source_artifact_id, sha256 FROM passport_source_artifacts
                            WHERE sku_id = %(s)s AND sha256 IS NOT NULL""", {"s": sku})
    if err or df.empty or "sha256" not in df.columns:
        return {}
    return {txt(r["sha256"]): txt(r["source_artifact_id"]) for _, r in df.iterrows()}


# ---------------------------------------------------------------- оси статуса
def _for_sku(df: pd.DataFrame, sku: str) -> pd.DataFrame:
    if df is None or df.empty or "sku_id" not in df.columns:
        return pd.DataFrame()
    return df[df["sku_id"].astype(str) == str(sku)]


def valid_block(b: pd.Series) -> bool:
    """Блокер действует, только если у него есть всё, что требует ТЗ 9.6.3:
    ID формата BLK-<RUN>-<NNN>, причина, ответственная сторона и условие
    возобновления. Неполная запись — не основание показывать «Заблокирован»."""
    return (bool(re.match(r"^BLK-[A-Za-z0-9._-]+-[0-9]{3,}$", txt(b.get("block_id"))))
            and all(txt(b.get(k)).strip() for k in ("reason", "responsible_party", "resume_condition")))


def active_blocks(blocks: pd.DataFrame, sku: str) -> pd.DataFrame:
    part = _for_sku(blocks, sku)
    if part.empty:
        return part
    return part[part.apply(valid_block, axis=1)]


def display_state(obj: pd.Series | None, blocks: pd.DataFrame) -> str | None:
    """Каноническое состояние для показа; None — Паспорта нет (не состояние).

    BLOCKED — только при действующем блокере; без него записанное BLOCKED
    показывается как NOT_READY (ТЗ 3.1). И наоборот: действующий блокер
    даёт BLOCKED поверх любого записанного состояния (06E: «любой валидный
    active block → BLOCKED»)."""
    if obj is None:
        return None
    if not blocks.empty:
        return "BLOCKED"
    # Незнакомое значение (база держит CHECK, но читать могут и старую схему)
    # не становится ни READY, ни пустотой: это «В работе», без права действий.
    state = txt(obj.get("state"))
    return "NOT_READY" if state == "BLOCKED" or state not in STATES else state


def freshness(obj: pd.Series | None, open_run: bool, load_error: bool) -> str:
    """Актуальность данных (ТЗ 9.6.4) — отдельно от состояния Паспорта.

    Версия и SHA «подтверждены», когда системный read-back с тома совпал с
    записанным SHA. Не совпал или не выполнялся ни разу — «Данные устарели»:
    ТЗ 9.8 разрешает в этом случае просмотр, но запирает изменяющие действия.
    Идущий запуск — «Обновляется»: просмотр можно, второй запуск нельзя."""
    if load_error:
        return LOAD_ERROR
    if open_run:
        return UPDATING
    if obj is None:
        return CURRENT
    sha, back = txt(obj.get("sha256")), txt(obj.get("readback_sha256"))
    return CURRENT if sha and back and sha == back else STALE


def my_items(questions: pd.DataFrame, blocks: pd.DataFrame, sku: str,
             email: str, roles: tuple) -> dict:
    """Что из активного назначено ИМЕННО этому пользователю (ТЗ 9.6.3):
    вопрос Верификатора со статусом SENT и действующий блокер, где
    ответственный — он сам или его каноническая роль. NOT_READY само по
    себе действия пользователя не означает."""
    def mine(r) -> bool:
        user = txt(r.get("responsible_user")).strip().lower()
        role = txt(r.get("responsible_role")).strip()
        return bool((email and user == email.strip().lower()) or (role and role in roles))

    qs = _for_sku(questions, sku)
    qs = qs[qs["status"] == "SENT"] if not qs.empty else qs
    my_q = sorted(txt(r["question_id"]) for _, r in qs.iterrows() if mine(r)) if not qs.empty else []
    bl = active_blocks(blocks, sku)
    my_b = sorted(txt(r["block_id"]) for _, r in bl.iterrows() if mine(r)) if not bl.empty else []
    return {"questions": my_q, "blocks": my_b}


def next_action(*, has_passport: bool, state: str | None, fresh: str, duplicate: bool,
                mine: dict) -> tuple[str, str | None]:
    """Одно следующее действие строки (ТЗ 9.7) и его объект.

    Порядок 9.6.5 и приоритет 9.7: конфликт идентичности → актуальность →
    внешний блокер → отправленный вопрос → ограничение → просмотр. Разные
    действия в одну кнопку не склеиваются."""
    if duplicate:
        return COMPARE, None
    if fresh in (LOAD_ERROR, STALE, UPDATING):
        # Изменяющие действия заперты; просмотр — если есть что смотреть.
        if not has_passport:
            return (OPEN_WORK, None) if fresh == UPDATING else (WAIT, None)
        return (OPEN_WORK if fresh == UPDATING else OPEN_PASSPORT), None
    if not has_passport:
        return CREATE, None
    if state == "BLOCKED" and mine.get("blocks"):
        return DO_REQUIRED, mine["blocks"][0]
    if mine.get("questions"):
        return ANSWER, mine["questions"][0]
    if state == "READY_WITH_LIMITATIONS":
        return OPEN_LIMITATIONS, None
    if state == "NOT_READY":
        return OPEN_WORK, None
    return OPEN_PASSPORT, None


# ---------------------------------------------------------------- поиск и строки
def duplicate_map(directory: pd.DataFrame) -> dict[str, set]:
    """SKU → другие SKU справочника с тем же EAN или ASIN Amazon.

    «Возможный дубликат» (ТЗ 9.6.2) — сигнал, а не решение: два кода на один
    штрихкод или один ASIN значат, что точный товар выбирает человек. Так
    ловится, например, внутренняя метка акции рядом с базовым SKU; привести
    её к базовому — решение Верификатора, а не Реестра."""
    if directory is None or directory.empty:
        return {}
    pairs: dict[str, set] = {}
    keys: dict[str, set] = {}
    for _, r in directory.iterrows():
        sku = txt(r.get("sku"))
        ean = txt(r.get("ean")).strip()
        if ean:
            keys.setdefault("ean:" + ean, set()).add(sku)
        for a in txt(r.get("asins")).split():
            keys.setdefault("asin:" + a, set()).add(sku)
    for group in keys.values():
        if len(group) > 1:
            for s in group:
                pairs.setdefault(s, set()).update(group - {s})
    return pairs


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def search(directory: pd.DataFrame, objects: pd.DataFrame, query: str) -> tuple[pd.DataFrame, int]:
    """Строки справочника и Паспортов под запрос: SKU, название, модель, ASIN
    или EAN. Без запроса — товары, у которых Паспорт уже есть.

    Совпадение по названию или внешнему коду НЕ подтверждает SKU (ТЗ 9.3):
    оно только показывает строки, а точный товар человек выбирает сам.
    Точное совпадение кода SKU идёт первым."""
    base = directory.copy() if directory is not None and not directory.empty else \
        pd.DataFrame(columns=["sku", "name", "ean", "is_active", "asins"])
    objs = objects if objects is not None and not objects.empty else pd.DataFrame(
        columns=["sku_id", "product_name", "model"])
    known = set(base["sku"].astype(str))
    extra = [{"sku": txt(o["sku_id"]), "name": txt(o.get("product_name")), "ean": "",
              "is_active": True, "asins": ""}
             for _, o in objs.iterrows() if txt(o["sku_id"]) not in known]
    if extra:
        base = pd.concat([base, pd.DataFrame(extra)], ignore_index=True)
    model = {txt(o["sku_id"]): txt(o.get("model")) for _, o in objs.iterrows()}
    base["model"] = base["sku"].astype(str).map(model).fillna("")

    q = _norm(query or "")
    if not q:
        view = base[base["sku"].astype(str).isin(set(objs["sku_id"].astype(str)))]
        return view.reset_index(drop=True), len(view)

    def hit(r) -> bool:
        hay = " ".join(txt(r.get(k)) for k in ("sku", "name", "model", "ean", "asins"))
        return q in _norm(hay)

    view = base[base.apply(hit, axis=1)].copy()
    view["_exact"] = view["sku"].astype(str).map(lambda s: _norm(s) == q)
    view = view.sort_values(["_exact", "sku"], ascending=[False, True]).drop(columns="_exact")
    total = len(view)
    return view.head(SEARCH_LIMIT).reset_index(drop=True), total


def registry_rows(view: pd.DataFrame, data: dict, dupes: dict, email: str, roles: tuple,
                  load_error: bool = False) -> pd.DataFrame:
    """Строки Реестра: по строке справочника — четыре оси и следующее действие."""
    objs, qs, bl, runs = data.get("objects"), data.get("questions"), data.get("blocks"), data.get("runs")
    by_sku = {txt(o["sku_id"]): o for _, o in objs.iterrows()} if objs is not None and not objs.empty else {}
    rows = []
    for _, r in view.iterrows():
        sku = txt(r["sku"])
        obj = by_sku.get(sku)
        blocks = active_blocks(bl, sku)
        state = display_state(obj, blocks)
        open_run = not _for_sku(runs, sku).empty
        fresh = freshness(obj, open_run, load_error)
        mine = my_items(qs, bl, sku, email, roles)
        sent = _for_sku(qs, sku)
        n_sent = int((sent["status"] == "SENT").sum()) if not sent.empty else 0
        limits = _limitations(obj)
        act, target = next_action(has_passport=obj is not None, state=state, fresh=fresh,
                                  duplicate=sku in dupes, mine=mine)
        rows.append({
            "sku": sku,
            "name": txt(r.get("name")) or (txt(obj.get("product_name")) if obj is not None else ""),
            "model": txt(r.get("model")),
            "product_version": txt(obj.get("product_version")) if obj is not None else "",
            "has_passport": obj is not None,
            "state": state,
            "passport_id": txt(obj.get("passport_id")) if obj is not None else "",
            "passport_version": txt(obj.get("passport_version")) if obj is not None else "",
            "questions": n_sent,
            "limitations": len(limits),
            "blocks": len(blocks),
            "block_ids": [txt(b["block_id"]) for _, b in blocks.iterrows()],
            "my_action": bool(mine["questions"] or mine["blocks"]),
            "fresh": fresh,
            "last_event_type": txt(obj.get("last_event_type")) if obj is not None else "",
            "last_event_at": obj.get("last_event_at") if obj is not None else None,
            "duplicate_of": sorted(dupes.get(sku, ())),
            "action": act,
            "action_target": target,
            "materials_url": txt(obj.get("materials_url")) if obj is not None else "",
            "asins": txt(r.get("asins")),
            "ean": txt(r.get("ean")),
        })
    return pd.DataFrame(rows)


def _limitations(obj) -> list:
    if obj is None:
        return []
    raw = obj.get("limitations")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    return list(raw) if isinstance(raw, (list, tuple)) else []


def filter_rows(rows: pd.DataFrame, states: list, need_action: str) -> pd.DataFrame:
    """Фильтры ТЗ 9.3: состояние Паспорта (включая «отсутствует» — это
    отдельная опция, а не пятое состояние) и наличие моего действия."""
    if rows.empty:
        return rows
    out = rows
    if states:
        want_absent = "ABSENT" in states
        out = out[out.apply(lambda r: (r["state"] in states) or (want_absent and not r["has_passport"]), axis=1)]
    if need_action == "yes":
        out = out[out["my_action"]]
    elif need_action == "no":
        out = out[~out["my_action"]]
    return out


# ---------------------------------------------------------------- вопросы Верификатора
# Пользовательские состояния вопроса (ТЗ 11.5) — проекция статуса вопроса
# (06E: OPEN → SENT → ANSWER_RECEIVED → RESOLVED) и вердикта по последнему
# ответу (RECEIVED → VERIFIED | PARTIAL | REJECTED). OPEN — вопрос ещё не
# отправлен, человеку его не показывают.
NEEDS_ANSWER, AWAITING_CHECK, NEEDS_CLARIFICATION = "NEEDS_ANSWER", "AWAITING_CHECK", "NEEDS_CLARIFICATION"
ANSWER_REJECTED, RESOLVED, CANCELLED = "ANSWER_REJECTED", "RESOLVED", "CANCELLED"
USER_STATES = (NEEDS_ANSWER, ANSWER_REJECTED, NEEDS_CLARIFICATION, AWAITING_CHECK, RESOLVED, CANCELLED)


@st.cache_data(ttl=60, show_spinner=False)
def load_questions() -> dict:
    """Вопросы (кроме неотправленных), версии ответов и вердикты по ним."""
    out = {"questions": pd.DataFrame(), "answers": pd.DataFrame(), "verdicts": pd.DataFrame(),
           "error": None, "missing": False}
    if table_exists("listing_data.passport_questions") is False:
        out["missing"] = True
        return out
    queries = {
        "questions": """SELECT question_id, run_id, sku_id, product_version, passport_id, question_type, status,
                               impact, block_id, responsible_role, responsible_user, question_text, reason_text,
                               affected_object, expected_answer, closure_criterion, evidence_required, due_at,
                               conflict, created_at, updated_at
                          FROM passport_questions WHERE status <> 'OPEN'""",
        "answers": """SELECT answer_id, question_id, answer_version, supersedes_answer_id, author, answer_text,
                             decision, source_artifact_ids, created_at
                        FROM passport_answers""",
        "verdicts": """SELECT answer_id, seq, verdict, reason, created_at FROM passport_answer_verdicts""",
    }
    return _read_all(out, queries)


def last_verdict(question_id: str, answers: pd.DataFrame, verdicts: pd.DataFrame) -> str | None:
    """Вердикт по ПОСЛЕДНЕЙ версии ответа; None — ответа нет или он ещё не
    проверен. Вердикт по старой версии на новую не переносится."""
    if answers is None or answers.empty:
        return None
    mine = answers[answers["question_id"] == question_id]
    if mine.empty:
        return None
    last = mine.sort_values("answer_version").iloc[-1]["answer_id"]
    if verdicts is None or verdicts.empty:
        return None
    v = verdicts[verdicts["answer_id"] == last]
    return None if v.empty else txt(v.sort_values("seq").iloc[-1]["verdict"])


def user_state(q: pd.Series, answers: pd.DataFrame, verdicts: pd.DataFrame) -> str:
    """Пользовательское состояние вопроса (ТЗ 11.5). ANSWER_RECEIVED не
    закрывает вопрос: это ожидание проверки, а не «решён»."""
    status = txt(q.get("status"))
    if status == "RESOLVED":
        return RESOLVED
    if status in ("SUPERSEDED", "OUT_OF_SCOPE"):
        return CANCELLED
    v = last_verdict(txt(q.get("question_id")), answers, verdicts)
    if v == "PARTIAL":
        return NEEDS_CLARIFICATION
    if v == "REJECTED":
        return ANSWER_REJECTED
    if status == "SENT":
        return NEEDS_ANSWER
    return AWAITING_CHECK


def question_impact(q: pd.Series, blocks: pd.DataFrame) -> str:
    """«Блокирует Паспорт» — только при действующем BLK с причиной,
    ответственным и условием возобновления (ТЗ 11.3.2). Без него записанное
    BLOCKS_PASSPORT показывается как «Требуется для готовности»."""
    impact = txt(q.get("impact"))
    if impact != "BLOCKS_PASSPORT":
        return impact or "NON_BLOCKING"
    bid = txt(q.get("block_id"))
    act = active_blocks(blocks, txt(q.get("sku_id")))
    ok = bid and not act.empty and bid in set(act["block_id"].astype(str))
    return "BLOCKS_PASSPORT" if ok else "REQUIRED_FOR_READINESS"


def is_mine(q: pd.Series, email: str, roles: tuple) -> bool:
    user = txt(q.get("responsible_user")).strip().lower()
    role = txt(q.get("responsible_role")).strip()
    return bool((email and user == email.strip().lower()) or (role and role in roles))


def question_rows(data: dict, blocks: pd.DataFrame, email: str, roles: tuple) -> pd.DataFrame:
    qs = data.get("questions")
    if qs is None or qs.empty:
        return pd.DataFrame(columns=["question_id", "sku_id", "user_state", "impact", "mine"])
    rows = []
    for _, q in qs.iterrows():
        rows.append({**{k: q.get(k) for k in qs.columns},
                     "user_state": user_state(q, data.get("answers"), data.get("verdicts")),
                     "impact": question_impact(q, blocks),
                     "mine": is_mine(q, email, roles)})
    return pd.DataFrame(rows)


def question_counters(rows: pd.DataFrame) -> dict:
    """Счётчики вкладки (ТЗ 11.3.1). «Требуют моего ответа» — мои вопросы без
    ответа и с отклонённым ответом: и там, и там ход за человеком."""
    if rows.empty:
        return {"mine": 0, "check": 0, "clarify": 0, "resolved": 0}
    return {
        "mine": int((rows["mine"] & rows["user_state"].isin([NEEDS_ANSWER, ANSWER_REJECTED])).sum()),
        "check": int((rows["user_state"] == AWAITING_CHECK).sum()),
        "clarify": int((rows["user_state"] == NEEDS_CLARIFICATION).sum()),
        "resolved": int((rows["user_state"] == RESOLVED).sum()),
    }


DEFAULT_QUESTION_STATES = (NEEDS_ANSWER, ANSWER_REJECTED, NEEDS_CLARIFICATION)


# ---------------------------------------------------------------- сообщения
@st.cache_resource(show_spinner=False)
def message_catalog() -> dict:
    """Каталог сообщений канона: код → severity и разрешённое действие.
    Тексты — в i18n (`pp.msg.<код>`), ru и uk дословно из каталога, en — наш:
    в каталоге en-US «PLANNED», а у Listing Suite три языка (правило 5)."""
    data = json.loads((PASSPORT_DIR / "Listing_Suite_Message_Catalog_v1.0.json").read_text(encoding="utf-8"))
    return {m["user_message_code"]: m for m in data["messages"]}


def resolve_message(code: str) -> dict:
    """Код → запись каталога. Неизвестный код — CONTRACT_COMPATIBILITY_ERROR,
    никогда не успех (UI Message Mapping, «Правила mapping»)."""
    cat = message_catalog()
    if code in cat:
        return {**cat[code], "resolved": "DIRECT"}
    return {**cat["CONTRACT_COMPATIBILITY_ERROR"], "resolved": "UNKNOWN_CODE", "requested_code": code}


# ---------------------------------------------------------------- статус по квитанции
# result квитанции → operation_status ответа на read-only запрос статуса.
_OPERATION_STATUS = {
    "NO_PASSPORT_CHANGE": "COMPLETED", "PASSPORT_UPDATED": "COMPLETED", "DECISION_REQUIRED": "COMPLETED",
    "WRONG_SKU_OR_SCOPE": "COMPLETED", "STANDARDS_MATERIAL_ROUTED": "COMPLETED",
    "REQUEST_REJECTED": "REJECTED", "RECREATE_ACCEPTED": "ACCEPTED", "RECREATE_IN_PROGRESS": "IN_PROGRESS",
    "RECREATE_REJECTED": "REJECTED", "RECREATE_COMMITTED": "COMPLETED", "RECREATE_ROLLED_BACK": "ROLLED_BACK",
}
LOOKUP_KEYS = ("request_id", "operation_id", "idempotency_key")


class CompatibilityError(Exception):
    """Сохранённая квитанция несёт result, которого контракт не знает."""


def lookup_status(sku_id: str, by: str, value: str, read=safe_read) -> dict:
    """Read-only lookup по сохранённой квитанции (Implementation Handoff §6):
    повторный показ уже созданного receipt без пересчёта и без права менять.
    Ровно один идентификатор; ответ — по listing_suite_passport_status_response."""
    if by not in LOOKUP_KEYS:
        raise ValueError(f"lookup только по одному из {LOOKUP_KEYS}")
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    query_id = "LS-PSP-QUERY-" + hashlib.sha256(f"{by}:{value}:{now}".encode()).hexdigest()[:16].upper()
    df, err = read(
        f"""SELECT receipt_id, request_id, operation_id, result, receipt_sha256
              FROM ai_receipts WHERE sku_id = %(s)s AND {by} = %(v)s
             ORDER BY created_at DESC LIMIT 1""", {"s": sku_id, "v": value})
    base = {"schema_version": "1.0", "query_id": query_id, "sku_id": sku_id, "replayed_from_storage": True,
            "mutation_authority": "NONE", "evaluated_at": now}
    if err or df.empty:
        return {**base, "lookup_status": "NOT_FOUND", "operation_status": "NOT_AVAILABLE",
                "request_id": None, "operation_id": None, "latest_receipt_ref": None,
                "latest_receipt_sha256": None}
    r = df.iloc[0]
    result = txt(r["result"])
    if result not in _OPERATION_STATUS:
        raise CompatibilityError(result)
    op = txt(r.get("operation_id"))
    return {**base, "lookup_status": "FOUND", "operation_status": _OPERATION_STATUS[result],
            "request_id": txt(r["request_id"]), "operation_id": op or None,
            "latest_receipt_ref": txt(r["receipt_id"]),
            "latest_receipt_sha256": txt(r["receipt_sha256"])}


def flag_on(name: str) -> bool:
    """Флаг функции. Все выключены до этапа 7: включение по контракту —
    отдельная квитанция с тестами (listing_suite_feature_activation_receipt),
    а её механизма ещё нет. Неизвестное имя — ошибка, а не «выключено»:
    опечатка в имени флага иначе выглядела бы как штатно выключенная функция."""
    if name not in FLAGS:
        raise KeyError(name)
    return False
