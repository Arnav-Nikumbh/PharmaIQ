"""PharmaIQ web interface.

Run: uv run streamlit run app.py

Each answer can be opened up to show how it was reached: which path was
taken, what research was found, what was pulled out of that research, and
the query that produced the numbers.

The colours and font live in .streamlit/config.toml. The CSS below only adds
spacing and a few classes for the header and sidebar tags.
"""

import html

import pandas as pd
import streamlit as st

import config
from agents.llm import get_llm
from graph import ask, build_graph
from tools.tools import get_db, get_retriever

st.set_page_config(page_title="PharmaIQ", page_icon="🔎", layout="wide")

# label, badge colour, icon
ROUTES = {
    "research": ("Published research", "blue", ":material/science:"),
    "sql": ("Sales data", "green", ":material/database:"),
    "cross": ("Research, then sales data", "violet", ":material/hub:"),
    "off_topic": ("Outside what this assistant covers", "gray", ":material/block:"),
}

STARTERS = [
    (
        "Research",
        "What do recent studies report about treatments for type 2 diabetes?",
    ),
    (
        "Sales data",
        "Which therapy areas are selling best in the West region?",
    ),
    (
        "Both",
        "Recent research covers diabetes and heart treatments. Compare how those "
        "two therapy areas are performing across our regions.",
    ),
]

USER_AVATAR = ":material/person:"
ASSISTANT_AVATAR = ":material/biotech:"

CSS = """
<style>
[data-testid="stMainBlockContainer"] { max-width: 1080px; padding-top: 2.5rem; }
[data-testid="stSidebarContent"] { padding-top: 0.5rem; }

.piq-eyebrow {
  font-size: 0.75rem; font-weight: 600; letter-spacing: 0.08em;
  text-transform: uppercase; color: #0E7C7B;
}
.piq-title { font-size: 2.2rem; font-weight: 700; line-height: 1.15; margin: 0.25rem 0 0.5rem; }
.piq-sub { color: #52606D; font-size: 1.02rem; max-width: 44rem; margin-bottom: 1.5rem; }

.piq-label {
  font-size: 0.72rem; font-weight: 600; letter-spacing: 0.06em;
  text-transform: uppercase; color: #52606D; margin: 1.1rem 0 0.4rem;
}
.piq-tags { display: flex; flex-wrap: wrap; gap: 0.35rem; }
.piq-tag {
  background: #EDF2F6; color: #1B2733; border-radius: 6px;
  padding: 0.15rem 0.5rem; font-size: 0.8rem; line-height: 1.4;
}
.piq-note { color: #7B8794; font-size: 0.78rem; line-height: 1.45; }

.piq-starter-kind {
  font-size: 0.72rem; font-weight: 600; letter-spacing: 0.06em;
  text-transform: uppercase; color: #0E7C7B;
}
.piq-starter-text { font-size: 0.95rem; color: #1B2733; margin: 0.3rem 0 0.6rem; }
@media (min-width: 640px) { .piq-starter-text { min-height: 6.2rem; } }

[data-testid="stChatMessage"] {
  background: #FFFFFF; border: 1px solid #DCE3EA; border-radius: 12px;
  padding: 1rem 1.25rem; margin-bottom: 0.75rem;
}
</style>
"""


@st.cache_resource
def load_graph():
    return build_graph(get_retriever(), get_db(), get_llm())


@st.cache_data(ttl=600)
def loaded_topics() -> list[str]:
    """Research topics that have been ingested, read from the saved chunk files."""
    files = sorted(config.DATA_DIR.glob("chunks_*.json"))
    return [f.stem.removeprefix("chunks_").replace("-", " ").capitalize() for f in files]


@st.cache_data(ttl=600)
def catalogue() -> dict:
    """What the sales data covers, so people know what they can ask about."""
    db = get_db()
    return {
        "regions": [r["RegionDescription"] for r in db.execute_select(
            "SELECT RegionDescription FROM Region ORDER BY RegionID")],
        "areas": [r["CategoryName"] for r in db.execute_select(
            "SELECT CategoryName FROM Categories ORDER BY CategoryName")],
        "countries": [r["Country"] for r in db.execute_select(
            "SELECT DISTINCT Country FROM Customers ORDER BY Country")],
    }


def tags(values) -> str:
    spans = "".join(f'<span class="piq-tag">{html.escape(str(v))}</span>' for v in values)
    return f'<div class="piq-tags">{spans}</div>'


def label(text: str, target=st) -> None:
    target.markdown(f'<div class="piq-label">{html.escape(text)}</div>', unsafe_allow_html=True)


def show_details(state):
    """Show the working behind an answer."""
    route = state.get("route", "")
    if route in ROUTES:
        text, colour, icon = ROUTES[route]
        st.badge(text, icon=icon, color=colour)

    if state.get("documents"):
        citations = state.get("citations", [])
        with st.expander(f"Sources ({len(citations)} cited)", icon=":material/article:"):
            for citation in citations:
                st.markdown(
                    f"**[{citation['number']}] {citation['title']}**  \n"
                    f":gray[{citation['source']} · {citation['document_id']}] · "
                    f"[open]({citation['url']})"
                )
            st.divider()
            st.caption(f"{len(state['documents'])} extracts were read")
            for chunk in state["documents"]:
                st.text(chunk["text"][:400] + "...")

    context = state.get("research_context") or {}
    if context.get("entities"):
        with st.expander("What was pulled out of the research", icon=":material/manage_search:"):
            st.json(context["entities"], expanded=False)
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
        with st.expander("Database query", icon=":material/code:"):
            st.code(state["sql_query"], language="sql")
            if state.get("sql_error"):
                st.error(f"The query failed: {state['sql_error']}")
            elif state.get("sql_results"):
                rows = state["sql_results"]
                st.caption(f"{len(rows)} rows")
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            else:
                st.info(
                    "The query ran but returned no rows. The sidebar lists the "
                    "regions and therapy areas the sales data covers."
                )


def sidebar():
    with st.sidebar:
        st.markdown("### PharmaIQ")
        st.caption("Research and sales intelligence for life sciences.")

        try:
            research = get_retriever().count()
        except Exception as exc:
            research = None
            st.error(f"Search index not ready: {exc}")
        try:
            orders = get_db().execute_select("SELECT COUNT(*) AS n FROM Orders")[0]["n"]
        except Exception as exc:
            orders = None
            st.error(f"Database not ready: {exc}")

        left, right = st.columns(2)
        left.metric("Research extracts", f"{research:,}" if research is not None else "–")
        right.metric("Orders", f"{orders:,}" if orders is not None else "–")

        topics = loaded_topics()
        if topics:
            label("Research covers")
            st.markdown(tags(topics), unsafe_allow_html=True)

        if orders is not None:
            covers = catalogue()
            label("Sales regions")
            st.markdown(tags(covers["regions"]), unsafe_allow_html=True)
            label("Therapy areas")
            st.markdown(tags(covers["areas"]), unsafe_allow_html=True)
            if covers["countries"]:
                st.markdown(
                    '<p class="piq-note" style="margin-top:0.6rem">Customers are in '
                    f'{html.escape(", ".join(covers["countries"]))} only.</p>',
                    unsafe_allow_html=True,
                )

        st.write("")
        if st.button("New conversation", icon=":material/add_comment:", width="stretch"):
            st.session_state.messages = []
            st.session_state.thread += 1
            st.rerun()

        st.markdown(
            '<p class="piq-note" style="margin-top:1rem">Sales figures are synthetic. '
            "Research comes from ClinicalTrials.gov and PubMed.</p>",
            unsafe_allow_html=True,
        )


def header():
    st.markdown(
        '<div class="piq-eyebrow">Commercial intelligence</div>'
        '<div class="piq-title">PharmaIQ</div>'
        '<div class="piq-sub">Ask about published research, our sales data, or both. '
        "For combined questions, the research decides what gets looked up in the "
        "sales data.</div>",
        unsafe_allow_html=True,
    )


def queue_question(question: str) -> None:
    st.session_state.pending = question


def starters():
    """Example questions, one per path through the system."""
    columns = st.columns(len(STARTERS))
    for column, (kind, question) in zip(columns, STARTERS):
        with column.container(border=True):
            st.markdown(
                f'<div class="piq-starter-kind">{kind}</div>'
                f'<div class="piq-starter-text">{html.escape(question)}</div>',
                unsafe_allow_html=True,
            )
            st.button(
                "Ask this",
                key=f"starter-{kind}",
                icon=":material/arrow_forward:",
                on_click=queue_question,
                args=(question,),
                width="stretch",
            )


def main():
    st.markdown(CSS, unsafe_allow_html=True)
    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.thread = 1

    sidebar()
    header()

    if not config.GROQ_API_KEY:
        st.warning(
            "No Groq API key found. Locally, put GROQ_API_KEY in a .env file. "
            "On a host such as Render, add it as an environment variable. Then "
            "reload this page.",
            icon=":material/key:",
        )
        st.stop()

    question = st.chat_input("Ask about research, sales, or both")
    question = question or st.session_state.pop("pending", None)

    if not st.session_state.messages and not question:
        starters()
        return

    for message in st.session_state.messages:
        avatar = USER_AVATAR if message["role"] == "user" else ASSISTANT_AVATAR
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])
            if message.get("state"):
                show_details(message["state"])

    if not question:
        return

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(question)

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        with st.spinner("Reading the research and checking the data..."):
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
