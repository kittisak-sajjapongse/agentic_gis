import os
from typing import TypedDict, Annotated, Optional

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import interrupt, Command

load_dotenv()


class GraphState(TypedDict):
    messages: Annotated[list, add_messages]
    question_for_user: Optional[str]
    final_response: Optional[str]


llm = ChatOpenAI(
    model="gpt-4o",
    api_key=os.environ.get("OPENAI_API_KEY"),
    temperature=0.7,
)


def ai_node(state: GraphState) -> GraphState:
    system_prompt = SystemMessage(
        content=(
            "You are a helpful AI assistant.\n"
            "When you receive a request:\n"
            "- If you need clarification to give a better answer, respond ONLY with:\n"
            "  QUESTION: <your single clarifying question here>\n"
            "- If you have enough information, respond ONLY with:\n"
            "  ANSWER: <your full response here>"
        )
    )

    response = llm.invoke([system_prompt] + state["messages"])
    ai_text = response.content.strip()

    if ai_text.startswith("QUESTION:"):
        question = ai_text[len("QUESTION:") :].strip()
        return {
            "messages": [AIMessage(content=ai_text)],
            "question_for_user": question,
            "final_response": None,
        }

    answer = ai_text[len("ANSWER:") :].strip() if ai_text.startswith("ANSWER:") else ai_text
    return {
        "messages": [AIMessage(content=ai_text)],
        "question_for_user": None,
        "final_response": answer,
    }


def check_if_question(state: GraphState) -> str:
    if state.get("question_for_user"):
        return "ask_user"
    return "end"


def ask_user_node(state: GraphState) -> GraphState:
    question = state["question_for_user"]
    user_answer = interrupt({"question": question, "type": "clarification"})
    return {
        "messages": [HumanMessage(content=user_answer)],
        "question_for_user": None,
        "final_response": None,
    }


def build_graph():
    builder = StateGraph(GraphState)
    builder.add_node("ai_node", ai_node)
    builder.add_node("ask_user", ask_user_node)

    builder.add_edge(START, "ai_node")
    builder.add_conditional_edges("ai_node", check_if_question, {"ask_user": "ask_user", "end": END})
    builder.add_edge("ask_user", "ai_node")

    return builder.compile(checkpointer=MemorySaver())


def run_cli() -> None:
    graph = build_graph()
    config = {"configurable": {"thread_id": "human-in-the-loop-cli"}}

    print("Human-in-the-loop CLI started. Type 'exit' to quit.")
    pending_interrupt_id = None

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
            inputs = {"messages": [HumanMessage(content=user_text)]}

        graph.invoke(inputs, config=config)
        state = graph.get_state(config)

        if state.interrupts:
            matched = state.interrupts[0]
            pending_interrupt_id = matched.id
            question = None
            if isinstance(matched.value, dict):
                question = matched.value.get("question")
            print(f"AI (Needs Clarification): {question or 'Need clarification.'}")
            continue

        pending_interrupt_id = None
        final_answer = state.values.get("final_response")
        print(f"AI: {final_answer}")


if __name__ == "__main__":
    run_cli()
