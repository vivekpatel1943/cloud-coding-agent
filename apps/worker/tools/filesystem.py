"""File tools: read, edit, write and list files through an Executor."""
from typing import Callable

from executor.base import Executor

from ._common import tool_errors

MAX_READ_LINES = 400
MAX_DIR_ENTRIES = 200
IGNORED_DIRS = {".git", "node_modules", ".venv", "__pycache__", "dist", "build"}


def _split_lines(text: str) -> list[str]:
    """Split on '\\n' only (unlike str.splitlines, which also splits on \\x0c, \\u2028, ...),
    so line numbers agree with what edit_file matches against."""
    if text == "":
        return []
    lines = text.split("\n")
    if lines[-1] == "":  # trailing newline -> no extra empty line
        lines.pop()
    return [line.removesuffix("\r") for line in lines]


def make_filesystem_tools(executor: Executor) -> list[Callable]:
    """Build file tools bound to one executor (one workspace)."""

    @tool_errors
    def read_file(path: str, start_line: int = 1, end_line: int = 0) -> str:
        """Read a text file with line numbers.

        Line numbers are shown as '   12| ' prefixes and are NOT part of the file content.
        Large files are returned in chunks; call again with a later start_line to continue.

        Args:
            path: File path relative to the repository root.
            start_line: First line to show (1-based). Defaults to 1.
            end_line: Last line to show (inclusive). 0 means 'until the chunk limit'.
        """
        lines = _split_lines(executor.read_text(path))
        total = len(lines)
        if total == 0:
            return f"{path} is empty."

        start = max(start_line, 1)
        if start > total:
            return f"Error: start_line {start} is past the end of the file ({total} lines)."
        end = total if end_line <= 0 else min(end_line, total)
        if end < start:
            return f"Error: end_line {end_line} is before start_line {start}."
        end = min(end, start + MAX_READ_LINES - 1)

        body = "\n".join(f"{i:>5}| {lines[i - 1]}" for i in range(start, end + 1))
        header = f"{path} (lines {start}-{end} of {total})"
        footer = (
            f"\n[{total - end} more lines; call read_file with start_line={end + 1}]"
            if end < total
            else ""
        )
        return f"{header}\n{body}{footer}"

    @tool_errors
    def edit_file(path: str, old_str: str, new_str: str) -> str:
        """Edit a file by replacing one exact occurrence of old_str with new_str.

        old_str must match the file content exactly (including indentation) and must be unique.
        Include a few surrounding lines to make it unique. Do not include line-number prefixes.

        Args:
            path: File path relative to the repository root.
            old_str: Exact existing text to replace. Must not be empty.
            new_str: Replacement text.
        """
        if old_str == "":
            return "Error: old_str must not be empty. To create or fill a file, use write_file."

        raw = executor.read_text(path)
        uses_crlf = "\r\n" in raw
        text = raw.replace("\r\n", "\n")  # the model always writes '\n'
        old = old_str.replace("\r\n", "\n")
        new = new_str.replace("\r\n", "\n")

        count = text.count(old)
        if count == 0:
            return "Error: old_str not found. Re-read the file and copy the text exactly."
        if count > 1:
            return f"Error: old_str matches {count} places. Add more surrounding lines to make it unique."

        updated = text.replace(old, new, 1)
        if uses_crlf:
            updated = updated.replace("\n", "\r\n")  # keep the file's original line endings
        executor.write_text(path, updated)
        return f"Edited {path}: replaced 1 occurrence."

    @tool_errors
    def write_file(path: str, content: str, overwrite: bool = False) -> str:
        """Create a new file. Prefer edit_file for changing existing files.

        Args:
            path: File path relative to the repository root.
            content: Full file content.
            overwrite: Set true only to deliberately replace an entire existing file
                (or to fill an existing empty file).
        """
        if executor.exists(path) and not overwrite:
            return (
                f"Error: {path} already exists. Use edit_file, "
                "or pass overwrite=true to replace it entirely."
            )
        executor.write_text(path, content)
        return f"Wrote {len(content)} characters to {path}."

    @tool_errors
    def list_dir(path: str = ".", recursive: bool = False) -> str:
        """List files and folders in a directory (folders end with '/').

        Args:
            path: Directory relative to the repository root. Defaults to the root.
            recursive: If true, list everything below the directory as relative paths.
        """
        base = path.strip().rstrip("/\\") or "."

        def entries_of(rel: str):
            entries = [e for e in executor.list_dir(rel) if e.name not in IGNORED_DIRS]
            entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))  # folders first
            return entries

        lines: list[str] = []
        omitted = 0

        if not recursive:
            for e in entries_of(base):
                if len(lines) < MAX_DIR_ENTRIES:
                    lines.append(e.name + ("/" if e.is_dir else ""))
                else:
                    omitted += 1
        else:
            stack = [""]  # paths relative to `base`
            while stack:
                rel = stack.pop()
                full = base if rel == "" else f"{base}/{rel}"
                children = entries_of(full)
                sub_dirs = []
                for e in children:
                    child = e.name if rel == "" else f"{rel}/{e.name}"
                    if len(lines) < MAX_DIR_ENTRIES:
                        lines.append(child + ("/" if e.is_dir else ""))
                    else:
                        omitted += 1
                    if e.is_dir:
                        sub_dirs.append(child)
                stack.extend(reversed(sub_dirs))  # visit in sorted order

        if omitted:
            lines.append(f"[... {omitted} more entries]")
        return "\n".join(lines) or "(empty directory)"

    return [read_file, edit_file, write_file, list_dir]