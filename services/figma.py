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

# Подпись товара на холсте. Написана людьми и потому пишется
# по-разному — восемь вариантов на 44 подписи страницы UK/US:
#
#   Main Images_B0GTW2CTWZ  54894000 Blower (Small) TJF-36   ← два пробела
#   B0DG2Y9MSS 41500000 Blower DVB-200                       ← без типа
#   Main Images_B0DG3T7VKM_80625040_Welding inverter …       ← подчёркивания
#   Main Images_41473000_B0DG616BXX_Cordless angle grinder    ← SKU впереди
#   A+ Premium Content_B0H26Y485K  Cordless blower …          ← без SKU
#   …_B0FXY75N5G_84516000-49_Cordless chainsaw                ← SKU с хвостом
#
# Поэтому разбор не по шаблону строки, а по ПРИЗНАКАМ: ASIN узнаётся
# сам, SKU — число подходящей длины, остальное имя. Прежний строгий
# шаблон понимал один вариант из восьми и молча терял остальные.
LABEL_TYPE = ("Main Images", "A+ Premium Content")
ASIN_RE = re.compile(r"B0[A-Z0-9]{8}")
SKU_RE = re.compile(r"(?<![\w-])(\d{6,10}(?:-[A-Za-z0-9]+)?)(?![\d])")

# Макет товара: фрейм верхнего уровня с ASIN в имени — «B0G4S9SJ3M.PT01»,
# «B0G4S9SJ3M.MAIN». Связь по имени однозначна, геометрия не нужна.
#
# Перед ASIN допускаются одна-две лишние буквы: в файле есть
# «BB0GJMT58WT.MAIN», «BB0FXY75N5G.MAIN», «BB0DG616BXX.MAIN» — опечатка
# дизайнера, лишняя B. Строгий шаблон терял у этих товаров фрейм
# `.MAIN`, то есть ГЛАВНОЕ изображение: превью и миниатюра показывали
# бы вместо него слайд PT01. Текста в `.MAIN` нет, поэтому перевод
# не страдал — страдало то, по чему товар узнают в списке.
#
# Опечатки не проглатываются молча: имена попадают в отчёт (`typo_frames`),
# чтобы их поправили в Figma, а не чинили разбором вечно.
FRAME_RE = re.compile(r"^(?P<junk>[A-Z]{0,2})(?P<asin>B0[A-Z0-9]{8})\.(?P<part>.+)$")

# Модули A+ называются «carousel 2.2» и ASIN в имени НЕ содержат:
# на UK/US таких 365, и одно и то же имя встречается у разных товаров.
# Связать их с товаром можно только геометрией, а она на проверке
# разошлась с именами там, где ответ известен (114 расхождений из 212).
# Поэтому A+ отложены целиком и попадают в отчёт числом, а не молча.
APLUS_RE = re.compile(r"^carousel\b", re.I)

SECTION_MAIN = "Main Images"

# Пробный заход: четыре товара вместо двадцати одного.
#
# Выбраны не наугад — у этих есть готовые переводы, и из них сразу
# собирается глоссарий: B0G4S9SJ3M переведён на DE (единственный
# в файле), остальные три — на ES и IT. То есть уже на первом чтении
# видно, попадает ли модель в словарь дизайнера.
#
# Ограничение снимается галочкой на экране, а не правкой кода: решение
# «идём на весь файл» принимает человек, когда убедится, что перевод
# годный.
FIRST_PASS_ASINS = ("B0G4S9SJ3M", "B0GTW2CTWZ", "B0DG2Y9MSS", "B0H26QX9DJ")

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

# Ссылку на рендер Figma держит около часа, поэтому кэшируется не она,
# а САМА КАРТИНКА — на сутки. Кэш ссылки на сутки означал бы битые
# миниатюры через час: ссылка протухла, а мы её всё ещё раздаём.
# Скачивание картинки идёт с файлового хранилища, а не с API, и квоту
# не тратит — тратит её только запрос ссылки, раз в сутки на товар.
IMAGE_TTL = 24 * 60 * 60

# Миниатюра в списке: там важно отличить воздуходувку от степлера,
# а не читать подписи. Четверть масштаба — это около 750 px по ширине
# макета, с запасом под ретину.
THUMB_SCALE = 0.25


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


def node_png(node_id: str, key: str | None = None,
             scale: float = IMAGE_SCALE) -> tuple[bytes | None, str | None]:
    """Картинка узла байтами: (png, причина отказа).

    Двухшаговая: сначала ссылка у API (это квота), потом сама картинка
    с файлового хранилища (это не квота). Кэшировать имеет смысл именно
    результат: ссылка живёт около часа, а макет меняется раз в недели.
    """
    url, err = node_image(node_id, key=key, scale=scale)
    if err or not url:
        return None, err or "рендер не пришёл"
    try:
        r = requests.get(url, timeout=TIMEOUT)
    except requests.RequestException as e:
        return None, f"{type(e).__name__}: {e}"
    if r.status_code != 200:
        return None, f"картинка не скачалась: HTTP {r.status_code}"
    # Подпись PNG проверяется здесь, а не на экране: Streamlit отдаёт
    # байты в PIL, и на обрезанном ответе страница падает целиком —
    # список товаров уносит миниатюра, которая была лишь удобством.
    if not r.content.startswith(b"\x89PNG\r\n\x1a\n"):
        return None, f"ответ не похож на PNG ({len(r.content)} байт)"
    return r.content, None


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


def _walk_text(node: dict, out: list, frame: str = "", path: tuple = ()) -> None:
    """Рекурсивный обход: текстовые слои лежат на разной глубине.

    Обход именно рекурсивный, а не по верхнему уровню: между фреймом
    товара и текстом бывает три-четыре вложенных фрейма. Картинки
    не трогаем вовсе — они вставлены с отрицательными координатами
    и обрезаны рамкой, любое вмешательство сдвинет кадр.

    Каждому слою даётся `slot` — «имя фрейма плюс путь в дереве».
    Это единственное, чем строка одного языка связывается со строкой
    другого: id узла на каждой языковой странице свой, а текст на то
    и перевод, что не совпадает. Проверено на живом файле: структура
    UK/US и DE сходится точно, английское «Battery Capacity»
    и немецкое «Batteriekapazität» лежат в одном месте `PT01#0.1.2`.
    """
    if not isinstance(node, dict):
        return
    if node.get("type") == "TEXT":
        text = str(node.get("characters") or "").strip()
        if text:
            out.append({
                "layer_id": str(node.get("id")),
                "frame_name": frame or str(node.get("name") or ""),
                "slot": f"{frame}#{'.'.join(str(i) for i in path)}",
                "source_text": text,
                "char_limit": char_limit(node),
            })
    for i, child in enumerate(node.get("children") or ()):
        _walk_text(child, out, frame, path + (i,))


def parse_label(text: str) -> dict | None:
    """Подпись товара на холсте → ASIN, SKU, название, тип.

    Разбирается по признакам, а не по шаблону строки: подписи пишут
    люди, и на одной странице их восемь вариантов написания. None —
    когда ASIN не нашёлся, то есть подпись не про товар.
    """
    raw = str(text or "").strip()
    kind = None
    for name in LABEL_TYPE:
        if raw.startswith(name):
            kind, raw = name, raw[len(name):].lstrip("_ ")
            break
    hit = ASIN_RE.search(raw)
    if not hit:
        return None
    rest = (raw[:hit.start()] + " " + raw[hit.end():]).replace("_", " ")
    sku = SKU_RE.search(rest)
    title = (rest[:sku.start()] + " " + rest[sku.end():]) if sku else rest
    return {"type": kind, "asin": hit.group(0),
            "sku": sku.group(1) if sku else None,
            "name": " ".join(title.split())}


def parse_document(doc: dict, only_asins: set | None = None) -> dict:
    """Документ → товары, слои и ОТЧЁТ о том, что не разобралось.

    Товар определяется ИМЕНЕМ ФРЕЙМА: «B0G4S9SJ3M.PT01» — макет
    с ASIN в имени, и связь однозначна без всякой геометрии. Подписи
    на холсте дают только SKU и человеческое название.

    `only_asins` сужает разбор до нескольких товаров: перевод сначала
    проверяется на четырёх, и незачем заводить в базу два десятка.

    Отчёт обязателен: молча пропустить непонятое — значит показать
    неполный список полным.
    """
    pages = (doc.get("document") or {}).get("children") or []
    by_key: dict[tuple, dict] = {}
    labels: dict[str, dict] = {}
    skipped_labels: list[str] = []
    skipped_pages: list[str] = []
    aplus_frames = 0
    other_frames: list[str] = []
    typo_frames: list[str] = []

    for page in pages:
        page_name = str(page.get("name") or "")
        lang = PAGE_LANG.get(page_name)
        if lang is None:
            skipped_pages.append(page_name)
            continue
        for node in page.get("children") or ():
            name = str(node.get("name") or "")
            kind = node.get("type")

            # подписи: справочник «ASIN → SKU и название»
            if kind == "TEXT":
                got = parse_label(node.get("characters") or name)
                if got is None:
                    skipped_labels.append(f"{page_name}: {name[:60]}")
                elif lang == SOURCE_LANG or got["asin"] not in labels:
                    labels[got["asin"]] = got
                continue

            if kind != "FRAME":
                continue
            if APLUS_RE.match(name):
                # A+ отложены намеренно, см. APLUS_RE
                aplus_frames += 1
                continue
            m = FRAME_RE.match(name)
            if not m:
                other_frames.append(f"{page_name}: {name[:60]}")
                continue
            asin = m.group("asin")
            if m.group("junk"):
                # разобрали, но сказали вслух: чинить надо в Figma
                typo_frames.append(f"{page_name}: {name[:60]}")
            if only_asins and asin not in only_asins:
                continue

            key = (asin, SECTION_MAIN)
            prod = by_key.get(key)
            if prod is None:
                prod = by_key[key] = {
                    "asin": asin, "sku": None, "name": "",
                    "section_type": SECTION_MAIN,
                    # страница и узел описывают ИСХОДНИК: по ним берётся
                    # превью и по ним ищут макет в Figma руками
                    "page_name": page_name,
                    "figma_node_id": str(node.get("id")),
                    # узлы .MAIN по языкам: часть товаров дизайнер уже
                    # перевёл в самой Figma, и для них есть НАСТОЯЩИЙ
                    # макет на языке — показывать вместо него английский
                    # значит прятать готовую работу
                    "lang_nodes": {},
                    "langs": [], "layers": [],
                }
            if m.group("part").upper().startswith("MAIN"):
                # `.MAIN` — главное изображение товара. В слоях его нет
                # и быть не может: текста в нём нет ни у одного товара
                # из двадцати одного, обход текстовых слоёв его не видит.
                if lang == SOURCE_LANG:
                    prod["page_name"] = page_name
                    prod["figma_node_id"] = str(node.get("id"))
                else:
                    prod["lang_nodes"][lang] = str(node.get("id"))
            if lang not in prod["langs"]:
                prod["langs"].append(lang)

            found: list = []
            _walk_text(node, found, frame=name)
            # язык принадлежит слою, а не товару: у товара их несколько
            for layer in found:
                layer["lang"] = lang
                layer["page_name"] = page_name
            prod["layers"].extend(found)

    products = list(by_key.values())
    # SKU и название — из подписи, они есть только там
    for prod in products:
        got = labels.get(prod["asin"])
        if got:
            prod["sku"] = got.get("sku")
            prod["name"] = got.get("name") or ""
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
        "skipped_sections": skipped_labels + other_frames,
        "skipped_pages": skipped_pages,
        "aplus_frames": aplus_frames,
        "typo_frames": typo_frames,
        "source_checked": src_total,
        "source_over": src_over,
        "read_at": time.time(),
    }
