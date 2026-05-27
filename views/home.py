"""Landing page."""

from __future__ import annotations

from importlib import metadata

import streamlit as st


def render() -> None:
    st.markdown(
        """
        <div style='margin-bottom:28px;'>
          <h1 style='font-weight:700;font-size:2.6rem;color:#F1F5F9;
                     margin:0 0 10px 0;line-height:1.1;letter-spacing:-0.02em;'>
            COTTAS Manager
          </h1>
          <p style='color:#94A3B8;font-size:1.15rem;max-width:720px;
                    margin:0;line-height:1.6;'>
            Compression, querying, and analysis of RDF graphs through the
            columnar <b style='color:#F1F5F9;font-weight:600;'>COTTAS</b> format.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _section_title("Conversion", "Transformation between RDF and COTTAS")
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        st.markdown(_card("compress", "#3B82F6", "Compress",
            "From RDF to COTTAS. Accepts TTL, NT, NQ, TriG, N3, and RDF/XML."), unsafe_allow_html=True)
    with c2:
        st.markdown(_card("unarchive", "#3B82F6", "Decompress",
            "From COTTAS to RDF in the output format you need."), unsafe_allow_html=True)

    st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)

    _section_title("Query & analysis", "Exploration of the compressed graph")
    c3, c4, c5 = st.columns(3, gap="medium")
    with c3:
        st.markdown(_card("travel_explore", "#A78BFA", "Explore",
            "Metadata, triple sample, and predicate distribution."), unsafe_allow_html=True)
    with c4:
        st.markdown(_card("manage_search", "#A78BFA", "Triple Search",
            "Triple patterns directly on the compressed file."), unsafe_allow_html=True)
    with c5:
        st.markdown(_card("terminal", "#A78BFA", "SPARQL",
            "SELECT queries using COTTASStore and RDFLib."), unsafe_allow_html=True)

    st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)

    _section_title("Graph operations", "Comparison and composition")
    c6, c7 = st.columns(2, gap="medium")
    with c6:
        st.markdown(_card("compare", "#3B82F6", "Difference",
            "Triples present in one graph but absent in the other."), unsafe_allow_html=True)
    with c7:
        st.markdown(_card("merge", "#3B82F6", "Merge",
            "Union of two COTTAS files into a single graph."), unsafe_allow_html=True)

    st.divider()

    with st.expander("About COTTAS", expanded=False):
        st.markdown("""
**COTTAS** (*Columnar Triple Table Storage*) stores RDF as a triple table in **Apache Parquet**, a columnar format designed for large-scale analytics.

The **pycottas** library provides:

- Compression and decompression between RDF and COTTAS.
- Triple pattern evaluation.
- SPARQL support via RDFLib.
- Merge and difference operations between graphs.
- Support for **quads** in addition to triples.
        """)

    with st.expander("Quick start"):
        st.markdown("""
1. Compress a `.nt`, `.ttl`, `.nq`, `.trig`, `.n3`, or `.rdf` file from the **Compress** view.
2. Explore the generated `.cottas` to inspect metadata and statistics.
3. Search triple patterns or run **SPARQL SELECT** queries.
4. Decompress to RDF or apply **difference** and **merge** operations.
        """)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    _section_title("Environment status", "Main dependencies")
    _check_deps()

    history = st.session_state.get("history", [])
    if history:
        with st.expander(f"Operation history · {len(history)}"):
            for entry in reversed(history[-20:]):
                st.markdown(f"- {entry}")


def _section_title(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div style='margin:8px 0 18px 0;'>
          <div style='color:#F1F5F9;font-size:0.95rem;font-weight:600;
                      text-transform:uppercase;letter-spacing:0.08em;'>
            {title}
          </div>
          <div style='color:#94A3B8;font-size:1.0rem;margin-top:4px;'>
            {subtitle}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _card(icon: str, color: str, title: str, desc: str) -> str:
    return f"""
<div style='background:#111827;border:1px solid #1F2937;border-radius:12px;
            padding:22px 24px;height:100%;min-height:150px;
            transition:border-color 0.2s, transform 0.2s;'
     onmouseover="this.style.borderColor='#334155';"
     onmouseout="this.style.borderColor='#1F2937';">
  <span class='material-symbols-outlined'
        style='font-size:30px;color:{color};
               font-variation-settings:"FILL" 0,"wght" 400,"GRAD" 0,"opsz" 24;'>
    {icon}
  </span>
  <div style='font-family:"Space Grotesk",sans-serif;font-weight:600;
              color:#F1F5F9;font-size:1.18rem;margin-top:12px;margin-bottom:8px;
              letter-spacing:-0.01em;'>
    {title}
  </div>
  <div style='color:#94A3B8;font-size:1.0rem;line-height:1.6;'>
    {desc}
  </div>
</div>
<link href='https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined' rel='stylesheet'>
"""


def _check_deps() -> None:
    cols = st.columns(3)
    deps = [("pycottas", "pycottas"), ("duckdb", "DuckDB"), ("rdflib", "RDFLib")]
    for col, (package_name, label) in zip(cols, deps):
        with col:
            try:
                version = metadata.version(package_name)
                st.markdown(
                    f"""
                    <div style='background:#111827;border:1px solid #1F2937;
                                border-left:3px solid #10B981;border-radius:0 8px 8px 0;
                                padding:14px 18px;'>
                      <div style='color:#F1F5F9;font-weight:600;font-size:1.05rem;'>{label}</div>
                      <div style='color:#94A3B8;font-size:0.92rem;font-family:"JetBrains Mono",monospace;margin-top:4px;'>v{version}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            except Exception:
                st.markdown(
                    f"""
                    <div style='background:#111827;border:1px solid #1F2937;
                                border-left:3px solid #EF4444;border-radius:0 8px 8px 0;
                                padding:14px 18px;'>
                      <div style='color:#F1F5F9;font-weight:600;font-size:1.05rem;'>{label}</div>
                      <div style='color:#EF4444;font-size:0.92rem;margin-top:4px;'>Not available</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
