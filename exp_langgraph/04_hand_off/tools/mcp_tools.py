from __future__ import annotations

from typing import List, Optional

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from runtime.settings import AppSettings

from .base import ToolProvider


class DockerMCPToolProvider(ToolProvider):
    """Provides Docker MCP tools with lazy initialization and caching."""

    def __init__(
        self,
        settings: AppSettings,
        client: Optional[MultiServerMCPClient] = None,
    ):
        self._settings = settings
        self._client = client
        self._tools: Optional[List[BaseTool]] = None

    def _get_client(self) -> MultiServerMCPClient:
        if self._client is not None:
            return self._client

        self._client = MultiServerMCPClient(
            {
                self._settings.docker_mcp_server_name: {
                    "transport": "sse",
                    "url": self._settings.mcp_server_url,
                }
            }
        )
        return self._client

    async def get_tools(self) -> List[BaseTool]:
        if self._tools is not None:
            return self._tools

        client = self._get_client()
        self._tools = await client.get_tools(
            server_name=self._settings.docker_mcp_server_name
        )
        return self._tools
