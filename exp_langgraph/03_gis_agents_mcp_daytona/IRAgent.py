import json
from langchain_core.language_models import BaseChatModel
from AgentBase import AgentBase
from IAgentState import IAgentState

from langchain_core.messages import SystemMessage

GIS_CATALOG = [
    {"file": "", "description": "", "type": "GEOPARQUET"},
    {"file": "", "description": "", "type": "GEOTIFF"},
]


class InputRetrievalAgent(AgentBase[IAgentState]):
    NAME = "InputRetrieval"

    def __init__(self, llm: BaseChatModel, name: str = NAME):
        super().__init__(llm, name)

    def handleMessage(self, state: IAgentState) -> IAgentState:
        catalog = json.dumps(GIS_CATALOG)
        self._prompt = SystemMessage(
            content=(
                f"""
You are a GIS data librarian managing a catalog of GeoParquet (vector data) and Cloud-Optimized GeoTIFF (raster data) files.

You are provided with a JSON catalog containing available files and their default descriptions. 
Your task is to recommend which file or files are required to complete the user's requested analysis.

For each recommended file, you must rewrite its description to explicitly explain how and why it applies to the user's specific task.

You must respond ONLY with valid JSON using the exact schema below:

{{
    "geoparquet": [
        {{
            "path": "<PATH_TO_FILE>",
            "description": "<DESCRIPTION_TAILORED_TO_USER_TASK>"
        }}
    ],   
    "geotiff": [
        {{
            "path": "<PATH_TO_FILE>",
            "description": "<DESCRIPTION_TAILORED_TO_USER_TASK>"
        }}
    ]
}}

Rules:
- Output valid JSON only. Do not wrap the response in markdown blocks (e.g., no ```json).
- Do not include explanations, greetings, or any text outside the JSON object.
- If no files from a specific category are needed, return an empty list for that category.
- If no files are needed at all, return exactly:
  {{
      "geoparquet": [],
      "geotiff": []
  }}

Here is the JSON catalog:
{catalog}
"""
            )
        )
        return state
