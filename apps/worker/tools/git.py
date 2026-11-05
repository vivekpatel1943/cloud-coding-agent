"""Read-only git tool. Git writes (branch/commit/push) belong to the orchestrator, not the model."""
from typing import Callable

from executor.base import Executor

from ._common import format_result, tool_errors, truncate


def make_git_tools(executor: Executor) -> list[Callable]:
    """Build git tools bound to one executor (one workspace)."""

    @tool_errors
    def git_diff() -> str:
        """Show all changes made so far: changed/untracked files plus the full diff against HEAD.
        Use this to review your work before finishing."""
        status = executor.run("git --no-pager status --short", timeout=30)
        if status.exit_code != 0:
            return format_result(status)
        if not status.stdout.strip():
            return "No changes."

        diff = executor.run("git --no-pager diff HEAD", timeout=30)
        return (
            f"Changed files ('??' = untracked, read them with read_file):\n{status.stdout.strip()}"
            f"\n\nDiff:\n{truncate(diff.stdout.strip()) or '(only untracked files)'}"
        )

    return [git_diff]
