from __future__ import annotations

import json
from typing import List

from langchain_core.tools import BaseTool, tool

from domain.gis_catalog import GIS_COLLECTION

from .base import ToolProvider


@tool
def search_gis_collection() -> str:
    """Retrieve entries of GIS layers in the collection."""
    return json.dumps(GIS_COLLECTION)


class GISCatalogToolProvider(ToolProvider):
    async def get_tools(self) -> List[BaseTool]:
        return [search_gis_collection]
