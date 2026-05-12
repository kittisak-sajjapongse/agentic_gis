import json
from datetime import datetime, timezone
from typing import List

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool

from AgentBase import AgentBase
from domain.state_models import IAgentState


class IrManager(AgentBase[IAgentState]):
    NAME = "INPUT_RETRIEVAL_MANAGER"

    def __init__(
        self,
        llm: BaseChatModel,
        tools: List[BaseTool],
        name: str = NAME,
    ):
        super().__init__(llm, name)
        self._tools = tools
        self._system_prompt = SystemMessage(
            content="""
        You are an expert technical manager in the area of Geographic Information System (GIS).
        You own a collection of GIS data in the GeoParquet format for vector layers and the GeoTIFF format for raster layers.

        You goal is to find required GIS layers that can be used as inputs or answer user's query.
        The GIS layers specified from you may be used to construct a Python script to answer user's query if the layer
        requires processing or analysis.

        You task steps to achieve the goal:
        1. Determine user's language
        2. Determine if user's prompt is a GIS-related question. If the prompt is not a question or is not GIS-related, simply decline and give a reason.
        3. Search your collection using tools provided to find useful GIS layers
        4. Note the details of the layers you selected and fill the detail into your response structure
        5. If you can't find any suitable layer from the collection, determine and indicate if the layers required are of general knowledge
        6. Accept user's prompt only if (1) the prompt is GIS-related, and (2) all required layers can be found
        7. If the user's prompt is not accepted, add reason in the declining message
        8. If the user's prompt is accepted, rewrite summary of user's request once you find out more information from the user.
        Note:
        - Each task step can be an iterative loop where you ask questions to the user if there's any ambiguity or unclear statements until you have a clear idea what user the needs, then move to the next task step.
        - You may ask multiple questions in one response

        Output Requirements:
        - Your response must be a valid raw JSON string that can be parsed by json.loads
        - Output only the JSON object; do not use markdown fences and do not add extra prose
        - Format JSON as pretty-printed multiline JSON with indentation and actual line breaks
        - Do not wrap the JSON object in quotes
        - You will respond only in English with some exceptions as indicated below
        - Respond without markup, without annotation, and without explanation outside the JSON structure
        - You will always respond using the JSON structure below:
        {
            "user_language": <STRING - language the user uses. Use the full name of the language and do not use abbreviation>
            "clarification_question": <STRING - clarifying question, null if you don't have any question. You will respond in the language the user uses>,
            "gis_related": <BOOLEAN - true if the prompt is a GIS-related question>,
            "decline_message": <STRING - reason if the prompt is decline, null if the prompt is GIS-related question.>,
            "selected_layers": [
                {
                    "path": <file path of the selected layers>,
                    "ftype": <GEOPARQUET or GEOTIFF>,
                    "description": <description of the layer with the context of user's request>
                },
                ...
            ] <This field is null if you haven't decided yet what layers to be included>,
            "general_layers": <BOOLEAN - true if all layer required are of general knowledge>,
            "is_query_accepted": <BOOLEAN - true if user's prompt is accepted, null if not determined yet>
            "query_summary": <STRING - Summary of user's request once accepted, null if not determined yet>
        }
        """
        )

    def handleMessage(self, state: IAgentState):
        llm_with_tools = self._llm.bind_tools(self._tools)

        current_utc_time = datetime.now(timezone.utc)
        current_dt = current_utc_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        time_prompt = SystemMessage(
            content=f"\nFor your reference, the current date and time is: {current_dt}"
        )

        response = llm_with_tools.invoke([self._system_prompt, time_prompt] + state["_messages"])
        separate_line = "=" * 80
        print(f"=== IrManager {separate_line}")
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
            "user_language": resp_js["user_language"],
            "query_summary": resp_js["query_summary"],
            "selected_layers": resp_js["selected_layers"],
            "clarification_question": resp_js["clarification_question"],
            "gis_related": resp_js["gis_related"],
            "decline_message": resp_js["decline_message"],
            "general_layers": resp_js["general_layers"],
            "is_query_accepted": resp_js["is_query_accepted"],
            "_messages": [response],
        }
