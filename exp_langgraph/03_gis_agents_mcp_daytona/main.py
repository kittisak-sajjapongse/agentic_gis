from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from IAgentState import IAgentState
from MgmtDept import buildManagementDept, MANAGEMENT_DEPARTMENT_NAME
from IRAgent import InputRetrievalAgent
from OGAgent import OutputGenerationAgent
from TestUtils import run_test_update, create_png_graph_viz

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
workflow.add_conditional_edges(
    MANAGEMENT_DEPARTMENT_NAME,
    lambda state: state["gis_related"],
    {
        True: ir_agent.name,
        False: END
    }
)
workflow.add_conditional_edges(
    ir_agent.name,
    lambda state: "STOP" if state["coder_summary"] is None else "CONTINUE",
    {
        "CONTINUE": og_agent.name,
        "STOP": END
    }
)
workflow.add_edge(ir_agent.name, og_agent.name)
workflow.add_edge(og_agent.name, END)

graph = workflow.compile()
create_png_graph_viz(graph)

initial_state = {"original_human_message": [HumanMessage(content=user_query)]}
run_test_update(graph, initial_state)
