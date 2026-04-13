"""View for COTTAS -> RDF decompression."""
from __future__ import annotations
import datetime, os, time
import streamlit as st
from utils.cottas_bridge import COTTASError, decompress_cottas, get_metadata
from utils.file_manager import file_size_mb, persist_uploaded_file, read_bytes, temp_path
from utils.validation import format_supports_named_graphs, sanitize_output_stem

OUTPUT_FORMATS = {
    "N-Triples (.nt)": ("ntriples", ".nt", "application/n-triples"),
    "Turtle (.ttl)": ("turtle", ".ttl", "text/turtle"),
    "N-Quads (.nq)": ("nquads", ".nq", "application/n-quads"),
    "TriG (.trig)": ("trig", ".trig", "application/trig"),
    "Notation3 (.n3)": ("n3", ".n3", "text/n3"),
    "RDF/XML (.rdf)": ("xml", ".rdf", "application/rdf+xml"),
}


def render() -> None:
    _page_header("Descomprimir", "Recupera el contenido RDF de un fichero COTTAS en el formato que necesites.")

    tab_upload, tab_active = st.tabs(["Subir fichero", "Fichero activo"])
    cottas_path = None
    cottas_name = None

    with tab_upload:
        uploaded = st.file_uploader("Fichero COTTAS", type=["cottas", "parquet"])
        if uploaded:
            cottas_path = persist_uploaded_file(uploaded, state_key="decompress_uploaded_path", suffix=".cottas")
            cottas_name = uploaded.name
            st.session_state["active_cottas"] = cottas_path
            st.session_state["active_name"] = cottas_name
            st.success(f"{cottas_name} ({file_size_mb(cottas_path):.2f} MB) listo.")

    with tab_active:
        if st.session_state.get("active_cottas"):
            cottas_path = st.session_state["active_cottas"]
            cottas_name = st.session_state["active_name"]
            st.info(f"Usando **{cottas_name}** · {file_size_mb(cottas_path):.2f} MB")
        else:
            st.markdown(
                "<div class='info-box muted'>No hay ningún fichero COTTAS activo. "
                "Carga uno desde la pestaña <b>Subir fichero</b>.</div>",
                unsafe_allow_html=True,
            )

    if cottas_path is None:
        return

    try:
        meta = get_metadata(cottas_path)
    except COTTASError as exc:
        st.error(str(exc))
        return

    st.divider()
    _section_title("Formato de salida")

    fmt_label = st.selectbox("Formato RDF", list(OUTPUT_FORMATS.keys()), key="decompress_format")
    fmt_id, fmt_ext, fmt_mime = OUTPUT_FORMATS[fmt_label]

    if meta["is_quad_table"] and fmt_id != "ntriples" and not format_supports_named_graphs(fmt_id):
        st.warning("El fichero es un **quad table**. Para preservar los named graphs usa **N-Quads** o **TriG**.")
    elif meta["is_quad_table"] and fmt_id == "ntriples":
        st.warning("N-Triples no puede representar named graphs. Selecciona otro formato para continuar.")

    with st.form("decompress_form"):
        output_name = sanitize_output_stem(
            st.text_input("Nombre del fichero de salida (sin extensión)",
                          value=os.path.splitext(cottas_name or "output")[0]),
            fallback="output",
        )
        disable_button = bool(meta["is_quad_table"] and fmt_id == "ntriples")
        submitted = st.form_submit_button("Descomprimir", type="primary",
                                           use_container_width=True, disabled=disable_button)

    if submitted:
        _run_decompression(cottas_path, fmt_id, fmt_ext, fmt_mime, output_name, cottas_name or "output.cottas")


def _run_decompression(cottas_path, fmt_id, fmt_ext, fmt_mime, output_name, cottas_name):
    output_path = temp_path(f"{output_name}{fmt_ext}")
    with st.spinner("Descomprimiendo…"):
        t0 = time.perf_counter()
        try:
            decompress_cottas(input_path=cottas_path, output_path=output_path, output_format=fmt_id)
            elapsed = time.perf_counter() - t0
        except COTTASError as exc:
            st.error(str(exc))
            return

    cottas_mb = file_size_mb(cottas_path)
    output_mb = file_size_mb(output_path)
    st.success(f"Descompresión completada en {elapsed:.1f} s.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Tamaño COTTAS", f"{cottas_mb:.2f} MB")
    c2.metric("Tamaño RDF", f"{output_mb:.2f} MB")
    c3.metric("Factor de expansión", f"{output_mb / cottas_mb:.1f}×" if cottas_mb else "N/D")

    filename = f"{output_name}{fmt_ext}"
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    st.session_state["history"].append(f"[{ts}] Descompresión · `{cottas_name}` → `{filename}` ({elapsed:.1f}s)")

    st.download_button(label=f"Descargar {filename}", data=read_bytes(output_path),
                       file_name=filename, mime=fmt_mime, use_container_width=True,
                       key=f"decompress_download_{filename}")


def _page_header(title, subtitle):
    st.markdown(f"<div style='margin-bottom:24px;'><h1 style='color:#F1F5F9;font-weight:700;font-size:2rem;margin:0 0 8px 0;letter-spacing:-0.02em;'>{title}</h1><p style='color:#94A3B8;font-size:1.05rem;margin:0;line-height:1.55;'>{subtitle}</p></div>", unsafe_allow_html=True)


def _section_title(title):
    st.markdown(f"<div style='color:#F1F5F9;font-size:0.95rem;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;margin:6px 0 16px 0;'>{title}</div>", unsafe_allow_html=True)
