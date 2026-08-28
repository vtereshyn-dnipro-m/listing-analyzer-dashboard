# -*- coding: utf-8 -*-
"""
services/spapi.py — отправка принятого тайтла прямо в Amazon.

Это единственное место в приложении, которое ПИШЕТ в живые листинги клиента.
Отсюда устройство модуля: он ничего не решает сам. Диалог подтверждения,
выбор товара и защита от повтора живут на странице; сюда приходит уже
подтверждённая одна позиция. Отправка пачкой не поддерживается намеренно —
пока единичная не подтвердится на проде.

Три вещи, которые нельзя брать из головы, берутся из загруженного шаблона
Seller Central (`flatfile_templates`):

  · marketplace_id и language_tag — они лежат прямо в машинном имени
    атрибута `item_name[marketplace_id=…][language_tag=…]`, то есть в файле,
    который Amazon сам и выдал. Хардкодить таблицу идентификаторов рынков
    для операции записи в чужой каталог — риск не того рынка;
  · product_type — из карты отчёта, он свой у каждого товара;
  · SKU — оттуда же, FBM без суффикса -FBA (см. sku_for в
    services/flatfile_template.py).

Без шаблона отправка не работает и говорит об этом прямо: лучше отказать,
чем угадать идентификатор рынка.

Политика Amazon с 27.07.2026: тайтл ≤ 75 символов, Item Highlights ≤ 125,
причём Highlights принимаются ТОЛЬКО когда тайтл в пределах лимита. Поэтому
тайтл сверх лимита не отправляется вовсе, а Highlights уходят лишь вместе
с укладывающимся тайтлом.

Секреты (Streamlit Secrets, как и остальные ключи):
    SP_API_CLIENT_ID, SP_API_CLIENT_SECRET, SP_API_REFRESH_TOKEN,
    SP_API_SELLER_ID
"""
from __future__ import annotations

import json
import re
import time

import pandas as pd
import requests
import streamlit as st

from services.db import cfg, get_conn

LWA_URL = "https://api.amazon.com/auth/o2/token"
LISTINGS_PATH = "/listings/2021-08-01/items/{seller}/{sku}"

# регион по маркетплейсу — это хост API, а не идентификатор рынка:
# ошибиться здесь нельзя тихо, запрос просто не найдёт листинг
REGION_HOST = {
    "eu": "https://sellingpartnerapi-eu.amazon.com",
    "na": "https://sellingpartnerapi-na.amazon.com",
    "fe": "https://sellingpartnerapi-fe.amazon.com",
}
MARKETPLACE_REGION = {
    "es": "eu", "de": "eu", "fr": "eu", "it": "eu", "co.uk": "eu",
    "nl": "eu", "se": "eu", "pl": "eu", "com.tr": "eu", "ae": "eu",
    "com": "na", "ca": "na", "com.mx": "na", "com.br": "na",
    "co.jp": "fe", "com.au": "fe", "sg": "fe",
}

SECRETS = ("SP_API_CLIENT_ID", "SP_API_CLIENT_SECRET",
           "SP_API_REFRESH_TOKEN", "SP_API_SELLER_ID")

_TOKEN_KEY = "spapi.token"


def missing_secrets() -> list[str]:
    """Каких секретов не хватает — страница показывает список, а не «ошибку»."""
    return [n for n in SECRETS if not cfg(n)]


def configured() -> bool:
    return not missing_secrets()


def marketplace_meta(templates: list[dict]) -> tuple[str, str] | None:
    """(marketplace_id, language_tag) из машинного имени item_name в шаблоне."""
    for tpl in templates or []:
        attr = str(tpl.get("item_name_attr") or "")
        mp = re.search(r"marketplace_id=([A-Z0-9]+)", attr)
        lang = re.search(r"language_tag=([A-Za-z_\-]+)", attr)
        if mp and lang:
            return mp.group(1), lang.group(1)
    return None


def host_for(marketplace: str) -> str | None:
    region = MARKETPLACE_REGION.get(str(marketplace).lower())
    return REGION_HOST.get(region) if region else None


def access_token() -> tuple[str | None, str | None]:
    """(токен, ошибка). Живёт ~час, держим в сессии с запасом."""
    cached = st.session_state.get(_TOKEN_KEY) or {}
    if cached.get("token") and cached.get("until", 0) > time.time():
        return cached["token"], None
    try:
        r = requests.post(LWA_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": str(cfg("SP_API_REFRESH_TOKEN") or "").strip(),
            "client_id": str(cfg("SP_API_CLIENT_ID") or "").strip(),
            "client_secret": str(cfg("SP_API_CLIENT_SECRET") or "").strip(),
        }, timeout=30)
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
    if r.status_code != 200:
        return None, f"LWA HTTP {r.status_code}: {r.text[:300]}"
    try:
        body = r.json()
        token = body["access_token"]
        ttl = int(body.get("expires_in") or 3600)
    except Exception:
        return None, f"LWA: ответ без токена — {r.text[:300]}"
    st.session_state[_TOKEN_KEY] = {"token": token,
                                    "until": time.time() + max(60, ttl - 300)}
    return token, None


PARTICIPATIONS_PATH = "/sellers/v1/marketplaceParticipations"


def check_connection(region: str = "eu", timeout: int = 30) -> dict:
    """Проверка связи с SP-API до первой отправки.

    Берём самый лёгкий эндпоинт — список рынков продавца. Он ничего
    не меняет, но проходит весь путь целиком: refresh token → access token →
    подписанный запрос. Если авторизация сломана, узнать об этом надо здесь,
    а не когда «Отправить в Amazon» упадёт на живом товаре.

    Регион по умолчанию европейский: все рынки бренда там. Хост — это
    не идентификатор рынка, а точка входа API.
    """
    out = {"ok": False, "status": "", "markets": [], "suspended": [],
           "error": "", "missing": missing_secrets()}
    if out["missing"]:
        out["error"] = "нет ключей: " + ", ".join(out["missing"])
        return out
    token, err = access_token()
    if not token:
        out["error"] = err or "нет токена"
        return out
    host = REGION_HOST.get(region)
    if not host:
        out["error"] = f"неизвестный регион {region}"
        return out
    try:
        r = requests.get(host + PARTICIPATIONS_PATH,
                         headers={"x-amz-access-token": token},
                         timeout=timeout)
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        return out
    out["status"] = f"HTTP {r.status_code}"
    if r.status_code != 200:
        out["error"] = f"HTTP {r.status_code}: {r.text[:300]}"
        return out
    try:
        body = r.json()
    except Exception:
        out["error"] = f"ответ не JSON: {r.text[:300]}"
        return out
    items = body.get("payload") if isinstance(body, dict) else body
    if not isinstance(items, list):
        out["error"] = f"ответ без списка рынков: {str(body)[:300]}"
        return out
    for it in items:
        if not isinstance(it, dict):
            continue
        mk = it.get("marketplace") or {}
        part = it.get("participation") or {}
        code = str(mk.get("countryCode") or mk.get("id") or "?")
        out["markets"].append(code)
        # hasSuspendedListings — ранний сигнал: связь есть, а часть товаров
        # уже снята с продажи. Молчать об этом на экране проверки нельзя
        if part.get("hasSuspendedListings"):
            out["suspended"].append(code)
    out["ok"] = True
    return out


def build_patches(title: str, highlights: str, mp_id: str, lang: str,
                  title_limit: int, hl_limit: int) -> tuple[list, list[str]]:
    """(патчи, что пропущено и почему).

    Highlights уходят только вместе с укладывающимся тайтлом — по политике
    Amazon от 27.07.2026 иначе они не принимаются, и отправлять их значило бы
    делать запрос, заведомо обречённый на отказ.
    """
    skipped: list[str] = []
    title = str(title or "").strip()
    if not title:
        return [], ["пустой тайтл"]
    if len(title) > title_limit:
        return [], [f"тайтл {len(title)} символов при лимите {title_limit}"]

    def value(v: str) -> list:
        return [{"value": v, "marketplace_id": mp_id, "language_tag": lang}]

    patches = [{"op": "replace", "path": "/attributes/item_name",
                "value": value(title)}]
    hl = str(highlights or "").strip()
    if hl:
        if len(hl) > hl_limit:
            skipped.append(
                f"Item Highlights {len(hl)} символов при лимите {hl_limit}")
        else:
            patches.append({"op": "replace",
                            "path": "/attributes/title_differentiation",
                            "value": value(hl)})
    return patches, skipped


def push_title(sku: str, marketplace: str, product_type: str,
               title: str, highlights: str, mp_id: str, lang: str,
               title_limit: int, hl_limit: int,
               timeout: int = 60) -> dict:
    """Один PATCH по одному товару. Возвращает разбор ответа Amazon.

    Никогда не зовётся напрямую из виджета: страница обязана сначала
    получить подтверждение человека.
    """
    out = {"ok": False, "status": "", "submission_id": "", "issues": [],
           "error": "", "skipped": [], "sent_highlights": False}
    patches, skipped = build_patches(title, highlights, mp_id, lang,
                                     title_limit, hl_limit)
    out["skipped"] = skipped
    if not patches:
        out["error"] = "; ".join(skipped) or "нечего отправлять"
        return out
    out["sent_highlights"] = len(patches) > 1

    host = host_for(marketplace)
    if not host:
        out["error"] = f"неизвестный регион для маркетплейса {marketplace}"
        return out
    token, err = access_token()
    if not token:
        out["error"] = err or "нет токена"
        return out

    url = host + LISTINGS_PATH.format(
        seller=str(cfg("SP_API_SELLER_ID") or "").strip(), sku=sku)
    try:
        r = requests.patch(
            url,
            params={"marketplaceIds": mp_id, "issueLocale": "en_US"},
            headers={"x-amz-access-token": token,
                     "content-type": "application/json"},
            data=json.dumps({"productType": product_type, "patches": patches},
                            ensure_ascii=False).encode("utf-8"),
            timeout=timeout)
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        return out

    try:
        body = r.json()
    except Exception:
        body = {}
    out["status"] = str(body.get("status") or f"HTTP {r.status_code}")
    out["submission_id"] = str(body.get("submissionId") or "")
    out["issues"] = body.get("issues") or []
    if r.status_code >= 400:
        out["error"] = f"HTTP {r.status_code}: {r.text[:400]}"
        return out
    # ACCEPTED — заявка принята; отказ приходит как INVALID со списком issues
    out["ok"] = out["status"].upper() == "ACCEPTED"
    if not out["ok"] and not out["error"]:
        out["error"] = issues_text(out["issues"]) or out["status"]
    return out


def issues_text(issues: list) -> str:
    """Причины от Amazon одной строкой — их и показываем человеку."""
    parts = []
    for it in issues or []:
        if not isinstance(it, dict):
            continue
        code = str(it.get("code") or "")
        msg = str(it.get("message") or "")
        sev = str(it.get("severity") or "")
        parts.append(" ".join(x for x in (sev, code, msg) if x).strip())
    return " · ".join(p for p in parts if p)


# ---------------------------------------------------------------- журнал

def log_push(asin: str, sku: str, marketplace: str, before: str, after: str,
             highlights: str, res: dict) -> str | None:
    """Запись в listing_push_log. Пишется И при успехе, И при отказе:
    отправка в чужой каталог без следа — то, чего быть не должно."""
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO listing_push_log
                    (asin, sku, marketplace, before_text, after_text,
                     after_extra, submission_id, status, ok, issues, error)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (asin, sku, marketplace, before, after,
                 highlights if res.get("sent_highlights") else None,
                 res.get("submission_id") or None,
                 res.get("status") or "", bool(res.get("ok")),
                 issues_text(res.get("issues")) or None,
                 res.get("error") or None))
        conn.close()
        return None
    except Exception as e:
        return f"{type(e).__name__}: {e}"


@st.cache_data(ttl=60, show_spinner=False)
def load_pushes() -> dict:
    """(asin, marketplace) -> последняя УСПЕШНАЯ отправка. Нужна защите
    от повтора: человек должен видеть, что уже отправлял и когда."""
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT DISTINCT ON (asin, marketplace)
                   asin, marketplace, sku, after_text, pushed_at,
                   submission_id
            FROM listing_push_log
            WHERE ok IS TRUE
            ORDER BY asin, marketplace, pushed_at DESC
            """, conn)
        conn.close()
    except Exception:
        return {}
    return {(r["asin"], r["marketplace"]): r.to_dict()
            for _, r in df.iterrows()}
