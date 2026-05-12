"""Canonical module for output-producer graph wiring."""

from GroupOutputProducer import (  # compatibility import during migration
    OUTPUT_PRODUCER_GRAPH_NAME,
    OP_CLARIFICATION_INTERRUPT_TYPE,
    OpState,
    build_output_producer_graph,
)

__all__ = [
    "OUTPUT_PRODUCER_GRAPH_NAME",
    "OP_CLARIFICATION_INTERRUPT_TYPE",
    "OpState",
    "build_output_producer_graph",
]
