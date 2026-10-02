# -*- coding: utf-8 -*-
"""auth.py — вход через Google и права по ролям в Listing Suite.

Устроено как в Кабинете, и намеренно теми же словами: одно место, где решается «кто
это и что ему можно», проверка вызывается **в обработчике действия**, а не только при
отрисовке, а список страниц и список прав — один и тот же список.

Три отличия от Кабинета, и каждое — решение, а не случайность.

**Люди живут в базе Кабинета** (`services/kdb.py`): один список на два продукта.
У человека две роли в двух колонках — `role` для Кабинета, `ls_role` для Listing
Suite. Пустая `ls_role` означает «доступа сюда нет» и это НЕ «Просмотр».

**Listing Suite никого не заводит.** В Кабинете первый вход с рабочей почты создаёт
карточку с ролью «Просмотр»; здесь — нет. Открытие второго продукта не должно молча
давать доступ к первому, а карточка в `app_users` — это и доступ в Кабинет тоже.
Поэтому незнакомая почта получает отказ, администраторы — сообщение в Telegram, а
роль назначает человек в «Кабинет → Доступ».

**Внешний заслон здесь уже есть.** Приложение на Streamlit Cloud закрыто авторизацией
самого Cloud, и запрос постороннего не доходит до кода вовсе. Значит вход через Google
добавляет не защиту от посторонних, а РОЛИ: кто правит, кто утверждает, кто
отправляет в Amazon. Ожидать от него второго замка не надо.

Режим входа живёт в базе (`reorder_params.ls_auth_enabled`), отдельно от кабинетного:
общий на два продукта означал бы, что авария в одном гасит кнопки в другом.

    2 — раскатка: входа нет, кнопки у всех, как было до этой работы;
    1 — вход обязателен, роли работают;
    0 — авария: входа нет, у всех «Просмотр».
"""
from __future__ import annotations

import streamlit as st

from i18n import t
from services.kdb import get_conn

PRODUCT = "ls"            # этим помечаются записи журналов и тестовые токены

MODE_OFF = 0
MODE_ON = 1
MODE_ROLLOUT = 2

DOMAIN = "dniprom.com"

VIEWER = "viewer"
CONTENT_MANAGER = "content_manager"
APPROVER = "approver"
ADMIN = "admin"
ROLES = [VIEWER, CONTENT_MANAGER, APPROVER, ADMIN]

ANON = "listing-suite"

# Страницы одним списком: ключ, файл, подпись, значок, раздел сайдбара. Объявление
# живёт ЗДЕСЬ, а не в app.py, потому что видимость страницы — такое же право, как
# любое другое, и список страниц обязан совпадать со списком прав.
PAGES = [
    ("guide",       "pages/guide.py",        "nav.guide",       ":material/help:",         "work"),
    ("dashboard",   "pages/dashboard.py",    "nav.dashboard",   ":material/stethoscope:",  "work"),
    ("catalog",     "pages/catalog.py",      "nav.catalog",     ":material/table_rows:",   "work"),
    ("synthesis",   "pages/synthesis.py",    "nav.synthesis",   ":material/content_cut:",  "work"),
    ("photo",       "pages/photo.py",        "nav.photo",       ":material/photo_camera:", "work"),
    ("content",     "pages/content.py",      "nav.content",     ":material/translate:",    "work"),
    ("matrix",      "pages/matrix_setup.py", "nav.matrix",      ":material/account_tree:", "settings"),
    ("methodology", "pages/methodology.py",  "nav.methodology", ":material/menu_book:",    "settings"),
    ("settings",    "pages/settings.py",     "nav.settings",    ":material/settings:",     "settings"),
]

PAGE_ACTIONS = ["ls.page." + ключ for ключ, *_ in PAGES]

# Матрица прав по умолчанию — ТА ЖЕ, что в SQL-файле `sql/ls_login_2026-10-02.sql`
# репозитория Кабинета. Здесь она нужна на случай, когда таблица не прочиталась:
# код остаётся тем, что было, пока в базе не сказано иное.
#
# Почему именно так: `ls.amazon.push` меняет живой листинг на Amazon, поэтому
# начинается с утверждающего; `ls.method.edit` (версия навыка, пороги) меняет ВСЁ,
# что сгенерится потом; `ls.settings.edit` (ключи, шаблоны, расписание сбора) —
# только администратор, там и деньги, и доступы.
_MATRIX = {
    "ls.content.edit":  {CONTENT_MANAGER, APPROVER, ADMIN},
    "ls.amazon.push":   {APPROVER, ADMIN},
    "ls.method.edit":   {APPROVER, ADMIN},
    "ls.settings.edit": {ADMIN},
}
for _ключ, *_ in PAGES:
    _MATRIX["ls.page." + _ключ] = set(ROLES)


class User:
    def __init__(self, email="", name="", role=VIEWER, logged_in=False,
                 known=False, is_qa=False):
        self.email = email
        self.name = name or email
        self.role = role
        self.logged_in = logged_in
        self.known = known          # есть строка в app_users с непустой ls_role
        self.is_qa = is_qa

    @property
    def actor(self) -> str:
        return self.email or ANON

    @property
    def is_admin(self) -> bool:
        return self.role == ADMIN


# ---------- чтение настроек и людей ----------
@st.cache_data(ttl=30)
def mode() -> int:
    """Режим входа из базы. Кеш короткий: аварийный переключатель обязан срабатывать
    быстро. Нет строки или база недоступна — ведём себя как на раскатке: нехватка
    настройки не должна внезапно отбирать у людей кнопки.

    Но «раскатка по настройке» и «раскатка потому что не прочитали» — разные вещи, и
    вторую видно по `прочитан()`: причина лежит в `services.kdb`, уходит в лог
    приложения и подписывается в шапке. Раньше она терялась целиком, и включённый
    режим `1` снаружи выглядел ровно как невключённый."""
    try:
        conn = get_conn()
    except Exception:
        return MODE_ROLLOUT      # причину уже запомнил kdb
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT value FROM kabinet_data.reorder_params
                            WHERE key = 'ls_auth_enabled'""")
            row = cur.fetchone()
        if row is None:
            # Строки нет — это настройка, а не поломка: так и скажем отдельным словом,
            # иначе «нет строки» и «нет связи» снова станут одним состоянием.
            _ЧТЕНИЕ["итог"] = "нет строки ls_auth_enabled"
            return MODE_ROLLOUT
        _ЧТЕНИЕ["итог"] = ""
        return int(row[0])
    except Exception as e:
        _ЧТЕНИЕ["итог"] = f"{type(e).__name__}: {str(e).splitlines()[0][:200]}"
        print(f"[kabinet_db] режим не прочитался — {_ЧТЕНИЕ['итог']}", flush=True)
        return MODE_ROLLOUT
    finally:
        conn.close()


# Итог последнего чтения режима: пусто — прочитали, иначе причина словом.
_ЧТЕНИЕ = {"итог": ""}


def прочитан() -> tuple[bool, str]:
    """(прочитался ли режим, причина если нет). Причина берётся из двух мест:
    своей — чтение строки — и чужой — само подключение."""
    from services import kdb
    беда = _ЧТЕНИЕ["итог"] or kdb.последняя_беда()
    if not беда and not kdb.configured():
        беда = "нет секции [kabinet_db] в секретах"
    return (not беда), беда


@st.cache_data(ttl=60)
def _matrix():
    """Матрица прав из базы, только строки `ls.*`. None — «читать нечего, берём ту,
    что в коде».

    Пустая таблица и нечитаемая трактуются одинаково — не потому что безопаснее, а
    потому что предсказуемо. Действие, которого в таблице нет, а в коде есть,
    запрещено всем: новая кнопка не должна заработать раньше, чем кто-то решил, кому
    она доступна."""
    try:
        conn = get_conn()
    except Exception:
        return None
    try:
        with conn.cursor() as cur:
            # параметром, а не литералом: без аргументов psycopg2 строку не
            # разбирает, и «%%» уехало бы в базу как есть, ничего не найдя
            cur.execute("""SELECT action, role FROM kabinet_data.app_permissions
                            WHERE allowed AND action LIKE %s""", ("ls.%",))
            rows = cur.fetchall()
    except Exception:
        return None
    finally:
        conn.close()
    if not rows:
        return None
    out = {}
    for action, role in rows:
        out.setdefault(action, set()).add(role)
    return out


@st.cache_data(ttl=60)
def _load_user(email: str):
    """Строка человека. None — строки нет вовсе. `ls_role` пустая — строка есть, а
    доступа в Listing Suite нет, и это разные случаи: о первом сообщаем
    администраторам, второй они уже видят в «Доступе»."""
    try:
        conn = get_conn()
    except Exception:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ls_role, is_active, access_until,
                       access_until IS NOT NULL AND access_until < current_date AS expired
                  FROM kabinet_data.app_users WHERE email = %s
            """, (email,))
            row = cur.fetchone()
        if not row:
            return None
        # «истёк» считает база, а не Python: сервер живёт по UTC, и с полуночи до трёх
        # ночи по Киеву date.today() отдаёт вчерашнее число
        return {"ls_role": (row[0] or "").strip(), "is_active": bool(row[1]),
                "access_until": row[2], "expired": bool(row[3])}
    except Exception:
        return None
    finally:
        conn.close()


def _log_login(email, result, reason=""):
    try:
        conn = get_conn()
    except Exception:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO kabinet_data.app_login_log (email, result, reason, product)
                VALUES (%s, %s, %s, %s)
            """, (email or None, result, reason or None, PRODUCT))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def log_action(action, allowed, object_type=None, object_id=None, details=""):
    """След действия — и разрешённого, и отклонённого. Отклонённое писать важнее:
    попытка сделать то, на что права нет, — ровно то событие, ради которого проверка
    и стоит в обработчике."""
    u = current()
    try:
        conn = get_conn()
    except Exception:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO kabinet_data.app_action_log
                    (email, role, action, object_type, object_id, allowed, details, via, product)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (u.actor, u.role, action, object_type,
                  None if object_id is None else str(object_id), allowed,
                  details or None,
                  "system" if (not u.email or u.email == ANON) else "ui", PRODUCT))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def _touch_login(email):
    try:
        conn = get_conn()
    except Exception:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE kabinet_data.app_users
                   SET last_login_at = now(),
                       first_login_at = COALESCE(first_login_at, now())
                 WHERE email = %s
            """, (email,))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


# ---------- кто сейчас ----------
def current() -> User:
    if "_auth_user" in st.session_state:
        return st.session_state["_auth_user"]
    # Тестовый вход проверяем ПЕРВЫМ, до режима: он работает при любом, иначе
    # проверять приложение было бы нечем ровно в те дни, когда это нужнее всего.
    _qa = _qa_user_from_url()
    if _qa is not None:
        if not st.session_state.get("_qa_logged"):
            _log_login(QA_ACTOR, "ok", "тестовый вход по ссылке")
            st.session_state["_qa_logged"] = True
        st.session_state["_auth_user"] = _qa
        return _qa
    m = mode()
    if m == MODE_ROLLOUT:
        # как было: входа нет, права не ограничиваем. Роль администратора здесь —
        # не «повышение», а способ сказать «ограничений нет»
        u = User(role=ADMIN)
    elif m == MODE_OFF:
        u = User(role=VIEWER)
    else:
        u = _from_login()
    st.session_state["_auth_user"] = u
    return u


def _logged_in():
    """True / False / None, где None — «OAuth не настроен»."""
    try:
        return bool(st.user.is_logged_in)
    except Exception:
        return None


def _text(v) -> str:
    return "" if v is None else str(v)


def _from_login() -> User:
    if not _logged_in():
        return User(role=VIEWER, logged_in=False)
    email = _text(getattr(st.user, "email", "")).strip().lower()
    name = _text(getattr(st.user, "name", "")).strip()
    row = _load_user(email)
    if row is None or not row["ls_role"]:
        return User(email=email, name=name, role=VIEWER, logged_in=True, known=False)
    return User(email=email, name=name, role=row["ls_role"], logged_in=True, known=True)


QA_ACTOR = "qa-агент"


def _qa_enabled() -> bool:
    try:
        conn = get_conn()
    except Exception:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT value FROM kabinet_data.reorder_params
                            WHERE key = 'qa_access_enabled'""")
            row = cur.fetchone()
        return bool(row) and int(row[0]) == 1
    except Exception:
        # не прочиталось — считаем выключенным: тестовый вход не та вещь, которая
        # должна открываться сама при неполадке
        return False
    finally:
        conn.close()


def qa_hash(token: str) -> str:
    """Хеш токена с «перцем» из секретов: в базе лежит только хеш, и без перца
    украденный дамп можно было бы превратить в рабочую ссылку перебором."""
    import hashlib
    перец = ""
    try:
        перец = str(st.secrets["qa"]["pepper"])
    except Exception:
        перец = ""
    return hashlib.sha256((перец + "|" + token.strip()).encode()).hexdigest()


def _qa_user_from_url():
    """Пользователь по ссылке `?qa=токен`. Токен привязан к продукту: отозвать
    ссылку в одном приложении, не трогая другое, иначе было бы нельзя.

    Сверка хешей — `compare_digest`: обычное сравнение строк выходит из цикла на
    первом несовпавшем знаке, и по времени ответа токен подбирается посимвольно."""
    import hmac
    try:
        токен = st.query_params.get("qa", "")
    except Exception:
        токен = ""
    if not токен or not _qa_enabled():
        return None
    цель = qa_hash(токен)
    try:
        conn = get_conn()
    except Exception:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT id, token_hash FROM kabinet_data.qa_tokens
                            WHERE revoked_at IS NULL AND expires_at > now()
                              AND product = %s""", (PRODUCT,))
            живые = cur.fetchall()
            нашли = next((i for i, h in живые if hmac.compare_digest(h, цель)), None)
            if нашли is None:
                return None
            cur.execute("""UPDATE kabinet_data.qa_tokens
                              SET last_used_at = now(), uses = uses + 1 WHERE id = %s""",
                        (нашли,))
        conn.commit()
    except Exception:
        return None
    finally:
        conn.close()
    return User(email=QA_ACTOR, name=QA_ACTOR, role=VIEWER, logged_in=True,
                known=False, is_qa=True)


# ---------- права ----------
def can(action: str) -> bool:
    u = current()
    m = mode()
    if u.is_qa:
        # Жёстко и раньше всех прочих правил, включая раскатку: робот смотрит, и
        # только. Видимость страниц — исключение, иначе проверять ему нечего.
        return action in PAGE_ACTIONS
    if m == MODE_ROLLOUT:
        return True
    if m == MODE_OFF:
        return False
    if not u.logged_in or not u.known:
        return False
    из_базы = _matrix()
    таблица = _MATRIX if из_базы is None else из_базы
    роли = таблица.get(action)
    return bool(роли) and u.role in роли


def require(action: str, object_type=None, object_id=None) -> bool:
    """Проверка в момент действия: отказ показывается и пишется в журнал.
    Возвращает True/False, а не бросает — обработчику надо не упасть, а не сделать."""
    ok = can(action)
    log_action(action, ok, object_type, object_id,
               details="" if ok else f"режим {mode()}, роль {current().role}")
    if not ok:
        st.error(t("auth.denied"))
    return ok


class Denied(Exception):
    """Отказ, который нельзя не заметить."""


def demand(action: str, object_type=None, object_id=None):
    """Жёсткая проверка: либо можно, либо исключение."""
    if not can(action):
        log_action(action, False, object_type, object_id,
                   details=f"режим {mode()}, роль {current().role}")
        raise Denied(t("auth.denied"))
    log_action(action, True, object_type, object_id)


def actor() -> str:
    """Чем подписывать запись в журналах Listing Suite."""
    return current().actor


# ---------- экраны ----------
def _screen(page_fn, title):
    """Показать ОДНУ страницу и ничего больше.

    Без этого Streamlit, не увидев `st.navigation` (а `guard()` останавливает прогон
    раньше него), собирает навигацию сам из папки `pages/` — и невошедшему видно всё
    оглавление. Навигация из одной страницы с `position="hidden"` убирает список
    целиком: это отсутствие, а не сокрытие стилями."""
    st.navigation([st.Page(page_fn, title=title)], position="hidden").run()
    st.stop()


_LOGIN_TEXTS = {
    "ru": {
        "title": "Listing Suite",
        "only": "Только для сотрудников Dnipro-M",
        "button": "Войти через Google",
        "denied": "Доступ для {email} в Listing Suite не открыт.",
        "hint": "Роль в Listing Suite назначает администратор: Кабинет → Доступ.",
        "logout": "Выйти",
    },
    "uk": {
        "title": "Listing Suite",
        "only": "Лише для співробітників Dnipro-M",
        "button": "Увійти через Google",
        "denied": "Доступ для {email} у Listing Suite не відкрито.",
        "hint": "Роль у Listing Suite призначає адміністратор: Кабінет → Доступ.",
        "logout": "Вийти",
    },
    "en": {
        "title": "Listing Suite",
        "only": "Dnipro-M employees only",
        "button": "Sign in with Google",
        "denied": "Access to Listing Suite for {email} is not granted.",
        "hint": "An administrator assigns the Listing Suite role: Kabinet → Access.",
        "logout": "Sign out",
    },
}


def _texts() -> dict:
    """Язык экрана входа: до входа сайдбара нет, поэтому берём выбранный ранее или
    английский. По умолчанию английский — как в Кабинете."""
    lang = st.session_state.get("lang") or st.session_state.get("auth_lang") or "en"
    return _LOGIN_TEXTS.get(lang, _LOGIN_TEXTS["en"])


def _login_screen():
    texts = _texts()
    st.markdown("<div style='height:12vh'></div>", unsafe_allow_html=True)
    left, mid, right = st.columns([1, 2, 1])
    with mid:
        picked = st.segmented_control(
            " ", ["RU", "UK", "EN"],
            default={"ru": "RU", "uk": "UK", "en": "EN"}.get(
                st.session_state.get("lang", "en"), "EN"),
            key="auth_lang_pick", label_visibility="collapsed")
        # повторный клик по выбранному сегменту снимает выбор и возвращает None —
        # держим прежний язык, иначе экран останется без подписи
        код = {"RU": "ru", "UK": "uk", "EN": "en"}.get(picked or "")
        if код and код != st.session_state.get("lang"):
            st.session_state["lang"] = код
            st.rerun()
        texts = _texts()
        st.title(texts["title"])
        st.caption(texts["only"])
        if st.button(texts["button"], type="primary", width="stretch"):
            st.login()


def _denied_screen(email, no_role: bool):
    texts = _texts()
    left, mid, right = st.columns([1, 2, 1])
    with mid:
        st.markdown("<div style='height:10vh'></div>", unsafe_allow_html=True)
        st.title(texts["title"])
        st.error(texts["denied"].format(email=email))
        # «роли нет» и «доступ снят» — разные причины, и человек должен видеть, какая
        st.caption(texts["hint"] if no_role else texts["only"])
        if st.button(texts["logout"], width="stretch"):
            st.logout()


def guard():
    """Ворота. Зовётся в `app.py` раньше, чем читается хоть одна бизнес-таблица."""
    m = mode()
    _note_mode(m)
    if current().is_qa:
        return
    if m != MODE_ON:
        return
    logged = _logged_in()
    if logged is None:
        _screen(lambda: st.error(t("auth.no_oauth")), "Sign in")
        return
    if not logged:
        _screen(_login_screen, "Sign in")
        return
    email = _text(getattr(st.user, "email", "")).strip().lower()
    row = _load_user(email)
    # Домен сам по себе доступа ЗДЕСЬ не даёт: роль в Listing Suite назначают.
    # Приложение никого не заводит — карточка в app_users это ещё и доступ в Кабинет,
    # и открытие второго продукта не должно молча давать первый.
    if row is None:
        _log_login(email, "denied_domain", "нет карточки в списке людей")
        notify_unknown(email, _text(getattr(st.user, "name", "")))
        _screen(lambda: _denied_screen(email, no_role=True), "Access")
        return
    if not row["is_active"] or row.get("expired") or not row["ls_role"]:
        причина = ("срок доступа истёк" if row.get("expired")
                   else "строка отключена" if not row["is_active"]
                   else "роль в Listing Suite не назначена")
        _log_login(email, "denied_disabled", причина)
        _screen(lambda: _denied_screen(email, no_role=bool(row["is_active"])), "Access")
        return
    if not st.session_state.get("_auth_touched"):
        _touch_login(email)
        _log_login(email, "ok")
        st.session_state["_auth_touched"] = True


# ---------- Telegram ----------
def _telegram(text: str):
    """Отправка в общий канал. Токен — в скоупе `kabinet-alerts`, читаем его тем же
    принципалом, что и базу; копии в секретах нет намеренно."""
    import base64
    import requests
    from databricks.sdk import WorkspaceClient
    from services.kdb import _sec
    d = _sec("databricks")
    w = WorkspaceClient(host=d["host"], client_id=d["client_id"],
                        client_secret=d["client_secret"])
    token = base64.b64decode(
        w.secrets.get_secret(scope="kabinet-alerts", key="telegram-bot-token").value).decode()
    chat = base64.b64decode(
        w.secrets.get_secret(scope="kabinet-alerts", key="telegram-chat-id").value).decode()
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                  json={"chat_id": chat, "text": text, "parse_mode": "HTML"}, timeout=10)


def notify_unknown(email, name):
    """Telegram администраторам о том, кого не пустили.

    Неудачу кладём в журнал, а не глотаем: канал не должен молчать только потому, что
    грант на скоуп забыли выдать. Шлём ОДИН раз за сессию — отказ повторяется на
    каждом прогоне страницы, а событие тут одно."""
    if st.session_state.get("_notified_unknown"):
        return
    st.session_state["_notified_unknown"] = True
    try:
        _telegram(f"🔒 Listing Suite: не пустили {name or ''} &lt;{email}&gt;\n"
                  f"Карточки в списке людей нет. Завести и назначить роль — "
                  f"«Кабинет → Доступ».")
        log_action("notify_unknown", True, "user", email, "отправлено приложением")
    except Exception as e:
        log_action("notify_unknown", False, "user", email,
                   f"приложение не отправило: {type(e).__name__}: {str(e)[:120]}")


@st.cache_data(ttl=60)
def _journaled_mode():
    """Режим, записанный в журнале последним. None — записи ещё нет.

    Порядок по `ts DESC, id DESC`, а не по одному `ts`: `now()` в Postgres — время
    НАЧАЛА транзакции, у строк одной транзакции оно совпадает до микросекунды."""
    try:
        conn = get_conn()
    except Exception:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT details FROM kabinet_data.app_action_log
                            WHERE action = 'auth_mode' AND product = %s
                            ORDER BY ts DESC, id DESC LIMIT 1""", (PRODUCT,))
            row = cur.fetchone()
        if not row or not row[0]:
            return None
        import re
        m = re.search(r"режим (\d+)", row[0])
        return int(m.group(1)) if m else None
    except Exception:
        return None
    finally:
        conn.close()


def _note_mode(m: int):
    """Смену режима замечает приложение при первом же открытии страницы: флаг правят
    ПРЯМО В БАЗЕ, и перехватить `UPDATE` нельзя. Запись одна на смену состояния."""
    last = _journaled_mode()
    if last == m:
        return
    try:
        conn = get_conn()
    except Exception:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO kabinet_data.app_action_log
                               (email, role, action, allowed, details, via, product)
                           VALUES (%s, NULL, 'auth_mode', true, %s, 'system', %s)""",
                        (ANON,
                         f"режим {m}" + (f", было {last}" if last is not None
                                         else ", первая запись"),
                         PRODUCT))
        conn.commit()
    except Exception:
        return
    finally:
        conn.close()
    _journaled_mode.clear()
    if last is None:
        return   # первая запись — это не «изменение», сообщать не о чем
    words = {MODE_ROLLOUT: "раскатка — входа нет, кнопки у всех",
             MODE_ON: "вход обязателен, роли работают",
             MODE_OFF: "АВАРИЯ — входа нет, у всех «Просмотр»"}
    try:
        _telegram(f"🔑 Listing Suite, режим входа изменён: {last} → {m} "
                  f"({words.get(m, '?')})")
    except Exception as e:
        log_action("auth_mode_notify", False, "mode", str(m),
                   f"приложение не отправило: {type(e).__name__}: {str(e)[:120]}")


# ---------- шапка ----------
def header():
    """Имя, роль и «Выйти» — в сайдбаре. В режимах 2 и 0 показываем не человека, а
    сам режим: иначе на раскатке в шапке стояло бы «Администратор», и это читалось бы
    как выданное право."""
    u = current()
    if u.is_qa:
        st.sidebar.caption(t("auth.qa_badge"))
        return
    m = mode()
    if m == MODE_ROLLOUT:
        ок, беда = прочитан()
        if ок:
            st.sidebar.caption(t("auth.mode_rollout"))
        else:
            # Это не раскатка, а неизвестность: режим может быть и `1`. Говорим прямо
            # и называем причину — иначе включённый вход выглядит невключённым, и
            # искать будут не там.
            st.sidebar.warning(t("auth.mode_unread"))
            st.sidebar.caption(беда)
        return
    if m == MODE_OFF:
        st.sidebar.caption(t("auth.mode_off"))
        return
    if not u.logged_in:
        return
    st.sidebar.caption(f"**{u.name}**  \n{t('auth.role.' + u.role)}")
    if st.sidebar.button(t("auth.logout"), width="stretch"):
        _log_login(u.email, "logout")
        st.logout()
