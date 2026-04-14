from abc import ABC, abstractmethod

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from typing import Annotated, Generic, TypeVar
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class ObservableState(TypedDict):
    # For storing all messages exchanged between departments
    _messages: Annotated[list[BaseMessage], add_messages]


TState = TypeVar("TState", bound=ObservableState)


class AgentBase(ABC, Generic[TState]):
    def __init__(self, llm: BaseChatModel, name: str):
        if not isinstance(llm, BaseChatModel):
            raise TypeError(
                f"Expected 'llm' to be of type 'BaseChatModel', got '{type(llm).__name__}'"
            )
        if not isinstance(name, str):
            raise TypeError(
                f"Expected 'name' to be of type 'str', got '{type(name).__name__}'"
            )

        self._llm = llm
        self.name = name

    @abstractmethod
    def handleMessage(self, state: TState) -> TState:
        raise NotImplementedError

    def __call__(self, state: TState) -> TState:
        return self.handleMessage(state)
