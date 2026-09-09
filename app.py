"""PharmaIQ web interface.

Run: uv run streamlit run app.py

Each answer can be opened up to show how it was reached: which path was
taken, what research was found, what was pulled out of that research, and
the query that produced the numbers.
"""

import pandas as pd
import streamlit as st

import config
from agents.llm import get_llm
from graph import ask, build_graph
from tools.tools import get_db, get_retriever

st.set_page_config(page_title="PharmaIQ", page_icon="🔎", layout="wide")

ROUTE_LABELS = {
    "research": "Looked at published research only",
    "sql": "Looked at our sales data only",
    "cross": "Used the research to decide what to look up in our sales data",
    "off_topic": "Outside what this assistant covers",
}


@st.cache_resource
def load_graph():
    return build_graph(get_retriever(), get_db(), get_llm())


def show_details(state):
    """Show the working behind an answer."""
    route = state.get("route", "")
    if route:
        st.caption(ROUTE_LABELS.get(route, route))

    if state.get("documents"):
        with st.expander(f"Research found ({len(state['documents'])} extracts)"):
            for citation in state.get("citations", []):
                st.markdown(
                    f"**[{citation['number']}] {citation['title']}**  \n"
                    f"{citation['source']} {citation['document_id']} · "
                    f"[open]({citation['url']})"
                )
            st.divider()
            for chunk in state["documents"]:
                st.text(chunk["text"][:400] + "...")

    context = state.get("research_context") or {}
    if context.get("entities"):
        with st.expander("What was pulled out of the research"):
            st.json(context["entities"])
            matched = context.get("matched", {})
            found = [*matched.get("categories", []), *matched.get("products", [])]
            if found:
                st.success("Found in our catalogue: " + ", ".join(found))
            if context.get("unmatched"):
                st.info(
                    "Mentioned in the research but not in our catalogue: "
                    + ", ".join(context["unmatched"])
                )

    if state.get("sql_query"):
        with st.expander("Database query"):
            st.code(state["sql_query"], language="sql")
            if state.get("sql_error"):
                st.error(f"The query failed: {state['sql_error']}")
            elif state.get("sql_results"):
                st.dataframe(pd.DataFrame(state["sql_results"]), width="stretch")
            else:
                st.info("The query ran but returned no rows.")


def sidebar():
    st.sidebar.header("PharmaIQ")
    st.sidebar.write(
        "Ask about published research, about our sales data, or about both at once."
    )

    st.sidebar.subheader("What is loaded")
    try:
        st.sidebar.write(f"Research extracts indexed: {get_retriever().count()}")
    except Exception as exc:
        st.sidebar.error(f"Search index not ready: {exc}")
    try:
        rows = get_db().execute_select("SELECT COUNT(*) AS n FROM Orders")
        st.sidebar.write(f"Orders in the sales database: {rows[0]['n']}")
    except Exception as exc:
        st.sidebar.error(f"Database not ready: {exc}")

    st.sidebar.subheader("Add more research")
    st.sidebar.code(
        'uv run python -m ingestion.ingest --topic "your topic" --limit 25',
        language="bash",
    )

    if st.sidebar.button("Start a new conversation"):
        st.session_state.messages = []
        st.session_state.thread += 1
        st.rerun()


def main():
    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.thread = 1

    sidebar()
    st.title("PharmaIQ")

    if not config.GROQ_API_KEY:
        st.warning(
            "No API key found. Copy .env.example to .env and paste your Groq key "
            "into it, then reload this page."
        )
        st.stop()

    st.caption("Try: which therapy areas are selling best in the West region?")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("state"):
                show_details(message["state"])

    question = st.chat_input("Ask a question")
    if not question:
        return

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Working on it..."):
            try:
                state = ask(load_graph(), question, thread_id=str(st.session_state.thread))
            except Exception as exc:
                st.error(f"Something went wrong: {exc}")
                return
        answer = state.get("answer", "")
        st.markdown(answer)
        show_details(state)

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "state": state}
    )


if __name__ == "__main__":
    main()
