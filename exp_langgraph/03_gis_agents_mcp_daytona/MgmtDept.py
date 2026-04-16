import json
from typing import List, Dict
from langchain_core.language_models import BaseChatModel
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from AgentBase import AgentBase
from IAgentState import IAgentState

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()


class MgmtState(IAgentState):
    original_human_message: HumanMessage
    response_to_user: AIMessage
    gis_related: bool
    user_language: str
    features: List[str]
    locations: List[Dict]
    retriever_summary: str
    coder_summary: str


class LocationExtractor(AgentBase[MgmtState]):
    NAME = "MGMT_LocationExtractor"

    def __init__(self, llm: BaseChatModel, name: str = NAME):
        super().__init__(llm, name)

    def handleMessage(self, state: MgmtState) -> dict:
        system_prompt = SystemMessage(
            content=(
                f"""
    You are an expert in the area of Geography Information System (GIS).
    Your task is to do the following:
    1. Determine the language the user uses
    2. Extract GIS features or artifacts from user's request that can be displayed on a map and are not locations.
    3. Extract one or more locations from user's requests.
    4. Determine what continents and what countries the locations are in.
    

    You will respond in a JSON format only with the structure below:
    {{
        "user_language": <STRING>,
        "features": [<LIST_OF_KEYWORDS_AND_FEATURES],
        "locations": [
            {{
                "continent": <STRING>,
                "country": <STRING>,
                "area_name": <STRING>,
            }}
        ]
    }}

    1. Put the continent, country, and user-specified area name in the field `continent`, `country`, and `area_name`, respectively in `locations`
    2. Put `null` into the fields if you do not know for any user-specified area.
    3. Do not populate `locations` if the user does not mention area.

    Output requirements:
    - Use English language
    - Return valid JSON string only and no markdown.
    - Do not include any explanation or text outside the JSON.
    - Use exactly the given structure
"""
            )
        )
        messages = [system_prompt] + state["original_human_message"]
        response = self._llm.invoke(messages)
        _messages = state["original_human_message"] + [response]

        # TODO: Handles error here
        resp_js = json.loads(response.content)
        return {
            "user_language": resp_js["user_language"],
            "features": resp_js["features"],
            "locations": resp_js["locations"],
            "_messages": _messages,
        }


class TaskExtractor(AgentBase[MgmtState]):
    NAME = "MGMT_TaskExtractor"

    def __init__(self, llm: BaseChatModel, name: str = NAME):
        super().__init__(llm, name)

    def handleMessage(self, state: MgmtState) -> dict:
        current_utc_time = datetime.now(timezone.utc)
        current_dt = current_utc_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        system_prompt = SystemMessage(
            content=(
                f"""
You are an expert technical manager specializing in Geospatial Information Systems (GIS).
Your role is to evaluate user requests and delegate tasks to your team.

Your team consists of two specialists:
1. GIS Layer Librarian ("retriever"): Search and retrieves specific vector or raster layers from a data collection.
2. GIS Python Coder ("coder"): Writes Python code using the retrieved layers as input to process data and produce output layers.

Your task:
1. Determine if the user's request is GIS-related and can be fulfilled by your team.
2. If it is GIS-related, write highly specific task summaries for each specialist.
3. If it is not GIS-related, write a response to the user why you cannot fulfil the request in {state["user_language"]}.

Guidelines:
- Specificity: Explicitly mention target areas, locations, features, artifacts, dates, and times in your instructions. 
- Absolute Dates: The current date and time is {current_dt}. When writing your summaries, do NOT synthesize or use relative time terms (e.g., "yesterday", "last year", "recently"). Always write exact, absolute dates.
- Empty Tasks: If a specialist has no work to do, set their summary to `null`.
- Retrieval Only: If the task is just layer retrieval, set the summary for the coder to `null`"
- Populate response to user with null if request is GIS-related

Output Requirements:
- Respond in English.
- Output ONLY valid JSON. Do not use markdown formatting (e.g., no ```json fences).
- Do not include any greetings, explanations, or text outside the JSON object.
- Use exactly the following JSON schema:

{{
    "gis_related": <BOOLEAN>,
    "retriever": <NULL_OR_STRING>,
    "coder": <NULL_OR_STRING>,
    "response_to_user": <STRING>
}}
"""
            )
        )
        messages = [system_prompt] + state["original_human_message"]
        response = self._llm.invoke(messages)

        # TODO: Handles error here
        resp_js = json.loads(response.content)
        _messages = [response]
        return {
            "gis_related": resp_js["gis_related"],
            "retriever_summary": resp_js["retriever"],
            "coder_summary": resp_js["coder"],
            "response_to_user": resp_js["response_to_user"],
            "_messages": _messages,
        }


def buildManagementDept():
    workflow = StateGraph(MgmtState)

    locationExtractor = LocationExtractor(
        ChatOpenAI(model="gpt-4o-mini", temperature=0)
    )
    taskExtractor = TaskExtractor(ChatOpenAI(model="gpt-4o", temperature=0))
    workflow.add_node(locationExtractor.name, locationExtractor)
    workflow.add_node(taskExtractor.name, taskExtractor)

    workflow.add_edge(START, locationExtractor.name)
    workflow.add_edge(locationExtractor.name, taskExtractor.name)
    workflow.add_edge(taskExtractor.name, END)

    return workflow.compile()


from TestUtils import run_test_debug, run_test_fullstate, run_test_update
from UserQuery import GisQuery, NonGisQuery

graph = buildManagementDept()
initial_state = {"original_human_message": [HumanMessage(content=GisQuery.Q005)]}

run_test_fullstate(graph, initial_state)
