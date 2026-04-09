from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

load_dotenv()


class AgentState(TypedDict):
    # TypedDict supports partial updates per node; dataclass would require full-state returns
    # or custom merge logic, so partial patching would not work out of the box.
    user_request: str
    requirement_summary: str
    design_spec: str
    html: str
    output_path: str
    accepted: bool


def _designer_agent(design_brief: str) -> str:
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    # Improvement idea: use a structured schema (JSON) for theme/layout/functions validation.
    # Improvement idea: add a private reflection loop with a max-iterations guard.
    prompt = SystemMessage(content=(
        "You are a web designer. Create a concise design spec for a single-page HTML site.\n"
        "Return ONLY the design spec with sections:\n"
        "Theme:\nLayout:\nFunctions:\nTypography:\nColor Palette:\n"
        "Keep it text-only; no images. If illustration is needed, use ASCII or SVG.\n"
    ))
    response = llm.invoke([prompt, HumanMessage(content=design_brief)])
    return response.content.strip()


def _manager_accepts_design(design_spec: str) -> bool:
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    # Improvement idea: enforce a checklist-based scoring and auto-reject on missing sections.
    prompt = SystemMessage(content=(
        "You are a manager. Accept the design only if it includes all sections:\n"
        "Theme, Layout, Functions, Typography, Color Palette.\n"
        "Reply ONLY with 'ACCEPT' or 'REJECT'."
    ))
    verdict = llm.invoke([prompt, HumanMessage(content=design_spec)]).content.strip()
    return verdict == "ACCEPT"


def _coder_agent(design_spec: str) -> str:
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    # Improvement idea: validate output via HTML parser and auto-correct on errors.
    prompt = SystemMessage(content=(
        "You are a front-end coder. Create a single HTML file with embedded CSS.\n"
        "Follow the design spec exactly. Use text-only content (no images).\n"
        "If illustration is needed, use ASCII art or SVG.\n"
        "Return ONLY the full HTML document."
    ))
    response = llm.invoke([prompt, HumanMessage(content=design_spec)])
    return response.content.strip()

def _manager_accept_request_node(state: AgentState):
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    # Improvement idea: add a structured rubric and a fallback heuristic.
    prompt = SystemMessage(content=(
        "You are a manager. Decide if the user's request can be fulfilled with a "
        "single-page HTML document with embedded CSS and text-only content. "
        "Reply ONLY with 'ACCEPT' or 'REJECT'."
    ))
    verdict = llm.invoke([prompt, HumanMessage(content=state["user_request"])]).content.strip()
    accepted = verdict == "ACCEPT"
    summary = ""
    if accepted:
        summary_prompt = SystemMessage(content=(
            "Summarize the user's requirements for a single-page HTML site. "
            "Be concise and preserve all constraints."
        ))
        summary = llm.invoke([summary_prompt, HumanMessage(content=state["user_request"])]).content.strip()
        # Self-reflection: internal check before handing to designer.
        reflection_prompt = SystemMessage(content=(
            "Check whether the summary captures all requirements. "
            "If anything is missing or unclear, rewrite the summary. "
            "Return ONLY the corrected summary."
        ))
        summary = llm.invoke([reflection_prompt, HumanMessage(content=summary)]).content.strip()
    # Partial state update: only these fields are patched; others remain unchanged.
    return {"accepted": accepted, "requirement_summary": summary}


def _designer_node(state: AgentState):
    design_spec = _designer_agent(state["requirement_summary"] or state["user_request"])
    # Partial state update: patch only the design_spec.
    return {"design_spec": design_spec}


def _manager_review_design_node(state: AgentState):
    accepted = _manager_accepts_design(state["design_spec"])
    # Partial state update: patch only the accepted flag.
    return {"accepted": accepted}


def _coder_node(state: AgentState):
    html = _coder_agent(state["design_spec"])
    # Partial state update: patch only the HTML output.
    return {"html": html}


def _writer_node(state: AgentState, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "index.html"
    output_path.write_text(state["html"], encoding="utf-8")
    # Partial state update: patch only the output_path.
    return {"output_path": str(output_path)}


def _route_on_accept(state: AgentState) -> str:
    return "continue" if state.get("accepted") else "end"


def build_graph(output_dir: Path):
    workflow = StateGraph(AgentState)
    workflow.add_node("manager_accept", _manager_accept_request_node)
    workflow.add_node("designer", _designer_node)
    workflow.add_node("manager_review", _manager_review_design_node)
    workflow.add_node("coder", _coder_node)
    workflow.add_node("writer", lambda state: _writer_node(state, output_dir))

    workflow.add_edge(START, "manager_accept")
    workflow.add_conditional_edges(
        "manager_accept",
        _route_on_accept,
        {"continue": "designer", "end": END},
    )
    workflow.add_edge("designer", "manager_review")
    workflow.add_conditional_edges(
        "manager_review",
        _route_on_accept,
        {"continue": "coder", "end": END},
    )
    workflow.add_edge("coder", "writer")
    workflow.add_edge("writer", END)
    return workflow.compile()


def run_multi_agent(user_request: str, output_dir: Path) -> Path | None:
    graph = build_graph(output_dir)
    initial_state: AgentState = {
        "user_request": user_request,
        "requirement_summary": "",
        "design_spec": "",
        "html": "",
        "output_path": "",
        "accepted": False,
    }

    final_state = None
    for event in graph.stream(initial_state):
        for node_name, node_state in event.items():
            final_state = node_state
            if node_name == "manager_accept":
                if node_state.get("accepted"):
                    print("Manager: Request accepted. Assigning to designer...")
                else:
                    print("Manager: Request declined. Only single-page HTML requests are supported.")
            elif node_name == "designer":
                print("Manager: Design received from designer.")
            elif node_name == "manager_review":
                if node_state.get("accepted"):
                    print("Manager: Design accepted. Assigning to coder...")
                else:
                    print("Manager: Design rejected. Ask the designer to revise.")
            elif node_name == "coder":
                print("Manager: Code received from coder.")
            elif node_name == "writer":
                print(f"Manager: Wrote HTML to {node_state.get('output_path')}")

    if final_state and final_state.get("output_path"):
        return Path(final_state["output_path"])
    return None


if __name__ == "__main__":
    # request = "Create a single-page HTML for a minimalist cafe landing page."
    request = "Create a basic SQL tutorial and challenges page that looks catchy and colorful to attract teens"
    run_multi_agent(request, Path("exp/01_message_passing/output"))
