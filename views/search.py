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
    _page_header("Buscar tripletas",
                 "Evalúa patrones <code>(s, p, o[, g])</code> sobre el grafo comprimido. Deja un campo vacío para tratarlo como variable.")

    tab_upload, tab_active = st.tabs(["Subir fichero", "Fichero activo"])
    cottas_path = None

    with tab_upload:
        uploaded = st.file_uploader("Fichero COTTAS", type=["cottas", "parquet"], key="search_upload")
        if uploaded:
            cottas_path = persist_uploaded_file(uploaded, state_key="search_uploaded_path", suffix=".cottas")
            st.session_state["active_cottas"] = cottas_path
            st.session_state["active_name"] = uploaded.name
            st.success(f"{uploaded.name} ({file_size_mb(cottas_path):.2f} MB) listo.")

    with tab_active:
        if st.session_state.get("active_cottas"):
            cottas_path = st.session_state["active_cottas"]
            st.info(f"Usando **{st.session_state['active_name']}** · {file_size_mb(cottas_path):.2f} MB")
        else:
            st.markdown("<div class='info-box muted'>No hay ningún fichero COTTAS activo. Carga uno desde la pestaña <b>Subir fichero</b>.</div>", unsafe_allow_html=True)

    if cottas_path is None:
        return

    try:
        meta = get_metadata(cottas_path)
    except COTTASError as exc:
        st.error(str(exc))
        return

    st.divider()
    _section_title("Patrón de búsqueda")
    st.markdown(
        "<div class='info-box'>Términos RDF serializados en N3. Ejemplos: "
        "<code>&lt;http://dbpedia.org/resource/Madrid&gt;</code>, "
        "<code>&quot;Madrid&quot;@es</code>, "
        "<code>&quot;42&quot;^^&lt;http://www.w3.org/2001/XMLSchema#integer&gt;</code>.</div>",
        unsafe_allow_html=True,
    )

    col_s, col_p, col_o = st.columns(3)
    with col_s:
        subject = st.text_input("Sujeto", placeholder="<http://...> o vacío", key="search_subject")
    with col_p:
        predicate = st.text_input("Predicado", placeholder="<http://...> o vacío", key="search_predicate")
    with col_o:
        obj = st.text_input("Objeto", placeholder='<http://...> / "literal" o vacío', key="search_object")

    graph = None
    if meta.get("is_quad_table"):
        graph = st.text_input("Grafo (opcional)", placeholder="<http://...> o vacío", key="search_graph")

    pattern_preview = (
        build_triple_pattern(subject.strip() or None, predicate.strip() or None, obj.strip() or None,
                             (graph.strip() or None) if graph else None)
        if meta.get("is_quad_table")
        else build_triple_pattern(subject.strip() or None, predicate.strip() or None, obj.strip() or None)
    )
    suggestion = recommend_index(subject, predicate, obj)

    st.markdown(
        f"<div class='info-box' style='font-family:\"JetBrains Mono\",monospace;'>Patrón · <b>{pattern_preview}</b></div>",
        unsafe_allow_html=True,
    )
    st.caption(f"Índice sugerido: **{suggestion}**")

    with st.form("search_form"):
        with st.expander("Opciones avanzadas"):
            limit = st.number_input("Límite de resultados", min_value=1, max_value=1_000_000, value=MAX_DISPLAY, step=1_000)
            offset = st.number_input("Offset", min_value=0, max_value=1_000_000, value=0, step=100,
                                      help="Desplazamiento inicial para paginación en el motor.")
            page_size = st.selectbox("Filas por página", [25, 50, 100, 200, 500], index=1)

        with st.expander("SQL generado"):
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

        submitted = st.form_submit_button("Buscar", type="primary", use_container_width=True)

    if submitted:
        _run_search(cottas_path, subject.strip() or None, predicate.strip() or None, obj.strip() or None,
                    (graph.strip() or None) if (meta.get("is_quad_table") and graph) else None,
                    int(limit), int(offset), int(page_size))

    if st.session_state.get("last_search_df") is not None:
        _display_results(st.session_state["last_search_df"], int(page_size),
                         key_prefix=f"search_results_{st.session_state.get('last_search_token', 'default')}")


def _run_search(cottas_path, subject, predicate, obj, graph, limit, offset, page_size):
    with st.spinner("Evaluando patrón…"):
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
        st.warning(f"Se muestran los primeros **{n:,}** resultados desde el offset {offset:,}. "
                   "Aumenta el límite o el offset para seguir navegando.")
    else:
        st.success(f"{n:,} resultados en {elapsed:.3f} s.")

    ts = datetime.datetime.now().strftime("%H:%M:%S")
    st.session_state["history"].append(
        f"[{ts}] Búsqueda · ({subject or '?'}, {predicate or '?'}, {obj or '?'}) → {n:,} resultados ({elapsed:.3f}s)"
    )
    st.session_state["last_search_df"] = df
    st.session_state["last_search_token"] = datetime.datetime.now().strftime("%H%M%S%f")


def _display_results(df: pd.DataFrame, page_size: int, key_prefix: str = "search_results"):
    if df.empty:
        st.info("Sin resultados para el patrón especificado.")
        return

    n = len(df)
    total_pages = (n - 1) // page_size + 1
    _section_title(f"Resultados · {n:,} filas")

    if total_pages > 1:
        col_pg, col_info = st.columns([2, 3])
        with col_pg:
            page_num = st.number_input(f"Página (1–{total_pages})", min_value=1, max_value=total_pages,
                                        value=1, step=1, key=f"{key_prefix}_page")
        with col_info:
            st.caption(f"Página {page_num} de {total_pages} · {page_size} filas/página")
        start = (page_num - 1) * page_size
        page_df = df.iloc[start:start + page_size]
    else:
        page_df = df

    st.dataframe(page_df, use_container_width=True, height=420)
    st.download_button(label="Descargar resultados (CSV)",
                       data=df.to_csv(index=False).encode("utf-8"),
                       file_name="resultados_busqueda.csv", mime="text/csv",
                       key=f"{key_prefix}_download")


def _page_header(title, subtitle):
    st.markdown(f"<div style='margin-bottom:24px;'><h1 style='color:#F1F5F9;font-weight:700;font-size:2rem;margin:0 0 8px 0;letter-spacing:-0.02em;'>{title}</h1><p style='color:#94A3B8;font-size:1.05rem;margin:0;line-height:1.55;'>{subtitle}</p></div>", unsafe_allow_html=True)


def _section_title(title):
    st.markdown(f"<div style='color:#F1F5F9;font-size:0.95rem;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;margin:6px 0 16px 0;'>{title}</div>", unsafe_allow_html=True)
