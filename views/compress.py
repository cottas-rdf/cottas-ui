"""View for RDF -> COTTAS compression."""
from __future__ import annotations
import datetime, os, time
import streamlit as st
from utils.cottas_bridge import COTTASError, compress_rdf, get_metadata
from utils.file_manager import read_bytes, save_upload, temp_path
from utils.validation import sanitize_output_stem

ACCEPTED_FORMATS = {".nt":"N-Triples",".ttl":"Turtle",".nq":"N-Quads",".trig":"TriG",".n3":"Notation3",".rdf":"RDF/XML",".xml":"RDF/XML"}
INDEX_DESCRIPTIONS = {
    "SPO": "Equilibrada. Adecuada para exploración general y consultas por sujeto.",
    "SOP": "Consultas que filtran sujeto y objeto simultáneamente.",
    "PSO": "Consultas con predicado fijo (?s p ?o).",
    "POS": "Consultas con predicado y objeto fijos (?s p o).",
    "OSP": "Búsquedas guiadas por objeto.",
    "OPS": "Búsquedas guiadas por objeto y predicado.",
}


def render() -> None:
    _page_header("Comprimir", "Transforma un grafo RDF al formato columnar COTTAS.")

    uploaded = st.file_uploader(
        "Fichero RDF de entrada",
        type=[ext.lstrip(".") for ext in ACCEPTED_FORMATS],
        help="Formatos aceptados: " + ", ".join(sorted(set(ACCEPTED_FORMATS.values()))),
    )

    if uploaded is None:
        st.markdown("<div class='info-box muted'>Carga un fichero RDF para comenzar.</div>", unsafe_allow_html=True)
        return

    extension = os.path.splitext(uploaded.name)[1].lower()
    fmt_name = ACCEPTED_FORMATS.get(extension, "Desconocido")
    size_mb = len(uploaded.getbuffer()) / (1024 ** 2)

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Fichero", uploaded.name)
    col_b.metric("Formato", fmt_name)
    col_c.metric("Tamaño", f"{size_mb:.2f} MB")

    st.divider()
    _section_title("Parámetros")

    col1, col2 = st.columns(2)
    with col1:
        index = st.selectbox(
            "Índice COTTAS",
            list(INDEX_DESCRIPTIONS.keys()),
            help="Define la ordenación física de las tripletas y afecta al rendimiento de búsqueda.",
            key="compress_index",
        )
        st.caption(INDEX_DESCRIPTIONS[index])
    with col2:
        disk_mode = st.toggle(
            "Almacenamiento temporal en disco",
            value=False,
            help="Recomendado para ficheros grandes. Reduce picos de memoria a cambio de un tiempo de compresión mayor.",
            key="compress_disk_mode",
        )

    with st.form("compress_form"):
        output_name = sanitize_output_stem(
            st.text_input("Nombre del fichero de salida (sin extensión)", value=os.path.splitext(uploaded.name)[0]),
            fallback="graph",
        )
        submitted = st.form_submit_button("Comprimir", type="primary", use_container_width=True)

    if submitted:
        _run_compression(uploaded, index, disk_mode, output_name, size_mb)


def _run_compression(uploaded, index, disk_mode, output_name, original_size_mb):
    input_path = save_upload(uploaded, suffix=os.path.splitext(uploaded.name)[1])
    output_path = temp_path(f"{output_name}_{index}.cottas")

    with st.spinner("Comprimiendo…"):
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

    st.success(f"Compresión completada en {elapsed:.1f} s.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tamaño original", f"{original_size_mb:.2f} MB")
    c2.metric("Tamaño COTTAS", f"{output_size_mb:.2f} MB")
    c3.metric("Ratio", f"{acr:.1f}%")
    c4.metric("Tripletas", f"{meta['num_triples']:,}" if meta.get("num_triples") else "N/D")

    c5, c6, c7 = st.columns(3)
    c5.metric("Propiedades distintas", f"{meta['num_properties']:,}" if meta.get("num_properties") else "N/D")
    c6.metric("Índice", meta.get("index", index))
    c7.metric("Tipo", "Quad table" if meta.get("is_quad_table") else "Triple table")

    st.session_state["active_cottas"] = output_path
    st.session_state["active_name"] = filename

    ts = datetime.datetime.now().strftime("%H:%M:%S")
    st.session_state["history"].append(
        f"[{ts}] Compresión · `{uploaded.name}` → `{filename}` (índice {index}, disco={disk_mode}, {elapsed:.1f}s)"
    )

    st.download_button(
        label="Descargar fichero COTTAS",
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
