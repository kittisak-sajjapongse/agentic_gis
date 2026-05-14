import json
import pprint

from dotenv import load_dotenv
import chainlit as cl
from langgraph.types import Command
from langchain_core.messages import HumanMessage
from graphs.input_retrieval_graph import (
    IR_CLARIFICATION_INTERRUPT_TYPE,
)
from graphs.output_producer_graph import (
    OP_CLARIFICATION_INTERRUPT_TYPE,
    OUTPUT_PRODUCER_GRAPH_NAME,
)
from graphs.main_graph import build_main_graph

load_dotenv()
@cl.on_chat_start
async def on_chat_start():
    graph = await build_main_graph()
    thread_id = cl.user_session.get("id")
    cl.user_session.set("graph", graph)
    cl.user_session.set("config", {"configurable": {"thread_id": thread_id}})
    cl.user_session.set("is_interrupted", False)
    cl.user_session.set("pending_interrupt_id", None)


@cl.on_message
async def on_message(message: cl.Message):
    graph = cl.user_session.get("graph")
    config = cl.user_session.get("config")
    is_interrupted = cl.user_session.get("is_interrupted")
    pending_interrupt_id = cl.user_session.get("pending_interrupt_id")

    if is_interrupted:
        # Resume the exact pending interrupt by id.
        inputs = (
            Command(resume={pending_interrupt_id: message.content})
            if pending_interrupt_id
            else Command(resume=message.content)
        )
    else:
        inputs = {"_messages": [HumanMessage(content=message.content)]}

    async for event in graph.astream(inputs, config=config):
        for node_name, node_state in event.items():
            print(f"=== Node: {node_name} ===")
            pprint.pprint(node_state)
            print("-" * 80)

    state = await graph.aget_state(config)

    # For subgraphs, `state.next` may not expose inner node names (e.g. `ask_user`).
    # `state.interrupts` is the reliable signal that execution is paused at interrupt().
    if state.interrupts:
        # Typed interrupts: filter by `type` so we don't accidentally pick an
        # unrelated interrupt when multiple pause points exist.
        matching_interrupts = [
            intr
            for intr in state.interrupts
            if isinstance(intr.value, dict)
            and (
                intr.value.get("type") == IR_CLARIFICATION_INTERRUPT_TYPE or
                intr.value.get("type") == OP_CLARIFICATION_INTERRUPT_TYPE
            )
        ]

        if len(matching_interrupts) != 1:
            raise ValueError(
                f"Expected exactly one '{IR_CLARIFICATION_INTERRUPT_TYPE}' or '{OUTPUT_PRODUCER_GRAPH_NAME}' interrupt, "
                f"found {len(matching_interrupts)}"
            )

        matched_interrupt = matching_interrupts[0]
        interrupt_value = matched_interrupt.value
        question = interrupt_value.get("question")
        cl.user_session.set("is_interrupted", True)
        cl.user_session.set("pending_interrupt_id", matched_interrupt.id)

        await cl.Message(
            author="AI (Needs Clarification)",
            content=question,
        ).send()
        return

    cl.user_session.set("is_interrupted", False)
    cl.user_session.set("pending_interrupt_id", None)
    # response_payload = {
    #     "user_language": state.values.get("user_language"),
    #     "clarification_question": state.values.get("clarification_question"),
    #     "gis_related": state.values.get("gis_related"),
    #     "decline_message": state.values.get("decline_message"),
    #     "selected_layers": state.values.get("selected_layers"),
    #     "general_layers": state.values.get("general_layers"),
    #     "is_query_accepted": state.values.get("is_query_accepted"),
    #     "query_summary": state.values.get("query_summary"),
    # }
    response_payload = {
        "user_language": state.values.get("user_language"),
        "query_summary": state.values.get("query_summary"),
        "outputs": state.values.get("outputs"),
        "code_execution_result": state.values.get("code_execution_result"),
        "decline_message": state.values.get("decline_message"),
    }
    await cl.Message(content=json.dumps(response_payload, indent=2)).send()
