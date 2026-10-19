"""deploy_sync: номер коммита из .git, время старта процесса, один сброс на смену кода, `__main__` не выгружается."""
import os
import subprocess
import sys
import threading
import types

import deploy_sync as d


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=cwd, check=True,
                   capture_output=True)


def test_commit_from_git_dir(tmp_path, monkeypatch):
    _git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "a.txt").write_text("1")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "1")
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True).stdout.strip()
    monkeypatch.setattr(d, "ROOT", str(tmp_path))
    assert d.current_commit() == sha
    _git(tmp_path, "pack-refs", "--all")                     # ветка только в packed-refs
    assert d.current_commit() == sha
    _git(tmp_path, "checkout", "-q", "--detach")             # отделённая голова
    assert d.current_commit() == sha


def test_process_start_parsing():
    stat = "4242 (my (odd) proc) S 1 4242 4242 0 -1 4194560 100 0 0 0 5 3 0 0 20 0 7 0 12345 1000 50"
    assert d._parse_start(stat, "cpu 1\nbtime 1700000000\n", 100) == 1700000000 + 123.45
    assert d._parse_start("ерунда", "btime 1", 100) is None


def test_one_reset_for_many_sessions(monkeypatch):
    monkeypatch.setitem(d._state, "commit", "old")
    monkeypatch.setattr(d, "current_commit", lambda: "new")
    monkeypatch.setattr(d, "_forget_old_session_objects", lambda now: None)
    resets = []
    threads = [threading.Thread(target=lambda: resets.append(d.sync())) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sum(resets) == 1


def test_main_and_self_not_purged(monkeypatch):
    fake_main = types.ModuleType("__main__")
    fake_main.__file__ = os.path.join(d.ROOT, "app.py")
    monkeypatch.setitem(sys.modules, "__main__", fake_main)
    names = {n for n, _ in d._project_modules()}
    assert "__main__" not in names and d.__name__ not in names
