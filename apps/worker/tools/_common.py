"""Shared helpers for agent tools: output truncation, result formatting, error handling."""
import functools

from executor.base import CommandResult, PathOutsideWorkspaceError

HEAD_CHARS = 1_000
TAIL_CHARS = 3_000


def truncate(text: str, head: int = HEAD_CHARS, tail: int = TAIL_CHARS) -> str:
    """Keep the start (context) and the end (errors/summary) of long output."""
    if len(text) <= head + tail:
        return text
    omitted = len(text) - head - tail
    return f"{text[:head]}\n\n[... {omitted} characters truncated ...]\n\n{text[-tail:]}"


def format_result(r: CommandResult, timeout: int | None = None) -> str:
    """Render a CommandResult as text for the model."""
    parts = [
        f"Command timed out after {timeout}s (partial output below)."
        if r.timed_out
        else f"Exit code: {r.exit_code}"
    ]
    if r.stdout.strip():
        parts.append("STDOUT:\n" + truncate(r.stdout.strip()))
    if r.stderr.strip():
        parts.append("STDERR:\n" + truncate(r.stderr.strip()))
    if len(parts) == 1:
        parts.append("(no output)")
    return "\n\n".join(parts)


def tool_errors(fn):
    """Turn exceptions into readable error strings so the agent loop never crashes
    and the model gets feedback it can act on."""

    @functools.wraps(fn)  # keeps name, docstring and signature for Gemini's schema
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except PathOutsideWorkspaceError as e:
            return f"Error: {e}. Use paths relative to the repository root."
        except FileNotFoundError:
            return "Error: file not found. Use list_dir or search_code to locate it."
        except IsADirectoryError:
            return "Error: that path is a directory, not a file. Use list_dir to see its contents."
        except NotADirectoryError:
            return "Error: that path is a file, not a directory. Use read_file instead."
        except PermissionError:
            # On Windows, opening a directory as a file raises PermissionError.
            return "Error: permission denied (or the path is a directory). Use list_dir to check."
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"

    return wrapper
