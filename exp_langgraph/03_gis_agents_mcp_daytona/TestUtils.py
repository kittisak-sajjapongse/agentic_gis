import pprint
from typing import Dict
from langgraph.graph.state import CompiledStateGraph


# REFERENCE:
# 1. Streaming - https://docs.langchain.com/oss/python/langgraph/streaming


def run_test_update(graph: CompiledStateGraph, initial_state: Dict) -> None:
    for event in graph.stream(initial_state):
        for node_name, node_state in event.items():
            print(f"=== Node: {node_name} ===")
            pprint.pprint(node_state)
            print("-" * 80)


def run_test_fullstate(graph: CompiledStateGraph, initial_state: Dict) -> None:
    for state_snapshot in graph.stream(initial_state, stream_mode="values"):
        pprint.pprint(state_snapshot)
        print("-" * 80)


def run_test_debug(graph: CompiledStateGraph, initial_state: Dict) -> None:
    for chunk in graph.stream(initial_state, mode="debug", version="v2"):
        if chunk["type"] == "updates":
            for node_name, state in chunk["data"].items():
                print(f"=== Node: `{node_name}` updated state ===")
                pprint.pprint(state)
                print("+" * 80)
        elif chunk["type"] == "custom":
            print(f"=== Node: `{node_name}` custom data ===")
            pprint.pprint(chunk)
        print("-" * 80)
