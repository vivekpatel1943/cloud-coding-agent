"""Agent tools. Tools are built per task, bound to that task's executor (repo / sandbox)."""
from typing import Callable

from executor.base import Executor

from .filesystem import make_filesystem_tools
from .git import make_git_tools
from .search import make_search_tools


def build_tools(executor: Executor) -> list[Callable]:
    """All agent tools bound to one executor (one repo / one sandbox / one task).

    Pass the result to GenerateContentConfig(tools=...).
    """
    return [
        *make_filesystem_tools(executor),
        *make_search_tools(executor),
        *make_git_tools(executor),
        # run_command (terminal.py) is intentionally excluded in Phase 1: the playground lives
        # inside this project, so an unrestricted shell could read files like ../../.env.
    ]