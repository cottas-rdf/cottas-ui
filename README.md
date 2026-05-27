# COTTAS Manager

Streamlit web application for managing RDF graphs compressed in COTTAS format.

> TFG · Universidad Politécnica de Madrid · Tutor: Julián Arenas-Guerrero

## Features

The application wraps the **pycottas** library to provide a visual interface for the following operations:

- **Compression** RDF → COTTAS from TTL, NT, NQ, TriG, N3, and RDF/XML.
- **Decompression** COTTAS → RDF in any of the above formats.
- **Exploration** of metadata, predicate distribution, and triple samples.
- **Search** by pattern `(s, p, o[, g])` directly on the compressed file.
- **SPARQL SELECT queries** using `COTTASStore` as an RDFLib backend.
- **Difference** between two COTTAS graphs.
- **Merge** of two COTTAS files from the current UI; duplicate triples are collapsed according to RDF graph set semantics. The internal bridge accepts a list of paths, so the operation is prepared for N-file merge extension.

## Implementation details

Integration with `pycottas` (version 1.1.x) is concentrated in `utils/cottas_bridge.py`, which shields the application from future changes in the library's API:

- Compression uses the public parameters `index` and `disk` of `pycottas.rdf2cottas`.
- Decompression combines `pycottas.cottas2rdf` with format conversion via RDFLib.
- Pattern search uses `COTTASDocument.search(...)`.
- SPARQL is executed through `COTTASStore` as an RDFLib backend.
- `merge` and `diff` operations materialize the result with the user-selected index; empty difference results are handled as valid empty COTTAS outputs.
- Metadata, triple samples, and predicate distributions are memoized in memory with Python `functools.lru_cache`, keyed by file path, modification time, size, and query parameters.

## Requirements

- Python **3.11+**
- pip

## Local installation

```bash
python -m venv .venv
source .venv/bin/activate         # Linux / macOS
.venv\Scripts\activate            # Windows

pip install -r requirements.txt
streamlit run app.py
```

The application will be available at `http://localhost:8501`.

## Tests

Tests use `pytest`, which is a development dependency and is not installed with `requirements.txt`. To run them:

```bash
pip install pytest
pytest tests/ -v
```

The suite includes unit tests for the validation, file management, predicate-distribution visualization, and pycottas bridge layers, as well as integration tests for the complete compression, SPARQL query, difference, and merge flows.

## Docker deployment

```bash
docker compose up --build
```

The application will be available at `http://localhost:8501`.

The `Dockerfile` starts from `python:3.11-slim`, installs the dependencies declared in `requirements.txt`, exposes port `8501`, sets `COTTAS_TMP_DIR=/tmp/cottas_app`, and launches Streamlit in headless mode. The `docker-compose.yml` adds a volume for temporary files (`/tmp/cottas_app`) and a healthcheck against `/_stcore/health`.

## Project structure

```text
cottas-ui/
├── app.py                    # Streamlit entry point + routing
├── views/                    # Views (one per operation)
│   ├── home.py
│   ├── compress.py
│   ├── decompress.py
│   ├── explore.py
│   ├── search.py
│   ├── sparql.py
│   ├── diff.py
│   └── merge.py
├── utils/                    # Services layer
│   ├── cottas_bridge.py      # Wrapper over pycottas
│   ├── file_manager.py       # Sessions and temporary files
│   ├── stats.py              # Predicate-distribution visualization
│   └── validation.py         # Input validation
├── tests/                    # Unit and integration tests
├── .streamlit/               # Theme and server configuration
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Architecture

```text
┌──────────────────────────────────────┐
│  Streamlit UI  (app.py + views/)     │
│  home · compress · decompress ·      │
│  explore · search · sparql ·         │
│  diff · merge                        │
└─────────────────┬────────────────────┘
                  │
┌─────────────────▼────────────────────┐
│  Services layer (utils/)             │
│  cottas_bridge · validation ·        │
│  file_manager · stats                │
└─────────────────┬────────────────────┘
                  │
┌─────────────────▼────────────────────┐
│  pycottas  +  RDFLib  +  DuckDB      │
└──────────────────────────────────────┘
```

Views (`views/`) handle only UI and session state; all compression, query, and manipulation logic lives in `utils/cottas_bridge.py`. This separation shields the application from changes in the `pycottas` API: if the library evolves, only the bridge needs to be updated.

## Use cases

| View       | Input                                                         | Output                          |
|------------|---------------------------------------------------------------|---------------------------------|
| Compress   | `.ttl` / `.nt` / `.rdf` / `.nq`                               | `.cottas`                       |
| Decompress | `.cottas`                                                     | `.ttl` / `.nt` / `.rdf` / `.nq` |
| Explore    | `.cottas`                                                     | metadata + predicate chart      |
| Search     | `.cottas` + pattern `(s,p,o[,g])`                             | triples table                   |
| SPARQL     | `.cottas` + SELECT query                                      | results table                   |
| Diff       | 2 × `.cottas`                                                 | `.cottas` with the difference   |
| Merge      | 2 × `.cottas`in the current UI; list of paths in the bridge   | union `.cottas`                 |

## Technical notes

- COTTAS stores RDF as a triple table or quad table in **Apache Parquet**.
- The pycottas library supports both **triples and quads**.
- To preserve named graphs when decompressing a quad table, only formats such as **N-Quads** and **TriG** are valid. The interface automatically warns when an incompatible format is selected.
- The search view shows the **SQL generated** by pycottas in an expander, useful for understanding how a triple pattern is translated into a query over Parquet.
- The merge view computes the union of RDF triples, so merging two identical graphs produces the same number of triples, not twice as many.

## Possible extensions

- Public deployment on Streamlit Community Cloud.
- End-to-end UI tests with Playwright.
- Benchmarking module to compare performance between indexes with medium-sized datasets.
- Integration with external SPARQL endpoints for federated queries.

## License

Apache 2.0 — see `LICENSE`.
