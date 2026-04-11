import atexit
import asyncio
import json
import os
from typing import Annotated
from typing_extensions import TypedDict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_mcp_adapters.client import MultiServerMCPClient

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
# Connect to the local Docker MCP tool server over SSE
mcp_server_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000/sse")
mcp_client = MultiServerMCPClient(
    {
        "docker-python": {
            "transport": "sse",
            "url": mcp_server_url,
        }
    }
)

# Fetch MCP tools (Docker code execution) and bind them to the LLM
tools = asyncio.run(mcp_client.get_tools())

def _close_mcp_client():
    close_fn = getattr(mcp_client, "close", None)
    if callable(close_fn):
        close_fn()

atexit.register(_close_mcp_client)

# Initialize the LLMs with strict temperature
llm = ChatOpenAI(model="gpt-4o", temperature=0)
validator_llm = ChatOpenAI(model="gpt-4o", temperature=0)

# Bind the tools to the LLM.
# This injects the tool's schema into the LLM, allowing the LLM to know
# the tool exists and allowing it to emit a "tool_call" when needed.
llm_with_tools = llm.bind_tools(tools)

# ==========================================
# 3. Define the Nodes (The Graph Functions)
# ==========================================

def _tool_name_hint() -> str:
    tool_names = [tool.name for tool in tools if getattr(tool, "name", None)]
    if tool_names:
        return ", ".join(tool_names)
    return "the local Docker MCP tool"

# Node 1: The Reasoner (Agent Node)
def agent_node(state: AgentState):
    """
    This node calls the LLM. It takes the current message history,
    evaluates it, and decides whether to output a final answer or call a tool.
    """
    system_prompt = SystemMessage(content=(
        "You are an expert Python developer and a ReAct reasoning agent. "
        "1. Write Python code to solve the request. "
        f"2. ALWAYS execute the code using {_tool_name_hint()}. "
        "3. Check for errors. If there's an error, write a fix and execute again. "
        "4. Return the final answer based on the execution result.\n"
        "Your final answer MUST be a single JSON string with no markdown with exactly these keys: "
        "message (string), is_error (boolean), error_message (string). "
        "If is_error is false, error_message must be an empty string. "
        "If is_error is true, provide a clear reason in error_message."
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
    last_message = state["messages"][-1]

    # If the LLM decided to call a tool, route to the "tools" node.
    if last_message.tool_calls:
        return "continue"

    # If there are no tool calls, validate the final JSON response.
    return "validate"


def _validate_json_response(text: str) -> tuple[bool, dict | None, str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return False, None, f"Invalid JSON: {exc}"
    required = {"message": str, "is_error": bool, "error_message": str}
    for key, expected_type in required.items():
        if key not in data:
            return False, None, f"Missing key: {key}"
        if not isinstance(data[key], expected_type):
            return False, None, f"Invalid type for {key}"
    if data["is_error"] is False and data["error_message"]:
        return False, None, "error_message must be empty when is_error is false"
    if data["is_error"] is True and not data["error_message"]:
        return False, None, "error_message must be non-empty when is_error is true"
    return True, data, ""


def validate_agent_node(state: AgentState):
    last_message = state["messages"][-1]
    validator_prompt = SystemMessage(content=(
        "You are a strict JSON validator. "
        "Check whether the last assistant message is valid JSON with exactly these keys: "
        "message (string), is_error (boolean), error_message (string). "
        "If is_error is false, error_message must be empty. "
        "If is_error is true, error_message must be non-empty. "
        "Respond ONLY with JSON string withno markdown in this schema:\n"
        "{\n"
        "  \"valid\": boolean,\n"
        "  \"error_message\": string\n"
        "}\n"
        "Do not include any other text."
    ))
    response = validator_llm.invoke([validator_prompt, HumanMessage(content=last_message.content or "")])
    return {"messages": [response]}


def should_retry(state: AgentState) -> str:
    last_message = state["messages"][-1]
    try:
        decision = json.loads(last_message.content or "")
    except json.JSONDecodeError:
        return "retry"
    if isinstance(decision, dict) and decision.get("valid") is True:
        return "end"
    return "retry"

# ==========================================
# 5. Build and Compile the Graph
# ==========================================
# Initialize the state machine
workflow = StateGraph(AgentState)

# Add our two nodes to the graph
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)
workflow.add_node("validate", validate_agent_node)

# Set the entry point: the graph always starts at the reasoning agent
workflow.add_edge(START, "agent")

# Add the conditional edge: After 'agent', check 'should_continue'
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "continue": "tools",    # If the LLM called a tool, go to 'tools'
        "validate": "validate"  # Otherwise, validate JSON output
    }
)

# Add a normal edge: After tools execute, ALWAYS loop back to the 'agent'
# so the LLM can observe the output and decide what to do next (Reason).
workflow.add_edge("tools", "agent")
workflow.add_conditional_edges(
    "validate",
    should_retry,
    {
        "retry": "agent",
        "end": END,
    },
)

# Compile the graph into an executable application
react_graph = workflow.compile()

# ==========================================
# 6. Execute the Graph
# ==========================================

async def run_custom_react_agent(user_query: str):
    print(f"User Query: {user_query}\n" + "-"*50)

    # Initialize the starting state
    initial_state = {"messages": [HumanMessage(content=user_query)]}

    # Stream the state updates as the graph executes
    final_json = None
    async for event in react_graph.astream(initial_state):
        for node_name, node_state in event.items():
            print(f"\n>>> Step executed by node: [{node_name.upper()}] <<<")
            print("="*80)
            print(node_state)
            print("="*80)
            if not node_state.get("messages"):
                continue
            latest_message = node_state["messages"][-1]

            if node_name == "agent":
                if latest_message.tool_calls:
                    print(f"Action: LLM requested tool '{latest_message.tool_calls[0]['name']}'")
                else:
                    is_valid, data, _ = _validate_json_response(latest_message.content or "")
                    if is_valid:
                        final_json = data
                    print(f"Final Answer:\n{latest_message.content}")
            elif node_name == "validate":
                print(f"Validator Decision:\n{latest_message.content}")

            elif node_name == "tools":
                print(f"Observation (Execution Output):\n{latest_message.content}")

    if final_json is not None:
        print("\nFinal JSON Response:")
        print(json.dumps(final_json, ensure_ascii=True))

if __name__ == "__main__":
    # test_prompt = "Write a program to sort 100 numbers and show me the code"
    # test_prompt = "Create a shape file that contains a point exactly at Bangkok, Thailand (anywhere in Bangkok)"
    test_prompt = "ช่วยสร้างเลเยอร์ที่โชว์จุดสนามบินสุวรรณภูมืแล้ว export มาเป็น shape file"
    asyncio.run(run_custom_react_agent(test_prompt))
