from typing import List, Literal, Optional

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel

from agents.output_producer_agent import OpManager
from IAgentState import IAgentState
from runtime.settings import AppSettings
from tools.mcp_tools import DockerMCPToolProvider
from tools.tool_executor import ToolExecutorNode

OUTPUT_PRODUCER_GRAPH_NAME = "OUTPUT_PRODUCER_GRAPH"
OP_CLARIFICATION_INTERRUPT_TYPE = "op_clarification"


class OpOutput(BaseModel):
    output_type: Literal["GEOPARQUET_LAYER", "GEOTIFF_LAYER", "REPORTS", "CHARTS"]
    description: str
    path: str


class OpState(IAgentState):
    clarification_question: Optional[str]
    decline_message: Optional[str]
    outputs: Optional[List[OpOutput]]
    code: Optional[str]


def next_step(state: OpState) -> str:
    if len(state["_messages"][-1].tool_calls) > 0:
        return "tools"
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

    workflow.add_edge(START, op_manager.name)
    workflow.add_conditional_edges(
        op_manager.name,
        next_step,
        {
            "tools": "tools",
            "ask_user": "ask_user",
            "end": END,
        },
    )
    workflow.add_edge("tools", op_manager.name)
    workflow.add_edge("ask_user", op_manager.name)

    return workflow.compile()
