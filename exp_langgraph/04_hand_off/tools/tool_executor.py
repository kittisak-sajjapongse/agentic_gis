from __future__ import annotations

import json
from typing import List, Optional

from langchain_core.tools import BaseTool
from langgraph.prebuilt import ToolNode


class ToolExecutorNode:
    """Reusable LangGraph node wrapper for tool execution + optional logging."""

    def __init__(
        self,
        tools: List[BaseTool],
        messages_key: str = "_messages",
        log_prefix: Optional[str] = None,
    ):
        self._tool_node = ToolNode(tools, messages_key=messages_key)
        self._messages_key = messages_key
        self._log_prefix = log_prefix

    async def __call__(self, state: dict) -> dict:
        result = await self._tool_node.ainvoke(state)
        if self._log_prefix:
            self._log_tool_messages(result.get(self._messages_key, []))
        return result

    def _log_tool_messages(self, tool_messages: list) -> None:
        for message in tool_messages:
            tool_name = getattr(message, "name", "unknown_tool")
            print("-" * 80)
            print(f"[{self._log_prefix}:{tool_name}]")
            content = message.content
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text", "")
                        try:
                            parsed = json.loads(text)
                            stdout = parsed.get("stdout")
                            stderr = parsed.get("stderr")
                            if stdout is not None:
                                print("[stdout]")
                                print(stdout)
                            if stderr is not None:
                                print("[stderr]")
                                print(stderr)
                            if stdout is None and stderr is None:
                                print(json.dumps(parsed, ensure_ascii=False, indent=2))
                        except Exception:
                            print(text)
            else:
                print(content)
            print("-" * 80)
