from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from IAgentState import IAgentState
from MgmtDept import buildManagementDept, MANAGEMENT_DEPARTMENT_NAME
from IRAgent import InputRetrievalAgent
from OGAgent import OutputGenerationAgent
from TestUtils import run_test_update

load_dotenv()


user_query = "How many hotspots are there in Thailand this year on the map?"
# user_query = "Please show me the hotspot layer in Thailand on the map"
# user_query = "How does a bird fly?"

workflow = StateGraph(IAgentState)

mgmt_dept = buildManagementDept()
ir_agent = InputRetrievalAgent(ChatOpenAI(model="gpt-4o", temperature=0))
og_agent = OutputGenerationAgent(ChatOpenAI(model="gpt-4o", temperature=0))

workflow.add_node(MANAGEMENT_DEPARTMENT_NAME, mgmt_dept)
workflow.add_node(ir_agent.name, ir_agent)
workflow.add_node(og_agent.name, og_agent)

workflow.add_edge(START, MANAGEMENT_DEPARTMENT_NAME)
workflow.add_edge(MANAGEMENT_DEPARTMENT_NAME, ir_agent.name)
workflow.add_edge(ir_agent.name, og_agent.name)
workflow.add_edge(og_agent.name, END)

graph = workflow.compile()

initial_state = {"original_human_message": [HumanMessage(content=user_query)]}
run_test_update(graph, initial_state)
