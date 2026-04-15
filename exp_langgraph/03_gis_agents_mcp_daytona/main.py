from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from IAgentState import IAgentState
from MgmtAgent import ManagementAgent

load_dotenv()


# user_query = "How many hotspots are there in Thailand this year on the map?"
# user_query = "Please show me the hotspot layer in Thailand on the map"
user_query = "How does a bird fly?"

workflow = StateGraph(IAgentState)

mgmt = ManagementAgent(ChatOpenAI(model="gpt-4o", temperature=0))
workflow.add_node(mgmt.name, mgmt)

workflow.add_edge(START, mgmt.name)
workflow.add_edge(mgmt.name, END)

graph = workflow.compile()

initial_state = {"_messages": [HumanMessage(content=user_query)]}
latest_state = None
for event in graph.stream(initial_state):
    for node_name, node_state in event.items():
        print(node_name)
        latest_state = node_state

print(latest_state)
