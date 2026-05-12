"""Compatibility shim.

Use graphs.output_producer_graph for new imports.
"""

from graphs.output_producer_graph import (
    OP_CLARIFICATION_INTERRUPT_TYPE,
    OUTPUT_PRODUCER_GRAPH_NAME,
    OpState,
    ask_user_node,
    build_output_producer_graph,
    next_step,
)
from domain.state_models import OpOutput

__all__ = [
    "OUTPUT_PRODUCER_GRAPH_NAME",
    "OP_CLARIFICATION_INTERRUPT_TYPE",
    "OpOutput",
    "OpState",
    "next_step",
    "ask_user_node",
    "build_output_producer_graph",
]
