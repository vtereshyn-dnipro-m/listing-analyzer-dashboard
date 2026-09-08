# -*- coding: utf-8 -*-
"""
services/figma.py — чтение макетов из Figma и разбор их структуры.

Figma REST API умеет ТОЛЬКО читать. Запись текста в слои через него
невозможна — для этого нужен плагин. Здесь только чтение и разбор.

Про лимит запросов. Figma отвечает 429 и просит подождать сотни секунд,
причём на каждую попытку. Поэтому:

  · документ читается ЦЕЛИКОМ одним запросом и раскладывается в базу;
  · дальше страница работает из базы, а не из Figma;
  · перечитывание — раз в сутки или по кнопке;
  · при 429 ретраев НЕТ. Повтор внутри кода только съел бы лимит
    и растянул ожидание: единственное разумное поведение — сказать
    человеку, сколько ждать, и не трогать API до тех пор.

Про структуру файла. Она выяснена вручную по нескольким товарам,
поэтому разбор устроен как контракт: что не разобралось — попадает
в отчёт с примерами, а не роняет страницу и не исчезает молча.
"""
from __future__ import annotations

import re
import time

import requests

from services.db import cfg

API = "https://api.figma.com/v1"
TIMEOUT = 60

SOURCE_LANG = "en"

# Страница файла = язык. Английский — источник, остальные цели.
# Прочие страницы (OLD, Gazi, Tool Bundle Sets, For review, BD Print,
# From The Brand, Brand Store, References, «ES - from ukranian») не наши:
# это чужие рабочие области, старые версии и не карточки товаров.
PAGE_LANG = {
    "UK/US": "en",
    "DE": "de",
    "ES": "es",
    "IT": "it",
    "FR": "fr",
}

# «Main Images_B0G4S9SJ3M 54225000 Battery stapler Dnipro-M CC-36»
SECTION_RE = re.compile(
    r"^(?P<type>Main Images|A\+ Premium Content)_"
    r"(?P<asin>B0[A-Z0-9]{8})\s+"
    r"(?P<sku>\d{6,10})\s+"
    r"(?P<name>.+)$"
)

# Средняя ширина символа как доля кегля. Точного соответствия быть
# не может: ширина зависит от гарнитуры, начертания и самого текста —
# «iii» и «WWW» при одном кегле занимают разное место. Коэффициент
# подобран по гротескам, которыми набраны макеты (Inter, Roboto,
# Helvetica): у них средняя ширина строчного знака около половины кегля.
# Ошибка получается в пару знаков, и об этом сказано на экране —
# иначе строка, не влезшая на границе, выглядит багом расчёта.
AVG_CHAR_RATIO = 0.52

# Межстрочный интервал по умолчанию, если Figma его не отдала.
DEFAULT_LINE_RATIO = 1.2

# Retry-After Figma отдаёт то в секундах, то в МИЛЛИСЕКУНДАХ — заголовок
# один, единицы разные, и различить их можно только по величине. 306325
# это не 85 часов, а пять минут. Ошибка тут не косметическая: «ждать
# 85 часов» человек читает как «сегодня уже никак» и уходит, хотя
# перечитать макеты можно после чашки кофе.
#
# Порог — сутки: столько Figma ждать не просит никогда, а вот 86400
# миллисекунд (полторы минуты) просит регулярно.
RETRY_MS_OVER = 86_400

# Рендер узла под превью. Половинный масштаб: картинка стоит рядом
# с таблицей и нужна для понимания РОЛИ строки — крупный ли это
# заголовок на тёмном фоне или мелкая подпись, — а не для вычитки.
IMAGE_SCALE = 0.5

# Ссылку на рендер Figma держит около часа. Кэшируем с запасом: истёкшая
# ссылка отдаёт битую картинку, а лишний запрос — это квота.
IMAGE_TTL = 50 * 60


class FigmaError(Exception):
    """Отказ Figma, о котором нужно сказать человеку дословно."""

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


def node_image(node_id: str, key: str | None = None,
               scale: float = IMAGE_SCALE) -> tuple[str | None, str | None]:
    """Ссылка на PNG-рендер узла: (url, причина отказа).

    Рендер запрашивается ТОЛЬКО для открытого товара. Миниатюры в списке
    стоили бы по запросу на строку, а список — это сотни строк: тот же
    лимит, который закрывается от одного чтения документа.

    Ссылку Figma держит около часа и отдаёт на файловом хранилище,
    поэтому кэшируется она сама, а не картинка: перекачивать байты
    незачем, а вот повторно просить ссылку — значит тратить квоту.
    """
    key = key or file_key()
    tok = token()
    if not tok or not key or not node_id:
        return None, "нет секретов: " + ", ".join(missing_secrets() or ["node_id"])
    try:
        r = requests.get(f"{API}/images/{key}",
                         params={"ids": node_id, "format": "png",
                                 "scale": scale},
                         headers={"X-Figma-Token": tok}, timeout=TIMEOUT)
    except requests.RequestException as e:
        return None, f"{type(e).__name__}: {e}"
    if r.status_code == 429:
        secs = retry_seconds(r.headers.get("Retry-After"))
        return None, f"429, ждать {secs} с" if secs else "429"
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    try:
        data = r.json()
    except ValueError as e:
        return None, f"ответ не разобрался как JSON: {e}"
    # Figma кладёт причину отказа в поле err, а не в код ответа
    if data.get("err"):
        return None, str(data["err"])
    url = (data.get("images") or {}).get(node_id)
    return (url, None) if url else (None, "рендер не пришёл")


def retry_seconds(raw) -> int | None:
    """Сколько ждать по Retry-After — в секундах, каким бы ни пришёл ответ.

    См. RETRY_MS_OVER: единицы заголовка непостоянны. Нечисловое значение
    (HTTP-дата, пустая строка) даёт None — «сколько ждать, неизвестно»
    честнее выдуманного числа.
    """
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    if val < 0:
        return None
    if val > RETRY_MS_OVER:
        val /= 1000.0
    return int(val)


def token() -> str:
    return str(cfg("FIGMA_TOKEN") or "").strip()


def file_key() -> str:
    return str(cfg("FIGMA_FILE_KEY") or "").strip()


def missing_secrets() -> list[str]:
    """Каких секретов не хватает — по именам, чтобы не гадать."""
    return [name for name, val in (("FIGMA_TOKEN", token()),
                                   ("FIGMA_FILE_KEY", file_key())) if not val]


def fetch_document(key: str | None = None) -> dict:
    """Документ файла одним запросом.

    Ретраев нет намеренно, см. заголовок модуля. При 429 отдаём наверх
    FigmaError с числом секунд из Retry-After — это единственное, что
    здесь можно сделать полезного.
    """
    key = key or file_key()
    tok = token()
    if not tok or not key:
        raise FigmaError("нет секретов: " + ", ".join(missing_secrets()))
    try:
        r = requests.get(f"{API}/files/{key}",
                         headers={"X-Figma-Token": tok}, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise FigmaError(f"{type(e).__name__}: {e}") from e

    if r.status_code == 429:
        secs = retry_seconds(r.headers.get("Retry-After"))
        raise FigmaError("лимит запросов Figma исчерпан", retry_after=secs)
    if r.status_code == 403:
        raise FigmaError("токен не даёт доступа к файлу (403)")
    if r.status_code == 404:
        raise FigmaError(f"файл {key} не найден (404)")
    if r.status_code != 200:
        raise FigmaError(f"HTTP {r.status_code}: {r.text[:200]}")
    try:
        return r.json()
    except ValueError as e:
        raise FigmaError(f"ответ не разобрался как JSON: {e}") from e


# ---------------------------------------------------------------- разбор

def char_limit(node: dict) -> int | None:
    """Сколько знаков помещается в текстовый слой.

    Считается по ширине слоя и кеглю, с учётом числа строк: слой высотой
    в три строки вмещает втрое больше. Возвращает None, когда геометрии
    нет — «предел неизвестен» честнее выдуманного числа.
    """
    box = node.get("absoluteBoundingBox") or {}
    width = box.get("width")
    height = box.get("height")
    style = node.get("style") or {}
    size = style.get("fontSize")
    if not width or not size:
        return None
    line_h = style.get("lineHeightPx") or float(size) * DEFAULT_LINE_RATIO
    lines = max(1, int((height or line_h) // line_h)) if line_h else 1
    per_line = int(float(width) // (float(size) * AVG_CHAR_RATIO))
    return max(1, per_line * lines) if per_line > 0 else None


def _walk_text(node: dict, out: list) -> None:
    """Рекурсивный обход: текстовые слои лежат на разной глубине.

    Обход именно рекурсивный, а не по верхнему уровню: в этом файле
    между фреймом и текстом бывает три-четыре вложенных фрейма.
    Картинки не трогаем вовсе — они вставлены с отрицательными
    координатами и обрезаны рамкой, любое вмешательство сдвинет кадр.
    """
    if not isinstance(node, dict):
        return
    if node.get("type") == "TEXT":
        text = str(node.get("characters") or "").strip()
        if text:
            out.append({
                "layer_id": str(node.get("id")),
                "frame_name": str(node.get("name") or ""),
                "source_text": text,
                "char_limit": char_limit(node),
            })
    for child in node.get("children") or ():
        _walk_text(child, out)


def parse_document(doc: dict) -> dict:
    """Документ → товары, слои и ОТЧЁТ о том, что не разобралось.

    Отчёт обязателен: структура выяснена вручную по нескольким товарам,
    и отклонения будут. Молча пропустить их — значит показать неполный
    список как полный.
    """
    pages = (doc.get("document") or {}).get("children") or []
    by_key: dict[tuple, dict] = {}
    skipped_sections: list[str] = []
    skipped_pages: list[str] = []

    for page in pages:
        page_name = str(page.get("name") or "")
        lang = PAGE_LANG.get(page_name)
        if lang is None:
            skipped_pages.append(page_name)
            continue
        for section in page.get("children") or ():
            name = str(section.get("name") or "")
            m = SECTION_RE.match(name)
            if not m:
                # секция чужого формата — в отчёт, а не в тишину
                skipped_sections.append(f"{page_name}: {name[:60]}")
                continue
            # Товар — это (ASIN, тип секции), а НЕ секция на странице.
            # Один товар нарисован на каждой языковой странице своим
            # узлом, и пока ключом был узел, стапler CC-36 лежал в базе
            # четырьмя записями, а сводка «Все языки» показывала ноль:
            # у каждой записи был ровно один язык.
            key = (m.group("asin"), m.group("type"))
            prod = by_key.get(key)
            if prod is None:
                prod = by_key[key] = {
                    "asin": m.group("asin"),
                    "sku": m.group("sku"),
                    "name": m.group("name").strip(),
                    "section_type": m.group("type"),
                    # страница и узел описывают ИСХОДНИК; до того, как
                    # встретится английская страница, держим первую
                    "page_name": page_name,
                    "figma_node_id": str(section.get("id")),
                    "langs": [],
                    "layers": [],
                }
            if lang == SOURCE_LANG:
                prod["page_name"] = page_name
                prod["figma_node_id"] = str(section.get("id"))
                # имя товара берём с английской страницы: переводные
                # страницы называют секции по-своему
                prod["sku"] = m.group("sku")
                prod["name"] = m.group("name").strip()
            if lang not in prod["langs"]:
                prod["langs"].append(lang)
            found: list = []
            _walk_text(section, found)
            # язык принадлежит слою, а не товару: у товара их несколько
            for layer in found:
                layer["lang"] = lang
                layer["page_name"] = page_name
            prod["layers"].extend(found)

    products = list(by_key.values())
    # Самопроверка коэффициента. Английский текст УЖЕ стоит в макете
    # и по определению в него влезает. Если расчётный предел говорит
    # обратное на заметной доле слоёв, занижен коэффициент, а не макет
    # неверный — и лучше узнать это от системы, чем от дизайнера,
    # которому мы пометили жёлтым половину исходных строк.
    src_total = src_over = 0
    for p in products:
        for lr in p["layers"]:
            if lr.get("lang") != SOURCE_LANG:
                continue
            lim = lr.get("char_limit")
            if lim is None:
                continue
            src_total += 1
            if len(lr["source_text"]) > lim:
                src_over += 1
    return {
        "products": products,
        "layers_total": sum(len(p["layers"]) for p in products),
        "skipped_sections": skipped_sections,
        "skipped_pages": skipped_pages,
        "source_checked": src_total,
        "source_over": src_over,
        "read_at": time.time(),
    }
