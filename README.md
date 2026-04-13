# COTTAS Manager

Aplicación web en Streamlit para la gestión de grafos RDF comprimidos en formato COTTAS.

> TFG · Universidad Politécnica de Madrid · Tutor: Julián Arenas-Guerrero

## Funcionalidad

La aplicación envuelve la librería **pycottas** para ofrecer una interfaz visual con las siguientes operaciones:

- **Compresión** RDF → COTTAS desde TTL, NT, NQ, TriG, N3 y RDF/XML.
- **Descompresión** COTTAS → RDF a cualquiera de los formatos anteriores.
- **Exploración** de metadatos, estadísticas y muestras de tripletas.
- **Búsqueda** por patrón `(s, p, o[, g])` directamente sobre el fichero comprimido.
- **Consultas SPARQL SELECT** mediante `COTTASStore` como backend de RDFLib.
- **Diferencia** entre dos grafos COTTAS.
- **Fusión** de múltiples grafos COTTAS en uno único.

## Detalles de implementación

La integración con `pycottas` (versión 1.1.x) se concentra en `utils/cottas_bridge.py`, que aísla a la aplicación de cambios futuros en la API de la librería:

- La compresión usa los parámetros públicos `index` y `disk` de `pycottas.rdf2cottas`.
- La descompresión combina `pycottas.cottas2rdf` con conversión a otros formatos mediante RDFLib.
- La búsqueda por patrón utiliza `COTTASDocument.search(...)`.
- SPARQL se ejecuta a través de `COTTASStore` como backend de RDFLib.
- Las operaciones `merge` y `diff` materializan el resultado con el índice elegido por el usuario.
- Los metadatos y la muestra de tripletas se cachean con `st.cache_data` para evitar recomputaciones cuando el fichero no cambia.

## Requisitos

- Python **3.11+**
- pip

## Instalación local

```bash
python -m venv .venv
source .venv/bin/activate         # Linux / macOS
.venv\Scripts\activate            # Windows

pip install -r requirements.txt
streamlit run app.py
```

La aplicación quedará disponible en `http://localhost:8501`.

## Tests

Los tests usan `pytest`, que es una dependencia de desarrollo y no se instala con `requirements.txt`. Para ejecutarlos:

```bash
pip install pytest
pytest tests/ -v
```

La suite incluye tests unitarios para las capas de validación, gestión de ficheros, estadísticas y bridge a pycottas, así como tests de integración para los flujos completos de compresión, consulta SPARQL, diferencia y fusión.

## Despliegue con Docker

```bash
docker compose up --build
```

La aplicación quedará disponible en `http://localhost:8501`.

El `Dockerfile` parte de `python:3.11-slim`, instala las dependencias fijadas en `requirements.txt`, expone el puerto `8501` y lanza Streamlit en modo *headless*. El `docker-compose.yml` añade un volumen para ficheros temporales (`/tmp/cottas_app`) y un *healthcheck* contra `/_stcore/health`.

## Estructura del proyecto

```text
cottas-ui/
├── app.py                    # Punto de entrada Streamlit + enrutamiento
├── views/                    # Vistas (una por operación)
│   ├── home.py
│   ├── compress.py
│   ├── decompress.py
│   ├── explore.py
│   ├── search.py
│   ├── sparql.py
│   ├── diff.py
│   └── merge.py
├── utils/                    # Capa de servicios
│   ├── cottas_bridge.py      # Wrapper sobre pycottas
│   ├── file_manager.py       # Sesiones y ficheros temporales
│   ├── stats.py              # Métricas y visualizaciones
│   └── validation.py         # Validación de entradas
├── tests/                    # Tests unitarios y de integración
├── .streamlit/               # Configuración de tema y servidor
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Arquitectura

```text
┌──────────────────────────────────────┐
│  Streamlit UI  (app.py + views/)     │
│  home · compress · decompress ·      │
│  explore · search · sparql ·         │
│  diff · merge                        │
└─────────────────┬────────────────────┘
                  │
┌─────────────────▼────────────────────┐
│  Capa de servicios (utils/)          │
│  cottas_bridge · validation ·        │
│  file_manager · stats                │
└─────────────────┬────────────────────┘
                  │
┌─────────────────▼────────────────────┐
│  pycottas  +  RDFLib  +  DuckDB      │
└──────────────────────────────────────┘
```

Las vistas (`views/`) gestionan únicamente la UI y el estado de sesión; toda la lógica de compresión, consulta y manipulación vive en `utils/cottas_bridge.py`. Esta separación aísla la aplicación de los cambios en la API de `pycottas`: si la librería evoluciona, solo se modifica el bridge.

## Casos de uso

| Vista       | Entrada                          | Salida                          |
|-------------|----------------------------------|---------------------------------|
| Compress    | `.ttl` / `.nt` / `.rdf` / `.nq`  | `.cottas`                       |
| Decompress  | `.cottas`                        | `.ttl` / `.nt` / `.rdf` / `.nq` |
| Explore     | `.cottas`                        | metadatos + estadísticas        |
| Search      | `.cottas` + patrón `(s,p,o[,g])` | tabla de tripletas              |
| SPARQL      | `.cottas` + consulta SELECT      | tabla de resultados             |
| Diff        | 2 × `.cottas`                    | `.cottas` con la diferencia     |
| Merge       | N × `.cottas`                    | `.cottas` fusionado             |

## Notas técnicas

- COTTAS almacena RDF como triple table o quad table en **Apache Parquet**.
- La librería pycottas soporta tanto **triples como quads**.
- Para preservar named graphs al descomprimir un quad table, solo formatos como **N-Quads** y **TriG** son válidos. La interfaz advierte automáticamente cuando se selecciona un formato incompatible.
- La vista de búsqueda muestra el **SQL generado** por pycottas en un expander, útil para entender cómo se traduce un patrón de tripletas a una consulta sobre Parquet.

## Posibles extensiones

- Despliegue público en Streamlit Community Cloud.
- Tests end-to-end de la interfaz con Playwright.
- Módulo de benchmarking para comparar rendimiento entre índices con datasets medianos.
- Integración con SPARQL endpoints externos para consultas federadas.

## Licencia

Apache 2.0 — ver `LICENSE`.