# -*- coding: utf-8 -*-
"""
services/product_specs.py — характеристики товара для тайтла (пилот «Генератор
текстов», шаг 2).

Откуда. В `product_matrix` характеристик нет вовсе (проверено 20.10.2026), они
лежат в двух местах:

1. **Атрибуты каталога Amazon** (`listing_attributes.raw->attributes`, SP-API):
   мощность, обороты, Ø диска, момент, напряжение, ёмкость аккумулятора,
   модель, состав набора, источник питания. Источник главный.
2. **Текст карточки** — снапшот ScrapingDog (`listing_snapshots.raw`:
   `product_information`, `item_highlight`) и тайтл. Отсюда — то, чего в
   атрибутах нет: энергия удара (J), SDS, глубина пропила, Ø диска у пилы.

Каждое значение хранит источник. Если два источника называют разное (живой
случай: у DHR-202BC в атрибуте аккумулятор 4 Ah, а в наборе — BP-260 6Ah),
это не выбирается молча, а уходит в `conflicts`: чинить надо карточку, а не
прятать расхождение в тайтле.

Что ставить в тайтл и в каком порядке, говорит таблица `TOOL_TYPES` — черновик
владельца от 20.10.2026, финально его подтверждает Ярослав. Мощность у
аккумуляторного инструмента не пишется (в таблице — «только сетевая»), вольтаж
у инструмента — никогда (`services/title_rules.py`), у аккумуляторов и
зарядок — главная характеристика.

Разбор (`extract`) чистый: ни Streamlit, ни базы — его возьмут и страница, и
задача Databricks. Чтение из базы — отдельной функцией `load`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from services.title_rules import POWER_PACK, TOOL

# -------------------------------------------------------------------- поля
# Поле → (единица в тайтле, приставка). Единица пишется вплотную к числу:
# «2400W», «Ø230mm», «6500rpm» — формат владельца.
FIELDS = {
    "power_w": ("W", ""),
    "disc_mm": ("mm", "Ø"),
    "rpm": ("rpm", ""),
    "torque_nm": ("Nm", ""),
    "impact_j": ("J", ""),
    "sds": ("", ""),
    "drill_concrete_mm": ("mm", "Ø"),
    "chuck_mm": ("mm", ""),
    "cut_depth_mm": ("mm", ""),
    "stroke_mm": ("mm", ""),
    "spm": ("spm", ""),
    "bpm": ("bpm", ""),
    "bar_cm": ("cm", ""),
    "chain_speed_ms": ("m/s", ""),
    "pad_mm": ("mm", "Ø"),
    "orbit_mm": ("mm", ""),
    "air_speed_ms": ("m/s", ""),
    "pressure_bar": ("bar", ""),
    "flow_lh": ("l/h", ""),
    "head_m": ("m", ""),
    "flow_lmin": ("l/min", ""),
    "tank_l": ("l", ""),
    "temp_c": ("°C", ""),
    "capacity_ah": ("Ah", ""),
    "voltage_v": ("V", ""),
}

# Поле, которое пишется только у сетевого инструмента.
CORDED_ONLY = {"power_w"}


@dataclass(frozen=True)
class ToolType:
    key: str
    amazon_types: tuple          # productTypes SP-API
    title_re: str                # по-испански, в тайтле или названии
    fields: tuple                # что ставить в тайтл, по порядку
    kind: str = TOOL


# Черновик владельца 20.10.2026 («основные характеристики по типу инструмента»).
# Порядок типов важен: первый подошедший по тайтлу побеждает, поэтому
# перфоратор стоит раньше дрели (у обоих productType DRILL), торцовочная —
# раньше циркулярной.
TOOL_TYPES = (
    ToolType("grinder", ("DISC_GRINDER_TOOL", "GRINDER"), r"amoladora|esmeriladora", ("power_w", "disc_mm", "rpm")),
    ToolType("hammer", ("ROTARY_HAMMER", "DRILL"), r"martillo\s+perforador|perforador|martillo\s+percutor",
             ("impact_j", "sds", "power_w", "drill_concrete_mm")),
    ToolType("impact_wrench", ("IMPACT_WRENCH",), r"llave\s+de\s+impacto", ("torque_nm", "bpm")),
    ToolType("drill", ("DRILL", "DRILL_DRIVER", "SCREWDRIVER"), r"taladro|atornillador",
             ("torque_nm", "rpm", "chuck_mm")),
    ToolType("miter_saw", ("MITER_SAW",), r"ingletadora|sierra\s+de\s+inglete", ("disc_mm", "power_w")),
    ToolType("circular_saw", ("SAW", "CIRCULAR_SAW"), r"sierra\s+circular", ("disc_mm", "cut_depth_mm", "power_w")),
    ToolType("jigsaw", ("JIGSAW",), r"sierra\s+de\s+calar|caladora", ("stroke_mm", "spm", "cut_depth_mm")),
    ToolType("reciprocating_saw", ("RECIPROCATING_SAW",), r"sierra\s+sable", ("stroke_mm", "spm")),
    ToolType("chainsaw", ("CHAINSAW",), r"motosierra", ("bar_cm", "chain_speed_ms")),
    ToolType("orbital_sander", ("SANDER",), r"lijadora", ("pad_mm", "orbit_mm")),
    ToolType("blower", ("LEAF_BLOWER", "BLOWER"), r"soplador", ("air_speed_ms",)),
    ToolType("pressure_washer", ("PRESSURE_WASHER",), r"hidrolimpiadora|limpiadora\s+de\s+alta", ("pressure_bar", "flow_lh")),
    ToolType("pump", ("WATER_PUMP", "PUMP"), r"bomba", ("flow_lh", "head_m", "power_w")),
    ToolType("compressor", ("AIR_COMPRESSOR",), r"compresor", ("pressure_bar", "flow_lmin", "tank_l")),
    ToolType("heat_gun", ("HEAT_GUN",), r"pistola\s+de\s+calor|decapador", ("temp_c", "flow_lmin")),
    ToolType("stapler", ("STAPLER",), r"grapadora", ()),
    ToolType("battery", ("BATTERY",), r"bater[ií]a\s+(?:de\s+)?(?:litio|recargable|bp-)|^bater[ií]a",
             ("voltage_v", "capacity_ah"), POWER_PACK),
    ToolType("charger", ("BATTERY_CHARGER", "CHARGER"), r"^cargador|cargador\s+r[aá]pido", ("voltage_v",), POWER_PACK),
)
TYPE_BY_KEY = {tt.key: tt for tt in TOOL_TYPES}


@dataclass(frozen=True)
class Spec:
    value: object        # число или строка
    source: str          # "attribute" | "snapshot" | "highlights" | "title"


@dataclass
class ProductSpecs:
    asin: str
    marketplace: str
    tool_type: str | None
    kind: str
    model: str | None
    corded: bool | None
    values: dict = field(default_factory=dict)       # поле → Spec
    kit: list = field(default_factory=list)          # дополнения набора
    conflicts: list = field(default_factory=list)    # (поле, Spec, Spec)
    missing: list = field(default_factory=list)      # поля типа, которых нет нигде


# --------------------------------------------------------- атрибуты SP-API
def _attr(attrs: dict, key: str) -> list:
    v = (attrs or {}).get(key)
    return v if isinstance(v, list) else []


def _first_num(attrs: dict, *keys) -> float | None:
    for k in keys:
        for item in _attr(attrs, k):
            for fld in ("value", "decimal_value"):
                v = item.get(fld) if isinstance(item, dict) else None
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    return float(v)
    return None


def _first_text(attrs: dict, key: str) -> str | None:
    for item in _attr(attrs, key):
        v = item.get("value") if isinstance(item, dict) else None
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _texts(attrs: dict, key: str) -> list[str]:
    return [i["value"].strip() for i in _attr(attrs, key)
            if isinstance(i, dict) and isinstance(i.get("value"), str) and i["value"].strip()]


def _nested_num(attrs: dict, key: str, inner: str) -> float | None:
    """`wheel[].diameter[]`, `battery[].capacity[]` — величина во вложенном списке."""
    for item in _attr(attrs, key):
        for sub in (item.get(inner) or []) if isinstance(item, dict) else []:
            for fld in ("value", "decimal_value"):
                v = sub.get(fld) if isinstance(sub, dict) else None
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    return float(v)
    return None


def from_attributes(attrs: dict) -> dict:
    """Поле → число из атрибутов каталога. Только то, что там есть."""
    out = {
        "power_w": _first_num(attrs, "wattage", "maximum_power", "horsepower"),
        "rpm": _first_num(attrs, "maximum_rotational_speed", "speed"),
        "disc_mm": _nested_num(attrs, "wheel", "diameter") or _nested_num(attrs, "blade", "diameter"),
        "torque_nm": _first_num(attrs, "maximum_torque", "item_torque"),
        "voltage_v": _first_num(attrs, "voltage"),
        "capacity_ah": _nested_num(attrs, "battery", "capacity"),
        "drill_concrete_mm": _first_num(attrs, "drilling_capacity_concrete", "drilling_capacity_masonry"),
        "chuck_mm": _first_num(attrs, "chuck_size"),
    }
    return {k: v for k, v in out.items() if v is not None}


# ---------------------------------------------------- текст карточки (ES)
_N = r"(\d+(?:[.,]\d+)?)"
TEXT_PATTERNS = {
    "impact_j": re.compile(rf"{_N}\s?J\b"),
    "disc_mm": re.compile(rf"(?:Ø\s?|disco\s+de\s+|di[aá]metro\s+(?:de\s+)?){_N}\s?mm", re.I),
    "cut_depth_mm": re.compile(rf"corte\s+(?:de\s+)?{_N}\s?mm", re.I),
    "rpm": re.compile(r"(\d{1,2}[.,]?\d{3}|\d{3,5})\s?(?:rpm|r\.?p\.?m|U/min)\b", re.I),
    "torque_nm": re.compile(rf"{_N}\s?Nm\b", re.I),
    "capacity_ah": re.compile(rf"{_N}\s?A/?h\b", re.I),
    "power_w": re.compile(r"(\d{3,4})\s?W\b"),
    "voltage_v": re.compile(rf"{_N}\s?V\b"),
    "drill_concrete_mm": re.compile(rf"hormig[oó]n[^\d]{{0,12}}{_N}\s?mm|{_N}\s?mm\s+(?:en\s+)?hormig[oó]n", re.I),
}
_SDS = re.compile(r"SDS[- ]?(Plus|Max)\b", re.I)


def _num(s: str) -> float:
    s = s.strip()
    # «10.000» и «10,000» — тысячи (три цифры после разделителя), «2,8» — дробь
    if re.fullmatch(r"\d{1,2}[.,]\d{3}", s):
        return float(re.sub(r"[.,]", "", s))
    return float(s.replace(",", "."))


def from_text(text: str) -> dict:
    """Поле → число (или строка для SDS) из свободного текста карточки."""
    out = {}
    for key, rx in TEXT_PATTERNS.items():
        m = rx.search(text or "")
        if m:
            g = next(x for x in m.groups() if x is not None)
            out[key] = _num(g)
    m = _SDS.search(text or "")
    if m:
        out["sds"] = "SDS-" + m.group(1).capitalize()
    return out


# ------------------------------------------------------------------ разбор
def detect_type(title: str, amazon_type: str | None, attrs: dict | None = None) -> str | None:
    """Тип по тайтлу (испанские слова), иначе по productType SP-API.

    productType один на дрель и перфоратор (DRILL), на пилы разных видов (SAW),
    поэтому слова тайтла главнее. `drill_type = hammer_drill` — перфоратор."""
    t = (title or "").lower()
    for tt in TOOL_TYPES:
        if re.search(tt.title_re, t):
            if tt.key == "drill" and _first_text(attrs or {}, "drill_type") == "hammer_drill":
                return "hammer"
            return tt.key
    if amazon_type:
        if amazon_type == "DRILL" and _first_text(attrs or {}, "drill_type") == "hammer_drill":
            return "hammer"
        for tt in TOOL_TYPES:
            if amazon_type in tt.amazon_types:
                return tt.key
    return None


def _corded(attrs: dict) -> bool | None:
    src = (_first_text(attrs, "power_source_type") or "").lower()
    if "cable" in src or "corded" in src or "eléctric" in src:
        return True
    if "bater" in src or "battery" in src or "cordless" in src:
        return False
    return None


_MANUAL = re.compile(r"manual|instrucciones|user\s+manual", re.I)


def kit_items(attrs: dict, model: str | None, type_re: str | None) -> list[str]:
    """Дополнения набора: аккумулятор, зарядка, кейс — без самого инструмента и
    без инструкции. «Amoladora DGA-201M» в составе — это сам товар."""
    out = []
    for item in _texts(attrs, "included_components"):
        low = item.lower()
        if _MANUAL.search(low):
            continue
        if model and model.split()[0].lower() in low:
            continue
        if type_re and re.search(type_re, low):
            continue
        out.append(item)
    return out


# Код модели в тайтле: «GL-240», «DHR-202BC», «CD-12QBC», «DGA-201M». Нужен,
# когда в атрибутах нет `model_name` (у GL-240 его нет): префикс Highlights
# «Model <модель>: » без модели не собрать.
_MODEL_RE = re.compile(r"\b([A-Z]{1,4}-\d{2,4}[A-Z]{0,4})\b")


def model_from_title(title: str, brand: str = "Dnipro-M") -> str | None:
    for m in _MODEL_RE.finditer(title or ""):
        if m.group(1).upper() != brand.upper().replace(" ", ""):
            return m.group(1)
    return None


def _same(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < 1e-6
    return str(a).lower() == str(b).lower()


def _conflict(ps: "ProductSpecs", k: str, have: Spec, other: Spec) -> None:
    """Одно расхождение — одна запись: «4 Ah в атрибуте против 6 Ah» называется
    один раз, даже если 6 Ah стоит и в тайтле, и в наборе."""
    if not any(c[0] == k and _same(c[2].value, other.value) for c in ps.conflicts):
        ps.conflicts.append((k, have, other))


def extract(asin: str, marketplace: str, *, title: str = "", attributes: dict | None = None,
            amazon_type: str | None = None, product_information: dict | None = None,
            item_highlight: str = "") -> ProductSpecs:
    """Характеристики одного товара из уже прочитанных данных."""
    attrs = attributes or {}
    tkey = detect_type(title, amazon_type, attrs)
    tt = TYPE_BY_KEY.get(tkey)
    model = _first_text(attrs, "model_name") or model_from_title(title)
    ps = ProductSpecs(asin=asin, marketplace=marketplace, tool_type=tkey,
                      kind=tt.kind if tt else TOOL, model=model, corded=_corded(attrs))

    for k, v in from_attributes(attrs).items():
        ps.values[k] = Spec(v, "attribute")
    info_text = " ".join(f"{k}: {v}" for k, v in (product_information or {}).items() if isinstance(v, str))
    for source, text in (("snapshot", info_text), ("highlights", item_highlight or ""), ("title", title or "")):
        for k, v in from_text(text).items():
            have = ps.values.get(k)
            if have is None:
                ps.values[k] = Spec(v, source)
            elif not _same(have.value, v):
                _conflict(ps, k, have, Spec(v, source))

    ps.kit = kit_items(attrs, model, tt.title_re if tt else None)
    # Ёмкость из набора («BP-260 6A/h») против атрибута аккумулятора — частое
    # расхождение карточки: называем его, а не выбираем.
    for item in ps.kit:
        m = TEXT_PATTERNS["capacity_ah"].search(item)
        if m:
            v = _num(m.group(1))
            have = ps.values.get("capacity_ah")
            if have is None:
                ps.values["capacity_ah"] = Spec(v, "kit")
            elif not _same(have.value, v):
                _conflict(ps, "capacity_ah", have, Spec(v, "kit"))
    if tt:
        ps.missing = [f for f in tt.fields if f not in ps.values
                      and not (f in CORDED_ONLY and ps.corded is False)]
    return ps


# ---------------------------------------------------------------- в тайтл
def fmt(field_key: str, value) -> str:
    """«2400W», «Ø230mm», «6500rpm», «2,8J» — вплотную, десятичная запятая (ES)."""
    unit, prefix = FIELDS[field_key]
    if isinstance(value, str):
        return value
    v = float(value)
    num = str(int(v)) if v.is_integer() else f"{v:.2f}".rstrip("0").replace(".", ",")
    return f"{prefix}{num}{unit}"


def title_parts(ps: ProductSpecs) -> list[str]:
    """Характеристики для тайтла в порядке таблицы типов: без мощности у
    аккумуляторного инструмента, без вольтажа у инструмента."""
    tt = TYPE_BY_KEY.get(ps.tool_type)
    if not tt:
        return []
    out = []
    for f in tt.fields:
        if f in CORDED_ONLY and ps.corded is False:
            continue
        if f == "voltage_v" and ps.kind == TOOL:
            continue
        spec = ps.values.get(f)
        if spec is not None:
            out.append(fmt(f, spec.value))
    return out


# ------------------------------------------------------------------ чтение
def load(asin: str, marketplace: str) -> tuple[dict | None, str | None]:
    """Сырые данные товара: тайтл и снапшот (последний удачный), атрибуты.

    (данные, None) — прочитано; (None, причина) — не прочиталось. Пустых данных
    при сбое нет: «нет характеристик» и «не прочиталось» — разные ответы."""
    import pandas as pd

    from services.db import get_engine
    try:
        snap = pd.read_sql(
            """SELECT title, raw FROM listing_snapshots
               WHERE asin = %(a)s AND marketplace = %(m)s AND title IS NOT NULL
               ORDER BY fetched_at DESC LIMIT 1""",
            get_engine(), params={"a": asin, "m": marketplace})
        attrs = pd.read_sql(
            """SELECT product_type, raw FROM listing_attributes
               WHERE asin = %(a)s AND marketplace = %(m)s
               ORDER BY fetched_at DESC LIMIT 1""",
            get_engine(), params={"a": asin, "m": marketplace})
    except Exception as e:  # noqa: BLE001 — причина уходит на экран
        return None, f"{type(e).__name__}: {str(e).strip().splitlines()[0] if str(e).strip() else ''}"
    raw = snap.iloc[0]["raw"] if not snap.empty else None
    araw = attrs.iloc[0]["raw"] if not attrs.empty else None
    ptype = attrs.iloc[0]["product_type"] if not attrs.empty else None
    return {
        "title": str(snap.iloc[0]["title"]) if not snap.empty else "",
        "attributes": (araw or {}).get("attributes") if isinstance(araw, dict) else {},
        "amazon_type": ptype if isinstance(ptype, str) else None,
        "product_information": (raw or {}).get("product_information") if isinstance(raw, dict) else {},
        "item_highlight": str((raw or {}).get("item_highlight") or "") if isinstance(raw, dict) else "",
    }, None


def same_type_asins(tool_type: str, marketplace: str) -> tuple[list[str] | None, str | None]:
    """Наши (не конкурентные) ASIN рынка того же типа инструмента.

    Тип — по тайтлу и productType тем же `detect_type`: productType у дрели и
    перфоратора один (DRILL), а ключи у них разные. (список, None) или
    (None, причина)."""
    import pandas as pd

    from services.db import get_engine
    try:
        df = pd.read_sql(
            """SELECT pm.asin, ll.title, la.product_type, la.raw->'attributes' AS attributes
                 FROM product_matrix pm
                 LEFT JOIN listing_latest ll ON ll.asin = pm.asin AND ll.marketplace = pm.marketplace
                 LEFT JOIN listing_attributes la ON la.asin = pm.asin AND la.marketplace = pm.marketplace
                WHERE pm.marketplace = %(m)s AND NOT pm.is_competitor""",
            get_engine(), params={"m": marketplace})
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {str(e).strip().splitlines()[0] if str(e).strip() else ''}"
    out = []
    for _, r in df.iterrows():
        title = r["title"] if isinstance(r["title"], str) else ""
        ptype = r["product_type"] if isinstance(r["product_type"], str) else None
        attrs = r["attributes"] if isinstance(r["attributes"], dict) else {}
        if detect_type(title, ptype, attrs) == tool_type:
            out.append(str(r["asin"]))
    return sorted(set(out)), None


def for_product(asin: str, marketplace: str) -> tuple[ProductSpecs | None, str | None]:
    """Прочитать и разобрать. (характеристики, None) или (None, причина)."""
    data, err = load(asin, marketplace)
    if err:
        return None, err
    return extract(asin, marketplace, **data), None
