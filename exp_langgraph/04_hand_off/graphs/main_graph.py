from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from domain.state_models import IAgentState
from .input_retrieval_graph import (
    INPUT_RETRIEVAL_GRAPH_NAME,
    build_input_retrieval_graph,
)
from .output_producer_graph import (
    OUTPUT_PRODUCER_GRAPH_NAME,
    build_output_producer_graph,
)


def route_after_ir(state: IAgentState) -> bool:
    """Route output of IR graph to OP graph only for explicitly accepted queries.

    IR can emit decline paths where `is_query_accepted` is `None` (unset).
    LangGraph conditional routing keys must match declared edges; returning
    `None` here would raise KeyError(None). Treat any non-True value as decline.
    Prompt improvements reduce frequency of bad values but should not be the
    only safeguard.
    """
    return bool(state.get("is_query_accepted") is True)


async def build_main_graph():
    workflow = StateGraph(IAgentState)
    ir_graph = build_input_retrieval_graph()
    op_graph = await build_output_producer_graph()

    workflow.add_node(INPUT_RETRIEVAL_GRAPH_NAME, ir_graph)
    workflow.add_node(OUTPUT_PRODUCER_GRAPH_NAME, op_graph)

    workflow.add_edge(START, INPUT_RETRIEVAL_GRAPH_NAME)
    workflow.add_conditional_edges(
        INPUT_RETRIEVAL_GRAPH_NAME,
        route_after_ir,
        {
            True: OUTPUT_PRODUCER_GRAPH_NAME,
            False: END,
        },
    )
    workflow.add_edge(OUTPUT_PRODUCER_GRAPH_NAME, END)

    return workflow.compile(checkpointer=MemorySaver())
