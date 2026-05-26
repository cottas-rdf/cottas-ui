"""View for exploring metadata and basic statistics of a COTTAS file."""
from __future__ import annotations
import streamlit as st
from utils.cottas_bridge import (COTTASError, get_metadata, get_predicate_distribution,
                                  get_sample_triples, verify_cottas_file)
from utils.file_manager import file_size_mb, persist_uploaded_file
from utils.stats import build_predicate_bar_chart


def render() -> None:
    _page_header("Explore", "Metadata, statistics, and triple sample without decompressing the graph.")

    tab_upload, tab_active = st.tabs(["Upload file", "Active file"])
    cottas_path = None
    cottas_name = None

    with tab_upload:
        uploaded = st.file_uploader("COTTAS file", type=["cottas", "parquet"])
        if uploaded:
            cottas_path = persist_uploaded_file(uploaded, state_key="explore_uploaded_path", suffix=".cottas")
            cottas_name = uploaded.name
            st.session_state["active_cottas"] = cottas_path
            st.session_state["active_name"] = cottas_name
            st.success(f"{cottas_name} ({file_size_mb(cottas_path):.2f} MB) loaded.")

    with tab_active:
        if st.session_state.get("active_cottas"):
            cottas_path = st.session_state["active_cottas"]
            cottas_name = st.session_state["active_name"]
            st.info(f"Using **{cottas_name}** · {file_size_mb(cottas_path):.2f} MB")
        else:
            st.markdown("<div class='info-box muted'>No active COTTAS file. Load one from the <b>Upload file</b> tab.</div>", unsafe_allow_html=True)

    if cottas_path is None:
        return

    try:
        is_valid = verify_cottas_file(cottas_path)
        meta = get_metadata(cottas_path)
    except COTTASError as exc:
        st.error(str(exc))
        return

    st.divider()
    _section_title("Metadata")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Valid", "Yes" if is_valid else "No")
    c2.metric("Triples", f"{meta['num_triples']:,}" if meta.get("num_triples") else "N/A")
    c3.metric("Index", meta.get("index", "N/A"))
    c4.metric("Properties", f"{meta['num_properties']:,}" if meta.get("num_properties") else "N/A")
    c5.metric("Type", "Quad table" if meta.get("is_quad_table") else "Triple table")

    c6, c7, c8, c9 = st.columns(4)
    c6.metric("Distinct subjects", f"{meta['num_distinct_subjects']:,}" if meta.get("num_distinct_subjects") else "N/A")
    c7.metric("Distinct objects", f"{meta['num_distinct_objects']:,}" if meta.get("num_distinct_objects") else "N/A")
    c8.metric("Row groups", f"{meta['num_triples_groups']:,}" if meta.get("num_triples_groups") else "N/A")
    c9.metric("Compression", meta.get("compression", "N/A"))

    if meta.get("issued") or meta.get("custom_metadata"):
        with st.expander("Additional metadata"):
            if meta.get("issued"):
                st.write(f"**Issued:** {meta['issued']}")
            st.json(meta.get("custom_metadata", {}))

    st.divider()
    _section_title("Triple sample")
    sample_limit = st.slider("Number of triples", min_value=10, max_value=500, value=50, step=10)

    if st.button("Load sample", use_container_width=True, key="explore_load_sample"):
        with st.spinner("Loading sample..."):
            try:
                df = get_sample_triples(cottas_path, limit=sample_limit)
            except COTTASError as exc:
                st.error(str(exc))
                return
        if df.empty:
            st.info("The graph contains no results for the requested sample.")
        else:
            st.dataframe(df, use_container_width=True, height=360)
            st.caption(f"Showing {len(df)} rows.")

    st.divider()
    _section_title("Predicate distribution")
    top_n = st.slider("Top-N predicates", min_value=5, max_value=50, value=20, step=5)

    if st.button("Calculate distribution", use_container_width=True, key="explore_calc_distribution"):
        with st.spinner("Calculating distribution..."):
            try:
                dist_df = get_predicate_distribution(cottas_path, top_n=top_n)
            except COTTASError as exc:
                st.error(str(exc))
                return
        if dist_df.empty:
            st.info("Could not calculate predicate distribution.")
            return
        st.plotly_chart(build_predicate_bar_chart(dist_df), use_container_width=True)
        with st.expander("View table"):
            st.dataframe(dist_df, use_container_width=True)


def _page_header(title, subtitle):
    st.markdown(f"<div style='margin-bottom:24px;'><h1 style='color:#F1F5F9;font-weight:700;font-size:2rem;margin:0 0 8px 0;letter-spacing:-0.02em;'>{title}</h1><p style='color:#94A3B8;font-size:1.05rem;margin:0;line-height:1.55;'>{subtitle}</p></div>", unsafe_allow_html=True)


def _section_title(title):
    st.markdown(f"<div style='color:#F1F5F9;font-size:0.95rem;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;margin:6px 0 16px 0;'>{title}</div>", unsafe_allow_html=True)
