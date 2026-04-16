import json
from typing import List, Dict
from langchain_core.language_models import BaseChatModel
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from AgentBase import AgentBase
from IAgentState import IAgentState

from langchain_core.messages import SystemMessage, HumanMessage

from dotenv import load_dotenv

load_dotenv()


class MgmtState(IAgentState):
    original_human_message: HumanMessage
    features: List[str]
    valid_locations: List[Dict]
    invalid_locations: List[Dict]
    tasks: List[str]
    related: bool


class FeatureExtractor(AgentBase[MgmtState]):
    NAME = "MGMT_FeatureExtractor"

    def __init__(self, llm: BaseChatModel, name: str = NAME):
        super().__init__(llm, name)

    def handleMessage(self, state: MgmtState) -> MgmtState:
        system_prompt = SystemMessage(
            content=(
                f"""
    You are an expert in the area of Geography Information System (GIS).
    Look for GIS features or artifacts the user mentioned that can be displayed on a map and are not locations.
    You will respond in a JSON format only with the structure below:
    {{"features": [<LIST_OF_KEYWORDS_AND_FEATURES]}}

    Output requirements:
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
        return {"features": resp_js["features"], "_messages": _messages}


class LocationExtractor(AgentBase[MgmtState]):
    NAME = "MGMT_LocationExtractor"

    def __init__(self, llm: BaseChatModel, name: str = NAME):
        super().__init__(llm, name)

    def handleMessage(self, state: MgmtState) -> MgmtState:
        system_prompt = SystemMessage(
            content=(
                f"""
    You are an expert in the area of Geography of the world.
    Your task is to do the following:
    1. Extract one or more locations from user's requests.
    2. Verify if the locations physically exist
    3. Determine what continents and what countries the locations are in
    

    You will respond in a JSON format only with the structure below:
    {{
        "valid_locations": [
            {{
                "continent": <STRING>,
                "country": <STRING>,
                "area_name": <STRING>,
            }}
        ],
        "invalid_locations": [
            <LIST_OF_AREA_NAMES>
        ]
    }}

    1. Put the continent, country, and user'specified area name in the field `continent`, `country`, and `area_name`, respectively in `valid_locations` if the locations physically exist
    2. Put the user-specified area name in the list `invalid_locations` if the locations do not physically exist.

    Output requirements:
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
            "valid_locations": resp_js["valid_locations"],
            "invalid_locations": resp_js["invalid_locations"],
            "_messages": _messages,
        }


class TaskExtractor(AgentBase[MgmtState]):
    NAME = "MGMT_TaskExtractor"

    def __init__(self, llm: BaseChatModel, name: str = NAME):
        super().__init__(llm, name)

    def handleMessage(self, state: MgmtState) -> MgmtState:
        return state


class SummaryGenerator(AgentBase[MgmtState]):
    NAME = "MGMT_SummaryGenerator"

    def __init__(self, llm: BaseChatModel, name: str = NAME):
        super().__init__(llm, name)

    def handleMessage(self, state: MgmtState) -> MgmtState:
        return state


def buildManagementDept():
    workflow = StateGraph(IAgentState)

    featureExtractor = FeatureExtractor(ChatOpenAI(model="gpt-4o-mini", temperature=0))
    locationExtractor = LocationExtractor(ChatOpenAI(model="gpt-4o-mini", temperature=0))
    taskExtractor = TaskExtractor(ChatOpenAI(model="gpt-4o", temperature=0))
    summaryGenerator = SummaryGenerator(ChatOpenAI(model="gpt-4o", temperature=0))
    workflow.add_node(featureExtractor.name, featureExtractor)
    workflow.add_node(locationExtractor.name, locationExtractor)
    workflow.add_node(taskExtractor.name, taskExtractor)
    workflow.add_node(summaryGenerator.name, summaryGenerator)

    workflow.add_edge(START, featureExtractor.name)
    workflow.add_edge(featureExtractor.name, locationExtractor.name)
    workflow.add_edge(locationExtractor.name, taskExtractor.name)
    workflow.add_edge(taskExtractor.name, summaryGenerator.name)
    workflow.add_edge(summaryGenerator.name, END)

    return workflow.compile()


# user_query = "How many hotspots are there in Kanchanapisek this year on the map?"
user_query = "อุณหภูมิที่สัตหีบเป็นเท่าไร โชว์บนแผนที่ให้ดูหน่อย"
# user_query = "Please show me the hotspot layer in Thailand on the map"
# user_query = "How does a bird fly?"

graph = buildManagementDept()

initial_state = {"original_human_message": [HumanMessage(content=user_query)]}
latest_state = None
for event in graph.stream(initial_state):
    for node_name, node_state in event.items():
        print(node_name)
        latest_state = node_state

print(latest_state)
