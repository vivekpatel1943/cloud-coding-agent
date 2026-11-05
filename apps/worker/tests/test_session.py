"""SessionLog and files_changed tracking. Pure logic: no network, no Git Bash."""
from agent import AgentResult, SessionLog
from agent.loop import _changed_path


def _result(text: str = "Done.", files: list[str] | None = None, reason: str = "done") -> AgentResult:
    return AgentResult(text, steps=1, tool_calls=0, stopped_reason=reason, files_changed=files or [])


def test_empty_log_has_no_preamble():
    assert SessionLog().preamble() == ""


def test_preamble_has_task_outcome_and_files():
    log = SessionLog()
    log.add("Rename add", _result("Renamed in 2 files.", ["a.py", "b.py"]))
    text = log.preamble()
    assert "1. Task: Rename add" in text
    assert "Outcome (done): Renamed in 2 files." in text
    assert "Files changed: a.py, b.py" in text
    assert text.endswith("Current task:\n")


def test_keeps_only_last_n():
    log = SessionLog(max_entries=2)
    for name in ("alpha", "beta", "gamma"):
        log.add(f"task {name}", _result())
    assert len(log) == 2
    assert "alpha" not in log.preamble()
    assert "gamma" in log.preamble()


def test_zero_disables_memory():
    log = SessionLog(max_entries=0)
    log.add("anything", _result())
    assert len(log) == 0 and log.preamble() == ""


def test_clear():
    log = SessionLog()
    log.add("x", _result())
    log.clear()
    assert log.preamble() == ""


def test_long_text_is_clipped_to_one_line():
    log = SessionLog()
    log.add("t" * 5000, _result("line1\nline2 " + "o" * 5000))
    text = log.preamble()
    assert len(text) < 1500
    assert "line1 line2" in text


def test_changed_path():
    assert _changed_path("edit_file", {"path": "src\\a.py"}, "Edited src/a.py: replaced 1 occurrence.") == "src/a.py"
    assert _changed_path("write_file", {"path": "new.py"}, "Wrote 10 characters to new.py.") == "new.py"
    assert _changed_path("edit_file", {"path": "a.py"}, "Error: old_str not found.") is None
    assert _changed_path("read_file", {"path": "a.py"}, "a.py (lines 1-3 of 3)") is None

