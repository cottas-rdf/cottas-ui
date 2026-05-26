"""View for RDF -> COTTAS compression."""
from __future__ import annotations
import datetime, os, time
import streamlit as st
from utils.cottas_bridge import COTTASError, compress_rdf, get_metadata
from utils.file_manager import read_bytes, save_upload, temp_path
from utils.validation import sanitize_output_stem

ACCEPTED_FORMATS = {".nt":"N-Triples",".ttl":"Turtle",".nq":"N-Quads",".trig":"TriG",".n3":"Notation3",".rdf":"RDF/XML",".xml":"RDF/XML"}
INDEX_DESCRIPTIONS = {
    "SPO": "Balanced. Suitable for general exploration and subject-based queries.",
    "SOP": "Queries filtering by subject and object simultaneously.",
    "PSO": "Queries with a fixed predicate (?s p ?o).",
    "POS": "Queries with fixed predicate and object (?s p o).",
    "OSP": "Object-guided searches.",
    "OPS": "Object- and predicate-guided searches.",
}


def render() -> None:
    _page_header("Compress", "Transform an RDF graph into the columnar COTTAS format.")

    uploaded = st.file_uploader(
        "Input RDF file",
        type=[ext.lstrip(".") for ext in ACCEPTED_FORMATS],
        help="Accepted formats: " + ", ".join(sorted(set(ACCEPTED_FORMATS.values()))),
    )

    if uploaded is None:
        st.markdown("<div class='info-box muted'>Load an RDF file to begin.</div>", unsafe_allow_html=True)
        return

    extension = os.path.splitext(uploaded.name)[1].lower()
    fmt_name = ACCEPTED_FORMATS.get(extension, "Unknown")
    size_mb = len(uploaded.getbuffer()) / (1024 ** 2)

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("File", uploaded.name)
    col_b.metric("Format", fmt_name)
    col_c.metric("Size", f"{size_mb:.2f} MB")

    st.divider()
    _section_title("Parameters")

    col1, col2 = st.columns(2)
    with col1:
        index = st.selectbox(
            "COTTAS index",
            list(INDEX_DESCRIPTIONS.keys()),
            help="Defines the physical ordering of triples and affects search performance.",
            key="compress_index",
        )
        st.caption(INDEX_DESCRIPTIONS[index])
    with col2:
        disk_mode = st.toggle(
            "Temporary disk storage",
            value=False,
            help="Recommended for large files. Reduces memory peaks at the cost of longer compression time.",
            key="compress_disk_mode",
        )

    with st.form("compress_form"):
        output_name = sanitize_output_stem(
            st.text_input("Output file name (without extension)", value=os.path.splitext(uploaded.name)[0]),
            fallback="graph",
        )
        submitted = st.form_submit_button("Compress", type="primary", use_container_width=True)

    if submitted:
        _run_compression(uploaded, index, disk_mode, output_name, size_mb)


def _run_compression(uploaded, index, disk_mode, output_name, original_size_mb):
    input_path = save_upload(uploaded, suffix=os.path.splitext(uploaded.name)[1])
    output_path = temp_path(f"{output_name}_{index}.cottas")

    with st.spinner("Compressing..."):
        t0 = time.perf_counter()
        try:
            compress_rdf(input_path=input_path, output_path=output_path, index=index, disk=disk_mode)
            elapsed = time.perf_counter() - t0
            meta = get_metadata(output_path)
        except COTTASError as exc:
            st.error(str(exc))
            return

    output_size_mb = os.path.getsize(output_path) / (1024 ** 2)
    acr = (output_size_mb / original_size_mb) * 100 if original_size_mb else 0
    filename = f"{output_name}_{index}.cottas"

    st.success(f"Compression completed in {elapsed:.1f} s.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Original size", f"{original_size_mb:.2f} MB")
    c2.metric("COTTAS size", f"{output_size_mb:.2f} MB")
    c3.metric("Ratio", f"{acr:.1f}%")
    c4.metric("Triples", f"{meta['num_triples']:,}" if meta.get("num_triples") else "N/A")

    c5, c6, c7 = st.columns(3)
    c5.metric("Distinct properties", f"{meta['num_properties']:,}" if meta.get("num_properties") else "N/A")
    c6.metric("Index", meta.get("index", index))
    c7.metric("Type", "Quad table" if meta.get("is_quad_table") else "Triple table")

    st.session_state["active_cottas"] = output_path
    st.session_state["active_name"] = filename

    ts = datetime.datetime.now().strftime("%H:%M:%S")
    st.session_state["history"].append(
        f"[{ts}] Compression · `{uploaded.name}` → `{filename}` (index {index}, disk={disk_mode}, {elapsed:.1f}s)"
    )

    st.download_button(
        label="Download COTTAS file",
        data=read_bytes(output_path),
        file_name=filename,
        mime="application/octet-stream",
        use_container_width=True,
        key=f"compress_download_{filename}",
    )


def _page_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div style='margin-bottom:24px;'>
          <h1 style='color:#F1F5F9;font-weight:700;font-size:2rem;
                     margin:0 0 8px 0;letter-spacing:-0.02em;'>{title}</h1>
          <p style='color:#94A3B8;font-size:1.05rem;margin:0;line-height:1.55;'>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _section_title(title: str) -> None:
    st.markdown(
        f"""
        <div style='color:#F1F5F9;font-size:0.95rem;font-weight:600;
                    text-transform:uppercase;letter-spacing:0.08em;
                    margin:6px 0 16px 0;'>{title}</div>
        """,
        unsafe_allow_html=True,
    )
