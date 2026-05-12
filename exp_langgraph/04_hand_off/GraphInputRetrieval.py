"""Compatibility shim.

Use graphs.input_retrieval_graph for new imports.
"""

from graphs.input_retrieval_graph import (
    INPUT_RETRIEVAL_GRAPH_NAME,
    IR_CLARIFICATION_INTERRUPT_TYPE,
    IrState,
    ask_user_node,
    build_input_retrieval_graph,
    needs_tool_or_human,
)

__all__ = [
    "INPUT_RETRIEVAL_GRAPH_NAME",
    "IR_CLARIFICATION_INTERRUPT_TYPE",
    "IrState",
    "needs_tool_or_human",
    "ask_user_node",
    "build_input_retrieval_graph",
]
