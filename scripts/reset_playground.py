"""Rebuild agent_playground/test_files with known fixtures and a git baseline commit.

Usage (from the repo root):
    uv run python scripts/reset_playground.py

WARNING: deletes everything inside agent_playground/test_files first.
Add new fixtures to FIXTURES below rather than creating them by hand.
"""
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "agent_playground" / "test_files"

# ---- fixtures (written with "\n" line endings) ---------------------------------
FIXTURES: dict[str, str] = {
    # empty file: tests read_file on empty files and write_file(overwrite=true)
    "hello.md": "",
    # nested file: tests list_dir / discovery
    "notes/todo.md": """\
# TODO

- [ ] Write an intro in hello.md
- [ ] Fix the bug in src/calc.py
- [x] Set up the playground
""",
    # planted bug: average() divides by a hard-coded 2 instead of len(numbers)
    "src/calc.py": '''\
"""Tiny calculator module used to test the coding agent."""


def add(a, b):
    """Return the sum of a and b."""
    return a + b


def subtract(a, b):
    """Return a minus b."""
    return a - b


def average(numbers):
    """Return the arithmetic mean of a non-empty list of numbers."""
    total = 0
    for n in numbers:
        total = add(total, n)
    return total / 2
''',
    "tests/test_calc.py": """\
from src.calc import add, average, subtract


def test_add():
    assert add(2, 3) == 5


def test_subtract():
    assert subtract(5, 3) == 2


def test_average():
    assert average([1, 2, 3, 4]) == 2.5
""",
    # structured file: edits must keep it valid JSON
    "config/settings.json": """\
{
  "app_name": "playground",
  "version": "1.0.0",
  "debug": false,
  "max_items": 50
}
""",
    # repeated lines: edit_file must reject non-unique matches
    "dupes.py": """\
value = 1
print("checkpoint")
value = value + 1
print("checkpoint")
value = value * 2
print("checkpoint")
""",
    # ignored directory: should not show up in list_dir / search_code
    "node_modules/junk.js": "module.exports = function add() { return 'should be ignored'; };\n",
}

# written with "\r\n" line endings: edit_file must keep CRLF
CRLF_FIXTURES: dict[str, str] = {
    "crlf.txt": """\
This file uses Windows (CRLF) line endings.
Line two.
Change me: original text.
Last line.
""",
}


def _big_file() -> str:
    # tests read_file chunking (MAX_READ_LINES = 400)
    return "".join(f"line {i}: the quick brown fox jumps over the lazy dog\n" for i in range(1, 1201))


def _force_remove(func, path, _exc):
    """rmtree error handler: .git objects are read-only on Windows."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _write(rel: str, content: str, newline: str) -> None:
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    data = content.replace("\n", newline)
    with open(p, "w", encoding="utf-8", newline="") as f:  # exact bytes, no translation
        f.write(data)


def _git(*args: str) -> None:
    subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True)


def main() -> int:
    # Safety guard: never delete anything other than the playground.
    if ROOT.parts[-2:] != ("agent_playground", "test_files"):
        print(f"Refusing to reset unexpected path: {ROOT}", file=sys.stderr)
        return 1

    if ROOT.exists():
        shutil.rmtree(ROOT, onexc=_force_remove)
    ROOT.mkdir(parents=True)

    for rel, content in FIXTURES.items():
        _write(rel, content, "\n")
    for rel, content in CRLF_FIXTURES.items():
        _write(rel, content, "\r\n")
    _write("big.txt", _big_file(), "\n")

    _git("init", "-q")
    _git("config", "core.autocrlf", "false")  # keep crlf.txt as CRLF in the repo
    _git("config", "user.name", "playground")
    _git("config", "user.email", "playground@local")
    _git("add", "-A")
    _git("commit", "-q", "-m", "baseline")

    count = sum(1 for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts)
    print(f"Playground reset: {count} files at {ROOT} (git baseline committed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
