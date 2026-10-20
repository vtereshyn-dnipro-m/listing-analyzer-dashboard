# -*- coding: utf-8 -*-
"""
tests/test_title_rules.py — общий модуль правил тайтла (`services/title_rules.py`).

Две половины, и обе ломаются тихо:

1. **Синтез после переноса ведёт себя так же.** Проверки тайтла переехали из
   `pages/synthesis.py` (и `phrase_present` из `services/seo.py`) в общий
   модуль. Прежние реализации сохранены ЗДЕСЬ эталоном, байт в байт, и на
   наборе строк — обычных, пограничных и случайных — новые функции обязаны
   давать тот же ответ. Отдельно: функции, которые Синтез реально зовёт
   (загружены из страницы так же, как в `test_length_guard.py`), совпадают с
   эталоном при лимитах из настроек. И копий не осталось: страница и `seo` не
   определяют эти функции сами.
2. **Правила пилота — кодом, с параметрами.** Каждое нарушение (длина,
   символы, «|», повторы, 220V, вольтаж у инструмента, формат единиц, Ø,
   бренд, префикс Highlights) ловится, а верный текст проходит. Длина и
   позиция бренда — параметры: владелец их ещё не решил, и по умолчанию бренд
   не проверяется вовсе.

Запуск (pytest не нужен):  python tests/test_title_rules.py
"""
from __future__ import annotations

import ast
import pathlib
import random
import re
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from services import title_rules as tr  # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


def raises(fn) -> bool:
    try:
        fn()
    except Exception:
        return True
    return False


# ======================================= эталон: реализации ДО переноса
def old_norm(s):
    s = str(s).lower()
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def old_phrase_present(phrase, text):
    t = old_norm(text)
    words = [w for w in old_norm(phrase).split() if len(w) > 2]
    if not words:
        return False
    return all(w in t for w in words)


def old_trim_to_word(text, limit):
    if len(text) <= limit:
        return text
    cut = text[:limit + 1]
    if " " in cut:
        cut = cut[:cut.rindex(" ")]
    else:
        cut = cut[:limit]
    return cut.rstrip(" ,;·—–-|/")


def old_keeps_all(text, hl, keep):
    combined = f"{text} {hl}"
    return all(old_phrase_present(p, combined) for p in keep)


def old_enforce_limits(res, must_keep, TL, HL):
    marks = {"trimmed": [], "over": []}
    out = dict(res)
    for field, limit, key in (("title", TL, "title"), ("highlights", HL, "highlights")):
        val = str(out.get(field) or "")
        if len(val) <= limit:
            continue
        cand = old_trim_to_word(val, limit)
        probe = dict(out)
        probe[field] = cand
        if cand and old_keeps_all(str(probe.get("title") or ""), str(probe.get("highlights") or ""), must_keep):
            out[field] = cand
            marks["trimmed"].append(key)
        else:
            marks["over"].append(key)
    return out, marks


def old_over_limits(res, TL, HL):
    bad = []
    if len(str(res.get("title") or "")) > TL:
        bad.append(f"title {len(str(res.get('title') or ''))}/{TL}")
    if len(str(res.get("highlights") or "")) > HL:
        bad.append("highlights " f"{len(str(res.get('highlights') or ''))}/{HL}")
    return bad


OLD_FORBIDDEN = set("!$?_{}^¬¦®©™")


def old_bad_chars(new_title):
    return sorted({c for c in new_title if c in OLD_FORBIDDEN})


def old_over_words(new_title):
    words = re.findall(r"[a-zA-Zа-яА-ЯёЁáéíóúñüÁÉÍÓÚÑÜäöüßÄÖÜ0-9]+", new_title.lower())
    stop = {"de", "con", "para", "y", "el", "la", "und", "mit", "für", "et", "avec", "e", "con", "per"}
    return sorted({w for w in words if len(w) > 2 and w not in stop and words.count(w) > 2})


# ============================================================ набор строк
CRAFTED = [
    "", "x", "Amoladora Angular Dnipro-M GL-240 2400W 230 mm, 6500 RPM, Giratoria M14",
    "Martillo Perforador Dnipro-M DHR-202BC Ultra 20V, Brushless, SDS Plus, Martillo, martillo",
    "Taladro taladro TALADRO taladro de de de con con con para",
    "a" * 90, "word " * 30, "Ünïcödé ÄÖÜ ß ñ á é 2,8J 1.500W —– · |/",
    "Sierra Circular! a Batería? $99 {x} ^y ¬z ¦w ®™© _",
    "trailing sep ·", "ends with dash -", "single" + "x" * 80,
    "Dnipro-M Akku-Winkelschleifer 20V 125mm 10.000 U/min mit Akku und Ladegerät, M14",
    # Кириллица с ё, каждое стоп-слово трижды, двухбуквенные слова: без них
    # набор не видел мутаций алфавита, стоп-слов и `len(w) > 2` (проверяющий #143).
    "Шуруповёрт шуруповёрт ШУРУПОВЁРТ ёлка ёлка ёлка дрель Дрель дрель",
    " ".join(w for w in ("de", "con", "para", "y", "el", "la", "und", "mit", "für", "et", "avec", "e", "per")
             for _ in range(3)),
    "kit de 2 baterías, kit de 2 cargadores, en lo alto, en lo bajo, en lo medio",
]
rnd = random.Random(20261020)
ALPH = "abcdeñüá ÄÖ ёжЁ 0123456789,.-|/·—–!?$_{}^¬¦®©™ "
RANDOM = ["".join(rnd.choice(ALPH) for _ in range(rnd.randint(0, 140))) for _ in range(400)]
CORPUS = CRAFTED + RANDOM
PHRASES = ["amoladora angular", "martillo", "20V", "sds plus", "x", "", "ñandú", "taladro atornillador 60nm",
           "kit de 2", "en lo", "шуруповёрт дрель", "de"]

# ========================================== 1. Синтез ведёт себя так же
print("1. перенос проверок без изменения поведения")
mismatch = []
for s in CORPUS:
    for lim in (0, 1, 10, 74, 75, 76, 125):
        if tr.trim_to_word(s, lim) != old_trim_to_word(s, lim):
            mismatch.append(("trim", s[:30], lim))
    if tr.forbidden_chars(s) != old_bad_chars(s):
        mismatch.append(("chars", s[:30]))
    if tr.repeated_words(s) != old_over_words(s):
        mismatch.append(("repeats", s[:30]))
    if tr.norm_text(s) != old_norm(s):
        mismatch.append(("norm", s[:30]))
    for ph in PHRASES:
        if tr.phrase_present(ph, s) != old_phrase_present(ph, s):
            mismatch.append(("phrase", ph, s[:30]))
    for hl in ("", s[::-1]):
        keep = [p for p in PHRASES if p][: (len(s) % 4)]
        if tr.keeps_all(s, hl, keep) != old_keeps_all(s, hl, keep):
            mismatch.append(("keeps", s[:30]))
        res = {"title": s, "highlights": hl}
        for TL, HL in ((75, 125), (10, 20), (200, 300)):
            if tr.over_limits(res, TL, HL) != old_over_limits(res, TL, HL):
                mismatch.append(("over", s[:30], TL))
            if tr.enforce_limits(res, keep, TL, HL) != old_enforce_limits(res, keep, TL, HL):
                mismatch.append(("enforce", s[:30], TL))
check(f"новые функции = прежние на {len(CORPUS)} строках × лимиты и фразы ({mismatch[:3]})", not mismatch)
check("набор запрещённых символов Синтеза не изменился", tr.FORBIDDEN_CHARS == OLD_FORBIDDEN)

# Синтез: функции, которые страница реально зовёт, — загружены из её кода
import services.db  # noqa: E402

services.db.get_conn = lambda: type("C", (), {"close": lambda self: None})()
pd.read_sql = lambda *a, **k: pd.DataFrame()
src = open(ROOT / "pages/synthesis.py", encoding="utf-8").read()
head = src[:src.index("def save_draft")]
syn = types.ModuleType("syn")
syn.__dict__["__name__"] = "syn"
exec(compile(head, "syn", "exec"), syn.__dict__)
TL, HL = syn.TITLE_LIMIT, syn.HIGHLIGHTS_LIMIT
page_mismatch = []
for s in CORPUS:
    res = {"title": s, "highlights": s[:130]}
    keep = [p for p in PHRASES if p][: (len(s) % 3)]
    if syn.over_limits(res) != old_over_limits(res, TL, HL):
        page_mismatch.append(("over", s[:20]))
    if syn.enforce_limits(res, keep) != old_enforce_limits(res, keep, TL, HL):
        page_mismatch.append(("enforce", s[:20]))
    if syn.trim_to_word(s, TL) != old_trim_to_word(s, TL) or syn.keeps_all(s, "", keep) != old_keeps_all(s, "", keep):
        page_mismatch.append(("trim/keeps", s[:20]))
check(f"Синтез при лимитах {TL}/{HL}: обрезка, лимиты, фразы — как до переноса ({page_mismatch[:3]})",
      not page_mismatch)

# run_checks: тексты проверок те же — сравниваем со старой формулой на нескольких тайтлах
syn.t = lambda key, **kw: key + (str(sorted(kw.items())) if kw else "")


def old_run_checks(new_title, new_hl, keep, forbid):
    checks = []
    combined = f"{new_title} {new_hl}".lower()
    checks.append((len(new_title) <= TL, syn.t("chk.title_len", n=len(new_title), min=TL)))
    checks.append((len(new_hl) <= HL, syn.t("chk.hl_len", n=len(new_hl), min=HL)))
    bad = old_bad_chars(new_title)
    checks.append((not bad, syn.t("chk.forbidden_chars") + ": " + (" ".join(bad) if bad else syn.t("chk.none"))))
    ow = old_over_words(new_title)
    checks.append((not ow, syn.t("chk.word_repeats") + ": " + (", ".join(ow) if ow else syn.t("chk.none"))))
    for ph in keep:
        checks.append((ph.lower() in combined, f"{syn.t('chk.phrase_kept')}: «{ph}»"))
    for ph in forbid:
        checks.append((ph.lower() not in combined, f"{syn.t('chk.phrase_absent')}: «{ph}»"))
    return checks


rc_bad = [s[:20] for s in CRAFTED + RANDOM[:60]
          if syn.run_checks(s, s[::-1][:130], ["martillo"], ["milwaukee"]) !=
          old_run_checks(s, s[::-1][:130], ["martillo"], ["milwaukee"])]
check(f"run_checks Синтеза даёт те же проверки и тексты ({rc_bad[:3]})", not rc_bad)

# копий нет: страница и seo эти функции больше не определяют
defs = {n.name for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef)}
check(f"Синтез не определяет у себя trim_to_word и keeps_all ({sorted(defs & {'trim_to_word', 'keeps_all'})})",
      not defs & {"trim_to_word", "keeps_all"})
check("и не держит свой набор запрещённых символов", "FORBIDDEN_CHARS = set(" not in src)
seo_src = open(ROOT / "services/seo.py", encoding="utf-8").read()
seo_defs = {n.name for n in ast.walk(ast.parse(seo_src)) if isinstance(n, ast.FunctionDef)}
check("seo не определяет phrase_present и _norm у себя", not seo_defs & {"phrase_present", "_norm"})
from services import seo  # noqa: E402

check("seo.phrase_present — тот же, что в общем модуле", seo.phrase_present is tr.phrase_present)
mod_src = open(ROOT / "services/title_rules.py", encoding="utf-8").read()
check("модуль чистый: без Streamlit и базы", not re.search(r"^\s*(import streamlit|from services|import services)", mod_src, re.M))

# =========================================================== 2. правила пилота
print("2. правила пилота")


def cs(title, hl="", **kw):
    return tr.codes(tr.check(title, hl, **kw))


GOOD = "Amoladora Angular 2400W Ø230mm 6500rpm M14, Giratoria, Soft Start"
check(f"верный тайтл проходит ({cs(GOOD)})", cs(GOOD) == [])
check("по умолчанию бренд не проверяется (позиция не решена)", tr.Ruleset().brand_position is None and cs(GOOD) == [])
check("длина — параметр: 75 по умолчанию",
      "TITLE_TOO_LONG" in cs("x" * 76) and "TITLE_TOO_LONG" not in cs("x" * 75))
check("длина — параметр: при 200 тот же тайтл проходит",
      "TITLE_TOO_LONG" not in cs("x" * 76, rules=tr.Ruleset(title_limit=200)))
check("Highlights > 125 — нарушение", "HIGHLIGHTS_TOO_LONG" in cs(GOOD, "h" * 126))
check("«|» запрещён (разделитель — запятая)", "FORBIDDEN_CHAR" in cs("Amoladora 2400W | Kit"))
check("«│» и «¦» тоже", "FORBIDDEN_CHAR" in cs("Amoladora │ Kit") and "FORBIDDEN_CHAR" in cs("Amoladora ¦ Kit"))
check("запятая разрешена", "FORBIDDEN_CHAR" not in cs("Amoladora 2400W, Kit"))
check("запрещённые символы Amazon", "FORBIDDEN_CHAR" in cs("Amoladora! oferta?"))
check("слово больше двух раз", "WORD_REPEATED" in cs("Taladro taladro Taladro 60Nm"))
check("два раза — можно", "WORD_REPEATED" not in cs("Taladro y taladro 60Nm"))
check("220V — нарушение у инструмента", "MAINS_VOLTAGE" in cs("Amoladora 2400W 220V"))
check("230 V и 220-240V — тоже", "MAINS_VOLTAGE" in cs("Amoladora 230 V") and "MAINS_VOLTAGE" in cs("Amoladora 220-240V"))
check("220V — нарушение даже у аккумулятора", "MAINS_VOLTAGE" in cs("Cargador FC-230 220V", kind=tr.POWER_PACK))
check("вольтаж аккумулятора у инструмента — нарушение", "TOOL_VOLTAGE" in cs("Martillo Perforador 20V 50Nm"))
check("и с пробелом «12 V»", "TOOL_VOLTAGE" in cs("Taladro 12 V 30Nm"))
check("у аккумулятора и зарядки вольтаж можно",
      cs("Batería BP-260 20V 6Ah", kind=tr.POWER_PACK) == [] and cs("Cargador FC-230 20V", kind=tr.POWER_PACK) == [])
check("220V не считается дважды как вольтаж инструмента",
      tr.codes(tr.check("Amoladora 220V")) == ["MAINS_VOLTAGE"])
check("модель «BP-260», «FC-230», «M14» — не вольтаж и не единица", cs("Batería BP-260, Cargador FC-230, M14") == [])
check("число и единица через пробел — нарушение", "UNIT_SPACING" in cs("Amoladora 2400 W 230 mm"))
check("регистр единицы: RPM → rpm, NM → Nm", "UNIT_CASE" in cs("Amoladora 6500RPM") and "UNIT_CASE" in cs("Taladro 60NM"))
check("разделитель тысяч: 10.000rpm → 10000rpm", "UNIT_THOUSANDS" in cs("Amoladora 10.000rpm"))
check("десятичная запятая не принимается за тысячи: 2,8J", "UNIT_THOUSANDS" not in cs("Martillo 2,8J"))
check("Ø через пробел — нарушение", "DIAMETER_SPACING" in cs("Amoladora Ø 230mm"))
check("Ø вплотную — можно", "DIAMETER_SPACING" not in cs("Amoladora Ø230mm"))
# Число сразу после Ø тоже проверяется (проверяющий #143: «Ø» попадал в \w)
check("«Ø230 mm» — пробел перед единицей ловится", "UNIT_SPACING" in cs("Amoladora Ø230 mm"))
check("«Ø230MM» — регистр ловится", "UNIT_CASE" in cs("Amoladora Ø230MM"))
check("«Ø2.300mm» — тысячи ловятся", "UNIT_THOUSANDS" in cs("Disco Ø2.300mm"))
check("после запятой без пробела число проверяется: «2000W,60NM»", "UNIT_CASE" in cs("Taladro 2000W,60NM"))
check("тысячи через пробел: «10 000rpm»", "UNIT_THOUSANDS" in cs("Amoladora 10 000rpm"))
check("каждое «Ø » названо", sum(v.code == "DIAMETER_SPACING" for v in tr.check("Ø 230mm y Ø 125mm")) == 2)
check("вплотную «Ø230mm» с верным форматом не даёт ничего", cs("Amoladora Ø230mm 6500rpm 2400W") == [])
# Разделитель — работающий параметр
check("« - » при разделителе-запятой — нарушение", "SEPARATOR" in cs("Amoladora 2400W - Kit"))
check("« / » и «;» — тоже", "SEPARATOR" in cs("Amoladora / Kit") and "SEPARATOR" in cs("Amoladora; Kit"))
check("дефис в коде модели разделителем не считается", "SEPARATOR" not in cs("Amoladora DGA-201M SDS-Plus"))
check("при разделителе « - » он разрешён, а запятая не проверяется",
      cs("Amoladora 2400W - Kit, Maletín", rules=tr.Ruleset(separator=" - ")) == [])
check("неизвестный разделитель — отказ", raises(lambda: tr.check(GOOD, rules=tr.Ruleset(separator="|"))))
# Вольтаж инструмента в Highlights — параметр (вопрос владельцу)
HL20 = "Model CD-200BC: compatible con baterías 20V"
check("по умолчанию вольтаж инструмента запрещён и в Highlights",
      "TOOL_VOLTAGE" in cs("Taladro 60Nm", HL20, model="CD-200BC"))
check("с tool_voltage_in=('title',) в Highlights можно, в тайтле — нет",
      "TOOL_VOLTAGE" not in cs("Taladro 60Nm", HL20, model="CD-200BC", rules=tr.Ruleset(tool_voltage_in=("title",)))
      and "TOOL_VOLTAGE" in cs("Taladro 20V", rules=tr.Ruleset(tool_voltage_in=("title",))))

START = tr.Ruleset(brand_position="start")
check("бренд в начале: «DNIPRO-M Amoladora» проходит", "BRAND_NOT_FIRST" not in cs("DNIPRO-M " + GOOD, rules=START))
check("бренд не в начале — нарушение", "BRAND_NOT_FIRST" in cs("Amoladora DNIPRO-M 2400W", rules=START))
check("«Dnipro-M» в начале вместо «DNIPRO-M» — только код регистра, не «не первым»",
      cs("Dnipro-M Amoladora", rules=START) == ["BRAND_CASE"])
check("«DNIPRO-M-Amoladora» — бренд в начале, регистр верный", cs("DNIPRO-M-Amoladora", rules=START) == [])
check("«бренда быть не должно» — в любом регистре: «Dnipro-M amoladora» ловится",
      "BRAND_PRESENT" in cs("Dnipro-M amoladora", rules=tr.Ruleset(brand_position="absent")))
check("бренд где угодно", "BRAND_MISSING" in cs(GOOD, rules=tr.Ruleset(brand_position="anywhere")))
check("бренда быть не должно (методология v7)",
      "BRAND_PRESENT" in cs("DNIPRO-M " + GOOD, rules=tr.Ruleset(brand_position="absent")))
check("бренд целым словом: «DNIPRO-MX» — не бренд", "BRAND_NOT_FIRST" in cs("DNIPRO-MX Amoladora", rules=START))
check("неизвестная позиция бренда — отказ, а не молчаливое «не проверять»",
      raises(lambda: tr.check(GOOD, rules=tr.Ruleset(brand_position="first"))))
check("неизвестный вид товара — отказ", raises(lambda: tr.check(GOOD, kind="battery")))
check("Highlights: «Model DGA-201M: …» проходит",
      "HIGHLIGHTS_PREFIX" not in cs(GOOD, "Model DGA-201M: Ø125mm, 10000rpm", model="DGA-201M"))
check("Highlights без префикса — нарушение",
      "HIGHLIGHTS_PREFIX" in cs(GOOD, "Ø125mm, 10000rpm", model="DGA-201M"))
check("префикс — параметр", "HIGHLIGHTS_PREFIX" not in cs(
    GOOD, "Modelo DGA-201M - Ø125mm", model="DGA-201M", rules=tr.Ruleset(highlight_prefix="Modelo {model} - ")))
check("модель не задана — префикс не проверяется", "HIGHLIGHTS_PREFIX" not in cs(GOOD, "Ø125mm"))
check("те же правила символов и единиц — в Highlights",
      {"FORBIDDEN_CHAR", "TOOL_VOLTAGE"} <= set(cs(GOOD, "Model X: 20V | 6Ah", model="X")))

# Пять пилотных товаров: наброски из плана (не вывод модели) по шаблону владельца
print("3. пять пилотных товаров (наброски из плана)")
SKETCH = {
    "DGA-201M": "DNIPRO-M Amoladora Angular Ø125mm 10000rpm Brushless | Batería 6Ah + Cargador",
    "GL-240": "DNIPRO-M Amoladora Angular 2400W Ø230mm 6500rpm M14 | Giratoria, Soft Start",
    "DHR-202BC": "DNIPRO-M Martillo Perforador SDS-Plus 50Nm Brushless | Batería 6Ah + Cargador",
    "DSC-201BC": "DNIPRO-M Sierra Circular Ø165mm Corte 55mm LED | Sin Batería",
    "CD-200BC": "DNIPRO-M Taladro Atornillador 60Nm 1700rpm Brushless | Batería 4Ah",
}
got = {k: cs(v, rules=START) for k, v in SKETCH.items()}
check(f"«|» ловится у всех пяти ({got})", all("FORBIDDEN_CHAR" in c for c in got.values()))
check("длиннее 75 — DGA-201M и DHR-202BC, как в плане",
      {k for k, c in got.items() if "TITLE_TOO_LONG" in c} == {"DGA-201M", "DHR-202BC"})
fixed = {k: v.replace(" | ", ", ") for k, v in SKETCH.items()}
got2 = {k: cs(v, rules=START) for k, v in fixed.items()}
check(f"с запятой остаётся только длина у двух ({got2})",
      all(c in ([], ["TITLE_TOO_LONG"]) for c in got2.values())
      and {k for k, c in got2.items() if c} == {"DGA-201M", "DHR-202BC"})

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
