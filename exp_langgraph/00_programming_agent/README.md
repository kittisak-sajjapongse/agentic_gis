# pg_agent.py

## Setup (pip)
1) Create and activate a virtual environment.
2) Install minimal dependencies:

```bash
python -m venv .venv
. .venv/bin/activate
pip install langchain-openai langgraph langchain-experimental python-dotenv
```

3) Set your API key in `.env`:

```
OPENAI_API_KEY=your_key_here
```

4) Run:

```bash
python pg_agent.py
```

## What it does
`pg_agent.py` builds a LangGraph ReAct-style workflow with two LLM roles:
- **Code agent**: Writes Python code, calls the Python REPL tool, and produces the final JSON response.
- **Validator agent (manager)**: Validates that the final response is strict JSON with the schema:
  `{ "message": string, "is_error": boolean, "error_message": string }`.

If the validator rejects the response, the graph loops back to the code agent for a corrected output.

## Graph
```
START
  |
  v
AGENT (code)
  | tool_calls?
  | yes
  v
TOOLS (python_repl)
  |
  v
AGENT (code)
  | tool_calls?
  | no
  v
VALIDATE (manager)
  | valid?
  | yes --------> END
  |
  no
  |
  v
AGENT (code)
```
