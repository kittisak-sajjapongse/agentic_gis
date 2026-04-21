import json
import pprint
from typing import Dict, List, Optional

import chainlit as cl
from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt

from AgentBase import AgentBase
from GisCollection import GIS_COLLECTION
from IAgentState import IAgentState

load_dotenv()


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
        - You response will be a JSON string
        - Respond without markup or explanation outside the JSON structure
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
    user_answer = interrupt({"question": state["clarification_question"]})
    return {
        "_messages": [HumanMessage(content=user_answer)],
        "clarification_question": None,
    }


def build_graph():
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

    return workflow.compile(checkpointer=MemorySaver())


@cl.on_chat_start
async def on_chat_start():
    graph = build_graph()
    thread_id = cl.user_session.get("id")
    cl.user_session.set("graph", graph)
    cl.user_session.set("config", {"configurable": {"thread_id": thread_id}})
    cl.user_session.set("is_interrupted", False)


@cl.on_message
async def on_message(message: cl.Message):
    graph = cl.user_session.get("graph")
    config = cl.user_session.get("config")
    is_interrupted = cl.user_session.get("is_interrupted")

    if is_interrupted:
        inputs = Command(resume=message.content)
    else:
        inputs = {"_messages": [HumanMessage(content=message.content)]}

    for event in graph.stream(inputs, config=config):
        for node_name, node_state in event.items():
            print(f"=== Node: {node_name} ===")
            pprint.pprint(node_state)
            print("-" * 80)

    state = graph.get_state(config)

    # `state.next` lists scheduled next node(s); if it includes `ask_user`,
    # the graph is paused at interrupt() and waiting for human input to resume.
    if state.next and "ask_user" in state.next:
        cl.user_session.set("is_interrupted", True)
        await cl.Message(
            author="AI (Needs Clarification)",
            content=state.values.get("clarification_question"),
        ).send()
        return

    cl.user_session.set("is_interrupted", False)
    response_payload = {
        "clarification_question": state.values.get("clarification_question"),
        "gis_related": state.values.get("gis_related"),
        "decline_message": state.values.get("decline_message"),
        "selected_layers": state.values.get("selected_layers"),
        "general_layers": state.values.get("general_layers"),
        "accepted": state.values.get("accepted"),
        "query_summary": state.values.get("query_summary"),
    }
    await cl.Message(content=json.dumps(response_payload, indent=2)).send()
