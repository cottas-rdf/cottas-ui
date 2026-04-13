"""View for set difference between two COTTAS files."""
from __future__ import annotations
import datetime, os, time
import streamlit as st
from utils.cottas_bridge import (COTTASError, decompress_cottas, diff_cottas_files, get_metadata,
                                  get_sample_triples, verify_cottas_file)
from utils.file_manager import file_size_mb, persist_uploaded_file, read_bytes, temp_path
from utils.validation import sanitize_output_stem


def render() -> None:
    _page_header("Diferencia", "Calcula las tripletas presentes en el grafo A y ausentes en el grafo B.")

    col_a, col_b = st.columns(2)
    with col_a:
        _section_title("Grafo A")
        up_a = st.file_uploader("Fichero COTTAS A", type=["cottas", "parquet"], key="diff_a")
        path_a = persist_uploaded_file(up_a, state_key="diff_a_path", suffix=".cottas") if up_a else None
        if up_a and path_a:
            st.success(f"{up_a.name} ({file_size_mb(path_a):.2f} MB)")
        else:
            st.markdown("<div class='info-box muted'>Carga el grafo A.</div>", unsafe_allow_html=True)

    with col_b:
        _section_title("Grafo B")
        up_b = st.file_uploader("Fichero COTTAS B", type=["cottas", "parquet"], key="diff_b")
        path_b = persist_uploaded_file(up_b, state_key="diff_b_path", suffix=".cottas") if up_b else None
        if up_b and path_b:
            st.success(f"{up_b.name} ({file_size_mb(path_b):.2f} MB)")
        else:
            st.markdown("<div class='info-box muted'>Carga el grafo B.</div>", unsafe_allow_html=True)

    if not path_a or not path_b:
        return

    st.divider()
    with st.form("diff_form"):
        index = st.selectbox("Índice del resultado", ["SPO","SOP","PSO","POS","OSP","OPS"], index=0,
                              help="El resultado se materializa con el índice indicado.")
        output_name = sanitize_output_stem(
            st.text_input("Nombre del fichero resultado (sin extensión)",
                          value=f"{os.path.splitext(up_a.name)[0]}_minus_{os.path.splitext(up_b.name)[0]}"),
            fallback="diff_result",
        )
        submitted = st.form_submit_button("Calcular diferencia A − B", type="primary", use_container_width=True)

    if submitted:
        _run(path_a, path_b, output_name, index, up_a.name, up_b.name)

    if st.session_state.get("diff_result_path"):
        _show_panel(st.session_state["diff_result_path"],
                    st.session_state.get("diff_result_name", "resultado_diff.cottas"))


def _run(path_a, path_b, output_name, index, name_a, name_b):
    output_path = temp_path(f"{output_name}.cottas")
    with st.spinner("Calculando diferencia…"):
        t0 = time.perf_counter()
        try:
            diff_cottas_files(path_a, path_b, output_path, index=index)
            elapsed = time.perf_counter() - t0
        except COTTASError as exc:
            st.error(str(exc))
            return

    st.success(f"Diferencia calculada en {elapsed:.1f} s.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Tamaño A", f"{file_size_mb(path_a):.2f} MB")
    c2.metric("Tamaño B", f"{file_size_mb(path_b):.2f} MB")
    c3.metric("Resultado", f"{file_size_mb(output_path):.2f} MB")

    st.session_state["active_cottas"] = output_path
    st.session_state["active_name"] = f"{output_name}.cottas"
    st.session_state["diff_result_path"] = output_path
    st.session_state["diff_result_name"] = f"{output_name}.cottas"
    for k in ["diff_preview_meta","diff_preview_df","diff_preview_valid","diff_nt_path"]:
        st.session_state.pop(k, None)

    ts = datetime.datetime.now().strftime("%H:%M:%S")
    st.session_state["history"].append(
        f"[{ts}] Diferencia · `{name_a}` − `{name_b}` → `{output_name}.cottas` (índice {index}, {elapsed:.1f}s)"
    )


def _show_panel(result_path, result_name):
    st.divider()
    _section_title("Resultado")
    st.info("El resultado se ha dejado como **fichero activo**. Puedes abrirlo en **Explorar**, **Buscar tripletas** o **SPARQL**.")

    st.download_button("Descargar como COTTAS", data=read_bytes(result_path), file_name=result_name,
                       mime="application/octet-stream", use_container_width=True,
                       key="diff_result_download_cottas")

    col_preview, col_nt = st.columns(2)
    with col_preview:
        if st.button("Cargar vista previa", use_container_width=True, key="diff_load_preview"):
            with st.spinner("Preparando vista previa…"):
                try:
                    st.session_state["diff_preview_valid"] = verify_cottas_file(result_path)
                    st.session_state["diff_preview_meta"] = get_metadata(result_path)
                    st.session_state["diff_preview_df"] = get_sample_triples(result_path, limit=20)
                except COTTASError as exc:
                    st.error(str(exc))

    with col_nt:
        if st.session_state.get("diff_nt_path") and os.path.exists(st.session_state["diff_nt_path"]):
            st.download_button("Descargar como N-Triples", data=read_bytes(st.session_state["diff_nt_path"]),
                               file_name=result_name.replace(".cottas", ".nt"), mime="application/n-triples",
                               use_container_width=True, key="diff_result_download_nt")
        elif st.button("Preparar N-Triples", use_container_width=True, key="diff_prepare_nt"):
            nt_path = temp_path(os.path.splitext(result_name)[0] + ".nt")
            with st.spinner("Convirtiendo a N-Triples…"):
                try:
                    decompress_cottas(result_path, nt_path, output_format="ntriples")
                    st.session_state["diff_nt_path"] = nt_path
                    st.rerun()
                except COTTASError as exc:
                    st.warning(f"No se pudo preparar la descarga: {exc}")

    if st.session_state.get("diff_preview_meta") is not None:
        meta = st.session_state["diff_preview_meta"]
        sample_df = st.session_state.get("diff_preview_df")
        is_valid = st.session_state.get("diff_preview_valid")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Válido", "Sí" if is_valid else "No")
        c2.metric("Tripletas", f"{meta['num_triples']:,}" if meta.get("num_triples") else "N/D")
        c3.metric("Índice", meta.get("index", "N/D"))
        c4.metric("Tipo", "Quad table" if meta.get("is_quad_table") else "Triple table")
        if sample_df is None or sample_df.empty:
            st.info("El resultado es válido pero no contiene tripletas para mostrar.")
        else:
            st.caption("Muestra de las primeras tripletas del resultado")
            st.dataframe(sample_df, use_container_width=True, height=320)


def _page_header(title, subtitle):
    st.markdown(f"<div style='margin-bottom:24px;'><h1 style='color:#F1F5F9;font-weight:700;font-size:2rem;margin:0 0 8px 0;letter-spacing:-0.02em;'>{title}</h1><p style='color:#94A3B8;font-size:1.05rem;margin:0;line-height:1.55;'>{subtitle}</p></div>", unsafe_allow_html=True)


def _section_title(title):
    st.markdown(f"<div style='color:#F1F5F9;font-size:0.95rem;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;margin:6px 0 16px 0;'>{title}</div>", unsafe_allow_html=True)
