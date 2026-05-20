from typing import Optional

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from agents.output_producer_agent import OpManager
from domain.state_models import OpState
from runtime.settings import AppSettings
from tools.mcp_tools import DockerMCPToolProvider
from tools.tool_executor import ToolExecutorNode

OUTPUT_PRODUCER_GRAPH_NAME = "OUTPUT_PRODUCER_GRAPH"
OP_CLARIFICATION_INTERRUPT_TYPE = "op_clarification"

def next_step(state: OpState) -> str:
    last_message = state["_messages"][-1] if state.get("_messages") else None
    tool_calls = getattr(last_message, "tool_calls", None)
    if tool_calls and len(tool_calls) > 0:
        return "tools"
    if state.get("op_requires_tool_call"):
        return "enforce_tool_call"
    if state.get("clarification_question") is not None:
        return "ask_user"
    return "end"


def ask_user_node(state: OpState) -> dict:
    user_answer = interrupt(
        {
            "type": OP_CLARIFICATION_INTERRUPT_TYPE,
            "source": f"{OUTPUT_PRODUCER_GRAPH_NAME}.ask_user",
            "question": state["clarification_question"],
        }
    )
    return {
        "_messages": [HumanMessage(content=user_answer)],
        "clarification_question": None,
    }


def enforce_tool_call_node(_: OpState) -> dict:
    return {
        "_messages": [
            HumanMessage(
                content=(
                    "You returned non-empty code but did not call any Docker MCP tool yet. "
                    "Call run_python now (with required host_mount_dir) to execute the code "
                    "before returning final JSON."
                )
            )
        ],
        "op_requires_tool_call": False,
    }


async def build_output_producer_graph(
    tool_provider: Optional[DockerMCPToolProvider] = None,
):
    workflow = StateGraph(OpState)
    provider = tool_provider or DockerMCPToolProvider(AppSettings.from_env())
    mcp_tools = await provider.get_tools()
    op_manager = OpManager(ChatOpenAI(model="gpt-4o", temperature=0), tools=mcp_tools)
    op_tool_node = ToolExecutorNode(mcp_tools, log_prefix="OUTPUT_PRODUCER_TOOL")

    workflow.add_node(op_manager.name, op_manager)
    workflow.add_node("tools", op_tool_node)
    workflow.add_node("ask_user", ask_user_node)
    workflow.add_node("enforce_tool_call", enforce_tool_call_node)

    workflow.add_edge(START, op_manager.name)
    workflow.add_conditional_edges(
        op_manager.name,
        next_step,
        {
            "tools": "tools",
            "enforce_tool_call": "enforce_tool_call",
            "ask_user": "ask_user",
            "end": END,
        },
    )
    workflow.add_edge("tools", op_manager.name)
    workflow.add_edge("ask_user", op_manager.name)
    workflow.add_edge("enforce_tool_call", op_manager.name)

    return workflow.compile()
