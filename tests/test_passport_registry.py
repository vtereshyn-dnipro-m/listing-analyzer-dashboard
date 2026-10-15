# -*- coding: utf-8 -*-
"""
tests/test_passport_registry.py — «Контент → Паспорт SKU», этап 1: Реестр и
вкладки только на чтение.

Главное здесь — правила ТЗ v1.0, которые ломаются ТИХО: экран выглядит
нормально, а говорит неправду.

1. `BLOCKED` — только при действующем блокере BLK-<RUN>-<NNN> с причиной,
   ответственным и условием возобновления. Отправленный вопрос без блокера —
   «В работе» и отдельно «Требуется ответ» (ТЗ 3.1, 9.6.3). Записанное
   BLOCKED без блокера — тоже «В работе».
2. «Паспорт отсутствует» — не пятое состояние (9.6.2): машинный state пуст.
3. Актуальность — своя ось: SHA не подтверждён системной сверкой — «Данные
   устарели», изменяющие действия заперты, статус Паспорта не меняется.
4. Следующее действие одно и по приоритету 9.7: идентичность → блокер →
   вопрос → ограничение → просмотр. NOT_READY без адресного запроса — «Действие
   не требуется», а не кнопка запуска агента.
5. Возможный дубликат (тот же EAN или ASIN) запирает всё до выбора точного
   SKU — так ловится метка акции «21680000-4» рядом с базовым 21680000.
6. Поиск по названию НЕ подтверждает SKU: строки показываются, действие
   появляется только у выбранного товара.
7. «Ответить» ведёт к ТОЧНОМУ Q-… во вкладке Верификатора с тем же SKU.
8. Все изменяющие действия выключены и называют флаг — FEATURE_DISABLED.
9. Тексты кодов каталога канона: ru и uk дословно из каталога, en есть;
   неизвестный код — CONTRACT_COMPATIBILITY_ERROR, а не успех.
10. Статус по квитанции — ответ по схеме канона, только из хранилища.
11. Этап 1 ничего не пишет: в сервисе нет ни одного INSERT/UPDATE/DELETE.

База Listing Suite и база Кабинета подменены, сеть не трогается.

Запуск (pytest не нужен):  python tests/test_passport_registry.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import jsonschema
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


TS = pd.Timestamp("2026-10-06 12:00", tz="UTC")
SHA = "a" * 64

DIRECTORY = pd.DataFrame([
    dict(sku="21680000", name="Насос поверхностный PW-14B", ean="4823102300001", is_active=True, asins="B0AAAAAAA1"),
    dict(sku="21680000-4", name="Насос PW-14B акция", ean=None, is_active=True, asins="B0AAAAAAA1"),
    dict(sku="54225000", name="Степлер CC-36", ean=None, is_active=True, asins=""),
    dict(sku="11110000", name="Перфоратор SDS+", ean="4823102300002", is_active=True, asins="B0BBBBBBB2"),
    dict(sku="22220000", name="Дрель-шуруповёрт", ean="4823102300003", is_active=True, asins=""),
    dict(sku="33330000", name="Шлифмашина 125 мм", ean="", is_active=True, asins=""),
    dict(sku="55550000", name="Шуруповёрт ударный", ean="4823102300005", is_active=True, asins=""),
])


def obj(sku, state, model, readback=SHA, limitations=None, version="1.0"):
    return dict(passport_id=f"PSP-{sku}", lineage_id=f"LIN-{sku}", sku_id=sku, product_version="1.0",
                product_name=None, model=model, state=state, passport_version=version, sha256=SHA,
                storage_path=None, materials_url=None, limitations=json.dumps(limitations or []),
                last_event_type="APPLIED", last_event_at=TS, readback_sha256=readback, readback_at=TS)


OBJECTS = pd.DataFrame([
    obj("11110000", "NOT_READY", "RH-800"),                 # действующий блокер → BLOCKED
    obj("22220000", "READY", "CD-218"),
    obj("33330000", "READY_WITH_LIMITATIONS", "GL-125S", limitations=[{"id": "L1", "text": "без кейса"}]),
    obj("54225000", "NOT_READY", "CC-36"),                  # вопрос SENT без блокера
    obj("44440000", "READY", "BP-204", readback="b" * 64),  # SHA не подтверждён
    obj("66660000", "BLOCKED", "BC-204"),                   # BLOCKED записан, блокера нет
])
BLOCKS = pd.DataFrame([
    dict(block_id="BLK-RUN1-001", run_id="RUN1", sku_id="11110000", reason="нужно подтвердить комплектацию",
         responsible_party="Владелец SKU", responsible_role="PASSPORT_ADMIN", responsible_user=None,
         resume_condition="подтвердить комплектацию", created_at=TS),
    # неполный блокер: без условия возобновления он ничего не блокирует
    dict(block_id="BLK-RUN3-001", run_id="RUN3", sku_id="66660000", reason="что-то",
         responsible_party="кто-то", responsible_role=None, responsible_user=None,
         resume_condition="", created_at=TS),
])
QUESTIONS = pd.DataFrame([
    dict(question_id="Q-RUN2-001", run_id="RUN2", sku_id="54225000", product_version="1.0", passport_id="PSP-54225000",
         question_type="ANSWER", status="SENT", impact="REQUIRED_FOR_READINESS", block_id=None,
         responsible_role="PASSPORT_ADMIN", responsible_user=None, question_text="Какой вес нетто?",
         reason_text="вес расходится в двух источниках", affected_object="weight", expected_answer="число и единица",
         closure_criterion="подтверждённое значение", evidence_required=False, due_at=None, conflict=None,
         created_at=TS, updated_at=TS),
    dict(question_id="Q-RUN1-002", run_id="RUN1", sku_id="11110000", product_version="1.0", passport_id="PSP-11110000",
         question_type="DOCUMENT", status="ANSWER_RECEIVED", impact="NON_BLOCKING", block_id=None,
         responsible_role="PASSPORT_ADMIN", responsible_user=None, question_text="Пришлите инструкцию",
         reason_text=None, affected_object=None, expected_answer=None, closure_criterion=None,
         evidence_required=True, due_at=None, conflict=None, created_at=TS, updated_at=TS),
    dict(question_id="Q-RUN2-003", run_id="RUN2", sku_id="54225000", product_version="1.0", passport_id="PSP-54225000",
         question_type="CONFLICT", status="SENT", impact="BLOCKS_PASSPORT", block_id="BLK-RUN2-009",
         responsible_role="PRODUCT_OWNER", responsible_user=None, question_text="Какая производительность?",
         reason_text=None, affected_object=None, expected_answer=None, closure_criterion=None,
         evidence_required=False, due_at=None, conflict=None, created_at=TS, updated_at=TS),
])
ANSWERS = pd.DataFrame([
    dict(answer_id="A1", question_id="Q-RUN1-002", answer_version=1, supersedes_answer_id=None, author="x@dniprom.com",
         answer_text="инструкция во вложении", decision=None, source_artifact_ids="[]", created_at=TS),
])
VERDICTS = pd.DataFrame([dict(answer_id="A1", seq=1, verdict="PARTIAL", reason="не та модель", created_at=TS)])
RUNS = pd.DataFrame(columns=["run_id", "sku_id", "requested_action", "lifecycle_state", "current_node_id", "created_at"])

MODE = {"missing": False, "fail": False}


def fake_sql(sql, con=None, params=None, **kw):
    q = " ".join(str(sql).split())
    if "to_regclass" in q:
        name = (params or {}).get("n", "")
        return pd.DataFrame([{"t": None if (MODE["missing"] and "passport_" in name) else name}])
    if ("passport_" in q or "ai_runs" in q or "ai_receipts" in q) and MODE["fail"]:
        raise RuntimeError("база недоступна")
    if "FROM ai_runs" in q and "run_state" in q:
        # снимок Паспорта по запускам вопросов: в фикстуре запусков нет
        return pd.DataFrame(columns=["run_id", "run_state"])
    for table, df in (("FROM passport_objects", OBJECTS), ("FROM passport_questions", QUESTIONS),
                      ("FROM passport_blocks", BLOCKS), ("FROM ai_runs", RUNS),
                      ("FROM passport_answers", ANSWERS), ("FROM passport_answer_verdicts", VERDICTS)):
        if table in q:
            return df.copy()
    return pd.DataFrame()


pd.read_sql = fake_sql
import services.db as db                                   # noqa: E402
db.get_conn = lambda: type("C", (), {"close": lambda self: None})()


class _Cur:
    def __init__(self):
        self.description, self._rows = [], []

    def execute(self, sql, params=None):
        if "sku_master" not in sql:
            raise RuntimeError("в тесте Кабинет отвечает только справочником")
        self.description = [(c,) for c in DIRECTORY.columns]
        self._rows = [tuple(r) for r in DIRECTORY.itertuples(index=False)]

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


class _KConn:
    def cursor(self):
        return _Cur()

    def close(self):
        pass


import services.kdb as kdb                                 # noqa: E402
kdb.get_conn = lambda: _KConn()

import services.passport as pp                             # noqa: E402
import streamlit as st                                     # noqa: E402
from streamlit.testing.v1 import AppTest                   # noqa: E402

ADMIN = pp.CANONICAL_ROLES["admin"]

# ================================================================ правила
data = {"objects": OBJECTS, "questions": QUESTIONS, "blocks": BLOCKS, "runs": RUNS}
dupes = pp.duplicate_map(DIRECTORY)
view, _ = pp.search(DIRECTORY, OBJECTS, "")
rows = pp.registry_rows(view, data, dupes, "", ADMIN).set_index("sku")

check("1. действующий блокер → «Заблокирован», хотя записано NOT_READY",
      rows.loc["11110000", "state"] == "BLOCKED")
check("1. записанное BLOCKED без действующего блокера → «В работе»",
      rows.loc["66660000", "state"] == "NOT_READY")
check("1. неполный блокер (без условия возобновления) не считается",
      rows.loc["66660000", "blocks"] == 0)
check("1. вопрос SENT без блокера: «В работе» и отдельно «Требуется ответ»",
      rows.loc["54225000", "state"] == "NOT_READY" and bool(rows.loc["54225000", "my_action"]))
check("4. мой вопрос SENT → «Ответить» к точному Q-…",
      (rows.loc["54225000", "action"], rows.loc["54225000", "action_target"]) == (pp.ANSWER, "Q-RUN2-001"))
check("4. мой действующий блокер → «Выполнить требуемое действие» по BLK",
      (rows.loc["11110000", "action"], rows.loc["11110000", "action_target"]) == (pp.DO_REQUIRED, "BLK-RUN1-001"))
check("4. READY_WITH_LIMITATIONS → «Открыть ограничения», ограничений 1",
      rows.loc["33330000", "action"] == pp.OPEN_LIMITATIONS and rows.loc["33330000", "limitations"] == 1)
check("4. READY → «Открыть Паспорт»", rows.loc["22220000", "action"] == pp.OPEN_PASSPORT)
check("3. SHA не подтверждён → «Данные устарели», состояние остаётся «Готов»",
      rows.loc["44440000", "fresh"] == pp.STALE and rows.loc["44440000", "state"] == "READY")
check("3. подтверждённый SHA → «Актуально»", rows.loc["22220000", "fresh"] == pp.CURRENT)

absent_view, _ = pp.search(DIRECTORY, OBJECTS, "55550000")
absent = pp.registry_rows(absent_view, data, dupes, "", ADMIN).iloc[0]
check("2. «Паспорт отсутствует» — не состояние: state пуст, has_passport ложь",
      absent["state"] is None and not absent["has_passport"])
check("2. у отсутствующего Паспорта действие — «Создать Паспорт»", absent["action"] == pp.CREATE)

check("5. одинаковый ASIN: 21680000 и 21680000-4 — возможные дубликаты друг друга",
      dupes.get("21680000") == {"21680000-4"} and dupes.get("21680000-4") == {"21680000"})
dup_view, _ = pp.search(DIRECTORY, OBJECTS, "PW-14B")
dup_rows = pp.registry_rows(dup_view, data, dupes, "", ADMIN)
check("5. дубликат запирает всё: «Сравнить», а не «Создать»",
      len(dup_rows) == 2 and set(dup_rows["action"]) == {pp.COMPARE})

# порядок 9.6.5/9.7 на одном наборе осей
nx = pp.next_action
mine_all = {"questions": ["Q-X-001"], "blocks": ["BLK-X-001"]}
check("приоритет: дубликат сильнее блокера и вопроса",
      nx(has_passport=True, state="BLOCKED", fresh=pp.CURRENT, duplicate=True, mine=mine_all)[0] == pp.COMPARE)
check("приоритет: блокер сильнее вопроса",
      nx(has_passport=True, state="BLOCKED", fresh=pp.CURRENT, duplicate=False, mine=mine_all)[0] == pp.DO_REQUIRED)
check("устаревшие данные запирают «Создать»",
      nx(has_passport=False, state=None, fresh=pp.STALE, duplicate=False, mine={})[0] != pp.CREATE)
check("ошибка загрузки запирает «Создать»",
      nx(has_passport=False, state=None, fresh=pp.LOAD_ERROR, duplicate=False, mine={})[0] != pp.CREATE)
check("чужой блокер — только просмотр",
      nx(has_passport=True, state="BLOCKED", fresh=pp.CURRENT, duplicate=False,
         mine={"questions": [], "blocks": []})[0] == pp.OPEN_PASSPORT)
check("NOT_READY без адресного запроса — «Открыть работу», не запуск агента",
      nx(has_passport=True, state="NOT_READY", fresh=pp.CURRENT, duplicate=False,
         mine={"questions": [], "blocks": []})[0] == pp.OPEN_WORK)

# поиск
by_name, _ = pp.search(DIRECTORY, OBJECTS, "насос")
check("6. поиск по названию находит оба насоса", set(by_name["sku"]) == {"21680000", "21680000-4"})
exact, _ = pp.search(DIRECTORY, OBJECTS, "21680000")
check("точный код SKU — первым", exact.iloc[0]["sku"] == "21680000")
by_model, _ = pp.search(DIRECTORY, OBJECTS, "rh-800")
check("модель из Паспорта ищется, хотя в справочнике её нет", list(by_model["sku"]) == ["11110000"])
by_ean, _ = pp.search(DIRECTORY, OBJECTS, "4823102300005")
check("поиск по EAN; пустые EAN у других строк не ломают поиск", list(by_ean["sku"]) == ["55550000"])
empty, _ = pp.search(DIRECTORY, OBJECTS, "")
check("без запроса — только товары с Паспортом", set(empty["sku"]) == set(OBJECTS["sku_id"]))
check("фильтр «Паспорт отсутствует» — отдельная опция",
      list(pp.filter_rows(pp.registry_rows(absent_view, data, dupes, "", ADMIN), ["ABSENT"], "all")["sku"])
      == ["55550000"])

# вопросы
qd = {"questions": QUESTIONS, "answers": ANSWERS, "verdicts": VERDICTS}
qrows = pp.question_rows(qd, BLOCKS, "", ADMIN).set_index("question_id")
check("SENT без ответа → «Требуется ответ»", qrows.loc["Q-RUN2-001", "user_state"] == pp.NEEDS_ANSWER)
check("ответ с вердиктом PARTIAL → «Нужно уточнение», а не «решён»",
      qrows.loc["Q-RUN1-002", "user_state"] == pp.NEEDS_CLARIFICATION)
check("«Блокирует Паспорт» без действующего BLK → «Требуется для готовности»",
      qrows.loc["Q-RUN2-003", "impact"] == "REQUIRED_FOR_READINESS")
check("вопрос другой роли — не мой", not qrows.loc["Q-RUN2-003", "mine"])
c = pp.question_counters(pp.question_rows(qd, BLOCKS, "", ADMIN))
check(f"счётчики: моих 1, уточнений 1 ({c})", c["mine"] == 1 and c["clarify"] == 1 and c["resolved"] == 0)
v2 = pd.concat([ANSWERS, pd.DataFrame([dict(answer_id="A2", question_id="Q-RUN1-002", answer_version=2,
                                            supersedes_answer_id="A1", author="x", answer_text="другая", decision=None,
                                            source_artifact_ids="[]", created_at=TS)])])
check("вердикт по старой версии ответа на новую не переносится → «Ожидает проверки»",
      pp.user_state(QUESTIONS.iloc[1], v2, VERDICTS) == pp.AWAITING_CHECK)

# сообщения
import i18n                                                # noqa: E402
cat = json.loads((pp.PASSPORT_DIR / "Listing_Suite_Message_Catalog_v1.0.json").read_text(encoding="utf-8"))
bad = [m["user_message_code"] for m in cat["messages"]
       if i18n.LANGS["ru"].get("pp.msg." + m["user_message_code"]) != m["texts"]["ru-RU"]
       or i18n.LANGS["uk"].get("pp.msg." + m["user_message_code"]) != m["texts"]["uk-UA"]
       or not i18n.LANGS["en"].get("pp.msg." + m["user_message_code"])]
check(f"9. все {len(cat['messages'])} кодов каталога: ru и uk дословно, en есть ({bad})", not bad)
check("9. неизвестный код → CONTRACT_COMPATIBILITY_ERROR, не успех",
      pp.resolve_message("PASSPORT_SOMEHOW_OK")["user_message_code"] == "CONTRACT_COMPATIBILITY_ERROR")

# статус по квитанции
resp_schema = json.loads((pp.PASSPORT_DIR / "listing_suite_passport_status_response.schema.json").read_text(encoding="utf-8"))
validator = jsonschema.Draft202012Validator(resp_schema)
found = pp.lookup_status("54225000", "request_id", "LS-PSP-REQ-1", read=lambda sql, p: (pd.DataFrame([dict(
    receipt_id="LS-PSP-RECEIPT-1", request_id="LS-PSP-REQ-1", operation_id=None, result="DECISION_REQUIRED",
    receipt_sha256="c" * 64)]), None))
check(f"10. найденная квитанция — ответ по схеме канона ({list(validator.iter_errors(found))[:1]})",
      not list(validator.iter_errors(found)) and found["operation_status"] == "COMPLETED")
missing = pp.lookup_status("54225000", "idempotency_key", "k" * 16, read=lambda sql, p: (pd.DataFrame(), None))
check("10. не найдено — тоже по схеме, NOT_AVAILABLE", not list(validator.iter_errors(missing)))
try:
    pp.lookup_status("x", "request_id", "r", read=lambda sql, p: (pd.DataFrame([dict(
        receipt_id="r", request_id="r", operation_id=None, result="TOTALLY_NEW", receipt_sha256="c" * 64)]), None))
    check("10. неизвестный result квитанции — ошибка совместимости", False)
except pp.CompatibilityError:
    check("10. неизвестный result квитанции — ошибка совместимости", True)

check("8. все флаги выключены", not any(pp.flag_on(f) for f in pp.FLAGS))
try:
    pp.flag_on("listing_suite.typo")
    check("8. опечатка в имени флага — ошибка, а не «выключено»", False)
except KeyError:
    check("8. опечатка в имени флага — ошибка, а не «выключено»", True)

src = (ROOT / "services" / "passport.py").read_text(encoding="utf-8")
writes = re.findall(r"\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM)\b", src, re.I)
check(f"11. этап 1 только читает: в services/passport.py нет записи ({writes})", not writes)


# ================================================================ экран
def page(**state):
    st.cache_data.clear()
    st.cache_resource.clear()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=240).run()
    at.switch_page("pages/content.py")
    for k, v in state.items():
        at.session_state[k] = v
    return at.run()


def table(at, col="next"):
    for d in at.dataframe:
        df = d.value
        if isinstance(df, pd.DataFrame) and col in df.columns and "sku" in df.columns:
            return df
    return pd.DataFrame()


at = page()
check("страница «Контент» открывается с областью Паспорта", not at.exception)
opts = [str(o.content) for w in at.get("button_group") if getattr(w, "key", None) == "pp-tab"
        for o in w.proto.options]
check(f"ровно три вкладки v1, без Image Collection ({opts})",
      opts == ["Реестр Паспортов", "Создание Паспорта", "Взаимодействие с Верификатором"])
reg = table(at)
check(f"без запроса в Реестре — {len(OBJECTS)} товаров с Паспортом", len(reg) == len(OBJECTS))
check("NOT_READY без запроса показывает «Действие не требуется»",
      "Действие не требуется" in set(reg["next"]) and "Открыть работу" not in set(reg["next"]))

at.text_input(key="pp-q").set_value("PW-14B").run()
reg = table(at)
check("поиск «PW-14B»: два насоса, оба — «Сравнить»",
      len(reg) == 2 and set(reg["next"]) == {"Сравнить"})
check("по совпадению названия действие не запускается: карточки нет, пока товар не выбран",
      not any(getattr(b, "key", None) == "pp-act" for b in at.button))

at = page(**{"pp-sku": "54225000"})
act = next((b for b in at.button if b.key == "pp-act"), None)
check(f"7. карточка вопроса: основное действие «Ответить» ({act.label if act else None})",
      act is not None and act.label == "Ответить")
act.click().run()
check("7. «Ответить» открывает вкладку Верификатора на точном Q-RUN2-001",
      at.session_state["pp-tab"] == "verifier" and at.session_state["pp-question"] == "Q-RUN2-001")
qt = next((d.value for d in at.dataframe if "question" in getattr(d.value, "columns", [])), pd.DataFrame())
check("7. в очереди ровно этот вопрос", len(qt) == 1 and "Q-RUN2-001" in qt.iloc[0]["question"])
send = next((b for b in at.button if str(b.key).startswith("pp-send-")), None)
check("8. «Отправить ответ» выключена", send is not None and send.disabled)
check("ТЗ 11.4.1: подсказка поля ответа — «Введите ответ на запрос Верификатора»",
      any(ta.placeholder == "Введите ответ на запрос Верификатора" for ta in at.text_area))

at = page(**{"pp-sku": "11110000"})
check("1. у заблокированного — BLK, ответственный и условие возобновления на экране",
      any("BLK-RUN1-001" in str(e.value) and "подтвердить комплектацию" in str(e.value)
          and "Владелец SKU" in str(e.value) for e in at.error))

at = page(**{"pp-sku": "44440000"})
check("3. неподтверждённый SHA: предупреждение, что изменения заперты",
      any("изменяющие действия заблокированы" in str(w.value) for w in at.warning))

at = page(**{"pp-sku": "22220000", "pp-tab": "create"})
btns = {b.key: b for b in at.button}
check("Создание при существующем Паспорте: «Передать новые данные» и отдельно «Создать новый Паспорт»",
      "pp-delta-off" in btns and "pp-recreate-off" in btns and "pp-create-off" not in btns)
check("8. обе выключены", btns["pp-delta-off"].disabled and btns["pp-recreate-off"].disabled)
check("8. выключенность сказана текстом (FEATURE_DISABLED)",
      any("FEATURE_DISABLED" in str(c.value) for c in at.caption))
_md = " ".join(str(m.value) for m in at.markdown)
check("контроль перед запуском называет, чего не хватает: product_root и полномочия",
      "product_root" in _md and "○" in _md and "Профиль полномочий" in _md)
check("поле материалов на месте, тип файлов браузером не режется — отказ называет проверка",
      any(getattr(w, "key", "") == "pp-files-22220000" for w in at.get("file_uploader")))

at = page(**{"pp-sku": "55550000", "pp-tab": "create"})
btns = {b.key: b for b in at.button}
check("Создание без Паспорта: «Создать Паспорт», выключена", "pp-create-off" in btns and btns["pp-create-off"].disabled)
check("в заголовке вкладки — выбранный SKU (ТЗ §8)", any("55550000" in str(m.value) for m in at.markdown))

MODE["missing"] = True
at = page()
check("нет миграции: страница жива и называет файл миграции",
      not at.exception and any("2026-10-07_passport_sku_core.sql" in str(w.value) for w in at.warning))
MODE["missing"] = False

MODE["fail"] = True
at = page()
at.text_input(key="pp-q").set_value("55550000").run()
reg = table(at)
check("сбой чтения: «Ошибка загрузки» сказана, страница жива", not at.exception and len(at.error) > 0)
check("сбой чтения: «Создать Паспорт» не предлагается",
      not reg.empty and "Создать Паспорт" not in set(reg["next"]))
MODE["fail"] = False

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
