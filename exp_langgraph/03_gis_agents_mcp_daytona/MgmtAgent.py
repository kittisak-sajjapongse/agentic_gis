from langchain_core.language_models import BaseChatModel
from AgentBase import AgentBase
from IAgentState import IAgentState

from langchain_core.messages import SystemMessage


class ManagementAgent(AgentBase[IAgentState]):
    NAME = "Management"

    def __init__(self, llm: BaseChatModel, name: str = NAME):
        super().__init__(llm, name)
        self._prompt = SystemMessage(content=(""))

    def handleMessage(self, state: IAgentState) -> IAgentState:
        print(state)
        return state
