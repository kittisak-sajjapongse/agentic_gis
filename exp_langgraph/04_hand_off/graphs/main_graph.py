from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from IAgentState import IAgentState
from .input_retrieval_graph import (
    INPUT_RETRIEVAL_GRAPH_NAME,
    build_input_retrieval_graph,
)
from .output_producer_graph import (
    OUTPUT_PRODUCER_GRAPH_NAME,
    build_output_producer_graph,
)


async def build_main_graph():
    workflow = StateGraph(IAgentState)
    ir_graph = build_input_retrieval_graph()
    op_graph = await build_output_producer_graph()

    workflow.add_node(INPUT_RETRIEVAL_GRAPH_NAME, ir_graph)
    workflow.add_node(OUTPUT_PRODUCER_GRAPH_NAME, op_graph)

    workflow.add_edge(START, INPUT_RETRIEVAL_GRAPH_NAME)
    workflow.add_conditional_edges(
        INPUT_RETRIEVAL_GRAPH_NAME,
        lambda state: state["is_query_accepted"],
        {
            True: OUTPUT_PRODUCER_GRAPH_NAME,
            False: END,
        },
    )
    workflow.add_edge(OUTPUT_PRODUCER_GRAPH_NAME, END)

    return workflow.compile(checkpointer=MemorySaver())
