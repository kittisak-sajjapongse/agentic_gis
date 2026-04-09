import copy
from typing import Annotated
from typing_extensions import TypedDict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_experimental.tools import PythonREPLTool
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

# Add `OPENAI_API_KEY` in .env file
load_dotenv()

# ==========================================
# 1. Define the Graph State (Architecture)
# ==========================================
# In LangGraph, the 'State' is passed between nodes. 
# We define a TypedDict that will hold the history of messages.
# The 'add_messages' reducer is crucial: it tells LangGraph to APPEND 
# new messages to the list rather than overwriting the existing ones.
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

# ==========================================
# 2. Initialize Tools & LLM
# ==========================================
# Initialize the Python REPL tool
python_repl_tool = PythonREPLTool()
tools = [python_repl_tool]

# Initialize the LLM with strict temperature for coding
llm = ChatOpenAI(model="gpt-4o", temperature=0)

# Bind the tools to the LLM. 
# This injects the tool's schema into the LLM, allowing the LLM to know
# the tool exists and allowing it to emit a "tool_call" when needed.
llm_with_tools = llm.bind_tools(tools)

# ==========================================
# 3. Define the Nodes (The Graph Functions)
# ==========================================

# Node 1: The Reasoner (Agent Node)
def agent_node(state: AgentState):
    """
    This node calls the LLM. It takes the current message history, 
    evaluates it, and decides whether to output a final answer or call a tool.
    """
    system_prompt = SystemMessage(content=(
        "You are an expert Python developer and a ReAct reasoning agent. "
        "1. Write Python code to solve the request. "
        "2. ALWAYS execute the code using the python_repl_ast tool. "
        "3. Check for errors. If there's an error, write a fix and execute again. "
        "4. Return the final answer based on the execution result."
    ))
    
    # Prepend the system prompt to the existing conversation history
    messages_to_pass = [system_prompt] + state["messages"]
    
    # Invoke the LLM
    response = llm_with_tools.invoke(messages_to_pass)

    # The output returned here is automatically appended to state["messages"]
    # because of the 'add_messages' reducer we defined in AgentState.
    return {"messages": [response]}

# Node 2: The Actor (Tool Node)
# LangGraph provides a prebuilt ToolNode that handles the boilerplate of
# extracting 'tool_calls' from the LLM's message, executing the matched tool, 
# and returning a 'ToolMessage' with the observation/result.
tool_node = ToolNode(tools)

# ==========================================
# 4. Define the Router (Conditional Edge)
# ==========================================
def should_continue(state: AgentState) -> str:
    """
    This function acts as a traffic director after the agent_node runs.
    It checks the very last message in the state.
    """
    print("="*80)
    print(state)
    print("="*80)
    last_message = state["messages"][-1]
    
    # If the LLM decided to call a tool, route to the "tools" node.
    if last_message.tool_calls:
        return "continue"
    
    # If there are no tool calls, it means the LLM provided a final text answer.
    # Route to END to finish the execution graph.
    return "end"

# ==========================================
# 5. Build and Compile the Graph
# ==========================================
# Initialize the state machine
workflow = StateGraph(AgentState)

# Add our two nodes to the graph
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)

# Set the entry point: the graph always starts at the reasoning agent
workflow.add_edge(START, "agent")

# Add the conditional edge: After 'agent', check 'should_continue'
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "continue": "tools", # If the LLM called a tool, go to 'tools'
        "end": END           # Otherwise, end the loop
    }
)

# Add a normal edge: After tools execute, ALWAYS loop back to the 'agent'
# so the LLM can observe the output and decide what to do next (Reason).
workflow.add_edge("tools", "agent")

# Compile the graph into an executable application
react_graph = workflow.compile()

# ==========================================
# 6. Execute the Graph
# ==========================================
def run_custom_react_agent(user_query: str):
    print(f"User Query: {user_query}\n" + "-"*50)
    
    # Initialize the starting state
    initial_state = {"messages": [HumanMessage(content=user_query)]}
    
    # Stream the state updates as the graph executes
    for event in react_graph.stream(initial_state):
        for node_name, node_state in event.items():
            print(f"\n>>> Step executed by node: [{node_name.upper()}] <<<")
            latest_message = node_state["messages"][-1]
            
            if node_name == "agent":
                if latest_message.tool_calls:
                    print(f"Action: LLM requested tool '{latest_message.tool_calls[0]['name']}'")
                else:
                    print(f"Final Answer:\n{latest_message.content}")
            
            elif node_name == "tools":
                print(f"Observation (Execution Output):\n{latest_message.content}")

if __name__ == "__main__":
    # test_prompt = "Write a program to sort 100 numbers and show me the code"
    test_prompt = "Create a shape file that contains a point exactly at Bangkok, Thailand (anywhere in Bangkok)"
    run_custom_react_agent(test_prompt)