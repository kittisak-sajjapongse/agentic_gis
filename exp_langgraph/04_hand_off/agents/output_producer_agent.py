import json
from typing import List

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from AgentBase import AgentBase
from agents.json_response_parser import parse_llm_json_object
from agents.op_actions import validate_op_actions
from domain.state_models import IAgentState


class OpManager(AgentBase[IAgentState]):
    NAME = "OUTPUT_PRODUCER_MANAGER"

    def __init__(
        self,
        llm: BaseChatModel,
        tools: List[BaseTool],
        name: str = NAME,
    ):
        super().__init__(llm, name)
        self._tools = tools
        self._tool_names = {tool.name for tool in tools}
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
            - The `selected_layers` you receive from IR are file inputs resolved
              from the global GIS catalog and/or session context. Treat them as
              concrete input files available for analysis/code execution.
            - For every Docker MCP tool call, always pass:
              host_mount_dir="/Users/kittisak/data/work/agentic_gis/exp_langgraph/04_hand_off/data"
            - MCP base image already includes `pyarrow`, `geopandas`, and `shapely`.
              Do NOT include these in tool-call `requirements` unless a specific
              non-default version is explicitly required.
            - Any output layers created should be saved to `/data/output/`
            - For timeout handling: first call run_python without timeout_s (use tool default). Increase timeout_s only if execution times out.
            - If "code" is non-empty, you MUST call Docker MCP tool(s) to execute that code before returning final JSON.
            - Do not return final JSON with non-empty "code" until at least one tool execution result is observed.
            - If execution fails, you may revise code and call tool(s) again, or return decline_message with the execution reason.
            - You may call tools multiple times before finalizing.

            Action Semantics:
            - show_layer:
              Use exactly one selector field:
                - artifact (preferred)
                - catalogItemId
                - layerId
            - create_layer_from_artifact:
              Use when your executed code produced a new file and backend must
              register/materialize it as a session layer.
              Required:
                - artifact.path
              Optional:
                - artifact.format
                - artifact.description
            - show_created_layer:
              Use to make a previously created layer visible by referencing the
              index of a prior create_layer_from_artifact action.
              Required:
                - sourceActionIndex (integer)
            - rename_layer:
              Required:
                - layerId
                - name

            Example actions:
            - {"action":"show_layer","artifact":"cat_001"}
            - {"action":"create_layer_from_artifact","artifact":{"path":"/data/output/thailand_bbox.parquet","format":"GEOPARQUET","description":"Thailand bbox"}}
            - {"action":"show_created_layer","sourceActionIndex":0}
            - {"action":"rename_layer","layerId":"lyr_out_001","name":"Thailand Boundary"}

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
                "actions": [
                    {
                        "action": <STRING - one of show_layer, create_layer_from_artifact, show_created_layer, rename_layer>,
                    },
                    ...
                ],
                "code": <STRING - Python code that generates all the outputs>,
                "clarification_question": <STRING - clarifying question, null if you don't have any question. You will respond in the language the user uses>,
                "decline_message": <STRING - reason if you cannot fulfil use's query for any reasons, null if you can fulfil the query>,
            }
            """
        )

    def handleMessage(self, state: IAgentState):
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

        resp_js = parse_llm_json_object(content)
        validated_actions, action_error = validate_op_actions(resp_js.get("actions"))
        if action_error is not None:
            # Guardrail: malformed action payload should not crash graph runtime.
            # Convert to actionable decline for deterministic downstream behavior.
            return {
                "clarification_question": None,
                "decline_message": f"Invalid OP action payload: {action_error}",
                "code": None,
                "actions": [],
                "op_requires_tool_call": False,
                "_messages": [response],
            }
        code = resp_js.get("code")
        requires_tool_call = (
            isinstance(code, str)
            and code.strip() != ""
            and not self._has_tool_result_since_last_user(state)
        )
        return {
            "clarification_question": resp_js.get("clarification_question"),
            "decline_message": resp_js.get("decline_message"),
            "code": code,
            "actions": validated_actions,
            "op_requires_tool_call": requires_tool_call,
            "_messages": [response],
        }

    def _has_tool_result_since_last_user(self, state: IAgentState) -> bool:
        """Return True if an OP-phase tool result exists since latest user input.

        Important: IR graph may also emit ToolMessage instances (for catalog
        search). We must only count tool messages produced by this manager's
        MCP tool set; otherwise code can be finalized without OP execution.
        """
        for msg in reversed(state.get("_messages", [])):
            if isinstance(msg, ToolMessage) and getattr(msg, "name", None) in self._tool_names:
                return True
            if isinstance(msg, HumanMessage):
                return False
        return False
