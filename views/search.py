"""View for triple-pattern search over compressed COTTAS files."""
from __future__ import annotations
import datetime, time
import pandas as pd
import streamlit as st
from utils.cottas_bridge import COTTASError, get_metadata, get_search_sql, search_triple_pattern
from utils.file_manager import file_size_mb, persist_uploaded_file
from utils.validation import build_triple_pattern, recommend_index

MAX_DISPLAY = 10_000


def render() -> None:
    _page_header("Triple Search",
                 "Evaluate triple patterns directly on the compressed file. Leave a field empty to use it as a variable.")

    tab_upload, tab_active = st.tabs(["Upload file", "Active file"])
    cottas_path = None

    with tab_upload:
        uploaded = st.file_uploader("COTTAS file", type=["cottas", "parquet"], key="search_upload")
        if uploaded:
            cottas_path = persist_uploaded_file(uploaded, state_key="search_uploaded_path", suffix=".cottas")
            st.session_state["active_cottas"] = cottas_path
            st.session_state["active_name"] = uploaded.name
            st.success(f"{uploaded.name} ({file_size_mb(cottas_path):.2f} MB) ready.")

    with tab_active:
        if st.session_state.get("active_cottas"):
            cottas_path = st.session_state["active_cottas"]
            st.info(f"Using **{st.session_state['active_name']}** · {file_size_mb(cottas_path):.2f} MB")
        else:
            st.markdown("<div class='info-box muted'>No active COTTAS file. Load one from the <b>Upload file</b> tab.</div>", unsafe_allow_html=True)

    if cottas_path is None:
        return

    try:
        meta = get_metadata(cottas_path)
    except COTTASError as exc:
        st.error(str(exc))
        return

    st.divider()
    _section_title("Search pattern")
    st.markdown(
        "<div class='info-box'>N3-serialized RDF terms. Examples: "
        "<code>&lt;http://dbpedia.org/resource/Madrid&gt;</code>, "
        "<code>&quot;Madrid&quot;@es</code>, "
        "<code>&quot;42&quot;^^&lt;http://www.w3.org/2001/XMLSchema#integer&gt;</code>.</div>",
        unsafe_allow_html=True,
    )

    col_s, col_p, col_o = st.columns(3)
    with col_s:
        subject = st.text_input("Subject", placeholder="<http://...> or empty", key="search_subject")
    with col_p:
        predicate = st.text_input("Predicate", placeholder="<http://...> or empty", key="search_predicate")
    with col_o:
        obj = st.text_input("Object", placeholder='<http://...> / "literal" or empty', key="search_object")

    graph = None
    if meta.get("is_quad_table"):
        graph = st.text_input("Graph (optional)", placeholder="<http://...> or empty", key="search_graph")
        st.caption("This file is a quad table. You can optionally filter by named graph.")

    pattern_preview = (
        build_triple_pattern(subject.strip() or None, predicate.strip() or None, obj.strip() or None,
                             (graph.strip() or None) if graph else None)
        if meta.get("is_quad_table")
        else build_triple_pattern(subject.strip() or None, predicate.strip() or None, obj.strip() or None)
    )
    suggestion = recommend_index(subject, predicate, obj)

    st.markdown(
        f"<div class='info-box' style='font-family:\"JetBrains Mono\",monospace;'>Pattern · <b>{pattern_preview}</b></div>",
        unsafe_allow_html=True,
    )
    st.caption(f"Suggested index: **{suggestion}**")

    with st.form("search_form"):
        with st.expander("Advanced options"):
            limit = st.number_input("Result limit", min_value=1, max_value=1_000_000, value=MAX_DISPLAY, step=1_000)
            offset = st.number_input("Offset", min_value=0, max_value=1_000_000, value=0, step=100,
                                      help="Initial offset for engine-level pagination.")
            page_size = st.selectbox("Rows per page", [25, 50, 100, 200, 500], index=1)

        with st.expander("Generated SQL"):
            try:
                sql = get_search_sql(
                    cottas_path,
                    subject=subject.strip() or None,
                    predicate=predicate.strip() or None,
                    obj=obj.strip() or None,
                    graph=(graph.strip() or None) if (meta.get("is_quad_table") and graph) else None,
                    limit=int(limit), offset=int(offset),
                )
                st.code(sql, language="sql")
            except COTTASError as exc:
                st.warning(str(exc))

        submitted = st.form_submit_button("Search", type="primary", use_container_width=True)

    if submitted:
        _run_search(cottas_path, subject.strip() or None, predicate.strip() or None, obj.strip() or None,
                    (graph.strip() or None) if (meta.get("is_quad_table") and graph) else None,
                    int(limit), int(offset), int(page_size))

    if st.session_state.get("last_search_df") is not None:
        _display_results(st.session_state["last_search_df"], int(page_size),
                         key_prefix=f"search_results_{st.session_state.get('last_search_token', 'default')}")


def _run_search(cottas_path, subject, predicate, obj, graph, limit, offset, page_size):
    with st.spinner("Evaluating pattern..."):
        t0 = time.perf_counter()
        try:
            df = search_triple_pattern(cottas_path=cottas_path, subject=subject, predicate=predicate,
                                        obj=obj, graph=graph, limit=limit, offset=offset)
            elapsed = time.perf_counter() - t0
        except COTTASError as exc:
            st.error(str(exc))
            return

    n = len(df)
    if n >= limit:
        st.warning(f"Showing the first **{n:,}** results from offset {offset:,}. "
                   "Increase the limit or offset to continue browsing.")
    else:
        st.success(f"{n:,} results in {elapsed:.3f} s.")

    ts = datetime.datetime.now().strftime("%H:%M:%S")
    st.session_state["history"].append(
        f"[{ts}] Search · ({subject or '?'}, {predicate or '?'}, {obj or '?'}) → {n:,} results ({elapsed:.3f}s)"
    )
    st.session_state["last_search_df"] = df
    st.session_state["last_search_token"] = datetime.datetime.now().strftime("%H%M%S%f")


def _display_results(df: pd.DataFrame, page_size: int, key_prefix: str = "search_results"):
    if df.empty:
        st.info("No results for the specified pattern.")
        return

    n = len(df)
    total_pages = (n - 1) // page_size + 1
    _section_title(f"Results · {n:,} rows")

    if total_pages > 1:
        col_pg, col_info = st.columns([2, 3])
        with col_pg:
            page_num = st.number_input(f"Page (1–{total_pages})", min_value=1, max_value=total_pages,
                                        value=1, step=1, key=f"{key_prefix}_page")
        with col_info:
            st.caption(f"Page {page_num} of {total_pages} · {page_size} rows/page")
        start = (page_num - 1) * page_size
        page_df = df.iloc[start:start + page_size]
    else:
        page_df = df

    st.dataframe(page_df, use_container_width=True, height=420)
    st.download_button(label="Download results (CSV)",
                       data=df.to_csv(index=False).encode("utf-8"),
                       file_name="search_results.csv", mime="text/csv",
                       key=f"{key_prefix}_download")


def _page_header(title, subtitle):
    st.markdown(f"<div style='margin-bottom:24px;'><h1 style='color:#F1F5F9;font-weight:700;font-size:2rem;margin:0 0 8px 0;letter-spacing:-0.02em;'>{title}</h1><p style='color:#94A3B8;font-size:1.05rem;margin:0;line-height:1.55;'>{subtitle}</p></div>", unsafe_allow_html=True)


def _section_title(title):
    st.markdown(f"<div style='color:#F1F5F9;font-size:0.95rem;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;margin:6px 0 16px 0;'>{title}</div>", unsafe_allow_html=True)
