from __future__ import annotations

from typing import Dict

from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient

from .settings import AppSettings


class AppContainer:
    """Small dependency container used as a composition root.

    This intentionally keeps construction logic in one place while the rest of
    the codebase migrates from module-level globals to injected dependencies.
    """

    def __init__(self, settings: AppSettings):
        self.settings = settings

    @classmethod
    def from_env(cls) -> "AppContainer":
        return cls(AppSettings.from_env())

    def create_chat_model(self) -> ChatOpenAI:
        return ChatOpenAI(
            model=self.settings.openai_model,
            temperature=self.settings.llm_temperature,
        )

    def create_mcp_client(self) -> MultiServerMCPClient:
        servers: Dict[str, Dict[str, str]] = {
            self.settings.docker_mcp_server_name: {
                "transport": "sse",
                "url": self.settings.mcp_server_url,
            }
        }
        return MultiServerMCPClient(servers)
