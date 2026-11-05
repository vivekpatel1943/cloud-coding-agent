"""Short-term memory across REPL prompts.

Each task runs in a fresh Gemini chat. Instead of carrying the raw transcript
(every file read, every diff) into the next task, we keep a compact summary of
the last few tasks and prepend it to the next task's first message.
That costs roughly 100-300 tokens per remembered task instead of tens of thousands.
"""
from collections import deque
from dataclasses import dataclass, field

from .loop import AgentResult

MAX_TASK_CHARS = 300
MAX_OUTCOME_CHARS = 500


def _clip(text: str, limit: int) -> str:
    """Collapse whitespace to a single line and cut to `limit` characters."""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


@dataclass
class SessionEntry:
    task: str
    outcome: str
    stopped_reason: str
    files_changed: list[str] = field(default_factory=list)

    def render(self, index: int) -> str:
        outcome = _clip(self.outcome, MAX_OUTCOME_CHARS) or "(no text)"
        files = ", ".join(self.files_changed) or "(none)"
        return (
            f"{index}. Task: {_clip(self.task, MAX_TASK_CHARS)}\n"
            f"   Outcome ({self.stopped_reason}): {outcome}\n"
            f"   Files changed: {files}"
        )


class SessionLog:
    """The last `max_entries` task summaries. max_entries=0 disables memory."""

    def __init__(self, max_entries: int = 3) -> None:
        self._entries: deque[SessionEntry] = deque(maxlen=max(0, max_entries))

    def __len__(self) -> int:
        return len(self._entries)

    def add(self, task: str, result: AgentResult) -> None:
        self._entries.append(
            SessionEntry(task, result.final_text, result.stopped_reason, list(result.files_changed))
        )

    def clear(self) -> None:
        self._entries.clear()

    def render(self) -> str:
        """Human/model-readable list of remembered tasks (oldest first)."""
        return "\n\n".join(e.render(i) for i, e in enumerate(self._entries, 1))

    def preamble(self) -> str:
        """Text to prepend to the next task, or '' when nothing is remembered."""
        if not self._entries:
            return ""
        return (
            "Context from earlier tasks in this session (oldest first). These are summaries, "
            "and files may have changed since; re-read a file before relying on its contents.\n\n"
            f"{self.render()}\n\n"
            "Current task:\n"
        )

