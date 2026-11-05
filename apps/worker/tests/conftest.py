import os
import shutil
from pathlib import Path

import pytest

from executor import LocalExecutor


def _find_git_bash() -> str | None:
    """Prefer an explicit BASH_PATH, then Git Bash's default location.
    Avoid C:\\Windows\\System32\\bash.exe (WSL), which sees a different filesystem."""
    candidates = [
        os.environ.get("BASH_PATH"),
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return c
    found = shutil.which("bash")
    if found and "system32" not in found.lower():
        return found
    return None


GIT_BASH = _find_git_bash()

requires_bash = pytest.mark.skipif(GIT_BASH is None, reason="Git Bash not found")


@pytest.fixture
def executor(tmp_path: Path) -> LocalExecutor:
    if GIT_BASH is None:
        pytest.skip("Git Bash not found")
    return LocalExecutor(root=str(tmp_path), bash_path=GIT_BASH)


@pytest.fixture
def write(tmp_path: Path):
    """Write a file under the workspace with exact bytes."""

    def _write(rel: str, content: str) -> Path:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        return p

    return _write
