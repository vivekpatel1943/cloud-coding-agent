import time

import pytest

from executor import PathOutsideWorkspaceError


def test_resolve_rejects_escape(executor):
    with pytest.raises(PathOutsideWorkspaceError):
        executor.resolve("../outside.txt")
    with pytest.raises(PathOutsideWorkspaceError):
        executor.resolve("a/../../outside.txt")


def test_resolve_allows_inside(executor, tmp_path):
    assert executor.resolve("a/b.txt") == str((tmp_path / "a" / "b.txt").resolve())


def test_run_echo(executor):
    r = executor.run("echo hi")
    assert r.exit_code == 0
    assert r.stdout.strip() == "hi"
    assert not r.timed_out


def test_run_nonzero_exit(executor):
    r = executor.run("exit 3")
    assert r.exit_code == 3


def test_run_timeout(executor):
    r = executor.run("sleep 5", timeout=1)
    assert r.timed_out


def test_run_interactive_prompt_fails_fast(executor):
    start = time.monotonic()
    r = executor.run("read x", timeout=10)
    assert time.monotonic() - start < 5
    assert not r.timed_out


def test_run_hides_secrets(executor, monkeypatch):
    monkeypatch.setenv("MY_API_KEY", "super-secret-value")
    monkeypatch.setenv("HARMLESS_VAR", "visible")
    r = executor.run("env")
    assert "super-secret-value" not in r.stdout
    assert "visible" in r.stdout


def test_crlf_round_trip(executor):
    executor.write_text("w.txt", "a\r\nb\r\n")
    assert executor.read_text("w.txt") == "a\r\nb\r\n"


def test_write_creates_parents(executor):
    executor.write_text("deep/er/file.txt", "x")
    assert executor.exists("deep/er/file.txt")
