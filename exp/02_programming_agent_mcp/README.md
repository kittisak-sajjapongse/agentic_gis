# Programming Agent (MCP + Docker)

This example replaces the in-process Python REPL tool with a local MCP server
that runs Python code inside a Docker container. The container has internet
access (for `pip`) and a host-mounted directory for persisted outputs.

## Requirements

- Docker (or compatible CLI) installed and running
- Python 3.10+
- `OPENAI_API_KEY` in `.env`

## Install dependencies

MCP server:

```bash
pip install mcp
```

Agent:

```bash
pip install langchain-openai langgraph langgraph-prebuilt langchain-mcp-adapters python-dotenv
```

## Start the MCP server (SSE on localhost)

```bash
python exp/02_programming_agent_mcp/mcp_server.py
```

## Run the agent (in another terminal)

```bash
python exp/02_programming_agent_mcp/pg_agent.py
```

## MCP server configuration

Environment variables (optional):
- `MCP_DOCKER_IMAGE` (default: `python:3.11-slim`)
- `MCP_DOCKER_HOST_DIR` (default: `exp/02_programming_agent_mcp/runs`)
- `MCP_DOCKER_TIMEOUT_S` (default: `60`)
- `MCP_TRANSPORT` (default: `sse`)
- `MCP_HOST` (default: `127.0.0.1`)
- `MCP_PORT` (default: `8000`)
- `MCP_MOUNT_PATH` (default: `/`)

## Agent configuration

Environment variables (optional):
- `MCP_SERVER_URL` (default: `http://127.0.0.1:8000/sse`)

## MCP tools

Tool: `run_python`
- Inputs: `code` (string), `requirements` (list[str], optional),
  `workdir` (string, default `/data`), `timeout_s` (int)
- Outputs: `ok`, `exit_code`, `stdout`, `stderr`, `command`, `run_id`, `run_dir`

Tool: `list_runs`
- Lists run directories stored on the host mount.

## Notes

- The host mount directory is shared with the container for persistence.
- Each call creates a new run directory that is not deleted automatically.
- This is container isolation, not a hardened sandbox; only mount a dedicated
  directory for untrusted code.
