from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from langchain_core.tools import BaseTool


class ToolProvider(ABC):
    @abstractmethod
    async def get_tools(self) -> List[BaseTool]:
        raise NotImplementedError
