import json
from typing import Optional, Literal, List
from IAgentState import IAgentState
from AgentBase import AgentBase
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

OUTPUT_PRODUCER_GRAPH_NAME = "OUTPUT_PRODUCER_GRAPH"
OP_CLARIFICATION_INTERRUPT_TYPE = "op_clarification"

class OpOutput(BaseModel):
    output_type: Literal["GEOPARQUET_LAYER", "GEOTIFF_LAYER", "REPORTS", "CHARTS"]
    description: str
    path: str

class OpState(IAgentState):
    clarification_question: Optional[str]
    decline_message: Optional[str]
    outputs: List[OpOutput]
    code: str
    

class OpManager(AgentBase[OpState]):
    NAME = "OUTPUT_PRODUCER_MANAGER"

    def __init__(self, llm: BaseChatModel, name: str = NAME):
        super().__init__(llm, name)
        self._system_prompt = SystemMessage(
            content="""
            You are a Geographic Information System (GIS) specialist with expertise in Python.
            
            You goal is to answer user's GIS-related query.
            You may do one or more of the following to answer user's query:
                - Write a Python script to create new layers to show on map
                - Write a Python script to create visualizions or charts and export them in a .PNG format
                - Perform calculation

            Your task step is to achieve the goal:
            1. Determine the number of outputs the user require. The outputs is a list of instances.
               Each instance can be one of (1) GEOPARQUET_LAYER, (2) GEOTIFF_LAYER, (3) REPORTS, or (4) CHARTS
            2. Make a list of outputs and descriptions for all of the outputs
            3. Determine if you need to create a Python script to answer user's query
            4. Create a Python script to generate outputs if you detemine so
            Note: 
            - Each task step can be an iterative loop where you ask questions to the user if there's any ambiguity or unclear statements until you have a clear idea what user the needs, then move to the next task step.
            - You may ask multiple questions in one response

            Output Requirements:
            - You response will be a JSON string only
            - You will respond only in English with some exceptions as indicated below
            - Respond without markup, without annotation, and without explanation outside the JSON structure
            - You wil always respond using the JSON structure below:
            {
                "outputs": [
                    {
                        "output_type": <GEOPARQUET, GEOTIFF, REPORTS, or CHARTS>,
                        "description": <description of the output>,
                        "path": <path to output file generated from your script>
                    },
                    ...
                ],
                "code": <STRING - Python code that generates all the outputs>,
                "clarification_question": <STRING - clarifying question, null if you don't have any question. You will respond in the language the user uses>,
                "decline_message": <STRING - reason if you cannot fulfil use's query for any reasons, null if you can fulfil the query>,
            }
            """
        )

    def handleMessage(self, state):
        input_js = json.dumps([l for l in state["selected_layers"]])
        input_prompt = SystemMessage(content=f"""
        You are given the input files below:
        {input_js}
        """)
        response = self._llm.invoke([self._system_prompt, input_prompt] + state["_messages"])
        resp_js = json.loads(response.content)
        return {
            "clarification_question": resp_js["clarification_question"],
            "decline_message": resp_js["decline_message"],
            "code": resp_js["code"],
            "outputs": resp_js["outputs"],
        }
    
def needs_tool_or_human(state: OpState) -> str:
    # if len(state["_messages"][-1].tool_calls) > 0:
    #     return "tools"
    if state.get("clarification_question") is not None:
        return "ask_user"
    return "end"

    
def ask_user_node(state: OpState) -> dict:
    # Use a typed interrupt payload so callers can reliably identify this exact
    # pause reason even when multiple interrupt sources exist in the same thread.
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

def build_output_producer_graph():
    workflow = StateGraph(OpState)
    op_manager = OpManager(ChatOpenAI(model="gpt-4o", temperature=0))

    workflow.add_node(op_manager.name, op_manager)
    workflow.add_node("ask_user", ask_user_node)

    workflow.add_edge(START, op_manager.name)
    workflow.add_conditional_edges(
        op_manager.name,
        needs_tool_or_human,
        {
            "ask_user": "ask_user",
            "end": END,
        },
    )
    workflow.add_edge("ask_user", op_manager.name)

    return workflow.compile()