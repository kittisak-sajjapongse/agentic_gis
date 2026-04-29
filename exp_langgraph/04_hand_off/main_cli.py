import asyncio
import json

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from GraphInputRetrieval import (
    IR_CLARIFICATION_INTERRUPT_TYPE,
    INPUT_RETRIEVAL_GRAPH_NAME,
    build_input_retrieval_graph,
)
from GroupOutputProducer import (
    OP_CLARIFICATION_INTERRUPT_TYPE,
    OUTPUT_PRODUCER_GRAPH_NAME,
    build_output_producer_graph,
)
from IAgentState import IAgentState

from dotenv import load_dotenv

load_dotenv()


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
        {True: OUTPUT_PRODUCER_GRAPH_NAME, False: END},
    )
    workflow.add_edge(OUTPUT_PRODUCER_GRAPH_NAME, END)

    return workflow.compile(checkpointer=MemorySaver())


async def run_cli():
    graph = await build_main_graph()
    config = {"configurable": {"thread_id": "cli-session"}}
    pending_interrupt_id = None

    print("CLI chat started. Type 'exit' to quit.")

    while True:
        user_text = input("\nYou: ").strip()
        if user_text.lower() in {"exit", "quit"}:
            print("Bye.")
            return
        if not user_text:
            continue

        if pending_interrupt_id:
            inputs = Command(resume={pending_interrupt_id: user_text})
        else:
            inputs = {"_messages": [HumanMessage(content=user_text)]}

        async for _ in graph.astream(inputs, config=config):
            pass

        state = await graph.aget_state(config)

        if state.interrupts:
            matches = [
                intr
                for intr in state.interrupts
                if isinstance(intr.value, dict)
                and intr.value.get("type")
                in {IR_CLARIFICATION_INTERRUPT_TYPE, OP_CLARIFICATION_INTERRUPT_TYPE}
            ]
            if len(matches) != 1:
                print(
                    "AI: Error - expected exactly one known interrupt, "
                    f"found {len(matches)}"
                )
                pending_interrupt_id = None
                continue

            matched = matches[0]
            pending_interrupt_id = matched.id
            question = matched.value.get("question", "Need clarification.")
            print(f"AI (Needs Clarification): {question}")
            continue

        pending_interrupt_id = None
        response_payload = {
            "user_language": state.values.get("user_language"),
            "query_summary": state.values.get("query_summary"),
            "outputs": state.values.get("outputs"),
            "decline_message": state.values.get("decline_message"),
        }
        print(f"AI: {json.dumps(response_payload, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    asyncio.run(run_cli())
