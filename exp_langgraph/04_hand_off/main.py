import asyncio
import json

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from graphs.input_retrieval_graph import (
    IR_CLARIFICATION_INTERRUPT_TYPE,
)
from graphs.output_producer_graph import (
    OP_CLARIFICATION_INTERRUPT_TYPE,
)
from graphs.main_graph import build_main_graph

from dotenv import load_dotenv

load_dotenv()
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
            "actions": state.values.get("actions"),
            "decline_message": state.values.get("decline_message"),
        }
        print(f"AI: {json.dumps(response_payload, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    asyncio.run(run_cli())
