"""CLI for the coding agent.

Usage (from apps/worker):
    uv run main.py                                            # interactive REPL
    uv run main.py "Rename add to sum_numbers everywhere"     # one-shot: run one task and exit
    uv run main.py --root ../../agent_playground/test_files --max-steps 10 "List every file"

REPL commands: /help, /history, /reset, /exit
Ctrl+C during a task cancels it and restores every file it changed.
"""
import argparse
import sys

from google import genai

from agent import AgentResult, SessionLog, run_agent
from common.core.config import Settings
from executor import Executor, LocalExecutor

REPL_HELP = """\
Commands:
  /history   show what the agent remembers from earlier tasks
  /reset     forget earlier tasks (start a fresh session)
  /help      show this message
  /exit      quit (Ctrl+C at the prompt also quits)
Anything else is sent to the agent as a task.
Ctrl+C during a task cancels it and restores every file it changed."""


def _print_result(result: AgentResult) -> None:
    print("\n=== Final answer ===\n" + (result.final_text or "(no text)"))
    print(f"\n[{result.stopped_reason}] steps={result.steps} tool_calls={result.tool_calls}")
    if result.files_changed:
        print(f"[files changed] {', '.join(result.files_changed)}")


def _repl(executor: Executor, client: genai.Client, model: str, max_steps: int, memory: SessionLog) -> int:
    """Read tasks until /exit. Every task gets a fresh chat plus a summary of earlier tasks."""
    print("Interactive mode. Type a task, or /help for commands.")
    while True:
        try:
            line = input("\ntask> ").strip()
        except (EOFError, KeyboardInterrupt):  # Ctrl+Z/Ctrl+D or Ctrl+C at the prompt
            print()
            return 0

        if not line:
            continue
        command = line.lower()
        if command in {"/exit", "/quit"}:
            return 0
        if command == "/help":
            print(REPL_HELP)
            continue
        if command == "/reset":
            memory.clear()
            print("[memory] cleared")
            continue
        if command == "/history":
            print(memory.render() or "(no earlier tasks remembered)")
            continue
        if line.startswith("/"):
            print(f"Unknown command: {line}. Type /help.")
            continue

        if len(memory):
            print(f"[memory] including {len(memory)} earlier task(s)")
        try:
            result = run_agent(
                task=line,
                executor=executor,
                client=client,
                model=model,
                max_steps=max_steps,
                context=memory.preamble(),
            )
        except KeyboardInterrupt:
            # run_agent has already restored the files this task touched.
            print("\n[interrupted] Task cancelled, its file changes were rolled back, "
                  "and it was not added to memory.")
            continue
        except Exception as e:  # e.g. non-429 API errors or network failures: keep the REPL alive
            print(f"\n[error] {type(e).__name__}: {e}")
            continue

        _print_result(result)
        memory.add(line, result)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the coding agent (REPL if no task is given).")
    parser.add_argument("task", nargs="?", default=None, help="Run this single task and exit.")
    parser.add_argument("--root", default=None, help="Workspace root (default: settings.workspace_root).")
    parser.add_argument("--model", default=None, help="Gemini model (default: settings.gemini_model).")
    parser.add_argument("--max-steps", type=int, default=None, help="Max model turns per task.")
    parser.add_argument("--memory", type=int, default=None,
                        help="REPL: earlier tasks to remember (default: settings.session_memory, 0 = off).")
    args = parser.parse_args()

    settings = Settings()  # type: ignore[call-arg]  # values come from .env
    # The only place that knows which Executor we use; Phase 2 swaps in E2BExecutor here.
    executor = LocalExecutor(root=args.root or settings.workspace_root, bash_path=settings.bash_path)
    client = genai.Client(api_key=settings.gemini_api_key)
    model = args.model or settings.gemini_model
    max_steps = args.max_steps or settings.max_steps

    print(f"[workspace] {executor.root}")
    print(f"[model] {model}")

    if args.task is None:
        memory_size = settings.session_memory if args.memory is None else args.memory
        return _repl(executor, client, model, max_steps, SessionLog(memory_size))

    try:
        result = run_agent(task=args.task, executor=executor, client=client, model=model, max_steps=max_steps)
    except KeyboardInterrupt:
        print("\n[interrupted] Task cancelled and its file changes were rolled back.")
        return 130  # conventional exit code for Ctrl+C
    _print_result(result)
    return 0 if result.stopped_reason == "done" else 1


if __name__ == "__main__":
    sys.exit(main())
