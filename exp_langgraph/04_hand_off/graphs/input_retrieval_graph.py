from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from agents.input_retrieval_agent import IrManager
from domain.state_models import IrState
from tools.gis_catalog_tools import search_gis_collection
from tools.tool_executor import ToolExecutorNode

INPUT_RETRIEVAL_GRAPH_NAME = "INPUT_RETRIEVAL_GRAPH"
IR_CLARIFICATION_INTERRUPT_TYPE = "ir_clarification"

tools = [search_gis_collection]


def needs_tool_or_human(state: IrState) -> str:
    if len(state["_messages"][-1].tool_calls) > 0:
        return "tools"
    if state.get("clarification_question") is not None:
        return "ask_user"
    return "end"


def ask_user_node(state: IrState) -> dict:
    user_answer = interrupt(
        {
            "type": IR_CLARIFICATION_INTERRUPT_TYPE,
            "source": f"{INPUT_RETRIEVAL_GRAPH_NAME}.ask_user",
            "question": state["clarification_question"],
        }
    )
    return {
        "_messages": [HumanMessage(content=user_answer)],
        "clarification_question": None,
    }


def build_input_retrieval_graph():
    workflow = StateGraph(IrState)
    ir_manager = IrManager(ChatOpenAI(model="gpt-4o", temperature=0), tools=tools)

    workflow.add_node(ir_manager.name, ir_manager)
    workflow.add_node("tools", ToolExecutorNode(tools))
    workflow.add_node("ask_user", ask_user_node)

    workflow.add_edge(START, ir_manager.name)
    workflow.add_conditional_edges(
        ir_manager.name,
        needs_tool_or_human,
        {"tools": "tools", "ask_user": "ask_user", "end": END},
    )
    workflow.add_edge("tools", ir_manager.name)
    workflow.add_edge("ask_user", ir_manager.name)

    return workflow.compile()
