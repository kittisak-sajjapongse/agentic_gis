# msg_passing.py

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
python exp/01_message_passing/msg_passing.py
```

## What it does
`msg_passing.py` builds a LangGraph workflow with three agents:
- **Manager (Agent #1)**: Accepts or rejects the request, summarizes requirements, validates the design, and writes output.
- **Designer (Agent #2)**: Produces the theme, layout, and functions for a single-page HTML site.
- **Coder (Agent #3)**: Generates the HTML file based on the approved design.

The manager only forwards final artifacts (summary, design, HTML) between agents to keep message passing minimal. The manager also performs a short self-reflection step to refine the requirement summary before handing it to the designer.

## Graph
```
START
  |
  v
MANAGER_ACCEPT
  | accepted?
  | yes
  v
DESIGNER
  |
  v
MANAGER_REVIEW
  | accepted?
  | yes
  v
CODER
  |
  v
WRITER
  |
  v
END
```
