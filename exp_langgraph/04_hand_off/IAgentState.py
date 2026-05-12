from typing import List, Literal, Optional, Any
from AgentBase import ObservableState
from pydantic import BaseModel


class GISFile(BaseModel):
    path: str
    ftype: Literal["GEOPARQUET", "GEOTIFF"]
    description: str


# Three agents use this inter-agent state to exchange data. The agents include:
# 1.Management, 2.Input Retrieval, and 3. Output Generation
class IAgentState(ObservableState):
    # Summary of user's request
    query_summary: str

    # The language the user uses
    user_language: str

    # This indicates whether the query from the user is accepted.
    # If not accepted, we end the graph execution.
    is_query_accepted: bool

    # List of layers selected from the collection
    selected_layers: Optional[List[GISFile]]

    code: str

    outputs: Any
