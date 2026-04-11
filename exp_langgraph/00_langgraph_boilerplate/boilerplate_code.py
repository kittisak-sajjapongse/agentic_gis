from typing import TypedDict, Literal, Annotated
import operator
from langgraph.graph import StateGraph, START, END

### 1. Define the State Schema ###
class GraphState(TypedDict):
    # 'Annotated' with 'operator.add' tells LangGraph to append to this list 
    # instead of overwriting it when nodes return state updates.
    messages: Annotated[list, operator.add]
    status: str

### 2. Define Node Functions ###
def node_a(state: GraphState) -> dict:
    print("Executing Node A")
    # Return ONLY the keys you want to update/append in the state
    return {"messages": ["Node A completed"], "status": "processed"}

def node_b(state: GraphState) -> dict:
    print("Executing Node B")
    return {"messages": ["Node B completed"], "status": "finished"}

### 3. Define Conditional Routing ###
def router(state: GraphState) -> Literal["node_b", "__end__"]:
    # Inspect the current state to dictate the next transition
    if state.get("status") == "processed":
        return "node_b"
    return "__end__"

### 4. Build and Compile the Graph ###
# Initialize graph with the state schema
workflow = StateGraph(GraphState)

# Add nodes (assign a string name to each Python function)
workflow.add_node("node_a", node_a)
workflow.add_node("node_b", node_b)

# Define the flow (Edges)
workflow.add_edge(START, "node_a")
workflow.add_conditional_edges("node_a", router)
workflow.add_edge("node_b", END)

# Compile into a runnable application
# (You can optionally pass a checkpointer here for persistent memory)
app = workflow.compile()

### 5. Execute the Graph ###
if __name__ == "__main__":
    initial_state = {"messages": ["Start process"], "status": "started"}
    
    # Method 1: Invoke (Run to completion and return final state)
    final_state = app.invoke(initial_state)
    print("\nFinal State:", final_state)
    
    # Method 2: Stream (Yield state updates node-by-node as they occur)
    # for event in app.stream(initial_state):
    #     print("\nEvent Stream Update:", event)