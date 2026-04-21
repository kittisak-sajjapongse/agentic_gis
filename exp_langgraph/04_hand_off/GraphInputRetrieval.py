import json

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models import BaseChatModel
from AgentBase import AgentBase
from IAgentState import IAgentState
from GisCollection import GIS_COLLECTION
from langchain_core.tools import tool
from TestUtils import run_test_update, create_png_graph_viz
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from typing import List, Dict
from langchain_openai import ChatOpenAI

from dotenv import load_dotenv

load_dotenv()

class IrState(IAgentState):
    clarification_question: str
    gis_related: bool
    decline_message: str
    selected_layers: List[Dict]
    general_layers: bool
    accepted: bool

@tool
def search_gis_collection():
    """
    Retrieve entries of GIS layers in the collection
    """
    return json.dumps(GIS_COLLECTION)

tools = [search_gis_collection]

class IrManager(AgentBase[IrState]):
    NAME = "INPUT_RETRIEVAL_MANAGER"

    def __init__(self, llm: BaseChatModel, name: str=NAME):
        super().__init__(llm, name)
        self._system_prompt = SystemMessage(content=f"""
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
        Note: Each task step can be an iterative loop where you ask questions to the user if there's any ambiguity or unclear statements until you have a clear idea what user the needs, then move to the next task step.

        Output Requirements:
        - You response will be a JSON string
        - Respond without markup or explanation outside the JSON structure
        - You wil always respond using the JSON structure below:
        {{
            "clarification_question": <STRING - clarifying question, null if you don't have any question>,
            "gis_related": <BOOLEAN - true if the prompt is a GIS-related question>,
            "decline_message": <STRING - reason if the prompt is decline, null if the prompt is GIS-related question>,
            "selected_layers": [
                {{
                    "path": <file path of the selected layers>,
                    "type": <GEOPARQUET or GEOTIFF>
                }},
                ...
            ] <This field is null if you haven't decided yet what layers to be included>,
            "general_layers": <BOOLEAN - true if all layer required are of general knowledge>
            "accepted": <BOOLEAN - true if user's prompt is accepted, null if not determined yet>
        }}

        """)

    def handleMessage(self, state: IrState):
        instruction = state["user_query"]
        messages = [self._system_prompt, instruction]
        self._llm.bind_tools(tools)
        response = self._llm.invoke(messages)
        resp_js = json.loads(response.content)
        return {
            "clarification_question": resp_js["clarification_question"],
            "gis_related": resp_js["gis_related"],
            "decline_message": resp_js["decline_message"],
            "selected_layers": resp_js["selected_layers"],
            "general_layers": resp_js["general_layers"],
            "accepted": resp_js["accepted"],
            "_messages": [response]
        }
    
def main():
    workflow = StateGraph(IrState)

    ir_manager = IrManager(ChatOpenAI(model="gpt-4o", temperature=0))
    
    workflow.add_node(ir_manager.name, ir_manager)
    workflow.add_node("tools", ToolNode(tools))

    workflow.add_edge(START, ir_manager.name)
    workflow.add_conditional_edges(
        ir_manager.name,
        lambda state: len(state["_messages"][-1].tool_calls) > 0,
        {True: "tools", False: END}
    )
    workflow.add_edge("tools", ir_manager.name)

    graph = workflow.compile()
    create_png_graph_viz(graph)

    user_query = HumanMessage(content="""
        Please show the temperature of Sriracha on the map
    """)
    run_test_update(graph, {"user_query":user_query})

if __name__ == "__main__":
    main()