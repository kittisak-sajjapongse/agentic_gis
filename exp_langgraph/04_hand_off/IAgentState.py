from typing import List, Literal
from AgentBase import ObservableState
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage


class GISFile(BaseModel):
    path: str
    ftype: Literal["GEOPARQUET", "GEOTIFF"]
    description: str


# Three agents use this inter-agent state to exchange data. The agents include:
# 1.Management, 2.Input Retrieval, and 3. Output Generation
class IAgentState(ObservableState):
    # The original request from the user
    user_query: HumanMessage

    user_language: str

    gis_related: bool

    response_to_user: AIMessage

