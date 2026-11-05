"""Code search tool (grep via the executor's bash)."""
import shlex
from typing import Callable

from executor.base import Executor

from ._common import tool_errors, truncate

MAX_MATCHES = 100
EXCLUDE_DIRS = [".git", "node_modules", ".venv", "__pycache__", "dist", "build"]


def make_search_tools(executor: Executor) -> list[Callable]:
    """Build search tools bound to one executor (one workspace)."""

    @tool_errors
    def search_code(pattern: str, path: str = ".", file_glob: str = "") -> str:
        """Search file contents with a regular expression (grep -E). Returns 'file:line:text' matches.

        Args:
            pattern: Extended regular expression, e.g. 'def build_tools' or 'TODO|FIXME'.
            path: Directory or file to search, relative to the repository root.
            file_glob: Optional filename filter, e.g. '*.py'.
        """
        if pattern == "":
            return "Error: pattern must not be empty."
        path = path.strip().replace("\\", "/") or "."
        executor.resolve(path)  # raises if path escapes the workspace

        args = ["grep", "-rnIE", "--color=never"] + [f"--exclude-dir={d}" for d in EXCLUDE_DIRS]
        if file_glob:
            args.append(f"--include={file_glob}")
        args += ["--", pattern, path]  # '--' so patterns starting with '-' aren't flags
        # Every argument is quoted, so the model's pattern can't inject shell syntax.
        cmd = shlex.join(args) + f" | head -n {MAX_MATCHES + 1}"

        r = executor.run(cmd, timeout=30)
        if r.timed_out:
            return "Error: search timed out. Narrow the path or pattern."

        lines = r.stdout.splitlines()
        err = r.stderr.strip()
        if not lines:
            return f"Search error: {err}" if err else f"No matches for '{pattern}'."

        if len(lines) > MAX_MATCHES:
            lines = lines[:MAX_MATCHES] + [
                f"[more than {MAX_MATCHES} matches; narrow the pattern or path]"
            ]
        out = truncate("\n".join(lines))
        if err:
            out += f"\n\n(warnings: {truncate(err, 300, 300)})"
        return out

    return [search_code]
