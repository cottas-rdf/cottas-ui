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
    _page_header("Consulta SPARQL",
                 "Lanza consultas <code>SELECT</code> sobre el grafo COTTAS mediante COTTASStore como backend de RDFLib.")

    tab_up, tab_act = st.tabs(["Subir fichero", "Fichero activo"])
    cottas_path = None

    with tab_up:
        uploaded = st.file_uploader("Fichero COTTAS", type=["cottas", "parquet"], key="sparql_up")
        if uploaded:
            cottas_path = persist_uploaded_file(uploaded, state_key="sparql_uploaded_path", suffix=".cottas")
            st.session_state["active_cottas"] = cottas_path
            st.session_state["active_name"] = uploaded.name
            st.success(f"{uploaded.name} ({file_size_mb(cottas_path):.2f} MB) listo.")

    with tab_act:
        if st.session_state.get("active_cottas"):
            cottas_path = st.session_state["active_cottas"]
            st.info(f"Usando **{st.session_state['active_name']}** · {file_size_mb(cottas_path):.2f} MB")
        else:
            st.markdown("<div class='info-box muted'>No hay ningún fichero COTTAS activo. Carga uno desde la pestaña <b>Subir fichero</b>.</div>", unsafe_allow_html=True)

    if not cottas_path:
        return

    try:
        meta = get_metadata(cottas_path)
    except COTTASError as exc:
        st.error(str(exc))
        return

    if meta.get("is_quad_table"):
        st.info("Este fichero es un **quad table**. Las consultas pueden referenciar named graphs.")

    st.divider()
    _section_title("Consulta")
    st.markdown(
        "<div class='info-box'>Solo se admiten consultas de lectura (<code>SELECT</code>). "
        "Las operaciones de modificación están fuera del alcance de la aplicación.</div>",
        unsafe_allow_html=True,
    )

    with st.form("sparql_form"):
        query = st.text_area("Consulta SPARQL", value=DEFAULT_QUERY, height=240,
                              help="Puedes incluir declaraciones PREFIX y una cláusula LIMIT en la propia consulta.")
        limit_override = st.number_input(
            "Recorte adicional de resultados (0 = sin recorte)",
            min_value=0, max_value=100_000, value=0, step=100,
            help="Se aplica tras ejecutar la consulta para limitar las filas mostradas en la interfaz.",
        )
        submitted = st.form_submit_button("Ejecutar", type="primary", use_container_width=True)

    if submitted:
        _run_sparql(cottas_path, query, int(limit_override))

    if st.session_state.get("last_sparql_df") is not None:
        _show_results(st.session_state["last_sparql_df"],
                      key_prefix=f"sparql_results_{st.session_state.get('last_sparql_token', 'default')}")


def _run_sparql(cottas_path: str, query: str, limit_override: int):
    if not is_select_query(query):
        st.error("Solo se admiten consultas SELECT. Puedes incluir PREFIX o BASE antes del SELECT.")
        return

    with st.spinner("Ejecutando consulta…"):
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
        st.warning(f"La consulta devolvió {total_rows:,} filas. Se muestran solo las primeras {limit_override:,}.")

    st.success(f"{total_rows:,} resultados en {elapsed:.3f} s.")

    ts = datetime.datetime.now().strftime("%H:%M:%S")
    st.session_state["history"].append(f"[{ts}] SPARQL · {total_rows:,} resultados ({elapsed:.3f}s)")
    st.session_state["last_sparql_df"] = df
    st.session_state["last_sparql_token"] = datetime.datetime.now().strftime("%H%M%S%f")


def _show_results(df, key_prefix: str = "sparql_results"):
    if df.empty:
        st.info("La consulta no devolvió resultados.")
        return

    _section_title(f"Resultados · {len(df):,} filas")
    st.dataframe(df, use_container_width=True, height=420)
    st.download_button("Descargar CSV", df.to_csv(index=False).encode("utf-8"),
                       file_name="sparql_results.csv", mime="text/csv",
                       key=f"{key_prefix}_download")


def _page_header(title, subtitle):
    st.markdown(f"<div style='margin-bottom:24px;'><h1 style='color:#F1F5F9;font-weight:700;font-size:2rem;margin:0 0 8px 0;letter-spacing:-0.02em;'>{title}</h1><p style='color:#94A3B8;font-size:1.05rem;margin:0;line-height:1.55;'>{subtitle}</p></div>", unsafe_allow_html=True)


def _section_title(title):
    st.markdown(f"<div style='color:#F1F5F9;font-size:0.95rem;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;margin:6px 0 16px 0;'>{title}</div>", unsafe_allow_html=True)
