"""View for SPARQL SELECT queries over COTTAS files."""
from __future__ import annotations
import datetime, time
import streamlit as st
from utils.cottas_bridge import COTTASError, get_metadata, run_sparql_select
from utils.file_manager import file_size_mb, persist_uploaded_file
from utils.validation import is_select_query

DEFAULT_QUERY = """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?s ?p ?o
WHERE {
  ?s ?p ?o .
}
LIMIT 50
"""


def render() -> None:
    _page_header("SPARQL Query",
                 "Run <code>SELECT</code> queries over the COTTAS graph using COTTASStore as an RDFLib backend.")

    tab_up, tab_act = st.tabs(["Upload file", "Active file"])
    cottas_path = None

    with tab_up:
        uploaded = st.file_uploader("COTTAS file", type=["cottas", "parquet"], key="sparql_up")
        if uploaded:
            cottas_path = persist_uploaded_file(uploaded, state_key="sparql_uploaded_path", suffix=".cottas")
            st.session_state["active_cottas"] = cottas_path
            st.session_state["active_name"] = uploaded.name
            st.success(f"{uploaded.name} ({file_size_mb(cottas_path):.2f} MB) ready.")

    with tab_act:
        if st.session_state.get("active_cottas"):
            cottas_path = st.session_state["active_cottas"]
            st.info(f"Using **{st.session_state['active_name']}** · {file_size_mb(cottas_path):.2f} MB")
        else:
            st.markdown("<div class='info-box muted'>No active COTTAS file. Load one from the <b>Upload file</b> tab.</div>", unsafe_allow_html=True)

    if not cottas_path:
        return

    try:
        meta = get_metadata(cottas_path)
    except COTTASError as exc:
        st.error(str(exc))
        return

    if meta.get("is_quad_table"):
        st.info("This file is a **quad table**. Queries may reference named graphs.")

    st.divider()
    _section_title("Query")
    st.markdown(
        "<div class='info-box'>Only read queries (<code>SELECT</code>) are supported. "
        "Modification operations are out of scope.</div>",
        unsafe_allow_html=True,
    )

    with st.form("sparql_form"):
        query = st.text_area("SPARQL Query", value=DEFAULT_QUERY, height=240,
                              help="You can include PREFIX declarations and a LIMIT clause in the query itself.")
        limit_override = st.number_input(
            "Additional result limit (0 = no limit)",
            min_value=0, max_value=100_000, value=0, step=100,
            help="Applied after query execution to limit the rows shown in the UI.",
        )
        submitted = st.form_submit_button("Execute", type="primary", use_container_width=True)

    if submitted:
        _run_sparql(cottas_path, query, int(limit_override))

    if st.session_state.get("last_sparql_df") is not None:
        _show_results(st.session_state["last_sparql_df"],
                      key_prefix=f"sparql_results_{st.session_state.get('last_sparql_token', 'default')}")


def _run_sparql(cottas_path: str, query: str, limit_override: int):
    if not is_select_query(query):
        st.error("Only SELECT queries are supported. You can include PREFIX or BASE before the SELECT.")
        return

    with st.spinner("Executing query..."):
        t0 = time.perf_counter()
        try:
            df = run_sparql_select(cottas_path, query)
            elapsed = time.perf_counter() - t0
        except COTTASError as exc:
            st.error(str(exc))
            return

    total_rows = len(df)
    if limit_override > 0 and len(df) > limit_override:
        df = df.head(limit_override)
        st.warning(f"The query returned {total_rows:,} rows. Showing only the first {limit_override:,}.")

    st.success(f"{total_rows:,} results in {elapsed:.3f} s.")

    ts = datetime.datetime.now().strftime("%H:%M:%S")
    st.session_state["history"].append(f"[{ts}] SPARQL · {total_rows:,} results ({elapsed:.3f}s)")
    st.session_state["last_sparql_df"] = df
    st.session_state["last_sparql_token"] = datetime.datetime.now().strftime("%H%M%S%f")


def _show_results(df, key_prefix: str = "sparql_results"):
    if df.empty:
        st.info("The query returned no results.")
        return

    _section_title(f"Results · {len(df):,} rows")
    st.dataframe(df, use_container_width=True, height=420)
    st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"),
                       file_name="sparql_results.csv", mime="text/csv",
                       key=f"{key_prefix}_download")


def _page_header(title, subtitle):
    st.markdown(f"<div style='margin-bottom:24px;'><h1 style='color:#F1F5F9;font-weight:700;font-size:2rem;margin:0 0 8px 0;letter-spacing:-0.02em;'>{title}</h1><p style='color:#94A3B8;font-size:1.05rem;margin:0;line-height:1.55;'>{subtitle}</p></div>", unsafe_allow_html=True)


def _section_title(title):
    st.markdown(f"<div style='color:#F1F5F9;font-size:0.95rem;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;margin:6px 0 16px 0;'>{title}</div>", unsafe_allow_html=True)
