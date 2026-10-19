"""Новый код после мержа — без ребута Streamlit Cloud (19.10.2026; в Кабинете — задача T-9, kabinet-dashboard#330).

Та же логика, что в `kabinet-dashboard/deploy_sync.py` — правка одного файла переносится в другой. Здесь
дополнительно остаётся `stale_modules()` в `app.py`: предупреждение «нужен ребут», если модули всё-таки отстали
(например, когда менялся сам этот файл — он доезжает только с ребутом).

Streamlit Cloud после пуша в main подтягивает файлы, но процесс сервера не перезапускает. `app.py` и страницы
Streamlit перечитывает с диска на каждом прогоне — а модули проекта (`i18n`, `auth`, `pbi`, …) остаются в
`sys.modules` такими, какими их импортировали при старте, и кэши `st.cache_data` / `st.cache_resource` живут дальше.
Отсюда «старый модуль рядом с новым»: страница уже новая, а переводы и функции модулей — прежние, новый ключ
перевода печатается самим ключом, пока кто-нибудь не перезапустит приложение руками.

Что делаем: на каждом прогоне читаем номер коммита рабочей копии (`.git/HEAD` → ref → sha, без git и без сети —
два маленьких файла) и сравниваем с номером, при котором процесс загрузил модули. Номер другой → сбросить оба кэша
и выгрузить модули проекта из `sys.modules`; `app.py` идёт дальше и импортирует их заново уже с диска, вместе со
свежим `i18n`.

Номер «при загрузке» хранится в переменной ЭТОГО модуля, а не в `st.cache_resource`: сам `deploy_sync` никогда не
выгружается, а кэш сбрасываем мы же — номер в нём пропадал бы вместе с кэшем, и следующий сеанс снова шёл бы в ветку
«первого прогона». Сброс — под блокировкой с повторной проверкой номера: два сеанса, одновременно увидевшие новый
коммит, иначе выгружали бы модули друг у друга посреди импорта (`KeyError` в чужом потоке — воспроизведено
проверяющим PR #330).

Первый прогон процесса — особый случай: номера «при загрузке» ещё нет. Выгружаем модули, только если какой-то файл
проекта НОВЕЕ самого процесса (время старта — `starttime` из `/proc/self/stat` + `btime` из `/proc/stat`; это Linux,
где живёт Streamlit Cloud): это ровно мерж, который принёс сам `deploy_sync` — процесс старый, файлы новые. Обычный
старт процесса ничего не выгружает. Время изменения каталога `/proc/<pid>` для этого НЕ годится: ядро ставит его,
когда лениво создаёт запись, а не при старте процесса. Где `/proc` нет (macOS), первый прогон не выгружает ничего.

Сеанс, открытый до мержа, держит в `st.session_state["_auth_user"]` объект пользователя СТАРОГО класса — после
выгрузки `auth` новый код ждал бы у него новых полей. Поэтому при смене кода в сеансе этот объект выбрасывается, и
`auth.current()` собирает его заново.

Ограничение: правка САМОГО `deploy_sync.py` доезжает только с ребутом — модуль себя не выгружает намеренно (иначе
терялись бы номер и блокировка). Звать `sync()` НАДО первой строкой `app.py`, до импорта модулей проекта: модуль,
импортированный раньше, `app.py` держал бы ссылкой на старый объект до конца прогона.
"""
import os
import sys
import threading
import time

import streamlit as st

ROOT = os.path.dirname(os.path.abspath(__file__))
_FALLBACK_EVERY_S = 30          # без .git отпечаток кода считается не чаще раза в 30 с
_fallback = {"at": 0.0, "value": None}
_state = {"commit": None, "last": None}   # номер при загрузке модулей и последний прочитанный; один на процесс
_lock = threading.Lock()
_SESSION_KEYS_OF_OLD_CODE = ("_auth_user",)   # объекты классов проекта, которые сеанс хранит между прогонами


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def current_commit():
    """sha коммита рабочей копии из `.git` (обычная ветка, отделённая голова, packed-refs, worktree); нет — None."""
    git = os.path.join(ROOT, ".git")
    if os.path.isfile(git):                       # worktree: в .git лежит «gitdir: <путь>»
        line = _read(git) or ""
        if line.startswith("gitdir:"):
            git = os.path.normpath(os.path.join(ROOT, line[len("gitdir:"):].strip()))
    head = _read(os.path.join(git, "HEAD"))
    if not head:
        return None
    if not head.startswith("ref:"):
        return head                               # отделённая голова: в HEAD сам sha
    ref = head[len("ref:"):].strip()
    sha = _read(os.path.join(git, ref))
    if sha:
        return sha
    common = _read(os.path.join(git, "commondir"))  # у worktree ветки лежат в общей папке
    base = os.path.normpath(os.path.join(git, common)) if common else git
    sha = _read(os.path.join(base, ref))
    if sha:
        return sha
    for line in (_read(os.path.join(base, "packed-refs")) or "").splitlines():
        parts = line.split(" ")
        if len(parts) == 2 and parts[1] == ref:
            return parts[0]
    return None


def _code_fingerprint():
    """Запасной отпечаток, если `.git` нет: время изменения и размер .py файлов проекта."""
    now = time.monotonic()
    if _fallback["value"] is not None and now - _fallback["at"] < _FALLBACK_EVERY_S:
        return _fallback["value"]
    parts = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if not d.startswith((".", "__")) and d not in ("nb", "sql", "scratchpad", "docs", "exports")]
        for name in files:
            if name.endswith(".py"):
                p = os.path.join(base, name)
                try:
                    s = os.stat(p)
                    parts.append(f"{p}:{s.st_mtime_ns}:{s.st_size}")
                except OSError:
                    pass
    _fallback.update(at=now, value="fp:" + format(abs(hash("|".join(sorted(parts)))), "x"))
    return _fallback["value"]


def version():
    """Что сейчас загружено: короткий sha (или «fp:» и 7 знаков отпечатка, если `.git` нет). Без повторного чтения."""
    v = _state["last"] or current_commit() or _code_fingerprint()
    return v[:10] if v.startswith("fp:") else v[:7]


def _parse_start(stat_text, proc_stat_text, clk_tck):
    """Время старта процесса (unix) из содержимого /proc/self/stat и /proc/stat; не разобралось — None."""
    try:
        rest = stat_text[stat_text.rindex(")") + 2:].split()   # после «(comm) » идёт поле 3 (state)
        starttime_ticks = int(rest[19])                        # поле 22 — индекс 19 от поля 3
        btime = next(int(l.split()[1]) for l in proc_stat_text.splitlines() if l.startswith("btime "))
        return btime + starttime_ticks / clk_tck
    except (ValueError, IndexError, StopIteration):
        return None


def _process_started_at():
    """Время старта процесса на Linux; где /proc нет — None."""
    stat, pstat = _read("/proc/self/stat"), _read("/proc/stat")
    if not stat or not pstat:
        return None
    try:
        tck = os.sysconf("SC_CLK_TCK")
    except (ValueError, OSError, AttributeError):
        return None
    return _parse_start(stat, pstat, tck)


def _project_modules():
    me = __name__
    for name, mod in list(sys.modules.items()):
        f = getattr(mod, "__file__", None) or ""
        # __main__ — это сам исполняемый скрипт (app.py или страница): Streamlit держит его в sys.modules, и выгрузка
        # роняла прогон KeyError '__main__' (поймано локальной пробой 19.10.2026)
        if name.startswith("__") or name == me or not f or "site-packages" in f:
            continue
        if os.path.abspath(f).startswith(ROOT + os.sep):
            yield name, f


def _project_newer_than(ts):
    """Есть ли загруженный модуль проекта, чей файл изменён позже ts."""
    for _, f in _project_modules():
        try:
            if os.stat(f).st_mtime > ts:
                return True
        except OSError:
            pass
    return False


def _forget_old_session_objects(now):
    """Сеанс, переживший смену кода, выбрасывает объекты старых классов — их соберут заново."""
    try:
        if st.session_state.get("_deploy_code") != now:
            for k in _SESSION_KEYS_OF_OLD_CODE:
                st.session_state.pop(k, None)
            st.session_state["_deploy_code"] = now
    except Exception:
        pass                        # вне сеанса (тесты, голый запуск) session_state недоступен — нечего чистить


def sync():
    """Первой строкой app.py. Коммит сменился (или первый прогон процесса после мержа) — сброс кэшей и выгрузка
    модулей проекта. Возвращает True, если сброс был в этом прогоне."""
    now = current_commit() or _code_fingerprint()
    _state["last"] = now
    reset = False
    if _state["commit"] != now:
        with _lock:
            if _state["commit"] != now:            # повторная проверка: другой сеанс мог успеть сбросить
                first = _state["commit"] is None
                started = _process_started_at() if first else None
                if not first or (started is not None and _project_newer_than(started)):
                    st.cache_data.clear()
                    st.cache_resource.clear()
                    for name, _ in list(_project_modules()):
                        sys.modules.pop(name, None)
                    reset = True
                    print(f"[deploy_sync] код {now[:12]}: кэши сброшены, модули проекта перечитаются", flush=True)
                _state["commit"] = now
    _forget_old_session_objects(now)
    return reset
