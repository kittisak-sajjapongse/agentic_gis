# 04_hand_off

Refactored LangGraph GIS hand-off example with explicit OOP boundaries for:
- domain contracts/data
- agent behavior
- tool providers/execution
- graph wiring
- runtime configuration

## Architecture

This example is structured so each layer has one responsibility:

- `domain/`: business data and shared workflow contracts
- `agents/`: LLM-driven manager classes (`IrManager`, `OpManager`)
- `tools/`: tool providers and reusable tool execution node
- `graphs/`: graph topology/routing and top-level graph composition
- `runtime/`: environment settings and dependency construction
- `main.py` / `main_cli.py`: CLI entrypoints only

## Directory Structure

```text
04_hand_off/
├─ agents/
│  ├─ input_retrieval_agent.py      # IrManager behavior/prompt + response parsing
│  └─ output_producer_agent.py      # OpManager behavior/prompt + response parsing
├─ domain/
│  ├─ gis_catalog.py                # GIS_COLLECTION data source
│  ├─ state_models.py               # IAgentState, IrState, OpState, GISFile, OpOutput
│  └─ __init__.py
├─ graphs/
│  ├─ input_retrieval_graph.py      # IR subgraph nodes, routing, compile
│  ├─ output_producer_graph.py      # OP subgraph nodes, routing, compile
│  ├─ main_graph.py                 # top-level graph composition
│  └─ __init__.py
├─ tools/
│  ├─ base.py                       # ToolProvider abstraction
│  ├─ gis_catalog_tools.py          # GIS catalog tool(s)
│  ├─ mcp_tools.py                  # DockerMCPToolProvider
│  ├─ tool_executor.py              # ToolExecutorNode wrapper around ToolNode
│  └─ __init__.py
├─ runtime/
│  ├─ settings.py                   # AppSettings.from_env()
│  ├─ container.py                  # AppContainer factories
│  └─ __init__.py
├─ main.py                          # CLI launcher
├─ main_cli.py                      # CLI app
└─ mcp_server.py                    # Docker-backed MCP server
```

## Graph Flow

1. `graphs.main_graph.build_main_graph()` composes two subgraphs:
   - `INPUT_RETRIEVAL_GRAPH`
   - `OUTPUT_PRODUCER_GRAPH`
2. Input retrieval validates GIS relevance and selected layers.
3. If accepted, output producer may call MCP tools for code execution.
4. Both subgraphs can pause via typed interrupts for clarification.

## How We Structure This Example

### 1. Keep state contracts in `domain`
State models are shared contracts across agents, tools, graphs, and interfaces. They do not belong to any single graph file.

### 2. Keep agent classes in `agents`
Agent modules should only contain LLM behavior:
- system prompts
- tool binding
- response parsing/validation

No graph topology logic in agents.

### 3. Keep tool wiring in `tools`
Tool providers own integration details (e.g., MCP client initialization). Graphs should ask providers for tools, not construct integration internals inline.

### 4. Keep graph topology in `graphs`
Graph modules define:
- node functions
- routing functions
- edge wiring
- compile step

No business data definitions in graph modules.

### 5. Keep entrypoints thin
`main.py` and `main_cli.py` should orchestrate session/input-output only.

## Run

### CLI
```bash
python main.py
```

### HTTP API (POC)
```bash
python main_api.py
```

### MCP server (Docker tools)
```bash
python mcp_server.py
```

### Build MCP base image (recommended for faster runs)
```bash
scripts/build_mcp_base_image.sh
```

## Environment

Common env vars used by this example:
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (optional, default in runtime settings)
- `LLM_TEMPERATURE` (optional)
- `MCP_SERVER_URL` (optional)
- `DOCKER_MCP_SERVER_NAME` (optional)
- `DATA_MOUNT_DIR` (optional)
- `MCP_DOCKER_IMAGE` (optional, default `agentic-gis-mcp-python:latest`)

## Extension Guide

### Add a new tool
1. Implement provider/tool under `tools/`.
2. Inject tools into the target graph builder.
3. Keep execution via `ToolExecutorNode` for consistent behavior/logging.

### Add a new agent
1. Create class in `agents/` extending `AgentBase`.
2. Add/extend state models in `domain/state_models.py` if needed.
3. Wire it into a graph in `graphs/`.

### Add a new graph stage
1. Create a new subgraph module in `graphs/`.
2. Compose it in `graphs/main_graph.py`.
3. Keep `main.py` and `main_cli.py` unchanged except for payload display as needed.
