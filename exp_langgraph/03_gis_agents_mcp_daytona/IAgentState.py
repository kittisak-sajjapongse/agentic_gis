from typing import List, Literal
from AgentBase import ObservableState
from pydantic import BaseModel
from langchain_core.messages import HumanMessage


class GISFile(BaseModel):
    path: str
    ftype: Literal["GEOPARQUET", "GEOTIFF"]
    description: str


# Three agents use this inter-agent state to exchange data. The agents include:
# 1.Management, 2.Input Retrieval, and 3. Output Generation
class IAgentState(ObservableState):
    # The original request from the user
    original_human_message: HumanMessage

    # Summary of requests from the user broken into bullets.
    # This serve as a single source-of-truth of all departments of
    # what they need to do.
    request_summary: str

    # Paths to input GIS layers
    input_layer_paths: List[GISFile]

    # Paths to output GIS layers
    output_layer_paths: List[GISFile]
