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
            Compresión, consulta y análisis de grafos RDF mediante el formato
            columnar <b style='color:#F1F5F9;font-weight:600;'>COTTAS</b>.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _section_title("Conversión", "Transformación entre RDF y COTTAS")
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        st.markdown(_card("compress", "#3B82F6", "Comprimir",
            "De RDF a COTTAS. Acepta TTL, NT, NQ, TriG, N3 y RDF/XML."), unsafe_allow_html=True)
    with c2:
        st.markdown(_card("unarchive", "#3B82F6", "Descomprimir",
            "De COTTAS a RDF en el formato de salida que necesites."), unsafe_allow_html=True)

    st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)

    _section_title("Consulta y análisis", "Exploración del grafo comprimido")
    c3, c4, c5 = st.columns(3, gap="medium")
    with c3:
        st.markdown(_card("travel_explore", "#A78BFA", "Explorar",
            "Metadatos, muestra de tripletas y distribución de predicados."), unsafe_allow_html=True)
    with c4:
        st.markdown(_card("manage_search", "#A78BFA", "Buscar tripletas",
            "Patrones (s, p, o[, g]) directamente sobre el fichero comprimido."), unsafe_allow_html=True)
    with c5:
        st.markdown(_card("terminal", "#A78BFA", "SPARQL",
            "Consultas SELECT mediante COTTASStore y RDFLib."), unsafe_allow_html=True)

    st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)

    _section_title("Operaciones entre grafos", "Comparación y composición")
    c6, c7 = st.columns(2, gap="medium")
    with c6:
        st.markdown(_card("compare", "#3B82F6", "Diferencia",
            "Tripletas presentes en un grafo y ausentes en el otro."), unsafe_allow_html=True)
    with c7:
        st.markdown(_card("merge", "#3B82F6", "Fusión",
            "Unión de múltiples ficheros COTTAS en un único grafo."), unsafe_allow_html=True)

    st.divider()

    with st.expander("Sobre COTTAS", expanded=False):
        st.markdown("""
**COTTAS** (*Columnar Triple Table Storage*) almacena RDF como una tabla de tripletas en **Apache Parquet**, un formato columnar diseñado para análisis a gran escala.

La librería **pycottas** proporciona:

- Compresión y descompresión entre RDF y COTTAS.
- Evaluación de patrones de tripleta.
- Soporte SPARQL a través de RDFLib.
- Operaciones de fusión y diferencia entre grafos.
- Soporte de **quads** además de triples.
        """)

    with st.expander("Guía rápida"):
        st.markdown("""
1. Comprime un `.nt`, `.ttl`, `.nq`, `.trig`, `.n3` o `.rdf` desde la vista **Comprimir**.
2. Explora el `.cottas` generado para inspeccionar metadatos y estadísticas.
3. Busca patrones de tripleta o lanza consultas **SPARQL SELECT**.
4. Descomprime a RDF o aplica operaciones de **diferencia** y **fusión**.
        """)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    _section_title("Estado del entorno", "Dependencias principales")
    _check_deps()

    history = st.session_state.get("history", [])
    if history:
        with st.expander(f"Historial de operaciones · {len(history)}"):
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
                      <div style='color:#EF4444;font-size:0.92rem;margin-top:4px;'>No disponible</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
