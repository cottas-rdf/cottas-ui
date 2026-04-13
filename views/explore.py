"""View for exploring metadata and basic statistics of a COTTAS file."""
from __future__ import annotations
import streamlit as st
from utils.cottas_bridge import (COTTASError, get_metadata, get_predicate_distribution,
                                  get_sample_triples, verify_cottas_file)
from utils.file_manager import file_size_mb, persist_uploaded_file
from utils.stats import (acr_gauge, build_predicate_bar_chart, build_size_comparison_chart,
                         compression_ratio, estimate_hdt_size_mb, estimate_nt_size_mb)


def render() -> None:
    _page_header("Explorar", "Metadatos, estadísticas y muestra de tripletas sin descomprimir el grafo.")

    tab_upload, tab_active = st.tabs(["Subir fichero", "Fichero activo"])
    cottas_path = None
    cottas_name = None

    with tab_upload:
        uploaded = st.file_uploader("Fichero COTTAS", type=["cottas", "parquet"])
        if uploaded:
            cottas_path = persist_uploaded_file(uploaded, state_key="explore_uploaded_path", suffix=".cottas")
            cottas_name = uploaded.name
            st.session_state["active_cottas"] = cottas_path
            st.session_state["active_name"] = cottas_name
            st.success(f"{cottas_name} ({file_size_mb(cottas_path):.2f} MB) cargado.")

    with tab_active:
        if st.session_state.get("active_cottas"):
            cottas_path = st.session_state["active_cottas"]
            cottas_name = st.session_state["active_name"]
            st.info(f"Usando **{cottas_name}** · {file_size_mb(cottas_path):.2f} MB")
        else:
            st.markdown("<div class='info-box muted'>No hay ningún fichero COTTAS activo. Carga uno desde la pestaña <b>Subir fichero</b>.</div>", unsafe_allow_html=True)

    if cottas_path is None:
        return

    try:
        is_valid = verify_cottas_file(cottas_path)
        meta = get_metadata(cottas_path)
    except COTTASError as exc:
        st.error(str(exc))
        return

    st.divider()
    _section_title("Metadatos")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Válido", "Sí" if is_valid else "No")
    c2.metric("Tripletas", f"{meta['num_triples']:,}" if meta.get("num_triples") else "N/D")
    c3.metric("Índice", meta.get("index", "N/D"))
    c4.metric("Propiedades", f"{meta['num_properties']:,}" if meta.get("num_properties") else "N/D")
    c5.metric("Tipo", "Quad table" if meta.get("is_quad_table") else "Triple table")

    c6, c7, c8, c9 = st.columns(4)
    c6.metric("Sujetos distintos", f"{meta['num_distinct_subjects']:,}" if meta.get("num_distinct_subjects") else "N/D")
    c7.metric("Objetos distintos", f"{meta['num_distinct_objects']:,}" if meta.get("num_distinct_objects") else "N/D")
    c8.metric("Row groups", f"{meta['num_triples_groups']:,}" if meta.get("num_triples_groups") else "N/D")
    c9.metric("Compresión", meta.get("compression", "N/D"))

    if meta.get("issued") or meta.get("custom_metadata"):
        with st.expander("Metadatos adicionales"):
            if meta.get("issued"):
                st.write(f"**Issued:** {meta['issued']}")
            st.json(meta.get("custom_metadata", {}))

    st.divider()
    _section_title("Compresión")

    nt_size = estimate_nt_size_mb(meta.get("num_triples"))
    hdt_size = estimate_hdt_size_mb(nt_size) if nt_size else None
    acr_pct = compression_ratio(meta["file_size_mb"], nt_size) * 100 if nt_size else None

    col_gauge, col_chart = st.columns([1, 2])
    with col_gauge:
        if acr_pct is not None:
            st.plotly_chart(acr_gauge(acr_pct), use_container_width=True)
            st.caption("La estimación de N-Triples es orientativa y se calcula a partir del número de tripletas.")
        else:
            st.info("No se pudo estimar el ratio por falta de metadatos.")
    with col_chart:
        st.plotly_chart(build_size_comparison_chart(meta["file_size_mb"], nt_size, hdt_size), use_container_width=True)

    st.divider()
    _section_title("Muestra de tripletas")
    sample_limit = st.slider("Número de tripletas", min_value=10, max_value=500, value=50, step=10)

    if st.button("Cargar muestra", use_container_width=True, key="explore_load_sample"):
        with st.spinner("Recuperando muestra…"):
            try:
                df = get_sample_triples(cottas_path, limit=sample_limit)
            except COTTASError as exc:
                st.error(str(exc))
                return
        if df.empty:
            st.info("El grafo no contiene resultados para la muestra solicitada.")
        else:
            st.dataframe(df, use_container_width=True, height=360)
            st.caption(f"Se muestran {len(df)} filas.")

    st.divider()
    _section_title("Distribución de predicados")
    top_n = st.slider("Top-N predicados", min_value=5, max_value=50, value=20, step=5)

    if st.button("Calcular distribución", use_container_width=True, key="explore_calc_distribution"):
        with st.spinner("Calculando distribución…"):
            try:
                dist_df = get_predicate_distribution(cottas_path, top_n=top_n)
            except COTTASError as exc:
                st.error(str(exc))
                return
        if dist_df.empty:
            st.info("No se pudo calcular la distribución de predicados.")
            return
        st.plotly_chart(build_predicate_bar_chart(dist_df), use_container_width=True)
        with st.expander("Ver tabla"):
            st.dataframe(dist_df, use_container_width=True)


def _page_header(title, subtitle):
    st.markdown(f"<div style='margin-bottom:24px;'><h1 style='color:#F1F5F9;font-weight:700;font-size:2rem;margin:0 0 8px 0;letter-spacing:-0.02em;'>{title}</h1><p style='color:#94A3B8;font-size:1.05rem;margin:0;line-height:1.55;'>{subtitle}</p></div>", unsafe_allow_html=True)


def _section_title(title):
    st.markdown(f"<div style='color:#F1F5F9;font-size:0.95rem;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;margin:6px 0 16px 0;'>{title}</div>", unsafe_allow_html=True)
