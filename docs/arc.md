# Notes: How to Build a Cloud Coding Agent

## 1. Core architecture

A cloud coding agent accepts a coding task, works on a repository independently, tests its changes, and creates a pull request.

It has six main components:

1. Interface: Accepts tasks from a web app, GitHub issue, or Slack.
2. Orchestrator: Queues tasks and assigns them to workers.
3. Agent loop: Communicates with the LLM and decides what to do next.
4. Tools: Allow the agent to execute commands, read and edit files, and search code.
5. Sandbox: An isolated cloud computer where the repository is cloned and modified.
6. GitHub integration: Commits changes and creates a pull request.

## 2. Technology stack

| Component               | Technology from the transcript |
| ----------------------- | ------------------------------ |
| Language                | TypeScript                     |
| Runtime/package manager | Bun                            |
| Monorepo                | Turborepo                      |
| LLM                     | Gemini through OpenRouter      |
| Sandbox                 | E2B                            |
| Version control         | Git and GitHub                 |

These are the technologies demonstrated, not mandatory choices.

## 3. Build the agent loop

The agent loop is the heart of the system.

Workflow:

1. Initialize conversation history with the system prompt and user task.
2. Send the conversation and available tool definitions to the LLM.
3. Receive the LLM's response.
4. If it requests a tool, execute that tool.
5. Append the tool result to the conversation history.
6. Call the LLM again.
7. Repeat until the LLM returns a final response or a limit is reached.

The LLM does not execute commands itself. It requests tool calls, and our application executes them.

## 4. Implement the tools

Start with four core tools:

- Bash: Execute commands, install packages, run tests, and use Git.
- Read: Read files and specific line ranges.
- Edit: Modify files using controlled search-and-replace operations.
- Search: Find relevant code across the repository.

Bash alone can perform many of these operations, but dedicated tools can provide better validation and more predictable behavior.

Important tool-design rules:

- Set timeouts and handle failed commands.
- Return stdout, stderr, and exit codes.
- Truncate excessive output.
- Validate tool arguments.
- Return actionable errors to the LLM.

## 5. Move execution into a sandbox

A local agent runs commands on your machine. A cloud agent runs them inside an isolated environment.

Workflow:

1. Create a sandbox using E2B or another provider.
2. Clone the GitHub repository into it.
3. Forward the agent's tool calls to the sandbox.
4. Return execution results to the LLM.
5. Preserve the completed changes.
6. Destroy the sandbox after the work is safely saved.

Sandboxes isolate tasks, reduce interference, and limit the impact of potentially dangerous commands.

For production, also enforce CPU, memory, disk, runtime, and network limits. Keep long-lived API keys outside the sandbox.

## 6. Connect GitHub

Sandbox changes are temporary, so the completed work must be published before the sandbox is destroyed.

1. Create a task-specific branch.
2. Modify the repository.
3. Run tests and inspect the diff.
4. Commit and push the changes.
5. Open a pull request.
6. Return the PR URL and task status to the user.

Use repository-scoped permissions and short-lived credentials wherever possible.

## 7. Handle context and failures

Large codebases cannot be loaded entirely into the LLM's context window.

Use targeted code search, read relevant files, limit tool output, and summarize older conversation history when necessary.

Also implement:

- Maximum agent iterations and execution time.
- Tool timeouts and error recovery.
- Task cancellation.
- Test execution and correction.
- Durable task state and retries for long-running tasks.

## 8. Scale into a complete cloud agent

Once the basic workflow works, add:

- Orchestration: Task queues, workers, status tracking, and retries.
- Context engineering: Repository understanding, summaries, and targeted retrieval.
- Planning and evaluation: Break down tasks, test changes, and verify results.
- Security: Sandbox isolation, least-privilege access, and network restrictions.
- Observability: Logs, execution times, failures, and LLM costs.
- Optimizations: Sandbox snapshots, warm pools, and parallel execution of independent tool calls.
- Integrations: Browser automation and MCP servers for external services.

## Recommended implementation order

1. Build the agent loop with an LLM and Bash tool.
2. Add reliable file-reading, editing, and search tools.
3. Move command execution into an E2B sandbox.
4. Implement GitHub commits and pull-request creation.
5. Add testing, context management, and error recovery.
6. Add orchestration, security, and production optimizations.

Key takeaway: The agent loop provides the intelligence, tools enable action, the sandbox provides isolated execution, and GitHub preserves and delivers the result. Orchestration and context management make the system reliable at scale.