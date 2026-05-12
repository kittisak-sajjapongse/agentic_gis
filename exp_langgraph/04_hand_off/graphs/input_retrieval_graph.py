"""Canonical module for input-retrieval graph wiring."""

from GraphInputRetrieval import (  # compatibility import during migration
    INPUT_RETRIEVAL_GRAPH_NAME,
    IR_CLARIFICATION_INTERRUPT_TYPE,
    IrState,
    build_input_retrieval_graph,
)

__all__ = [
    "INPUT_RETRIEVAL_GRAPH_NAME",
    "IR_CLARIFICATION_INTERRUPT_TYPE",
    "IrState",
    "build_input_retrieval_graph",
]
