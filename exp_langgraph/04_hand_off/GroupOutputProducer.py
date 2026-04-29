import json
import os
from typing import List, Literal, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt
from pydantic import BaseModel

from AgentBase import AgentBase
from IAgentState import IAgentState

OUTPUT_PRODUCER_GRAPH_NAME = "OUTPUT_PRODUCER_GRAPH"
OP_CLARIFICATION_INTERRUPT_TYPE = "op_clarification"
DOCKER_MCP_SERVER_NAME = "docker-python"


class OpOutput(BaseModel):
    output_type: Literal["GEOPARQUET_LAYER", "GEOTIFF_LAYER", "REPORTS", "CHARTS"]
    description: str
    path: str


class OpState(IAgentState):
    clarification_question: Optional[str]
    decline_message: Optional[str]
    outputs: Optional[List[OpOutput]]
    code: Optional[str]


_docker_mcp_client: Optional[MultiServerMCPClient] = None
_docker_mcp_tools: Optional[List[BaseTool]] = None
_op_tool_node: Optional[ToolNode] = None


def _get_docker_mcp_client() -> MultiServerMCPClient:
    global _docker_mcp_client
    if _docker_mcp_client is not None:
        return _docker_mcp_client

    # Chainlit uses port 8000 by default, so use 8001 here to avoid collisions.
    mcp_server_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8001/sse")

    _docker_mcp_client = MultiServerMCPClient(
        {
            DOCKER_MCP_SERVER_NAME: {
                "transport": "sse",
                "url": mcp_server_url,
            }
        }
    )
    return _docker_mcp_client


async def _get_docker_mcp_tools() -> List[BaseTool]:
    global _docker_mcp_tools
    if _docker_mcp_tools is not None:
        return _docker_mcp_tools

    mcp_client = _get_docker_mcp_client()
    _docker_mcp_tools = await mcp_client.get_tools(server_name=DOCKER_MCP_SERVER_NAME)
    return _docker_mcp_tools


async def op_tools_node(state: OpState) -> dict:
    if _op_tool_node is None:
        raise RuntimeError("Tool node is not initialized")

    result = await _op_tool_node.ainvoke(state)
    tool_messages = result.get("_messages", [])
    for message in tool_messages:
        tool_name = getattr(message, "name", "unknown_tool")
        print("-" * 80)
        print(f"[OUTPUT_PRODUCER_TOOL:{tool_name}]")
        content = message.content
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text", "")
                    try:
                        parsed = json.loads(text)
                        stdout = parsed.get("stdout")
                        stderr = parsed.get("stderr")
                        if stdout is not None:
                            print("[stdout]")
                            print(stdout)
                        if stderr is not None:
                            print("[stderr]")
                            print(stderr)
                        if stdout is None and stderr is None:
                            print(json.dumps(parsed, ensure_ascii=False, indent=2))
                    except Exception:
                        print(text)
        else:
            print(content)
        print("-" * 80)
    return result


class OpManager(AgentBase[OpState]):
    NAME = "OUTPUT_PRODUCER_MANAGER"

    def __init__(self, llm: BaseChatModel, tools: List[BaseTool], name: str = NAME):
        super().__init__(llm, name)
        self._tools = tools
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
            5. Use available Docker MCP tools to run your code in sandbox if code execution is required.
            Note:
            - Each task step can be an iterative loop where you ask questions to the user if there's any ambiguity or unclear statements until you have a clear idea what user the needs, then move to the next task step.
            - You may ask multiple questions in one response
            - You need to calls tools to execute code if there is a code to run
            - You may call tools multiple times before finalizing.

            Output Requirements:
            - Your response must be a valid raw JSON string that can be parsed by json.loads
            - Output only the JSON object; do not use markdown fences and do not add extra prose
            - Format JSON as pretty-printed multiline JSON with indentation and actual line breaks
            - Do not wrap the JSON object in quotes
            - You will respond only in English with some exceptions as indicated below
            - Respond without markup, without annotation, and without explanation outside the JSON structure
            - If you are making a tool call, do not output final JSON in that turn.
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

    def handleMessage(self, state: OpState):
        input_js = json.dumps([l for l in state["selected_layers"] or []])
        input_prompt = SystemMessage(
            content=f"""
            You are given the input files below:
            {input_js}
            """
        )

        llm_with_tools = self._llm.bind_tools(self._tools)
        response = llm_with_tools.invoke(
            [self._system_prompt, input_prompt] + state["_messages"]
        )
        separate_line = "=" * 80
        print(f"=== OpManager {separate_line}")
        if response.tool_calls:
            print(f"tool_call: {response.tool_calls}")
        else:
            print(response.content)
        print(separate_line)

        if response.tool_calls:
            return {"_messages": [response]}

        content = response.content if isinstance(response.content, str) else ""
        if not content.strip():
            raise ValueError("LLM returned empty content without tool_calls")

        resp_js = json.loads(content)
        return {
            "clarification_question": resp_js.get("clarification_question"),
            "decline_message": resp_js.get("decline_message"),
            "code": resp_js.get("code"),
            "outputs": resp_js.get("outputs"),
            "_messages": [response],
        }


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


async def build_output_producer_graph():
    global _op_tool_node
    workflow = StateGraph(OpState)
    mcp_tools = await _get_docker_mcp_tools()
    op_manager = OpManager(ChatOpenAI(model="gpt-4o", temperature=0), tools=mcp_tools)
    _op_tool_node = ToolNode(mcp_tools, messages_key="_messages")

    workflow.add_node(op_manager.name, op_manager)
    workflow.add_node("tools", op_tools_node)
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
