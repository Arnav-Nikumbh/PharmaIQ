"""The workflow that decides how a question gets answered.

    supervisor ─┬─ off_topic ─────────────────────────► end
                ├─ research ── rag ──────────► synthesis ► end
                ├─ sql ─────────────── sql ─── synthesis ► end
                └─ cross ───── rag ── context ─ sql ─ synthesis ► end

The cross path is the point of the project: what the research turns up
decides what gets looked up in the sales database.
"""

from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agents.rag_agent import answer_question
from agents.sql_agent import run_sql
from agents.supervisor import OFF_TOPIC_REPLY, classify
from agents.synthesis_agent import synthesize
from agents.context_extractor import extract_context

RAG_CHUNKS = 6


class State(TypedDict, total=False):
    question: str
    route: str
    documents: list[dict]
    research_answer: str
    research_context: dict
    citations: list[dict]
    sql_query: str
    sql_results: list[dict]
    sql_error: str | None
    answer: str


def build_graph(retriever, db, llm, checkpointer=None):
    """Wire the agents into a graph. Dependencies are injected so tests can stub them."""

    def supervisor_node(state: State) -> State:
        return {"route": classify(state["question"], llm)}

    def off_topic_node(state: State) -> State:
        return {"answer": OFF_TOPIC_REPLY}

    def rag_node(state: State) -> State:
        result = answer_question(state["question"], retriever, llm, k=RAG_CHUNKS)
        return {
            "documents": result["documents"],
            "research_answer": result["answer"],
            "citations": result["citations"],
        }

    def context_node(state: State) -> State:
        return {"research_context": extract_context(state.get("documents", []), llm, db)}

    def sql_node(state: State) -> State:
        result = run_sql(
            state["question"], db, llm, research_context=state.get("research_context")
        )
        return {
            "sql_query": result["sql"],
            "sql_results": result["results"],
            "sql_error": result["error"],
        }

    def synthesis_node(state: State) -> State:
        rag_result = {
            "answer": state.get("research_answer", ""),
            "citations": state.get("citations", []),
        }
        sql_result = None
        if state.get("sql_query"):
            sql_result = {
                "sql": state["sql_query"],
                "results": state.get("sql_results", []),
                "error": state.get("sql_error"),
            }
        return {"answer": synthesize(state["question"], rag_result, sql_result, llm)}

    graph = StateGraph(State)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("off_topic", off_topic_node)
    graph.add_node("rag", rag_node)
    graph.add_node("context", context_node)
    graph.add_node("sql", sql_node)
    graph.add_node("synthesis", synthesis_node)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        lambda state: state["route"],
        {"off_topic": "off_topic", "research": "rag", "sql": "sql", "cross": "rag"},
    )
    # After retrieval, a cross-source question carries on into the database.
    graph.add_conditional_edges(
        "rag",
        lambda state: "context" if state["route"] == "cross" else "synthesis",
        {"context": "context", "synthesis": "synthesis"},
    )
    graph.add_edge("context", "sql")
    graph.add_edge("sql", "synthesis")
    graph.add_edge("off_topic", END)
    graph.add_edge("synthesis", END)

    return graph.compile(checkpointer=checkpointer or MemorySaver())


def ask(compiled_graph, question: str, thread_id: str = "default") -> State:
    """Run one question through the graph and return the finished state."""
    return compiled_graph.invoke(
        {"question": question},
        config={"configurable": {"thread_id": thread_id}},
    )
