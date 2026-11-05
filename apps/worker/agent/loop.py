"""Manual agent loop: model -> tool calls -> results -> model ... until a final answer."""
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from google import genai
from google.genai import types
from google.genai.errors import ClientError

from executor.base import Executor
from executor.tracking import TrackingExecutor
from tools import build_tools

from .prompts import SYSTEM_PROMPT

# ── Rate-limit retry settings ──────────────────────────────────────────────
_MAX_RETRIES = 5
_DEFAULT_BACKOFFS = [15, 30, 60, 120, 120]  # seconds, used when we can't parse a retryDelay

# Tools whose successful calls modify a file; used to build AgentResult.files_changed.
_FILE_WRITE_TOOLS = {"edit_file", "write_file"}


@dataclass
class AgentResult:
    final_text: str
    steps: int
    tool_calls: int
    stopped_reason: str  # "done" | "max_steps"
    files_changed: list[str] = field(default_factory=list)  # paths edited/written, in first-touch order


def _short(value: Any, limit: int = 200) -> str:
    """One-line preview for logs."""
    text = str(value).replace("\r", "").replace("\n", "\\n")
    return text if len(text) <= limit else text[:limit] + f"... (+{len(text) - limit} chars)"


def _parse_retry_delay(error: ClientError) -> float | None:
    """Try to extract the retryDelay seconds from a 429 error's details.

    Google's error JSON includes a RetryInfo detail like:
        {'@type': '...google.rpc.RetryInfo', 'retryDelay': '13s'}
    or sometimes '13.350278758s'. We parse that into a float.
    """
    try:
        details = error.details.get("error", {}).get("details", [])
        for detail in details:
            if "RetryInfo" in detail.get("@type", ""):
                delay_str = detail.get("retryDelay", "")
                match = re.search(r"([\d.]+)s", delay_str)
                if match:
                    return float(match.group(1))
    except Exception:
        pass
    return None


def _send_with_retry(
    chat: genai.chats.Chat,
    message: Any,
    log: Callable[[str], None],
) -> types.GenerateContentResponse:
    """Wrap chat.send_message with automatic retry on 429 RESOURCE_EXHAUSTED.

    Parses the recommended retryDelay from Google's error response and sleeps
    for that duration (+ 2s buffer). Falls back to exponential backoff if
    parsing fails. Gives up after _MAX_RETRIES attempts.
    """
    for attempt in range(_MAX_RETRIES):
        try:
            return chat.send_message(message)
        except ClientError as e:
            if e.code != 429:
                raise  # not a rate-limit error — propagate immediately

            delay = _parse_retry_delay(e)
            if delay is None:
                delay = _DEFAULT_BACKOFFS[min(attempt, len(_DEFAULT_BACKOFFS) - 1)]
            else:
                delay += 2  # small buffer on top of Google's recommended delay

            log(f"[rate-limit] 429 RESOURCE_EXHAUSTED — waiting {delay:.0f}s before retry "
                f"(attempt {attempt + 1}/{_MAX_RETRIES})")
            time.sleep(delay)

    # Final attempt — let any exception propagate
    return chat.send_message(message)


def _call_tool(tool_map: dict[str, Callable[..., str]], name: str, args: dict[str, Any]) -> str:
    """Run one tool. Unknown tools and bad arguments become error strings for the model."""
    fn = tool_map.get(name)
    if fn is None:
        return f"Error: unknown tool '{name}'. Available tools: {', '.join(tool_map)}."
    try:
        return str(fn(**args))
    except TypeError as e:  # wrong/missing argument names (raised before the tool body runs)
        return f"Error: invalid arguments for {name}: {e}"


def _text_of(response: types.GenerateContentResponse) -> str:
    """Concatenate text parts without triggering SDK warnings about non-text parts."""
    if not response.candidates or not response.candidates[0].content:
        return ""
    parts = response.candidates[0].content.parts or []
    return "".join(p.text for p in parts if p.text and not p.thought)


def _changed_path(name: str, args: dict[str, Any], result: str) -> str | None:
    """Path modified by a successful edit_file/write_file call, else None.

    Tools report failures as strings starting with 'Error' (see tools/_common.py).
    """
    if name not in _FILE_WRITE_TOOLS or result.startswith("Error"):
        return None
    path = str(args.get("path") or "").strip().replace("\\", "/")
    return path or None


def run_agent(
    task: str,
    executor: Executor,
    client: genai.Client,
    model: str,
    max_steps: int = 25,
    log: Callable[[str], None] = print,
    context: str = "",
) -> AgentResult:
    """Run one task to completion (or until max_steps model turns).

    `context` (optional) is prepended to the first message, e.g. summaries of
    earlier tasks in a REPL session. Each call still uses a brand-new chat.

    If the task is interrupted (Ctrl+C), every file it wrote is restored to its
    state before the task started, then the KeyboardInterrupt is re-raised.
    """
    tracked = TrackingExecutor(executor)
    try:
        return _run_loop(task, tracked, client, model, max_steps, log, context)
    except KeyboardInterrupt:
        restored = tracked.restore()
        if restored:
            log(f"\n[rollback] restored {len(restored)} file(s): {', '.join(restored)}")
        raise


def _run_loop(
    task: str,
    executor: Executor,
    client: genai.Client,
    model: str,
    max_steps: int,
    log: Callable[[str], None],
    context: str,
) -> AgentResult:
    tools = build_tools(executor)
    tool_map = {fn.__name__: fn for fn in tools}

    # `chats` keeps the full history for us, including thought signatures on
    # function-call parts that newer Gemini models require to be sent back.
    chat = client.chats.create(
        model=model,
        config=types.GenerateContentConfig(
            tools=tools,  # SDK builds function schemas from signatures + docstrings
            system_instruction=SYSTEM_PROMPT,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )

    log(f"[task] {task}")
    response = _send_with_retry(chat, f"{context}{task}" if context else task, log)
    total_calls = 0
    files_changed: list[str] = []

    for step in range(1, max_steps + 1):
        calls = response.function_calls or []
        text = _text_of(response)
        if text and calls:
            log(f"[step {step}] model: {_short(text, 300)}")

        if not calls:
            return AgentResult(text, step, total_calls, "done", files_changed)

        parts: list[types.Part] = []
        for call in calls:  # the model may request several calls at once
            name = call.name or ""
            args = dict(call.args or {})
            log(f"[step {step}] -> {name}({_short(args)})")
            result = _call_tool(tool_map, name, args)
            log(f"[step {step}] <- {_short(result, 300)}")
            total_calls += 1
            changed = _changed_path(name, args, result)
            if changed and changed not in files_changed:
                files_changed.append(changed)
            parts.append(types.Part.from_function_response(name=name, response={"result": result}))

        response = _send_with_retry(chat, parts, log)  # all results go back in one turn

    return AgentResult(_text_of(response), max_steps, total_calls, "max_steps", files_changed)
