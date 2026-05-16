from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel

from AgentBase import ObservableState


class GISFile(BaseModel):
    path: str
    ftype: Literal["GEOPARQUET", "GEOTIFF"]
    description: str


class OpOutput(BaseModel):
    output_type: Literal["GEOPARQUET_LAYER", "GEOTIFF_LAYER", "REPORTS", "CHARTS"]
    description: str
    path: str


# Shared inter-agent state contract.
class IAgentState(ObservableState):
    query_summary: str
    user_language: str
    is_query_accepted: bool
    selected_layers: Optional[List[GISFile]]
    code: str
    outputs: Any


class IrState(IAgentState):
    clarification_question: Optional[str]
    gis_related: Optional[bool]
    decline_message: Optional[str]
    general_layers: Optional[bool]


class OpState(IAgentState):
    clarification_question: Optional[str]
    decline_message: Optional[str]
    outputs: Optional[List[OpOutput]]
    code: Optional[str]


class SessionModel(BaseModel):
    sessionId: str
    status: Literal["active", "closed"] = "active"
    createdAt: str
    lastRunId: Optional[str] = None

    @classmethod
    def create(cls) -> "SessionModel":
        return cls(
            sessionId=f"sess_{uuid4().hex[:12]}",
            status="active",
            createdAt=datetime.now(timezone.utc).isoformat(),
        )


class LayerSource(BaseModel):
    type: str
    url: str


class LayerStyle(BaseModel):
    preset: Optional[str] = None
    paint: Optional[Dict[str, Any]] = None
    layout: Optional[Dict[str, Any]] = None


class LayerDescriptor(BaseModel):
    id: str
    name: str
    kind: Literal["geojson", "vector", "raster", "cog", "wms"]
    source: LayerSource
    style: LayerStyle
    visible: bool = True
    opacity: Optional[float] = None
    bounds: Optional[List[float]] = None
    origin: Literal["input", "agent_output"]
    createdByRunId: Optional[str] = None
    createdAt: str


class LayerPatchRequest(BaseModel):
    visible: Optional[bool] = None
    opacity: Optional[float] = None
    style: Optional[LayerStyle] = None
