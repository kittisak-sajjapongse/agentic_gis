from typing import List
from langchain_core.language_models import BaseChatModel
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from AgentBase import AgentBase
from IAgentState import IAgentState

from langchain_core.messages import SystemMessage, HumanMessage

from dotenv import load_dotenv
load_dotenv()

class MgmtState(IAgentState):
    gis_features: List[str]
    gis_tasks: List[str]
    gis_related: bool

    
class FeatureExtractor(AgentBase[MgmtState]):
    NAME = "MGMT_FeatureExtractor"

    def __init__(self, llm: BaseChatModel, name: str = NAME):
        super().__init__(llm, name)

    def handleMessage(self, state: MgmtState) -> MgmtState:
        system_prompt = SystemMessage(
            content=(
f"""
    You are an expert in the area of Geography Information System (GIS).
    Look for keywords of features that can be related to GIS.
    You will respond in a JSON format only with the structure below:
    {{"features": [<LIST_OF_KEYWORDS_AND_FEATURES]}}
"""
            )
        )
        messages = [system_prompt] + state["_messages"]
        response = self._llm.invoke(messages)
        print(response)
        return {"_messages": [response]}
    
class TaskExtractor(AgentBase[MgmtState]):
    NAME = "MGMT_TaskExtractor"

    def __init__(self, llm: BaseChatModel, name: str = NAME):
        super().__init__(llm, name)

    def handleMessage(self, state: MgmtState) -> MgmtState:
        return {}
    
class SummaryGenerator(AgentBase[MgmtState]):
    NAME = "MGMT_SummaryGenerator"

    def __init__(self, llm: BaseChatModel, name: str = NAME):
        super().__init__(llm, name)

    def handleMessage(self, state: MgmtState) -> MgmtState:
        return {}

def buildManagementDept():
    workflow = StateGraph(IAgentState)

    featureExtractor = FeatureExtractor(ChatOpenAI(model="gpt-4o", temperature=0))
    taskExtractor = TaskExtractor(ChatOpenAI(model="gpt-4o", temperature=0))
    summaryGenerator = SummaryGenerator(ChatOpenAI(model="gpt-4o", temperature=0))
    workflow.add_node(featureExtractor.name, featureExtractor)
    workflow.add_node(taskExtractor.name, taskExtractor)
    workflow.add_node(summaryGenerator.name, summaryGenerator)

    workflow.add_edge(START, featureExtractor.name)
    workflow.add_edge(featureExtractor.name, taskExtractor.name)
    workflow.add_edge(taskExtractor.name, summaryGenerator.name)
    workflow.add_edge(summaryGenerator.name, END)

    return workflow.compile()



# user_query = "How many hotspots are there in Thailand this year on the map?"
# user_query = "Please show me the hotspot layer in Thailand on the map"
# user_query = "How does a bird fly?"

# graph = buildManagementDept()

# initial_state = {"_messages": [HumanMessage(content=user_query)]}
# latest_state = None
# for event in graph.stream(initial_state):
#     for node_name, node_state in event.items():
#         print(node_name)
#         latest_state = node_state

# print(latest_state)

class ManagementAgent(AgentBase[IAgentState]):
    NAME = "Management"

    def __init__(self, llm: BaseChatModel, name: str = NAME):
        super().__init__(llm, name)

    def handleMessage(self, state: IAgentState) -> IAgentState:
        system_prompt = SystemMessage(
            content=(
                f"""
You are a technical manager for Geospatial Information Systems (GIS).

Your task is to analyze the user's request and decide whether the request is GIS-related.
If the user's request involves features that can be display or analyzed using GIS, this is definitely GIS-related.

If the request is GIS-related, you must prepare three concise bullet-point summaries:
1. input_summary: extract the specific geographic features, locations, or datasets explicitly mentioned in the user's request (e.g., "hotspots", "Thailand borders").
2. output_summary: extract the specific spatial statistics, maps, or layers the user wants to see as a result.
3. task_summary: what geospatial work (e.g., spatial joins, counting features within a polygon) must be performed.
4. comments: your comments on the user's request

If the request is not GIS-related, you must always provide comments why the request is declined.

Consideration guideline:
- Request is GIS-related if the request involves geographic data, GIS analysis, vector data, raster data, maps, spatial queries, geoprocessing, coordinate systems, projections, remote sensing, or spatial workflows.
- Request is GIS-related if the request asks for spatial statistics (e.g., "how many", "how large") as long as they require GIS analysis to calculate the answer.
- A request is ONLY GIS-related if you can successfully extract specific, explicitly mentioned input datasets AND a specific spatial output. If the user asks a general knowledge question without providing data context, the request is NOT GIS-related.

Output requirements:
- Return valid JSON only.
- Do not include any explanation or text outside the JSON.
- Your comments need to be specific and actionable for the user.
- Use exactly this structure:

{{
  "gis_related": <BOOLEAN>,
  "input_summary": <NULL_OR_STRING>,
  "output_summary": <NULL_OR_STRING>,
  "task_summary": <NULL_OR_STRING>,
  "comments": <NULL_OR_STRING>
}}

Additional rules:
- If the request is not GIS-related, all three summary fields must be null.
- If the request is GIS-related, each summary field must be a string containing short bullet points.
- Do NOT invent, assume, or hallucinate GIS layers (like parcels or zoning) if they are not explicitly mentioned or directly implied by the user's request.
- Use the exact terminology the user provided (e.g., if they ask for "hotspots", write "hotspots").
- Do not invent unnecessary inputs or outputs; include only what is relevant to the user's request.
"""
            )
        )
        messages = [system_prompt] + state["_messages"]
        response = self._llm.invoke(messages)
        return {"_messages": [response]}
