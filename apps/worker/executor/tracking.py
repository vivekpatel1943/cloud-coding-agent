"""Executor wrapper that records file writes so a task's changes can be undone.

run_agent wraps the real executor in a TrackingExecutor for each task. Before the
first write to a path, it snapshots the original content (or notes that the file did
not exist). If the task is interrupted, restore() puts every touched file back.

This only covers writes made through write_text (edit_file / write_file). Shell
commands run via run() are not tracked; run_command is disabled in Phase 1, and the
tools that do use run() (search_code, git_diff) are read-only.
"""
from .base import CommandResult, DirEntry, Executor


class TrackingExecutor(Executor):
    def __init__(self, inner: Executor) -> None:
        self.inner = inner
        # absolute path -> (path as the agent gave it, original content or None if it didn't exist)
        self._originals: dict[str, tuple[str, str | None]] = {}

    # ── tracking ──────────────────────────────────────────────────────────
    def restore(self) -> list[str]:
        """Undo every write made through this executor. Returns the restored paths."""
        restored: list[str] = []
        for rel, original in self._originals.values():
            if original is None:
                self.inner.remove(rel)  # the task created this file
            else:
                self.inner.write_text(rel, original)
            restored.append(rel)
        self._originals.clear()
        return restored

    # ── Executor interface (writes are snapshotted, everything else delegates) ──
    def write_text(self, path: str, content: str) -> None:
        key = self.inner.resolve(path)  # also rejects paths outside the workspace
        if key not in self._originals:
            original = self.inner.read_text(path) if self.inner.exists(path) else None
            self._originals[key] = (path, original)
        self.inner.write_text(path, content)

    def resolve(self, path: str) -> str:
        return self.inner.resolve(path)

    def run(self, command: str, timeout: int = 60) -> CommandResult:
        return self.inner.run(command, timeout)

    def read_text(self, path: str) -> str:
        return self.inner.read_text(path)

    def exists(self, path: str) -> bool:
        return self.inner.exists(path)

    def list_dir(self, path: str) -> list[DirEntry]:
        return self.inner.list_dir(path)

    def remove(self, path: str) -> None:
        self.inner.remove(path)

