"""TrackingExecutor snapshots + run_agent rollback on Ctrl+C. No network, no Git Bash."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from google.genai import types

from agent import run_agent
from executor import LocalExecutor, TrackingExecutor


@pytest.fixture
def local(tmp_path: Path) -> LocalExecutor:
    # bash is never invoked by these tests; pass a dummy so Git Bash isn't required.
    return LocalExecutor(root=str(tmp_path), bash_path="bash")


def _read(p: Path) -> str:
    with open(p, encoding="utf-8", newline="") as f:
        return f.read()


def test_restore_reverts_edits_and_deletes_new_files(local, tmp_path):
    (tmp_path / "keep.py").write_bytes(b"original\r\n")
    tracked = TrackingExecutor(local)

    tracked.write_text("keep.py", "changed once\n")
    tracked.write_text("./keep.py", "changed twice\n")  # same file, different spelling
    tracked.write_text("new/dir/created.py", "brand new\n")

    restored = tracked.restore()

    assert _read(tmp_path / "keep.py") == "original\r\n"  # exact bytes, CRLF kept
    assert not (tmp_path / "new" / "dir" / "created.py").exists()
    assert sorted(restored) == ["keep.py", "new/dir/created.py"]


def test_restore_with_no_writes_is_noop(local):
    assert TrackingExecutor(local).restore() == []


def test_remove_missing_file_is_ok(local):
    local.remove("does_not_exist.txt")


# ── run_agent rollback with a fake Gemini client ─────────────────────────────

def _call_response(name: str, args: dict) -> types.GenerateContentResponse:
    part = types.Part(function_call=types.FunctionCall(name=name, args=args))
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=[part]))]
    )


class _FakeChat:
    """Turn 1: model asks to edit + create files. Turn 2: user presses Ctrl+C."""

    def __init__(self) -> None:
        self.turn = 0

    def send_message(self, message):
        self.turn += 1
        if self.turn == 1:
            resp = _call_response("write_file", {"path": "a.py", "content": "agent wrote this\n", "overwrite": True})
            resp.candidates[0].content.parts.append(
                types.Part(function_call=types.FunctionCall(
                    name="write_file", args={"path": "b.py", "content": "new file\n"}))
            )
            return resp
        raise KeyboardInterrupt


def test_run_agent_rolls_back_on_interrupt(local, tmp_path):
    (tmp_path / "a.py").write_text("before\n", encoding="utf-8")
    client = SimpleNamespace(chats=SimpleNamespace(create=lambda **kw: _FakeChat()))
    logs: list[str] = []

    with pytest.raises(KeyboardInterrupt):
        run_agent("do things", local, client, model="fake", log=logs.append)  # type: ignore[arg-type]

    assert (tmp_path / "a.py").read_text(encoding="utf-8") == "before\n"
    assert not (tmp_path / "b.py").exists()
    assert any("[rollback] restored 2 file(s)" in line for line in logs)

