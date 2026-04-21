import json
from typing import Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt

from AgentBase import AgentBase
from GisCollection import GIS_COLLECTION
from IAgentState import IAgentState

INPUT_RETRIEVAL_GRAPH_NAME = "INPUT_RETRIEVAL_GRAPH"
IR_CLARIFICATION_INTERRUPT_TYPE = "ir_clarification"


class IrState(IAgentState):
    clarification_question: Optional[str]
    gis_related: Optional[bool]
    decline_message: Optional[str]
    selected_layers: Optional[List[Dict]]
    general_layers: Optional[bool]
    accepted: Optional[bool]
    query_summary: Optional[str]


@tool
def search_gis_collection():
    """
    Retrieve entries of GIS layers in the collection
    """
    return json.dumps(GIS_COLLECTION)


tools = [search_gis_collection]


class IrManager(AgentBase[IrState]):
    NAME = "INPUT_RETRIEVAL_MANAGER"

    def __init__(self, llm: BaseChatModel, name: str = NAME):
        super().__init__(llm, name)
        self._system_prompt = SystemMessage(
            content="""
        You are an expert technical manager in the area of Geographic Information System (GIS).
        You own a collection of GIS data in the GeoParquet format for vector layers and the GeoTIFF format for raster layers.

        You goal is to find required GIS layers that can be used as inputs or answer user's query.
        The GIS layers specified from you may be used to construct a Python script to answer user's query if the layer
        requires processing or analysis.

        You task steps to achieve the goal:
        1. Determine if user's prompt is a GIS-related question. If the prompt is not a question or is not GIS-related, simply decline and give a reason.
        2. Search your collection using tools provided to find useful GIS layers
        3. Note the details of the layers you selected and fill the detail into your response structure
        4. If you can't find any suitable layer from the collection, determine and indicate if the layers required are of general knowledge
        5. Accept user's prompt only if (1) the prompt is GIS-related, and (2) all required layers can be found
        6. If the user's prompt is not accepted, add reason in the declining message
        7. If the user's prompt is accepted, rewrite summary of user's request once you find out more information from the user.
        Note: 
        - Each task step can be an iterative loop where you ask questions to the user if there's any ambiguity or unclear statements until you have a clear idea what user the needs, then move to the next task step.
        - You may ask multiple questions in one response

        Output Requirements:
        - You response will be a JSON string only
        - Respond without markup, without annotation, and without explanation outside the JSON structure
        - You wil always respond using the JSON structure below:
        {
            "clarification_question": <STRING - clarifying question, null if you don't have any question>,
            "gis_related": <BOOLEAN - true if the prompt is a GIS-related question>,
            "decline_message": <STRING - reason if the prompt is decline, null if the prompt is GIS-related question>,
            "selected_layers": [
                {
                    "path": <file path of the selected layers>,
                    "type": <GEOPARQUET or GEOTIFF>
                },
                ...
            ] <This field is null if you haven't decided yet what layers to be included>,
            "general_layers": <BOOLEAN - true if all layer required are of general knowledge>,
            "accepted": <BOOLEAN - true if user's prompt is accepted, null if not determined yet>
            "query_summary": <STRING - Summary of user's request once accepted, null if not determined yet>
        }
        """
        )

    def handleMessage(self, state: IrState):
        llm_with_tools = self._llm.bind_tools(tools)
        response = llm_with_tools.invoke([self._system_prompt] + state["_messages"])
        print("=" * 80)
        print(response.content)
        print("=" * 80)

        if response.tool_calls:
            return {"_messages": [response]}

        content = response.content if isinstance(response.content, str) else ""
        if not content.strip():
            raise ValueError("LLM returned empty content without tool_calls")

        resp_js = json.loads(content)
        return {
            "clarification_question": resp_js["clarification_question"],
            "gis_related": resp_js["gis_related"],
            "decline_message": resp_js["decline_message"],
            "selected_layers": resp_js["selected_layers"],
            "general_layers": resp_js["general_layers"],
            "accepted": resp_js["accepted"],
            "query_summary": resp_js["query_summary"],
            "_messages": [response],
        }


def needs_tool_or_human(state: IrState) -> str:
    if len(state["_messages"][-1].tool_calls) > 0:
        return "tools"
    if state.get("clarification_question") is not None:
        return "ask_user"
    return "end"


def ask_user_node(state: IrState) -> dict:
    # Use a typed interrupt payload so callers can reliably identify this exact
    # pause reason even when multiple interrupt sources exist in the same thread.
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
    ir_manager = IrManager(ChatOpenAI(model="gpt-4o", temperature=0))

    workflow.add_node(ir_manager.name, ir_manager)
    workflow.add_node("tools", ToolNode(tools, messages_key="_messages"))
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
