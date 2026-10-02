# ОТПЕЧАТОК ИСТОЧНИКА: 0d0735414fafec188b6be8dfd995142b2aa72b6ecf592d268366d00fea175bf0
# access_screen.py — экран «Доступ»: один на два приложения.
"""Админка доступа (ТЗ 010): люди, роли, матрица прав, тестовый вход, журналы.

**Этот файл — единственный источник, и он живёт в репозитории Кабинета.** В Listing
Suite лежит его выкладка, обязанная быть байт в байт (`scratchpad/sync_access_screen.py`
копирует и сверяет, а `tests/test_access_screen_copy.py` на той стороне падает, если
копию правили на месте). Приём в проекте уже обкатан на `nb/auth_switch.py`: источник
под версиями, выкладка скриптом, сверка побайтно.

Почему не submodule и не пакет, если «общий код» просился буквально. Streamlit Cloud
клонирует приватный репозиторий своим доступом; приватный submodule или
`pip install git+…` потребовали бы положить живой токен в репозиторий или в настройки
сборки — то есть ровно то, от чего мы месяц назад вычищали ноутбуки. Публичным пакетом
это быть не может: здесь имена наших таблиц и правила доступа. Поэтому источник один,
а копия механическая и сверяемая, а не «вторая версия, которую кто-то поправит».

Экран показывает ОБА продукта, потому что таблицы общие: один список людей с двумя
колонками ролей, две матрицы прав, два журнала, тестовый вход с выбором продукта.
Правка в любом из двух приложений сразу видна в другом — это одна и та же строка в
одной и той же базе, а не синхронизация.

Что приходит от приложения-хозяина (`render`): его модуль `auth` (проверки, журнал,
актор), его соединение с базой Кабинета, его `t()` и код продукта. Всё остальное —
здесь, включая словарь ролей обоих продуктов: вокабуляр экрана принадлежит экрану, а
не одному из приложений.

Своя проверка прав здесь обязательна и не дублирует сайдбар: пункт меню админам
показывает роутер, но на страницу можно прийти по прямой ссылке, и решает именно эта
проверка, а не отсутствие ссылки.

Удаления людей отсюда нет: доступ снимается флагом или сроком. Строка нужна журналам —
по удалённой почте потом не понять, кто и что делал.
"""
from datetime import date, datetime

import pandas as pd
import streamlit as st

# ── вокабуляр обоих продуктов ────────────────────────────────────────────────
# Наборы ролей РАЗНЫЕ, и живут они здесь, а не в `auth` одного из приложений: экран
# показывает оба продукта, значит оба набора — его дело. В базе это заперто CHECK'ом,
# который связывает префикс действия с набором ролей.
ПРОДУКТЫ = {
    "kabinet": {
        "roles": ["viewer", "country_manager", "demand_planner", "admin"],
        "default_role": "viewer",
        "mode_key": "auth_enabled",
    },
    "ls": {
        "roles": ["viewer", "content_manager", "approver", "admin"],
        "default_role": "viewer",
        "mode_key": "ls_auth_enabled",
    },
}

# Роль Кабинета, у которой обязаны быть страны. Проверка живёт на экране, потому что
# правит он общий список людей — и из Listing Suite тоже.
СТРАНОВОЙ = "country_manager"

# Пара «право × роль», которую нельзя снять: иначе в «Доступ» не войдёт никто, и
# вернуть его можно будет только запросом в базу. В базе на это стоит триггер; здесь —
# чтобы интерфейс знал, что заблокировать, и сказал словом.
ЗАПЕРТО = {"kabinet": ("admin", "admin"), "ls": ("ls.admin", "admin")}


def перец_задан() -> bool:
    """Задан ли «перец» для хеша тестового токена. Без него украденный дамп базы
    превращается в рабочую ссылку перебором, поэтому молчать об этом нельзя."""
    try:
        return bool(str(st.secrets["qa"]["pepper"]).strip())
    except Exception:
        return False


def as_text(v, пусто: str = "") -> str:
    """Значение из pandas — в текст. Ни `or`, ни `is` тут не годятся: NaN в Python
    истинен, а `pd.NA` бросает на проверке истинности. Единственная верная проверка —
    `pd.isna` (этот урок в репозитории оплачен трижды)."""
    try:
        if v is None or pd.isna(v):
            return пусто
    except (TypeError, ValueError):
        pass
    s = str(v)
    return пусто if s in ("", "nan", "None", "<NA>", "NaT") else s


def _обёртка_перевода(t, язык: str):
    """`t()` хозяина, а чего он не знает — из местного словаря.

    Кабинет свои ключи знает (они в его `i18n`), Listing Suite — нет, и заводить их
    там копией значило бы снова два источника одной фразы. `t()` на отсутствующем
    ключе возвращает сам ключ — по этому и отличаем."""
    def перевод(ключ, **kw):
        значение = t(ключ, **kw)
        if значение == ключ:
            шаблон = ТЕКСТЫ.get(язык, {}).get(ключ) or ТЕКСТЫ["ru"].get(ключ)
            if шаблон:
                try:
                    return шаблон.format(**kw) if kw else шаблон
                except (KeyError, IndexError):
                    return шаблон
        return значение
    return перевод


def render(*, product: str, auth, get_connection, t, lang: str = "ru") -> None:
    """Нарисовать экран. `product` — чей это хозяин: «kabinet» или «ls»."""
    if product not in ПРОДУКТЫ:
        raise ValueError(f"неизвестный продукт: {product}")
    t = _обёртка_перевода(t, lang)
    продукт = product
    право = ЗАПЕРТО[продукт][0]

    st.title(t("auth.admin.title"))
    # Право проверяется ЗДЕСЬ, а не только тем, что пункт меню нарисовался: на страницу
    # можно прийти по прямой ссылке.
    if not auth.can(право):
        st.error(t("auth.denied"))
        auth.log_action("admin.open", False, "page", "access")
        st.stop()
    auth.log_action("admin.open", True, "page", "access")
    st.caption(t("auth.admin.caption"))

    _m = auth.mode()
    st.info(t("auth.admin.mode", mode=t(f"auth.admin.mode_{_m}")) + "  \n"
            # подстановка названа `param`, а не `key`: `key` — имя первого
            # параметра самой `t()`, и вышло бы «t() got multiple values»
            + t("auth.admin.mode_where", param=ПРОДУКТЫ[продукт]["mode_key"]))

    def в_коде(чей: str):
        """Действия, объявленные В КОДЕ. Свои — из `auth._MATRIX` хозяина; чужие взять
        неоткуда: их код в другом репозитории, и копия списка здесь разошлась бы с
        ним. Для чужого продукта берём то, что заведено в базе, — и говорим это
        словом, чтобы «ничего не пропало» не читалось как «всё в порядке»."""
        if чей == продукт:
            return auth._MATRIX
        return sorted(set(только(load_matrix(), чей)["action"]))

    ROLES = ПРОДУКТЫ["kabinet"]["roles"]
    # В базе роль лежит английским кодом — её читают проверки прав; на экране слово.
    # При сохранении подпись переводится обратно, иначе в базу уехало бы «Просмотр»
    # и ни одна проверка её бы не узнала (тот же приём, что у типов маршрутов).
    ROLE_LABEL = {r: t(f"auth.role.{r}") for r in ROLES}
    LABEL_ROLE = {v: k for k, v in ROLE_LABEL.items()}

    # Роли Listing Suite — свой набор: продукт другой, и «Утверждающий» в Кабинете
    # ничего не значит. Подписи берутся из тех же ключей `auth.role.*`, что и кабинетные:
    # «Просмотр» и «Администратор» в обоих продуктах — это одно и то же слово.
    LS_ROLES = ПРОДУКТЫ["ls"]["roles"]
    LS_ROLE_LABEL = {r: t(f"auth.role.{r}") for r in LS_ROLES}
    LS_LABEL_ROLE = {v: k for k, v in LS_ROLE_LABEL.items()}
    # «Роли нет» — это НЕ «Просмотр»: пустая ls_role означает, что доступа в Listing
    # Suite нет вовсе. В выпадающем списке пустую строку от «не выбрано» не отличить,
    # поэтому нужен настоящий сентинел.
    LS_NONE = t("auth.admin.ls_none")

    # Раздел действия — по префиксу его кода. Отдельной колонки «страница» в журнале нет
    # и заводить её незачем: префикс и есть раздел, а два источника одной истины
    # разошлись бы в первый же день, когда кто-то добавит действие и забудет про колонку.
    SECTION_OF = {"forecast": "forecast", "dict": "dictionaries", "ads": "ads",
                  "reorder": "reorder", "incident": "incidents", "admin": "access"}
    # У Listing Suite первый токен всегда `ls` — он называет продукт, а не раздел,
    # поэтому раздел берётся вторым: `ls.amazon.push` → «Amazon».
    LS_SECTION_OF = {"content": "ls_content", "amazon": "ls_amazon",
                     "method": "ls_method", "settings": "ls_settings", "page": "ls_page"}


    def section_of(action: str) -> str:
        токены = as_text(action).split(".")
        if токены and токены[0] == "ls":
            return LS_SECTION_OF.get(токены[1] if len(токены) > 1 else "", "other")
        return SECTION_OF.get(токены[0] if токены else "", "other")


    def fmt_dt(v) -> str:
        """Дата текстом: пустая ячейка редактора рисуется словом «None» при любом типе."""
        if pd.isna(v):
            return "—"
        return pd.Timestamp(v).strftime("%d.%m.%Y %H:%M")


    def fmt_date(v) -> str:
        if pd.isna(v):
            return ""
        return pd.Timestamp(v).strftime("%d.%m.%Y")


    def parse_date(s):
        """Строка → дата. Возвращает (значение, ошибка). Пусто — это «без срока», а не ошибка."""
        s = as_text(s).strip()
        if not s:
            return None, None
        for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"):
            try:
                return datetime.strptime(s, fmt).date(), None
            except ValueError:
                continue
        return None, s


    @st.cache_data(ttl=60)
    def load_people():
        conn = get_connection()
        try:
            return pd.read_sql("""
                SELECT u.email, u.role, COALESCE(u.ls_role, '') AS ls_role,
                       u.is_active, COALESCE(u.note, '') AS note,
                       u.access_until, u.first_login_at, u.last_login_at,
                       (u.access_until IS NOT NULL AND u.access_until < current_date) AS expired,
                       COALESCE(string_agg(c.country, ', ' ORDER BY c.country), '') AS countries
                  FROM kabinet_data.app_users u
                  LEFT JOIN kabinet_data.app_user_countries c ON c.email = u.email
                 GROUP BY u.email, u.role, u.ls_role, u.is_active, u.note, u.access_until,
                          u.first_login_at, u.last_login_at
                 ORDER BY u.email
            """, conn)
        finally:
            conn.close()


    @st.cache_data(ttl=600)
    def known_countries() -> set:
        """Коды стран из справочника: проверяем ввод по нему, а не по длине строки."""
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT alpha2 FROM kabinet_data.countries")
                return {r[0].upper() for r in cur.fetchall()}
        except Exception:
            return set()
        finally:
            conn.close()


    @st.cache_data(ttl=60)
    def load_matrix() -> pd.DataFrame:
        """Вся матрица одним запросом: строки Кабинета и строки Listing Suite лежат в
        одной таблице и различаются префиксом действия. Два запроса здесь означали бы
        два кеша, которые расходятся на время своего TTL."""
        conn = get_connection()
        try:
            return pd.read_sql("""
                SELECT action, role, allowed FROM kabinet_data.app_permissions
            """, conn)
        finally:
            conn.close()


    def только(mx: pd.DataFrame, продукт: str) -> pd.DataFrame:
        """Строки одного продукта. `ls` — те, что начинаются на `ls.`, Кабинет — все
        остальные: префикс и есть признак, второй колонки для этого не нужно."""
        если_ls = mx["action"].astype(str).str.startswith("ls.")
        return mx[если_ls if продукт == "ls" else ~если_ls].reset_index(drop=True)


    @st.cache_data(ttl=60)
    def idle_threshold() -> int:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM kabinet_data.reorder_params WHERE key = 'auth_idle_days'")
                row = cur.fetchone()
            return int(row[0]) if row else 30
        except Exception:
            return 30
        finally:
            conn.close()


    # Действия, которые журнал пишет сам о себе: открытие экрана, уведомления, досылы.
    # Они не рассказывают, что человек СДЕЛАЛ, и по умолчанию прячутся — иначе настоящие
    # решения тонут в шуме. Прячутся, а не выбрасываются: переключатель рядом.
    СЛУЖЕБНЫЕ = {"admin.open", "notify_new_user", "notify_new_user_wd", "auth_mode_notify",
                 "notify_unknown"}


    def имя_объекта(тип, ид) -> str:
        """«С чем» — человеческим именем, а не кодом.

        У каждого вида объекта своё представление: право — это пара «действие и роль», а
        не строка `forecast.post/admin`; режим входа — слово, а не цифра. Там, где имя
        вывести неоткуда, оставляем как есть: выдумывать красивое имя хуже, чем показать
        то, что записано."""
        тип, ид = as_text(тип), as_text(ид)
        if not тип and not ид:
            return "—"
        if тип == "permission" and "/" in ид:
            действие, роль = ид.split("/", 1)
            return f'{t("auth.action." + действие)} — {ROLE_LABEL.get(роль, роль)}'
        if тип == "mode":
            return t(f"auth.admin.mode_{ид}") if ид in ("0", "1", "2") else ид
        if тип == "user":
            return ид or t("auth.admin.col_email")
        if тип == "page":
            return t("auth.admin.title") if ид == "access" else ид
        if тип == "qa":
            return t("auth.admin.qa")
        if тип == "log":
            return t("auth.admin.actions")
        return ид or тип


    # Технические имена писателей — словами. «kabinet-app» в колонке «Кто» не говорит
    # ничего тому, кто читает журнал, а «система» рядом с пометкой «запись кода» — это
    # ещё и масло масляное.
    СИСТЕМНЫЕ = {"система", "kabinet-app", "watchdog", "qa-агент"}


    def кто_словом(почта, откуда) -> str:
        почта = as_text(почта, "—")
        if почта in СИСТЕМНЫЕ:
            # у этих имя само и есть объяснение: пометку не добавляем
            return t(f"auth.log.who.{почта}")
        if откуда == "db":
            return f'{почта} · {t("auth.log.via_db")}'
        return почта


    def итог_словом(разрешено) -> str:
        return "✓" if bool(разрешено) else t("auth.log.denied")


    people = load_people()

    # Матрица и журнал Listing Suite — ОТДЕЛЬНЫМИ вкладками, а не фильтром внутри
    # кабинетных: роли у продуктов разные, и одна таблица с восемью колонками ролей
    # читалась бы как одна матрица на двоих, чем она не является.
    (tab_people, tab_matrix, tab_ls_matrix, tab_qa, tab_idle, tab_logins, tab_actions,
     tab_ls_actions) = st.tabs(
        [t("auth.admin.people"), t("auth.admin.matrix"), t("auth.admin.ls_matrix"),
         t("auth.admin.qa"), t("auth.admin.idle"), t("auth.admin.logins"),
         t("auth.admin.actions"), t("auth.admin.ls_actions")])

    # ─────────────────────────────── Люди ───────────────────────────────
    with tab_people:
        view = pd.DataFrame({
            "email": people["email"],
            "role": [ROLE_LABEL.get(r, r) for r in people["role"]],
            # Пустая роль в Listing Suite — это «доступа нет», а не «Просмотр», поэтому
            # у неё свой пункт списка, а не пустая ячейка: пустую от «не выбрано» в
            # st.data_editor не отличить.
            "ls_role": [LS_ROLE_LABEL.get(as_text(r), LS_NONE) if as_text(r) else LS_NONE
                        for r in people["ls_role"]],
            "countries": [as_text(c) for c in people["countries"]],
            "is_active": [bool(v) for v in people["is_active"]],
            "access_until": [fmt_date(v) for v in people["access_until"]],
            "note": [as_text(n) for n in people["note"]],
            "last": [fmt_dt(v) for v in people["last_login_at"]],
        })
        if bool(people["expired"].any()):
            st.warning(t("auth.admin.some_expired",
                         n=int(people["expired"].sum()),
                         who=", ".join(people.loc[people["expired"], "email"])))
        edited = st.data_editor(
            view, width="stretch", hide_index=True, key="people_editor",
            column_config={
                "email": st.column_config.TextColumn(t("auth.admin.col_email"), disabled=True),
                "role": st.column_config.SelectboxColumn(
                    t("auth.admin.col_role"), options=list(LABEL_ROLE.keys()), required=True),
                "ls_role": st.column_config.SelectboxColumn(
                    t("auth.admin.col_ls_role"),
                    options=[LS_NONE] + list(LS_LABEL_ROLE.keys()), required=True,
                    help=t("auth.admin.ls_role_help")),
                "countries": st.column_config.TextColumn(
                    t("auth.admin.col_countries"), help=t("auth.admin.countries_help")),
                "is_active": st.column_config.CheckboxColumn(t("auth.admin.col_active")),
                "access_until": st.column_config.TextColumn(
                    t("auth.admin.col_until"), help=t("auth.admin.until_help")),
                "note": st.column_config.TextColumn(t("auth.admin.col_note")),
                "last": st.column_config.TextColumn(t("auth.admin.col_last"), disabled=True),
            })

        if st.button(t("auth.admin.save"), type="primary", key="save_people"):
            # Право проверяется ЗДЕСЬ, в обработчике, а не только тем, что страница
            # открылась: между отрисовкой и нажатием доступ мог быть снят.
            if auth.require(право, object_type="page", object_id="access"):
                good = set(known_countries())
                errors, changes = [], []
                for i in range(len(view)):
                    email = view.at[i, "email"]
                    was = tuple(view.loc[i, ["role", "ls_role", "countries", "is_active",
                                             "access_until", "note"]])
                    now = (edited.at[i, "role"], edited.at[i, "ls_role"],
                           as_text(edited.at[i, "countries"]),
                           bool(edited.at[i, "is_active"]), as_text(edited.at[i, "access_until"]),
                           as_text(edited.at[i, "note"]))
                    if tuple(was) == now:
                        continue
                    role = LABEL_ROLE.get(now[0], ПРОДУКТЫ["kabinet"]["default_role"])
                    # «—» значит «доступа в Listing Suite нет»: в базу уезжает NULL
                    ls_role = LS_LABEL_ROLE.get(now[1])
                    codes = [c.strip().upper() for c in now[2].split(",") if c.strip()]
                    for c in codes:
                        if good and c not in good:
                            errors.append(t("auth.admin.bad_country", v=c, email=email))
                    if role == СТРАНОВОЙ and not codes:
                        errors.append(t("auth.admin.cm_no_countries", email=email))
                    until, bad = parse_date(now[4])
                    if bad:
                        errors.append(t("auth.admin.bad_date", v=bad, email=email))
                    changes.append((email, role, ls_role, codes, now[3], until, now[5]))
                if errors:
                    # одна плохая строка отменяет всё сохранение: половина применённых
                    # правок доступа хуже, чем ни одной, — потом не понять, что уже в силе
                    for e in errors:
                        st.error(e)
                elif not changes:
                    st.info(t("auth.admin.nochange"))
                else:
                    conn = get_connection()
                    try:
                        with conn.cursor() as cur:
                            for email, role, ls_role, codes, active, until, note in changes:
                                cur.execute("""
                                    UPDATE kabinet_data.app_users
                                       SET role = %s, ls_role = %s, is_active = %s,
                                           access_until = %s, note = NULLIF(%s, '')
                                     WHERE email = %s
                                """, (role, ls_role, active, until, note, email))
                                cur.execute("DELETE FROM kabinet_data.app_user_countries WHERE email = %s",
                                            (email,))
                                for c in codes:
                                    cur.execute("""
                                        INSERT INTO kabinet_data.app_user_countries (email, country)
                                        VALUES (%s, %s) ON CONFLICT DO NOTHING
                                    """, (email, c))
                        conn.commit()
                    finally:
                        conn.close()
                    for email, role, ls_role, codes, active, until, note in changes:
                        auth.log_action("admin.set_access", True, "user", email,
                                        f"роль {role}, Listing Suite {ls_role or '—'}, "
                                        f"страны {','.join(codes) or '—'}, "
                                        f"доступ {'есть' if active else 'снят'}, "
                                        f"срок {until or 'без срока'}")
                    load_people.clear()
                    auth._load_user.clear()
                    st.success(t("auth.admin.saved", n=len(changes)))
                    st.rerun()

    # ────────────────────────────── Матрица ─────────────────────────────
    # Один рисовальщик на два продукта: галочки, проверки и сохранение написаны один раз.
    # Второй экземпляр этого кода разошёлся бы с первым в первый же день — ровно так уже
    # было с навигацией, выписанной в app.py дважды.
    def рисовать_матрицу(продукт: str, роли: list, подписи: dict, в_коде_продукта) -> None:
        mx = только(load_matrix(), продукт)
        в_базе = sorted(set(mx["action"])) if not mx.empty else []
        в_коде = sorted(в_коде_продукта)
        # Действие, которого в таблице нет, запрещено всем: новая кнопка не должна начать
        # работать раньше, чем кто-то решил, кому она доступна. Молчать об этом нельзя —
        # иначе оно выглядит сломанным, а не незаполненным.
        нет_в_базе = [a for a in в_коде if a not in в_базе]
        if нет_в_базе:
            st.warning(t("auth.admin.missing_actions", n=len(нет_в_базе),
                         what=", ".join(нет_в_базе)))
        лишние = [a for a in в_базе if a not in в_коде]
        if лишние:
            st.caption(t("auth.admin.extra_actions", what=", ".join(лишние)))

        if mx.empty:
            st.warning(t("auth.admin.matrix_empty"))
        else:
            wide = mx.pivot(index="action", columns="role", values="allowed").reindex(columns=роли)
            wide = wide.fillna(False).astype(bool).reset_index()
            grid = pd.DataFrame({"action": [t(f"auth.action.{a}") for a in wide["action"]]})
            for r in роли:
                grid[r] = [bool(v) for v in wide[r]]
            edited_mx = st.data_editor(
                grid, width="stretch", hide_index=True, key=f"matrix_editor_{продукт}",
                column_config=dict(
                    {"action": st.column_config.TextColumn(t("auth.admin.col_action"), disabled=True)},
                    **{r: st.column_config.CheckboxColumn(подписи[r]) for r in роли}))
            st.caption(t("auth.admin.matrix_locked"))

            if st.button(t("auth.admin.save"), type="primary", key=f"save_matrix_{продукт}"):
                if auth.require(право, object_type="page", object_id=f"matrix:{продукт}"):
                    правки, отказ = [], []
                    for i, действие in enumerate(wide["action"]):
                        for r in роли:
                            было, стало = bool(wide.at[i, r]), bool(edited_mx.at[i, r])
                            if было == стало:
                                continue
                            if (действие, r) == ЗАПЕРТО[продукт] and not стало:
                                отказ.append(t("auth.admin.locked_pair"))
                                continue
                            правки.append((действие, r, стало))
                    for e in dict.fromkeys(отказ):
                        st.error(e)
                    if not правки and not отказ:
                        st.info(t("auth.admin.nochange"))
                    elif правки:
                        conn = get_connection()
                        try:
                            with conn.cursor() as cur:
                                for действие, r, стало in правки:
                                    cur.execute("""
                                        INSERT INTO kabinet_data.app_permissions
                                            (action, role, allowed, updated_at, updated_by)
                                        VALUES (%s, %s, %s, now(), %s)
                                        ON CONFLICT (action, role) DO UPDATE
                                           SET allowed = EXCLUDED.allowed, updated_at = now(),
                                               updated_by = EXCLUDED.updated_by
                                    """, (действие, r, стало, auth.actor()))
                            conn.commit()
                        except Exception as e:
                            conn.rollback()
                            st.error(t("auth.admin.matrix_failed", e=str(e).splitlines()[0][:200]))
                            правки = []
                        finally:
                            conn.close()
                        if правки:
                            for действие, r, стало in правки:
                                auth.log_action("admin.set_permission", True, "permission",
                                                f"{действие}/{r}",
                                                "разрешено" if стало else "запрещено")
                            load_matrix.clear()
                            auth._matrix.clear()
                            st.success(t("auth.admin.saved", n=len(правки)))
                            st.rerun()



    with tab_matrix:
        st.caption(t("auth.admin.matrix_caption"))
        рисовать_матрицу("kabinet", ROLES, ROLE_LABEL, в_коде("kabinet"))

    with tab_ls_matrix:
        st.caption(t("auth.admin.ls_matrix_caption"))
        # Список действий Listing Suite берётся ИЗ БАЗЫ, а не из кода Кабинета: его
        # засеял SQL-файл, и копия этого списка здесь разошлась бы с кодом другого
        # репозитория. Сверку «код Listing Suite против базы» делает его собственная
        # проверка — она видит обе стороны, а этот экран видит только базу.
        рисовать_матрицу("ls", LS_ROLES, LS_ROLE_LABEL, в_коде("ls"))

    # ──────────────────────── тестовый вход QA ──────────────────────────
    with tab_qa:
        st.caption(t("auth.qa.caption"))
        _вкл = False
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""SELECT value FROM kabinet_data.reorder_params
                                WHERE key = 'qa_access_enabled'""")
                _r = cur.fetchone()
                _вкл = bool(_r) and int(_r[0]) == 1
                cur.execute("""SELECT value FROM kabinet_data.reorder_params
                                WHERE key = 'qa_token_days'""")
                _r2 = cur.fetchone()
                _дней = int(_r2[0]) if _r2 else 7
            токены = pd.read_sql("""
                SELECT id, COALESCE(label, '') AS label, created_at, created_by,
                       expires_at, revoked_at, last_used_at, uses,
                       COALESCE(product, 'kabinet') AS product
                  FROM kabinet_data.qa_tokens ORDER BY id DESC LIMIT 50
            """, conn)
        finally:
            conn.close()

        # Состояние выключателя — первым и словом: «ссылка не работает» и «токен просрочен»
        # это разные причины, и человек должен видеть, которая из них
        (st.success if _вкл else st.warning)(
            t("auth.qa.on") if _вкл else t("auth.qa.off"))
        if not перец_задан():
            # Молча работать без «перца» нельзя: защита ослаблена, и об этом надо сказать
            st.info(t("auth.qa.no_pepper"))

        живых = 0
        if not токены.empty:
            живых = int(sum(1 for r in токены.itertuples()
                            if pd.isna(r.revoked_at) and pd.Timestamp(r.expires_at) > pd.Timestamp.now(tz="UTC")))
        # Токен принадлежит ПРОДУКТУ: ссылка в Кабинет не должна открывать Listing Suite,
        # и отозвать её надо уметь по одному продукту, а не по обоим сразу.
        c0, c1, c2 = st.columns([1.2, 1, 2])
        _продукты = {"kabinet": t("auth.qa.product_kabinet"), "ls": t("auth.qa.product_ls")}
        _продукт = c0.selectbox(t("auth.qa.product"), list(_продукты),
                                format_func=lambda k: _продукты[k], key="qa_product")
        if c1.button(t("auth.qa.new"), type="primary", key="qa_new"):
            if auth.require(право, object_type="qa", object_id="token"):
                import secrets as _secrets
                новый = _secrets.token_urlsafe(32)
                conn = get_connection()
                try:
                    with conn.cursor() as cur:
                        # прежние гасим — но только по ЭТОМУ продукту: гасить чужую
                        # ссылку заодно значило бы прервать чужую проверку
                        cur.execute("""UPDATE kabinet_data.qa_tokens SET revoked_at = now()
                                        WHERE revoked_at IS NULL AND product = %s""",
                                    (_продукт,))
                        cur.execute("""INSERT INTO kabinet_data.qa_tokens
                                           (token_hash, label, created_by, expires_at, product)
                                       VALUES (%s, %s, %s, now() + make_interval(days => %s), %s)""",
                                    (auth.qa_hash(новый), "QA", auth.actor(), _дней, _продукт))
                    conn.commit()
                finally:
                    conn.close()
                auth.log_action("qa.new_token", True, "qa", "token",
                                f"срок {_дней} дн., продукт {_продукты[_продукт]}")
                # Показываем ОДИН раз: открытый токен не хранится даже у нас
                st.session_state["qa_fresh"] = новый
                st.rerun()
        c2.caption(t("auth.qa.live", n=живых))

        _свежий = st.session_state.pop("qa_fresh", None)
        if _свежий:
            st.success(t("auth.qa.once"))
            st.code(f"?qa={_свежий}", language="text")

        if токены.empty:
            st.caption(t("auth.qa.none"))
        else:
            показ = pd.DataFrame({
                "продукт": [_продукты.get(as_text(v), as_text(v)) for v in токены["product"]],
                "выдан": [fmt_dt(v) for v in токены["created_at"]],
                "кем": [as_text(v, "—") for v in токены["created_by"]],
                "до": [fmt_dt(v) for v in токены["expires_at"]],
                "состояние": [
                    t("auth.qa.st_revoked") if not pd.isna(r.revoked_at)
                    else (t("auth.qa.st_expired")
                          if pd.Timestamp(r.expires_at) <= pd.Timestamp.now(tz="UTC")
                          else t("auth.qa.st_live"))
                    for r in токены.itertuples()],
                "заходов": [str(int(v)) for v in токены["uses"]],
                "последний": [fmt_dt(v) for v in токены["last_used_at"]],
            })
            st.dataframe(показ, width="stretch", hide_index=True)
            if живых and st.button(t("auth.qa.revoke"), key="qa_revoke"):
                if auth.require(право, object_type="qa", object_id="revoke"):
                    conn = get_connection()
                    try:
                        with conn.cursor() as cur:
                            # гасим все живые по обоим продуктам: кнопка называется
                            # «погасить все», и выборочность тут была бы ловушкой
                            cur.execute("""UPDATE kabinet_data.qa_tokens SET revoked_at = now()
                                            WHERE revoked_at IS NULL""")
                        conn.commit()
                    finally:
                        conn.close()
                    auth.log_action("qa.revoke", True, "qa", "token", "все живые токены погашены")
                    st.success(t("auth.qa.revoked"))
                    st.rerun()
        st.caption(t("auth.qa.note"))

    # ───────────────────────── Давно не заходил ─────────────────────────
    with tab_idle:
        порог = idle_threshold()
        st.caption(t("auth.admin.idle_caption", n=порог))
        df = people.copy()
        дней = []
        for v in df["last_login_at"]:
            дней.append(None if pd.isna(v) else (pd.Timestamp.now(tz="UTC") - pd.Timestamp(v).tz_convert("UTC")).days)
        df["дней"] = дней
        # «Ни разу не входил» и «давно не заходил» — разные вещи, и первое не «бесконечно
        # давно»: человека могли завести вчера. Показываем обоих, но подписываем по-разному.
        молчат = df[[(d is None) or (d >= порог) for d in df["дней"]]]
        if молчат.empty:
            st.success(t("auth.admin.idle_none", n=порог))
        else:
            show = pd.DataFrame({
                "email": молчат["email"],
                "role": [ROLE_LABEL.get(r, r) for r in молчат["role"]],
                "last": [t("auth.admin.never") if pd.isna(v) else fmt_dt(v)
                         for v in молчат["last_login_at"]],
                "days": [t("auth.admin.never_short") if d is None else str(int(d))
                         for d in молчат["дней"]],
                "active": [bool(v) for v in молчат["is_active"]],
            })
            st.dataframe(show, width="stretch", hide_index=True, column_config={
                "email": st.column_config.TextColumn(t("auth.admin.col_email")),
                "role": st.column_config.TextColumn(t("auth.admin.col_role")),
                "last": st.column_config.TextColumn(t("auth.admin.col_last")),
                "days": st.column_config.TextColumn(t("auth.admin.col_days")),
                "active": st.column_config.CheckboxColumn(t("auth.admin.col_active")),
            })

    # ─────────────────────────── Журнал входов ──────────────────────────
    with tab_logins:
        conn = get_connection()
        try:
            logins = pd.read_sql("""
                SELECT ts, email, result, COALESCE(reason, '') AS reason
                  FROM kabinet_data.app_login_log ORDER BY ts DESC, id DESC LIMIT 500
            """, conn)
        finally:
            conn.close()
        if logins.empty:
            st.caption(t("auth.admin.log_empty"))
        else:
            logins["ts"] = [fmt_dt(v) for v in logins["ts"]]
            logins["result"] = [t(f"auth.admin.res.{as_text(r)}") for r in logins["result"]]
            st.dataframe(logins, width="stretch", hide_index=True, column_config={
                "ts": st.column_config.TextColumn(t("auth.admin.col_ts")),
                "email": st.column_config.TextColumn(t("auth.admin.col_email")),
                "result": st.column_config.TextColumn(t("auth.admin.col_result")),
                "reason": st.column_config.TextColumn(t("auth.admin.col_reason"), width="large"),
            })

    # ────────────────────────── Журнал действий ─────────────────────────
    # Один журнал на два продукта: фильтры, подписи и правило «кто» написаны один раз, а
    # различает записи колонка `product`. Две таблицы означали бы два набора фильтров,
    # которые однажды разойдутся.
    def рисовать_журнал(продукт: str) -> None:
        conn = get_connection()
        try:
            acts = pd.read_sql("""
                SELECT ts, email, role, action, COALESCE(object_type, '') AS object_type,
                       COALESCE(object_id, '') AS object_id,
                       allowed, COALESCE(details, '') AS details, COALESCE(via, 'ui') AS via
                  FROM kabinet_data.app_action_log ORDER BY ts DESC, id DESC LIMIT 5000
            """, conn)
        finally:
            conn.close()
        if acts.empty:
            st.caption(t("auth.admin.log_empty"))
        else:
            acts["section"] = [section_of(a) for a in acts["action"]]
            acts["ts"] = pd.to_datetime(acts["ts"])
            f1, f2, f3, f4 = st.columns([1.4, 1.2, 1.4, 1.6])
            # Пустой выбор означает «все», а не «ничего»: человек снимает галочки, чтобы
            # перестать фильтровать, а не чтобы получить пустую таблицу.
            # Ключи обязательны: тот же журнал рисуется ДВА раза, по продукту на вкладку,
            # а Streamlit выводит id виджета из типа и параметров — без ключа второй
            # набор фильтров оказался бы тем же самым, и страница упала бы целиком.
            люди = f1.multiselect(t("auth.admin.f_who"),
                                  sorted({as_text(e) for e in acts["email"] if as_text(e)}),
                                  default=[], placeholder=t("auth.admin.f_all"),
                                  key=f"acts_who_{продукт}")
            разделы = f2.multiselect(t("auth.admin.f_section"),
                                     sorted(set(acts["section"])), default=[],
                                     format_func=lambda s: t(f"auth.admin.sec.{s}"),
                                     placeholder=t("auth.admin.f_all"),
                                     key=f"acts_section_{продукт}")
            действия = f3.multiselect(t("auth.admin.f_action"), sorted(set(acts["action"])),
                                      default=[], format_func=lambda a: t(f"auth.action.{a}"),
                                      placeholder=t("auth.admin.f_all"),
                                      key=f"acts_action_{продукт}")
            период = f4.date_input(t("auth.admin.f_period"),
                                   value=(acts["ts"].min().date(), acts["ts"].max().date()),
                                   key=f"acts_period_{продукт}")
            служебных = int(acts["action"].isin(СЛУЖЕБНЫЕ).sum())
            показать_служебные = st.checkbox(
                t("auth.log.show_service", n=служебных), value=False, key=f"acts_service_{продукт}")
            сито = acts if показать_служебные else acts[~acts["action"].isin(СЛУЖЕБНЫЕ)]
            if люди:
                сито = сито[сито["email"].isin(люди)]
            if разделы:
                сито = сито[сито["section"].isin(разделы)]
            if действия:
                сито = сито[сито["action"].isin(действия)]
            if isinstance(период, (tuple, list)) and len(период) == 2:
                с, по = период
                сито = сито[(сито["ts"].dt.date >= с) & (сито["ts"].dt.date <= по)]
            st.caption(t("auth.admin.shown", n=len(сито), all=len(acts)))
            show = pd.DataFrame({
                "ts": [fmt_dt(v) for v in сито["ts"]],
                # «Кто» — почта. Прямая правка в базе помечается рядом: через экран и
                # мимо экрана — разные уровни доверия к записи
                "email": [кто_словом(e, v) for e, v in zip(сито["email"], сито["via"])],
                "section": [t(f"auth.admin.sec.{s}") for s in сито["section"]],
                "action": [t(f"auth.log.act.{a}") for a in сито["action"]],
                "object": [имя_объекта(тип, ид)
                           for тип, ид in zip(сито["object_type"], сито["object_id"])],
                "result": [итог_словом(v) for v in сито["allowed"]],
                "details": [as_text(d) for d in сито["details"]],
            })
            if show.empty:
                st.caption(t("auth.admin.filtered_empty"))
            else:
                st.dataframe(show, width="stretch", hide_index=True, column_config={
                    "ts": st.column_config.TextColumn(t("auth.admin.col_ts"), width="small"),
                    # широкая намеренно: рядом с почтой стоит пометка «напрямую в базе»,
                    # и обрезанная до «напр…» она не значит ничего
                    "email": st.column_config.TextColumn(t("auth.log.col_who"), width="large"),
                    "section": st.column_config.TextColumn(t("auth.admin.col_section"), width="small"),
                    "action": st.column_config.TextColumn(t("auth.log.col_what"), width="large"),
                    "object": st.column_config.TextColumn(t("auth.log.col_with"), width="large"),
                    # «✓» и «отказано» словом, а не галочкой: галочка в колонке «итог»
                    # читается как «отметить», а не как «получилось»
                    "result": st.column_config.TextColumn(t("auth.log.col_result"), width="small"),
                    "details": st.column_config.TextColumn(t("auth.admin.col_details"), width="medium"),
                })


    with tab_actions:
        рисовать_журнал("kabinet")

    with tab_ls_actions:
        st.caption(t("auth.admin.ls_actions_caption"))
        рисовать_журнал("ls")


# ── тексты экрана ────────────────────────────────────────────────────────────
# Собираются ИЗ `i18n` Кабинета скриптом выкладки (`scratchpad/sync_access_screen.py`),
# а не пишутся здесь руками: иначе одна и та же фраза живёт в двух местах и однажды
# разойдётся. Нужны они только чужому хозяину — свой знает их из своего словаря.
# НАЧАЛО ТЕКСТОВ (не править руками)
ТЕКСТЫ = {
    "ru": {
        "auth.action.admin": "Доступ: управление",
        "auth.action.admin.delete_user": "Доступ: удаление записи",
        "auth.action.admin.open": "Доступ: открытие экрана",
        "auth.action.admin.set_access": "Доступ: правка человека",
        "auth.action.admin.set_permission": "Доступ: правка матрицы",
        "auth.action.ads.act": "Реклама: пауза и ставки",
        "auth.action.auth_mode": "Режим входа изменён",
        "auth.action.auth_mode_notify": "Уведомление о смене режима",
        "auth.action.dict.edit": "Справочники: правка",
        "auth.action.forecast.approve": "Прогноз: утверждение",
        "auth.action.forecast.edit": "Прогноз: правка черновика",
        "auth.action.forecast.post": "Прогноз: проведение",
        "auth.action.forecast.replace": "Прогноз: замена после изменения пула",
        "auth.action.forecast.upload": "Прогноз: загрузка из файла",
        "auth.action.incident.act": "Инциденты: принять и закрыть",
        "auth.action.ls.amazon.push": "Listing Suite: отправка в Amazon",
        "auth.action.ls.content.edit": "Listing Suite: правка контента",
        "auth.action.ls.method.edit": "Listing Suite: правка методики",
        "auth.action.ls.page.catalog": "Страница «Каталог»",
        "auth.action.ls.page.content": "Страница «Контент»",
        "auth.action.ls.page.dashboard": "Страница «Диагноз»",
        "auth.action.ls.page.guide": "Страница «Как работать»",
        "auth.action.ls.page.matrix": "Страница «Матрица»",
        "auth.action.ls.page.methodology": "Страница «Методика»",
        "auth.action.ls.page.photo": "Страница «Фото и A+»",
        "auth.action.ls.page.settings": "Страница «Настройки»",
        "auth.action.ls.page.synthesis": "Страница «Синтез»",
        "auth.action.ls.settings.edit": "Listing Suite: правка настроек",
        "auth.action.notify_new_user": "Уведомление о новом человеке",
        "auth.action.notify_new_user_wd": "Уведомление дослано сторожем",
        "auth.action.page.ads": "Страница: видеть «Реклама»",
        "auth.action.page.cm": "Страница: видеть «Площадки»",
        "auth.action.page.dictionaries": "Страница: видеть «Справочники»",
        "auth.action.page.forecast": "Страница: видеть «Прогноз»",
        "auth.action.page.home": "Страница: видеть «Обзор»",
        "auth.action.page.incidents": "Страница: видеть «Инциденты»",
        "auth.action.page.money": "Страница: видеть «Деньги»",
        "auth.action.page.reorder": "Страница: видеть «Автозаказ»",
        "auth.action.page.reviews": "Страница: видеть «Отзывы»",
        "auth.action.page.stock": "Страница: видеть «Остатки»",
        "auth.action.reorder.act": "Автозаказ: заказ и переброска",
        "auth.admin.actions": "Журнал действий",
        "auth.admin.bad_country": "Не код страны: {v} (у {email}). Нужны двухбуквенные коды из справочника.",
        "auth.admin.bad_date": "Не дата: {v} (у {email}). Нужен формат ДД.ММ.ГГГГ.",
        "auth.admin.caption": "Кто входит в Кабинет, с какой ролью и по каким странам.",
        "auth.admin.cm_no_countries": "У странового менеджера {email} не назначено ни одной страны — он не сможет ничего править.",
        "auth.admin.col_action": "Действие",
        "auth.admin.col_active": "Доступ",
        "auth.admin.col_countries": "Страны",
        "auth.admin.col_days": "Дней без входа",
        "auth.admin.col_details": "Подробности",
        "auth.admin.col_email": "Почта",
        "auth.admin.col_last": "Последний вход",
        "auth.admin.col_ls_role": "Роль в Listing Suite",
        "auth.admin.col_note": "Примечание",
        "auth.admin.col_reason": "Причина",
        "auth.admin.col_result": "Итог",
        "auth.admin.col_role": "Роль",
        "auth.admin.col_section": "Раздел",
        "auth.admin.col_ts": "Когда",
        "auth.admin.col_until": "Доступ до",
        "auth.admin.countries_help": "Коды стран через запятую (ES, FR). Нужны только страновому менеджеру.",
        "auth.admin.extra_actions": "В таблице есть действия, которых нет в коде: {what}. Они ни на что не влияют.",
        "auth.admin.f_action": "Действие",
        "auth.admin.f_all": "все",
        "auth.admin.f_period": "Период",
        "auth.admin.f_section": "Раздел",
        "auth.admin.f_who": "Человек",
        "auth.admin.filtered_empty": "Под фильтры ничего не попало — это фильтры, а не пустой журнал.",
        "auth.admin.idle": "Давно не заходили",
        "auth.admin.idle_caption": "Кто не входил {n} дней и дольше. Порог — настройка auth_idle_days.",
        "auth.admin.idle_none": "Все заходили за последние {n} дней.",
        "auth.admin.locked_pair": "«Администратор × Доступ» снять нельзя — остальные изменения сохранены.",
        "auth.admin.log_empty": "Записей пока нет.",
        "auth.admin.logins": "Журнал входов",
        "auth.admin.ls_actions": "Журнал Listing Suite",
        "auth.admin.ls_actions_caption": "Что делали в Listing Suite. Записи лежат в том же журнале и различаются продуктом.",
        "auth.admin.ls_matrix": "Матрица Listing Suite",
        "auth.admin.ls_matrix_caption": "Права в Listing Suite. Роли там свои: контент-менеджер правит, утверждающий отправляет в Amazon. Список действий берётся из базы — его засевает SQL того же продукта.",
        "auth.admin.ls_none": "— нет доступа —",
        "auth.admin.ls_role_help": "Пусто — доступа в Listing Suite нет вовсе. Это не «Просмотр»: в Кабинет человек входит, во второй продукт — нет.",
        "auth.admin.matrix": "Матрица прав",
        "auth.admin.matrix_caption": "Кому что можно. Правила читаются из базы; действие, которого в таблице нет, запрещено всем.",
        "auth.admin.matrix_empty": "Таблица прав пуста — работают правила из кода.",
        "auth.admin.matrix_failed": "Не сохранилось: {e}",
        "auth.admin.matrix_locked": "«Администратор × Доступ» снять нельзя: иначе в этот экран не войдёт никто, и вернуть право можно будет только запросом в базу.",
        "auth.admin.missing_actions": "Действий в коде, которых нет в таблице: {n} ({what}). Они запрещены всем, пока не заведены.",
        "auth.admin.mode": "Режим входа: {mode}",
        "auth.admin.mode_0": "авария — входа нет, у всех «Просмотр»",
        "auth.admin.mode_1": "вход обязателен, роли работают",
        "auth.admin.mode_2": "раскатка — входа нет, кнопки у всех",
        "auth.admin.mode_where": "Меняется в базе: reorder_params.{param}. Каждое переключение уходит в Telegram.",
        "auth.admin.never": "ни разу",
        "auth.admin.never_short": "—",
        "auth.admin.nochange": "Менять нечего.",
        "auth.admin.people": "Люди",
        "auth.admin.qa": "Тестовый вход",
        "auth.admin.res.denied_disabled": "отказ: доступ закрыт",
        "auth.admin.res.denied_domain": "отказ: домен",
        "auth.admin.res.first_login": "первый вход",
        "auth.admin.res.logout": "выход",
        "auth.admin.res.ok": "вход",
        "auth.admin.save": "Сохранить",
        "auth.admin.saved": "Сохранено: {n}",
        "auth.admin.sec.access": "Доступ",
        "auth.admin.sec.ads": "Реклама",
        "auth.admin.sec.dictionaries": "Справочники",
        "auth.admin.sec.forecast": "Прогноз",
        "auth.admin.sec.incidents": "Инциденты",
        "auth.admin.sec.ls_amazon": "Amazon",
        "auth.admin.sec.ls_content": "Контент",
        "auth.admin.sec.ls_method": "Методика",
        "auth.admin.sec.ls_page": "Страницы",
        "auth.admin.sec.ls_settings": "Настройки",
        "auth.admin.sec.other": "Прочее",
        "auth.admin.sec.reorder": "Автозаказ",
        "auth.admin.shown": "Показано {n} из {all}",
        "auth.admin.some_expired": "Срок доступа истёк у {n}: {who}. Вход закрыт, запись не выключена — продлите дату или снимите её.",
        "auth.admin.title": "Доступ",
        "auth.admin.until_help": "Последний день доступа включительно, ДД.ММ.ГГГГ. Пусто — без срока.",
        "auth.denied": "Недостаточно прав для этого действия. Ничего не изменено.",
        "auth.log.act.admin": "Управлял доступом",
        "auth.log.act.admin.delete_user": "Удалял запись о человеке",
        "auth.log.act.admin.open": "Открывал экран «Доступ»",
        "auth.log.act.admin.set_access": "Менял доступ человека",
        "auth.log.act.admin.set_permission": "Менял матрицу прав",
        "auth.log.act.ads.act": "Менял рекламу: пауза или ставка",
        "auth.log.act.auth_mode": "Режим входа изменён",
        "auth.log.act.auth_mode_notify": "Уведомление о смене режима",
        "auth.log.act.auth_mode_set": "Переключал режим входа",
        "auth.log.act.dict.edit": "Правил справочник",
        "auth.log.act.forecast.approve": "Утверждал прогноз",
        "auth.log.act.forecast.edit": "Правил черновик прогноза",
        "auth.log.act.forecast.post": "Проводил прогноз",
        "auth.log.act.forecast.replace": "Заменял прогнозы после изменения пула",
        "auth.log.act.forecast.upload": "Загружал прогноз из файла",
        "auth.log.act.incident.act": "Принимал или закрывал инцидент",
        "auth.log.act.ls.amazon.push": "Отправлял листинг в Amazon",
        "auth.log.act.ls.content.edit": "Правил контент",
        "auth.log.act.ls.method.edit": "Менял методику",
        "auth.log.act.ls.settings.edit": "Менял настройки",
        "auth.log.act.notify_new_user": "Уведомление о новом человеке",
        "auth.log.act.notify_new_user_wd": "Уведомление дослано сторожем",
        "auth.log.act.notify_unknown": "Уведомление о незнакомом входе",
        "auth.log.act.page.ads": "Открывал «Реклама»",
        "auth.log.act.page.cm": "Открывал «Площадки»",
        "auth.log.act.page.dictionaries": "Открывал «Справочники»",
        "auth.log.act.page.forecast": "Открывал «Прогноз»",
        "auth.log.act.page.home": "Открывал «Обзор»",
        "auth.log.act.page.incidents": "Открывал «Инциденты»",
        "auth.log.act.page.money": "Открывал «Деньги»",
        "auth.log.act.page.reorder": "Открывал «Автозаказ»",
        "auth.log.act.page.reviews": "Открывал «Отзывы»",
        "auth.log.act.page.stock": "Открывал «Остатки»",
        "auth.log.act.qa.new_token": "Выпускал токен тестового входа",
        "auth.log.act.qa.revoke": "Гасил токены тестового входа",
        "auth.log.act.reorder.act": "Подтверждал заказ или переброску",
        "auth.log.col_result": "Итог",
        "auth.log.col_what": "Что сделал",
        "auth.log.col_who": "Кто",
        "auth.log.col_with": "С чем",
        "auth.log.denied": "отказано",
        "auth.log.show_service": "Показать служебные записи ({n})",
        "auth.log.via_db": "напрямую в базе",
        "auth.log.who.kabinet-app": "Кабинет, автоматически",
        "auth.log.who.qa-агент": "QA-агент",
        "auth.log.who.watchdog": "сторож",
        "auth.log.who.система": "система",
        "auth.qa.caption": "Ссылка для проверяющих роботов: ?qa=токен. Только просмотр, все действия запрещены жёстко — независимо от матрицы прав.",
        "auth.qa.live": "Живых токенов: {n}. Новый гасит прежние — двух живых не бывает.",
        "auth.qa.new": "Сменить токен",
        "auth.qa.no_pepper": "В секретах нет [qa] pepper. Вход работает, но защита слабее: без «перца» украденный дамп базы позволяет подобрать токен.",
        "auth.qa.none": "Токенов ещё не выдавали.",
        "auth.qa.note": "Заходы по тестовой ссылке видны в журнале входов как «qa-агент» — мы их не прячем. Срок жизни токена — настройка qa_token_days.",
        "auth.qa.off": "Тестовый вход выключен — ссылка не работает, даже если токен жив. Включается настройкой qa_access_enabled.",
        "auth.qa.on": "Тестовый вход ВКЛЮЧЁН. Ссылка с живым токеном работает.",
        "auth.qa.once": "Токен показан ОДИН раз — у нас он хранится только хешем. Скопируйте ссылку сейчас; потеряли — выпустите новый.",
        "auth.qa.product": "Продукт",
        "auth.qa.product_kabinet": "Кабинет",
        "auth.qa.product_ls": "Listing Suite",
        "auth.qa.revoke": "Погасить все токены",
        "auth.qa.revoked": "Погашено. Ссылка больше не работает.",
        "auth.qa.st_expired": "просрочен",
        "auth.qa.st_live": "живой",
        "auth.qa.st_revoked": "погашен",
        "auth.role.admin": "Администратор",
        "auth.role.approver": "Утверждающий",
        "auth.role.content_manager": "Контент-менеджер",
        "auth.role.country_manager": "Страновой менеджер",
        "auth.role.demand_planner": "Планировщик спроса",
        "auth.role.viewer": "Просмотр",
    },
    "uk": {
        "auth.action.admin": "Доступ: керування",
        "auth.action.admin.delete_user": "Доступ: видалення запису",
        "auth.action.admin.open": "Доступ: відкриття екрана",
        "auth.action.admin.set_access": "Доступ: правка людини",
        "auth.action.admin.set_permission": "Доступ: правка матриці",
        "auth.action.ads.act": "Реклама: пауза і ставки",
        "auth.action.auth_mode": "Режим входу змінено",
        "auth.action.auth_mode_notify": "Сповіщення про зміну режиму",
        "auth.action.dict.edit": "Довідники: правка",
        "auth.action.forecast.approve": "Прогноз: затвердження",
        "auth.action.forecast.edit": "Прогноз: правка чернетки",
        "auth.action.forecast.post": "Прогноз: проведення",
        "auth.action.forecast.replace": "Прогноз: заміна після зміни пулу",
        "auth.action.forecast.upload": "Прогноз: завантаження з файлу",
        "auth.action.incident.act": "Інциденти: прийняти і закрити",
        "auth.action.ls.amazon.push": "Listing Suite: надсилання в Amazon",
        "auth.action.ls.content.edit": "Listing Suite: правка контенту",
        "auth.action.ls.method.edit": "Listing Suite: правка методики",
        "auth.action.ls.page.catalog": "Сторінка «Каталог»",
        "auth.action.ls.page.content": "Сторінка «Контент»",
        "auth.action.ls.page.dashboard": "Сторінка «Діагноз»",
        "auth.action.ls.page.guide": "Сторінка «Як працювати»",
        "auth.action.ls.page.matrix": "Сторінка «Матриця»",
        "auth.action.ls.page.methodology": "Сторінка «Методика»",
        "auth.action.ls.page.photo": "Сторінка «Фото та A+»",
        "auth.action.ls.page.settings": "Сторінка «Налаштування»",
        "auth.action.ls.page.synthesis": "Сторінка «Синтез»",
        "auth.action.ls.settings.edit": "Listing Suite: правка налаштувань",
        "auth.action.notify_new_user": "Сповіщення про нову людину",
        "auth.action.notify_new_user_wd": "Сповіщення дослано сторожем",
        "auth.action.page.ads": "Сторінка: бачити «Реклама»",
        "auth.action.page.cm": "Сторінка: бачити «Майданчики»",
        "auth.action.page.dictionaries": "Сторінка: бачити «Довідники»",
        "auth.action.page.forecast": "Сторінка: бачити «Прогноз»",
        "auth.action.page.home": "Сторінка: бачити «Огляд»",
        "auth.action.page.incidents": "Сторінка: бачити «Інциденти»",
        "auth.action.page.money": "Сторінка: бачити «Гроші»",
        "auth.action.page.reorder": "Сторінка: бачити «Автозамовлення»",
        "auth.action.page.reviews": "Сторінка: бачити «Відгуки»",
        "auth.action.page.stock": "Сторінка: бачити «Залишки»",
        "auth.action.reorder.act": "Автозамовлення: замовлення і перекидання",
        "auth.admin.actions": "Журнал дій",
        "auth.admin.bad_country": "Не код країни: {v} (у {email}). Потрібні дволітерні коди з довідника.",
        "auth.admin.bad_date": "Не дата: {v} (у {email}). Потрібен формат ДД.ММ.РРРР.",
        "auth.admin.caption": "Хто входить до Кабінету, з якою роллю та за якими країнами.",
        "auth.admin.cm_no_countries": "Країновому менеджеру {email} не призначено жодної країни — він не зможе нічого правити.",
        "auth.admin.col_action": "Дія",
        "auth.admin.col_active": "Доступ",
        "auth.admin.col_countries": "Країни",
        "auth.admin.col_days": "Днів без входу",
        "auth.admin.col_details": "Подробиці",
        "auth.admin.col_email": "Пошта",
        "auth.admin.col_last": "Останній вхід",
        "auth.admin.col_ls_role": "Роль у Listing Suite",
        "auth.admin.col_note": "Примітка",
        "auth.admin.col_reason": "Причина",
        "auth.admin.col_result": "Підсумок",
        "auth.admin.col_role": "Роль",
        "auth.admin.col_section": "Розділ",
        "auth.admin.col_ts": "Коли",
        "auth.admin.col_until": "Доступ до",
        "auth.admin.countries_help": "Коди країн через кому (ES, FR). Потрібні лише країновому менеджеру.",
        "auth.admin.extra_actions": "У таблиці є дії, яких немає в коді: {what}. Вони ні на що не впливають.",
        "auth.admin.f_action": "Дія",
        "auth.admin.f_all": "усі",
        "auth.admin.f_period": "Період",
        "auth.admin.f_section": "Розділ",
        "auth.admin.f_who": "Людина",
        "auth.admin.filtered_empty": "Під фільтри нічого не потрапило — це фільтри, а не порожній журнал.",
        "auth.admin.idle": "Давно не заходили",
        "auth.admin.idle_caption": "Хто не входив {n} днів і довше. Поріг — налаштування auth_idle_days.",
        "auth.admin.idle_none": "Усі заходили за останні {n} днів.",
        "auth.admin.locked_pair": "«Адміністратор × Доступ» зняти не можна — інші зміни збережено.",
        "auth.admin.log_empty": "Записів поки немає.",
        "auth.admin.logins": "Журнал входів",
        "auth.admin.ls_actions": "Журнал Listing Suite",
        "auth.admin.ls_actions_caption": "Що робили в Listing Suite. Записи лежать у тому ж журналі й різняться продуктом.",
        "auth.admin.ls_matrix": "Матриця Listing Suite",
        "auth.admin.ls_matrix_caption": "Права в Listing Suite. Ролі там свої: контент-менеджер править, затверджувач надсилає в Amazon. Список дій береться з бази — його засіває SQL того ж продукту.",
        "auth.admin.ls_none": "— немає доступу —",
        "auth.admin.ls_role_help": "Порожньо — доступу в Listing Suite немає взагалі. Це не «Перегляд»: у Кабінет людина входить, у другий продукт — ні.",
        "auth.admin.matrix": "Матриця прав",
        "auth.admin.matrix_caption": "Кому що можна. Правила читаються з бази; дія, якої в таблиці немає, заборонена всім.",
        "auth.admin.matrix_empty": "Таблиця прав порожня — працюють правила з коду.",
        "auth.admin.matrix_failed": "Не збереглося: {e}",
        "auth.admin.matrix_locked": "«Адміністратор × Доступ» зняти не можна: інакше до цього екрана не ввійде ніхто, і повернути право можна буде лише запитом до бази.",
        "auth.admin.missing_actions": "Дій у коді, яких немає в таблиці: {n} ({what}). Вони заборонені всім, доки не заведені.",
        "auth.admin.mode": "Режим входу: {mode}",
        "auth.admin.mode_0": "аварія — входу немає, в усіх «Перегляд»",
        "auth.admin.mode_1": "вхід обов’язковий, ролі працюють",
        "auth.admin.mode_2": "розкатка — входу немає, кнопки в усіх",
        "auth.admin.mode_where": "Змінюється в базі: reorder_params.{param}. Кожне перемикання йде в Telegram.",
        "auth.admin.never": "жодного разу",
        "auth.admin.never_short": "—",
        "auth.admin.nochange": "Змінювати нічого.",
        "auth.admin.people": "Люди",
        "auth.admin.qa": "Тестовий вхід",
        "auth.admin.res.denied_disabled": "відмова: доступ закрито",
        "auth.admin.res.denied_domain": "відмова: домен",
        "auth.admin.res.first_login": "перший вхід",
        "auth.admin.res.logout": "вихід",
        "auth.admin.res.ok": "вхід",
        "auth.admin.save": "Зберегти",
        "auth.admin.saved": "Збережено: {n}",
        "auth.admin.sec.access": "Доступ",
        "auth.admin.sec.ads": "Реклама",
        "auth.admin.sec.dictionaries": "Довідники",
        "auth.admin.sec.forecast": "Прогноз",
        "auth.admin.sec.incidents": "Інциденти",
        "auth.admin.sec.ls_amazon": "Amazon",
        "auth.admin.sec.ls_content": "Контент",
        "auth.admin.sec.ls_method": "Методика",
        "auth.admin.sec.ls_page": "Сторінки",
        "auth.admin.sec.ls_settings": "Налаштування",
        "auth.admin.sec.other": "Інше",
        "auth.admin.sec.reorder": "Автозамовлення",
        "auth.admin.shown": "Показано {n} з {all}",
        "auth.admin.some_expired": "Термін доступу минув у {n}: {who}. Вхід закрито, запис не вимкнено — подовжте дату або зніміть її.",
        "auth.admin.title": "Доступ",
        "auth.admin.until_help": "Останній день доступу включно, ДД.ММ.РРРР. Порожньо — без терміну.",
        "auth.denied": "Недостатньо прав для цієї дії. Нічого не змінено.",
        "auth.log.act.admin": "Керував доступом",
        "auth.log.act.admin.delete_user": "Видаляв запис про людину",
        "auth.log.act.admin.open": "Відкривав екран «Доступ»",
        "auth.log.act.admin.set_access": "Змінював доступ людини",
        "auth.log.act.admin.set_permission": "Змінював матрицю прав",
        "auth.log.act.ads.act": "Змінював рекламу: пауза або ставка",
        "auth.log.act.auth_mode": "Режим входу змінено",
        "auth.log.act.auth_mode_notify": "Сповіщення про зміну режиму",
        "auth.log.act.auth_mode_set": "Перемикав режим входу",
        "auth.log.act.dict.edit": "Правив довідник",
        "auth.log.act.forecast.approve": "Затверджував прогноз",
        "auth.log.act.forecast.edit": "Правив чернетку прогнозу",
        "auth.log.act.forecast.post": "Проводив прогноз",
        "auth.log.act.forecast.replace": "Замінював прогнози після зміни пулу",
        "auth.log.act.forecast.upload": "Завантажував прогноз із файлу",
        "auth.log.act.incident.act": "Приймав або закривав інцидент",
        "auth.log.act.ls.amazon.push": "Надсилав лістинг в Amazon",
        "auth.log.act.ls.content.edit": "Правив контент",
        "auth.log.act.ls.method.edit": "Змінював методику",
        "auth.log.act.ls.settings.edit": "Змінював налаштування",
        "auth.log.act.notify_new_user": "Сповіщення про нову людину",
        "auth.log.act.notify_new_user_wd": "Сповіщення дослано сторожем",
        "auth.log.act.notify_unknown": "Сповіщення про незнайомий вхід",
        "auth.log.act.page.ads": "Відкривав «Реклама»",
        "auth.log.act.page.cm": "Відкривав «Площадки»",
        "auth.log.act.page.dictionaries": "Відкривав «Справочники»",
        "auth.log.act.page.forecast": "Відкривав «Прогноз»",
        "auth.log.act.page.home": "Відкривав «Обзор»",
        "auth.log.act.page.incidents": "Відкривав «Инциденты»",
        "auth.log.act.page.money": "Відкривав «Деньги»",
        "auth.log.act.page.reorder": "Відкривав «Автозаказ»",
        "auth.log.act.page.reviews": "Відкривав «Отзывы»",
        "auth.log.act.page.stock": "Відкривав «Остатки»",
        "auth.log.act.qa.new_token": "Випускав токен тестового входу",
        "auth.log.act.qa.revoke": "Гасив токени тестового входу",
        "auth.log.act.reorder.act": "Підтверджував замовлення або перекидання",
        "auth.log.col_result": "Підсумок",
        "auth.log.col_what": "Що зробив",
        "auth.log.col_who": "Хто",
        "auth.log.col_with": "З чим",
        "auth.log.denied": "відмовлено",
        "auth.log.show_service": "Показати службові записи ({n})",
        "auth.log.via_db": "напряму в базі",
        "auth.log.who.kabinet-app": "Кабінет, автоматично",
        "auth.log.who.qa-агент": "QA-агент",
        "auth.log.who.watchdog": "сторож",
        "auth.log.who.система": "система",
        "auth.qa.caption": "Посилання для перевіряльних роботів: ?qa=токен. Лише перегляд, усі дії заборонені жорстко — незалежно від матриці прав.",
        "auth.qa.live": "Живих токенів: {n}. Новий гасить попередні — двох живих не буває.",
        "auth.qa.new": "Змінити токен",
        "auth.qa.no_pepper": "У секретах немає [qa] pepper. Вхід працює, але захист слабший: без «перцю» викрадений дамп бази дозволяє підібрати токен.",
        "auth.qa.none": "Токенів ще не видавали.",
        "auth.qa.note": "Заходи тестовим посиланням видно в журналі входів як «qa-агент» — ми їх не ховаємо. Термін життя токена — налаштування qa_token_days.",
        "auth.qa.off": "Тестовий вхід вимкнено — посилання не працює, навіть якщо токен живий. Вмикається налаштуванням qa_access_enabled.",
        "auth.qa.on": "Тестовий вхід УВІМКНЕНО. Посилання з живим токеном працює.",
        "auth.qa.once": "Токен показано ОДИН раз — у нас він зберігається лише хешем. Скопіюйте посилання зараз; загубили — випустіть новий.",
        "auth.qa.product": "Продукт",
        "auth.qa.product_kabinet": "Кабінет",
        "auth.qa.product_ls": "Listing Suite",
        "auth.qa.revoke": "Погасити всі токени",
        "auth.qa.revoked": "Погашено. Посилання більше не працює.",
        "auth.qa.st_expired": "прострочений",
        "auth.qa.st_live": "живий",
        "auth.qa.st_revoked": "погашений",
        "auth.role.admin": "Адміністратор",
        "auth.role.approver": "Затверджувач",
        "auth.role.content_manager": "Контент-менеджер",
        "auth.role.country_manager": "Країновий менеджер",
        "auth.role.demand_planner": "Планувальник попиту",
        "auth.role.viewer": "Перегляд",
    },
    "en": {
        "auth.action.admin": "Access: management",
        "auth.action.admin.delete_user": "Access: delete record",
        "auth.action.admin.open": "Access: open screen",
        "auth.action.admin.set_access": "Access: edit person",
        "auth.action.admin.set_permission": "Access: edit permissions",
        "auth.action.ads.act": "Ads: pause and bids",
        "auth.action.auth_mode": "Sign-in mode changed",
        "auth.action.auth_mode_notify": "Mode change notification",
        "auth.action.dict.edit": "Directories: edit",
        "auth.action.forecast.approve": "Forecast: approve",
        "auth.action.forecast.edit": "Forecast: edit draft",
        "auth.action.forecast.post": "Forecast: post",
        "auth.action.forecast.replace": "Forecast: replace after pool change",
        "auth.action.forecast.upload": "Forecast: upload from file",
        "auth.action.incident.act": "Incidents: acknowledge and resolve",
        "auth.action.ls.amazon.push": "Listing Suite: push to Amazon",
        "auth.action.ls.content.edit": "Listing Suite: edit content",
        "auth.action.ls.method.edit": "Listing Suite: edit methodology",
        "auth.action.ls.page.catalog": "Page “Catalog”",
        "auth.action.ls.page.content": "Page “Content”",
        "auth.action.ls.page.dashboard": "Page “Diagnosis”",
        "auth.action.ls.page.guide": "Page “Guide”",
        "auth.action.ls.page.matrix": "Page “Matrix”",
        "auth.action.ls.page.methodology": "Page “Methodology”",
        "auth.action.ls.page.photo": "Page “Photos & A+”",
        "auth.action.ls.page.settings": "Page “Settings”",
        "auth.action.ls.page.synthesis": "Page “Synthesis”",
        "auth.action.ls.settings.edit": "Listing Suite: edit settings",
        "auth.action.notify_new_user": "New person notification",
        "auth.action.notify_new_user_wd": "Notification sent by watchdog",
        "auth.action.page.ads": "Page: see Ads",
        "auth.action.page.cm": "Page: see Channels",
        "auth.action.page.dictionaries": "Page: see Directories",
        "auth.action.page.forecast": "Page: see Forecast",
        "auth.action.page.home": "Page: see Overview",
        "auth.action.page.incidents": "Page: see Incidents",
        "auth.action.page.money": "Page: see Money",
        "auth.action.page.reorder": "Page: see Reorder",
        "auth.action.page.reviews": "Page: see Reviews",
        "auth.action.page.stock": "Page: see Stock",
        "auth.action.reorder.act": "Reorder: order and transfer",
        "auth.admin.actions": "Action log",
        "auth.admin.bad_country": "Not a country code: {v} (for {email}). Two-letter codes from the directory.",
        "auth.admin.bad_date": "Not a date: {v} (for {email}). Use DD.MM.YYYY.",
        "auth.admin.caption": "Who signs in, with which role and for which countries.",
        "auth.admin.cm_no_countries": "Country manager {email} has no countries assigned and will not be able to edit anything.",
        "auth.admin.col_action": "Action",
        "auth.admin.col_active": "Access",
        "auth.admin.col_countries": "Countries",
        "auth.admin.col_days": "Days idle",
        "auth.admin.col_details": "Details",
        "auth.admin.col_email": "Email",
        "auth.admin.col_last": "Last sign-in",
        "auth.admin.col_ls_role": "Listing Suite role",
        "auth.admin.col_note": "Note",
        "auth.admin.col_reason": "Reason",
        "auth.admin.col_result": "Result",
        "auth.admin.col_role": "Role",
        "auth.admin.col_section": "Section",
        "auth.admin.col_ts": "When",
        "auth.admin.col_until": "Access until",
        "auth.admin.countries_help": "Country codes, comma separated (ES, FR). Only country managers need them.",
        "auth.admin.extra_actions": "The table has actions that do not exist in code: {what}. They have no effect.",
        "auth.admin.f_action": "Action",
        "auth.admin.f_all": "all",
        "auth.admin.f_period": "Period",
        "auth.admin.f_section": "Section",
        "auth.admin.f_who": "Person",
        "auth.admin.filtered_empty": "Nothing matches the filters — that is the filters, not an empty log.",
        "auth.admin.idle": "Inactive",
        "auth.admin.idle_caption": "Who has not signed in for {n} days or more. The threshold is the auth_idle_days setting.",
        "auth.admin.idle_none": "Everyone has signed in within the last {n} days.",
        "auth.admin.locked_pair": "“Administrator × Access” cannot be unchecked — the other changes were saved.",
        "auth.admin.log_empty": "No entries yet.",
        "auth.admin.logins": "Sign-in log",
        "auth.admin.ls_actions": "Listing Suite log",
        "auth.admin.ls_actions_caption": "What was done in Listing Suite. The records sit in the same log and differ by product.",
        "auth.admin.ls_matrix": "Listing Suite permissions",
        "auth.admin.ls_matrix_caption": "Listing Suite permissions. Its roles differ: a content manager edits, an approver pushes to Amazon. The action list comes from the database, seeded by that product’s SQL.",
        "auth.admin.ls_none": "— no access —",
        "auth.admin.ls_role_help": "Empty means no Listing Suite access at all. That is not “Viewer”: the person enters Kabinet but not the second product.",
        "auth.admin.matrix": "Permissions",
        "auth.admin.matrix_caption": "Who may do what. Rules come from the database; an action absent from the table is denied to everyone.",
        "auth.admin.matrix_empty": "The permissions table is empty — the built-in rules apply.",
        "auth.admin.matrix_failed": "Not saved: {e}",
        "auth.admin.matrix_locked": "“Administrator × Access” cannot be unchecked: otherwise nobody could open this screen, and the right could only be restored with a database query.",
        "auth.admin.missing_actions": "Actions present in code but missing from the table: {n} ({what}). They are denied to everyone until added.",
        "auth.admin.mode": "Sign-in mode: {mode}",
        "auth.admin.mode_0": "emergency — no sign-in, everyone is a viewer",
        "auth.admin.mode_1": "sign-in required, roles in effect",
        "auth.admin.mode_2": "rollout — no sign-in, buttons for everyone",
        "auth.admin.mode_where": "Changed in the database: reorder_params.{param}. Every switch is sent to Telegram.",
        "auth.admin.never": "never",
        "auth.admin.never_short": "—",
        "auth.admin.nochange": "Nothing to change.",
        "auth.admin.people": "People",
        "auth.admin.qa": "QA access",
        "auth.admin.res.denied_disabled": "denied: access closed",
        "auth.admin.res.denied_domain": "denied: domain",
        "auth.admin.res.first_login": "first sign-in",
        "auth.admin.res.logout": "sign-out",
        "auth.admin.res.ok": "sign-in",
        "auth.admin.save": "Save",
        "auth.admin.saved": "Saved: {n}",
        "auth.admin.sec.access": "Access",
        "auth.admin.sec.ads": "Ads",
        "auth.admin.sec.dictionaries": "Directories",
        "auth.admin.sec.forecast": "Forecast",
        "auth.admin.sec.incidents": "Incidents",
        "auth.admin.sec.ls_amazon": "Amazon",
        "auth.admin.sec.ls_content": "Content",
        "auth.admin.sec.ls_method": "Methodology",
        "auth.admin.sec.ls_page": "Pages",
        "auth.admin.sec.ls_settings": "Settings",
        "auth.admin.sec.other": "Other",
        "auth.admin.sec.reorder": "Reorder",
        "auth.admin.shown": "Showing {n} of {all}",
        "auth.admin.some_expired": "Access has expired for {n}: {who}. Sign-in is closed but the record is not disabled — extend or clear the date.",
        "auth.admin.title": "Access",
        "auth.admin.until_help": "Last day of access, inclusive, DD.MM.YYYY. Empty means no expiry.",
        "auth.denied": "Not enough rights for this action. Nothing was changed.",
        "auth.log.act.admin": "Managed access",
        "auth.log.act.admin.delete_user": "Deleted a person’s record",
        "auth.log.act.admin.open": "Opened the Access screen",
        "auth.log.act.admin.set_access": "Changed a person’s access",
        "auth.log.act.admin.set_permission": "Changed the permissions matrix",
        "auth.log.act.ads.act": "Changed ads: pause or bid",
        "auth.log.act.auth_mode": "Sign-in mode changed",
        "auth.log.act.auth_mode_notify": "Mode change notification",
        "auth.log.act.auth_mode_set": "Switched the sign-in mode",
        "auth.log.act.dict.edit": "Edited a directory",
        "auth.log.act.forecast.approve": "Approved a forecast",
        "auth.log.act.forecast.edit": "Edited a forecast draft",
        "auth.log.act.forecast.post": "Posted a forecast",
        "auth.log.act.forecast.replace": "Replaced forecasts after a pool change",
        "auth.log.act.forecast.upload": "Uploaded a forecast from a file",
        "auth.log.act.incident.act": "Acknowledged or resolved an incident",
        "auth.log.act.ls.amazon.push": "Pushed a listing to Amazon",
        "auth.log.act.ls.content.edit": "Edited content",
        "auth.log.act.ls.method.edit": "Changed methodology",
        "auth.log.act.ls.settings.edit": "Changed settings",
        "auth.log.act.notify_new_user": "New person notification",
        "auth.log.act.notify_new_user_wd": "Notification sent by the watchdog",
        "auth.log.act.notify_unknown": "Unknown sign-in notification",
        "auth.log.act.page.ads": "Opened «Реклама»",
        "auth.log.act.page.cm": "Opened «Площадки»",
        "auth.log.act.page.dictionaries": "Opened «Справочники»",
        "auth.log.act.page.forecast": "Opened «Прогноз»",
        "auth.log.act.page.home": "Opened «Обзор»",
        "auth.log.act.page.incidents": "Opened «Инциденты»",
        "auth.log.act.page.money": "Opened «Деньги»",
        "auth.log.act.page.reorder": "Opened «Автозаказ»",
        "auth.log.act.page.reviews": "Opened «Отзывы»",
        "auth.log.act.page.stock": "Opened «Остатки»",
        "auth.log.act.qa.new_token": "Issued a QA access token",
        "auth.log.act.qa.revoke": "Revoked QA access tokens",
        "auth.log.act.reorder.act": "Confirmed an order or transfer",
        "auth.log.col_result": "Result",
        "auth.log.col_what": "What they did",
        "auth.log.col_who": "Who",
        "auth.log.col_with": "With what",
        "auth.log.denied": "denied",
        "auth.log.show_service": "Show service entries ({n})",
        "auth.log.via_db": "directly in the database",
        "auth.log.who.kabinet-app": "Kabinet, automatically",
        "auth.log.who.qa-агент": "QA agent",
        "auth.log.who.watchdog": "watchdog",
        "auth.log.who.система": "system",
        "auth.qa.caption": "A link for checking robots: ?qa=token. View only; all actions are hard-blocked regardless of the permissions matrix.",
        "auth.qa.live": "Live tokens: {n}. A new one revokes the previous — there is never more than one.",
        "auth.qa.new": "Rotate token",
        "auth.qa.no_pepper": "No [qa] pepper in secrets. Access works, but protection is weaker: without it a stolen database dump allows guessing the token.",
        "auth.qa.none": "No tokens issued yet.",
        "auth.qa.note": "Sign-ins via the QA link appear in the log as “qa-агент” — we do not hide them. Token lifetime is the qa_token_days setting.",
        "auth.qa.off": "QA access is off — the link does not work even with a live token. Enabled by the qa_access_enabled setting.",
        "auth.qa.on": "QA access is ON. A link with a live token works.",
        "auth.qa.once": "The token is shown ONCE — we store only its hash. Copy the link now; if lost, issue a new one.",
        "auth.qa.product": "Product",
        "auth.qa.product_kabinet": "Kabinet",
        "auth.qa.product_ls": "Listing Suite",
        "auth.qa.revoke": "Revoke all tokens",
        "auth.qa.revoked": "Revoked. The link no longer works.",
        "auth.qa.st_expired": "expired",
        "auth.qa.st_live": "live",
        "auth.qa.st_revoked": "revoked",
        "auth.role.admin": "Administrator",
        "auth.role.approver": "Approver",
        "auth.role.content_manager": "Content manager",
        "auth.role.country_manager": "Country manager",
        "auth.role.demand_planner": "Demand planner",
        "auth.role.viewer": "Viewer",
    },
}
# КОНЕЦ ТЕКСТОВ
