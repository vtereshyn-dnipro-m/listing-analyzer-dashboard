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

import hashlib
import json
import math
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



def page_lang(name: str) -> str | None:
    """Язык страницы по имени: без хвостовых пробелов и регистра.
    «DE » — та же страница, что «DE»; плагин сравнивает так же."""
    return PAGE_LANG.get(str(name or "").strip().upper())


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

# A+ модули: «carousel 3.1» — модуль 3, слайд 1. ASIN в имени нет, одно
# имя у многих товаров, и у каждого модуля ДВА фрейма с одним именем —
# desktop 2718×1114 и mobile 1398×1048 (по 180 тех и других на UK/US).
#
# ПРИВЯЗКА К ТОВАРУ — по ПОДПИСЯМ, не по геометрии между фреймами:
# холст размечен полосами «подпись → её фреймы → следующая подпись»,
# и над блоком A+ стоит своя подпись «A+ Premium Content_<ASIN> …»
# (где её нет — одна подпись без типа на оба блока товара). Разведка
# 18.09 по живому файлу: 564 фрейма на четырёх страницах, все 564
# легли по этому правилу, ноль потерянных. Предыдущая попытка — по
# ближайшему фрейму товара — расходилась в 114 случаях из 212.
#
# КЛЮЧ МЕЖДУ ЯЗЫКАМИ — ПОРЯДОК ПО ПОЛОЖЕНИЮ, не имя. Имена модулей
# на языковых страницах плывут: у B0G4S9SJ3M на UK/US «carousel 26…31»,
# на DE те же места — «carousel 1, 4…8»; по именам совпадают 12 из 18,
# по позиции (сверху вниз, слева направо, внутри варианта) — 18 из 18,
# у B0H26WGJFS 2 против 10. Отсюда синтетическое имя фрейма для slot:
# «B0G4S9SJ3M.A+d05» — ASIN, вариант (d/m; иная ширина → x<ширина>),
# порядковый номер внутри варианта. Настоящее имя («carousel 3.1»)
# остаётся в frame_name — для человека. Файл дизайнера не трогается;
# плагин применяет то же правило (code.js, attachAplus), и тест
# требует равенства с этим кодом на одном дереве.
APLUS_WIDTH = {2718: "d", 1398: "m"}
APLUS_LABEL_RE = re.compile(r"A\+|premium", re.I)
APLUS_ROW_STEP = 100      # y округляется до сотен: фреймы одного ряда ±30 px


def _bbox(node: dict) -> tuple:
    b = node.get("absoluteBoundingBox") or {}
    return (b.get("x"), b.get("y"), b.get("width"), b.get("height"))


def _half_up(x: float) -> int:
    # Не round(): у Python он банковский (2.5 → 2), у JavaScript
    # Math.round — вверх (2.5 → 3). Ряд на границе сотни разошёлся бы
    # между плагином и разбором; floor(x + 0.5) одинаков у обоих.
    return math.floor(x + 0.5)


def aplus_variant(node: dict) -> str:
    w = _half_up(_bbox(node)[2] or 0)
    return APLUS_WIDTH.get(w, f"x{w}")


def attach_aplus(page_nodes: list) -> dict:
    """{id узла A+ → (asin, синтетическое имя, настоящее имя)}.

    Правило привязки: ближайшая ПОДПИСЬ ВЫШЕ фрейма в той же полосе
    по X (центр фрейма внутри ширины подписи). Подпись типа A+ — товар
    её. Подпись без типа или «Main Images» — тоже её товар, но только
    если фрейм лежит НИЖЕ слайдов этого товара: иначе это чужой блок
    над ней. Фрейм без подписи не привязывается и уходит в отчёт.

    Порядок внутри (товар, вариант): по рядам сверху вниз (y до сотен),
    в ряду слева направо. Тот же порядок обязан дать плагин.
    """
    labels: list = []
    bottom: dict = {}
    for n in page_nodes:
        t = n.get("type")
        if t == "TEXT":
            txt = n.get("characters") or n.get("name") or ""
            got = parse_label(txt)
            if got:
                x, y, w, _ = _bbox(n)
                labels.append((got["asin"], bool(APLUS_LABEL_RE.search(txt)), x, y, w))
        elif t == "FRAME":
            m = FRAME_RE.match(str(n.get("name") or ""))
            if m:
                x, y, w, h = _bbox(n)
                if y is not None and h is not None:
                    a = m.group("asin")
                    bottom[a] = max(bottom.get(a, float("-inf")), y + h)
    frames = [n for n in page_nodes
              if n.get("type") == "FRAME" and APLUS_RE.match(str(n.get("name") or ""))]
    frames.sort(key=lambda n: (_half_up((_bbox(n)[1] or 0) / APLUS_ROW_STEP), _bbox(n)[0] or 0))
    out: dict = {}
    per: dict = {}
    for n in frames:
        x, y, w, h = _bbox(n)
        if x is None or y is None or w is None:
            continue
        cx = x + w / 2
        above = [l for l in labels
                 if l[3] is not None and l[3] < y and l[2] is not None and l[4] is not None
                 and l[2] <= cx <= l[2] + l[4]]
        if not above:
            continue
        asin, is_aplus, *_ = max(above, key=lambda l: l[3])
        if not is_aplus and y < bottom.get(asin, float("-inf")):
            continue
        var = aplus_variant(n)
        k = per.get((asin, var), 0) + 1
        per[(asin, var)] = k
        out[str(n.get("id"))] = (asin, f"{asin}.A+{var}{k:02d}", str(n.get("name") or ""))
    return out



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

# Retry-After у Figma — ВСЕГДА секунды. Здесь было правило «больше суток —
# миллисекунды» (306325 читалось как пять минут), и оно было неверным:
# 27.09 сверка показала, что значение убывает ровно на секунды (за 32
# минуты — на 1924), а 266304 — это ~74 часа до сброса МЕСЯЧНОЙ квоты
# места View, а не «~4 мин». Правило делило честный срок на тысячу
# и звало повторять через пять минут то, что откроется через три дня.
#
# Тип лимита Figma присылает заголовком X-Figma-Rate-Limit-Type: «low» —
# лимит места View/Collab у владельца токена: 6 запросов в месяц на
# эндпоинты Tier 1 (чтение файла и рендер). Ждать тут бессмысленно,
# нужна причина: место Dev или Full.
RATE_LOW = "low"


def rate_limit_reason(kind: str | None, secs: int | None, what: str) -> str:
    """Причина 429 словами. При типе low — не «ждать», а чьё это место."""
    if (kind or "").lower() == RATE_LOW:
        reason = ("Figma: место View у владельца токена — 6 запросов в месяц "
                  "на чтение и рендер, нужно место Dev или Full")
        return reason + (f" (квота обновится через ~{wait_text(secs)})" if secs else "")
    base = f"Figma: лимит {what} исчерпан (429)"
    return base + (f", ждать ~{wait_text(secs)}" if secs else "")

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

    def __init__(self, message: str, retry_after: int | None = None,
                 limit_type: str | None = None):
        super().__init__(message)
        self.retry_after = retry_after
        self.limit_type = limit_type


# Пауза рендеров после 429 — на ПРОЦЕСС, то есть на все сессии: квота
# у токена одна. Без неё один показ списка просил ссылку на каждую
# миниатюру (21 товар), редактор — на каждый слайд (до 27), и каждый
# запрос получал тот же 429, продлевая ожидание (27.09: картинки
# пропали целиком, Retry-After 266304). Пока пауза идёт, в Figma не
# ходим вовсе и отдаём ту же причину.
_IMG_PAUSE = {"until": 0.0, "reason": ""}


def images_paused() -> str | None:
    """Причина паузы рендеров или None, если можно спрашивать."""
    if time.time() < _IMG_PAUSE["until"]:
        return _IMG_PAUSE["reason"]
    return None


RENDER_BATCH = 50      # узлов в одном запросе рендера: длина URL и время ответа


def node_images(node_ids: list, key: str | None = None,
                scale: float = IMAGE_SCALE) -> tuple[dict, str | None]:
    """Ссылки на PNG-рендер НЕСКОЛЬКИХ узлов одним запросом: ({id: url}, отказ).

    `/v1/images` принимает список узлов, и запрос считается ОДИН — а квота
    у места View шесть запросов в месяц на чтение и рендер вместе. Раньше
    список просил ссылку на каждую миниатюру, редактор — на каждый слайд:
    21 и 27 запросов там, где хватает одного. Узлы, которые Figma не
    отрендерила, в ответе с пустой ссылкой — они не попадают в словарь.

    Ссылку Figma держит около часа и отдаёт на файловом хранилище;
    скачивание самой картинки квоту не тратит (`download_png`).
    """
    ids = [str(n) for n in dict.fromkeys(node_ids) if n]
    key = key or file_key()
    tok = token()
    if not tok or not key or not ids:
        return {}, "нет секретов: " + ", ".join(missing_secrets() or ["node_id"])
    urls: dict = {}
    for i in range(0, len(ids), RENDER_BATCH):
        paused = images_paused()
        if paused:
            return urls, paused
        chunk = ids[i:i + RENDER_BATCH]
        try:
            r = requests.get(f"{API}/images/{key}",
                             params={"ids": ",".join(chunk), "format": "png",
                                     "scale": scale},
                             headers={"X-Figma-Token": tok}, timeout=TIMEOUT)
        except requests.RequestException as e:
            return urls, f"{type(e).__name__}: {e}"
        if r.status_code == 429:
            secs = retry_seconds(r.headers.get("Retry-After"))
            reason = rate_limit_reason(r.headers.get("X-Figma-Rate-Limit-Type"),
                                       secs, "рендеров")
            # пауза минимум на минуту, даже если срок не пришёл: иначе
            # следующая миниатюра того же показа спросит снова
            _IMG_PAUSE.update(until=time.time() + max(60, secs or 60), reason=reason)
            return urls, reason
        if r.status_code in (401, 403):
            return urls, f"HTTP {r.status_code}: токен не имеет доступа к рендеру файла"
        if r.status_code != 200:
            return urls, f"HTTP {r.status_code}"
        try:
            data = r.json()
        except ValueError as e:
            return urls, f"ответ не разобрался как JSON: {e}"
        # Figma кладёт причину отказа в поле err, а не в код ответа
        if data.get("err"):
            return urls, str(data["err"])
        urls.update({k: v for k, v in (data.get("images") or {}).items() if v})
    return urls, None


def node_image(node_id: str, key: str | None = None,
               scale: float = IMAGE_SCALE) -> tuple[str | None, str | None]:
    """Ссылка на рендер одного узла: (url, отказ) — node_images на одном id."""
    if not node_id:
        return None, "нет секретов: " + ", ".join(missing_secrets() or ["node_id"])
    urls, err = node_images([node_id], key=key, scale=scale)
    url = urls.get(str(node_id))
    if url:
        return url, None
    return None, err or "рендер не пришёл"


def download_png(url: str) -> tuple[bytes | None, str | None]:
    """Картинка по ссылке рендера: (байты, отказ). Квоту не тратит.

    Подпись PNG проверяется здесь, а не на экране: Streamlit отдаёт
    байты в PIL, и на обрезанном ответе страница падает целиком —
    список товаров уносит миниатюра, которая была лишь удобством."""
    try:
        r = requests.get(url, timeout=TIMEOUT)
    except requests.RequestException as e:
        return None, f"{type(e).__name__}: {e}"
    if r.status_code != 200:
        return None, f"картинка не скачалась: HTTP {r.status_code}"
    if not r.content.startswith(b"\x89PNG\r\n\x1a\n"):
        return None, f"ответ не похож на PNG ({len(r.content)} байт)"
    return r.content, None


# Что в узле влияет на картинку. Имя и id — нет: переименовал фрейм —
# рисовать заново незачем. Координаты — только ОТНОСИТЕЛЬНО самого узла:
# REST отдаёт абсолютные, и сдвиг фрейма по холсту иначе менял бы
# отпечаток всего поддерева, хотя картинка та же.
_HASH_SKIP = {"id", "name", "absoluteBoundingBox", "absoluteRenderBounds",
              "transitionNodeID", "prototypeStartNodeID", "flowStartingPoints"}


def _canon(node, ox: float, oy: float):
    if isinstance(node, dict):
        out = {k: _canon(v, ox, oy) for k, v in node.items() if k not in _HASH_SKIP}
        b = node.get("absoluteBoundingBox")
        if isinstance(b, dict):
            out["_rel"] = [round((b.get("x") or 0) - ox, 1), round((b.get("y") or 0) - oy, 1),
                           round(b.get("width") or 0, 1), round(b.get("height") or 0, 1)]
        return out
    if isinstance(node, list):
        return [_canon(v, ox, oy) for v in node]
    return node


def node_hash(node: dict) -> str:
    """Отпечаток узла — меняется, только когда меняется его картинка.

    По нему решается, перерисовывать ли сохранённый рендер. Не по
    `lastModified` файла: он меняется от ЛЮБОЙ правки в файле, и одна
    правленная карточка перерисовывала бы все две с половиной тысячи
    картинок — при квоте места View это шесть запросов в месяц на всё.
    Считается из документа, который и так читается при «Перечитать»,
    то есть без единого лишнего запроса."""
    b = node.get("absoluteBoundingBox") or {}
    canon = _canon(node, b.get("x") or 0, b.get("y") or 0)
    raw = json.dumps(canon, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def node_png(node_id: str, key: str | None = None,
             scale: float = IMAGE_SCALE) -> tuple[bytes | None, str | None]:
    """Картинка узла байтами: (png, причина отказа). Одиночный путь —
    пакетный живёт в localization.ensure_renders."""
    url, err = node_image(node_id, key=key, scale=scale)
    if err or not url:
        return None, err or "рендер не пришёл"
    return download_png(url)


def wait_text(secs: int | None) -> str:
    """«4 мин», «3 ч», «2 дн» — срок ожидания словами для экрана."""
    if not secs:
        return "—"
    if secs < 90:
        return f"{secs} с"
    if secs < 90 * 60:
        return f"{round(secs / 60)} мин"
    if secs < 36 * 3600:
        return f"{round(secs / 3600)} ч"
    return f"{round(secs / 86400)} дн"


def retry_seconds(raw) -> int | None:
    """Сколько ждать по Retry-After — секунды, как их и шлёт Figma.

    Никакого деления на тысячу (см. RATE_LOW выше: правило «больше
    суток — миллисекунды» показывало «~4 мин» вместо ~74 ч). Нечисловое
    значение (HTTP-дата, пустая строка) даёт None — «сколько ждать,
    неизвестно» честнее выдуманного числа.
    """
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    if val < 0:
        return None
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
        kind = r.headers.get("X-Figma-Rate-Limit-Type")
        raise FigmaError(rate_limit_reason(kind, secs, "запросов"),
                         retry_after=secs, limit_type=kind)
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


def _walk_text(node: dict, out: list, frame: str = "", path: tuple = (),
               label: str | None = None) -> None:
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
                "frame_name": label or frame or str(node.get("name") or ""),
                "slot": f"{frame}#{'.'.join(str(i) for i in path)}",
                "source_text": text,
                "char_limit": char_limit(node),
            })
    for i, child in enumerate(node.get("children") or ()):
        _walk_text(child, out, frame, path + (i,), label)


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

    aplus_orphans: list[str] = []
    # Два фрейма с одним именем на одной странице («B0DG3T7VKM.PT04»
    # дважды на UK/US) дают один slot на два слоя: в базе остаётся
    # последний, плагин на таком слоте откажется («несколько слоёв»).
    # Молчать нельзя — это чинится только в Figma.
    dupe_frames: list[str] = []
    for page in pages:
        page_name = str(page.get("name") or "")
        lang = page_lang(page_name)
        if lang is None:
            skipped_pages.append(page_name)
            continue
        page_nodes = page.get("children") or ()
        aplus_map = attach_aplus(list(page_nodes))
        seen_names: dict = {}
        for node in page_nodes:
            if node.get("type") == "FRAME" and FRAME_RE.match(str(node.get("name") or "")):
                nm = str(node.get("name"))
                seen_names[nm] = seen_names.get(nm, 0) + 1
        dupe_frames += [f"{page_name}: {nm} ×{c}" for nm, c in seen_names.items() if c > 1]
        for node in page_nodes:
            name = str(node.get("name") or "")
            kind = node.get("type")

            # подписи: справочник «ASIN → SKU и название»
            if kind == "TEXT":
                got = parse_label(node.get("characters") or name)
                if got is None:
                    skipped_labels.append(f"{page_name}: {name[:60]}")
                    continue
                # У товара подписей две — «Main Images_…» и «A+ Premium
                # Content_…», — и во второй SKU с названием часто нет.
                # Поля ДОПОЛНЯЮТСЯ, а не затираются: английская подпись
                # главнее языковой, но пустое поле не главнее заполненного.
                cur = labels.get(got["asin"])
                if cur is None:
                    labels[got["asin"]] = got
                else:
                    for f in ("sku", "name"):
                        if got[f] and (lang == SOURCE_LANG or not cur[f]):
                            cur[f] = got[f]
                continue

            if kind != "FRAME":
                continue
            if APLUS_RE.match(name):
                hit = aplus_map.get(str(node.get("id")))
                if hit is None:
                    aplus_orphans.append(f"{page_name}: {name[:40]} @ {_bbox(node)[:2]}")
                    continue
                asin, synth, real = hit
                if only_asins and asin not in only_asins:
                    continue
                aplus_frames += 1
                key = (asin, SECTION_MAIN)
                prod = by_key.get(key)
                if prod is None:
                    prod = by_key[key] = {
                        "asin": asin, "sku": None, "name": "",
                        "section_type": SECTION_MAIN, "page_name": page_name,
                        "figma_node_id": str(node.get("id")),
                        "lang_nodes": {}, "langs": [], "layers": [],
                    }
                # узел модуля — по синтетическому ключу без ASIN: «A+d05»
                prod["lang_nodes"].setdefault(lang, {})[synth.split(".", 1)[1]] = str(node.get("id"))
                prod.setdefault("node_hashes", {})[str(node.get("id"))] = node_hash(node)
                if lang not in prod["langs"]:
                    prod["langs"].append(lang)
                found = []
                _walk_text(node, found, frame=synth, label=real)
                for layer in found:
                    layer["lang"] = lang
                    layer["page_name"] = page_name
                prod["layers"].extend(found)
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
                    # узлы ВСЕХ слайдов по языкам:
                    #   {"en": {"MAIN": "1445:541", "PT01": "1445:575"}, …}
                    # Текст живёт в слайдах PT01…PT09, а не в .MAIN —
                    # там фото на белом фоне. Чтобы дизайнер видел, что
                    # написано на КАЖДОМ слайде, нужен узел каждого.
                    "lang_nodes": {},
                    "langs": [], "layers": [],
                }
            # Узлы слайдов в базе не выводятся из слоёв: `.MAIN` текста
            # не содержит вовсе, а у остальных в figma_layers лежит id
            # ТЕКСТОВОГО слоя, не фрейма. Поэтому запоминаются здесь.
            part = m.group("part").upper()
            prod["lang_nodes"].setdefault(lang, {})[part] = str(node.get("id"))
            # отпечаток — чтобы сохранённый рендер перерисовывался, только
            # когда картинка узла правда изменилась (localization.ensure_renders)
            prod.setdefault("node_hashes", {})[str(node.get("id"))] = node_hash(node)
            if part.startswith("MAIN") and lang == SOURCE_LANG:
                prod["page_name"] = page_name
                prod["figma_node_id"] = str(node.get("id"))
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
        "aplus_orphans": aplus_orphans,
        "dupe_frames": dupe_frames,
        "typo_frames": typo_frames,
        "source_checked": src_total,
        "source_over": src_over,
        "read_at": time.time(),
    }
