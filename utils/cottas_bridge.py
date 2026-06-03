"""Typed bridge between the Streamlit UI and pycottas 1.1.x.

The bridge centralises format conversions, validation, metadata access and query
helpers so the Streamlit views do not depend directly on the pycottas API.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from functools import lru_cache
from importlib import metadata
from typing import Optional

import duckdb
import pandas as pd
import rdflib

from utils.validation import (
    ValidationError,
    build_triple_pattern,
    format_supports_named_graphs,
    normalize_index,
)

logger = logging.getLogger(__name__)

try:
    import pycottas

    PYCOTTAS_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in environments without pycottas
    pycottas = None
    PYCOTTAS_AVAILABLE = False


try:
    PYCOTTAS_VERSION = metadata.version("pycottas") if PYCOTTAS_AVAILABLE else None
except metadata.PackageNotFoundError:  # pragma: no cover - relevant for mocked tests
    PYCOTTAS_VERSION = None


RDFLIB_SERIALIZATION_FORMATS = {
    "ntriples": "nt",
    "turtle": "turtle",
    "nquads": "nquads",
    "trig": "trig",
    "n3": "n3",
    "xml": "xml",
}

DEFAULT_LIMIT = 10_000


class COTTASError(Exception):
    """Generic bridge exception shown in the UI."""


def _require_pycottas() -> None:
    if not PYCOTTAS_AVAILABLE:
        raise COTTASError(
            "The pycottas library is not installed in the active environment. "
            "Install it with `pip install pycottas` and restart the application."
        )


def _ensure_output_exists(path: str, operation: str) -> None:
    if not os.path.exists(path):
        raise COTTASError(
            f"Operation {operation} finished without producing the expected file: {path}"
        )


def _escape_path(path: str) -> str:
    return path.replace("'", "''")


def _file_cache_token(path: str) -> tuple[str, int, int]:
    if not os.path.exists(path):
        return os.path.abspath(path), 0, 0
    stat = os.stat(path)
    return os.path.abspath(path), int(stat.st_mtime_ns), int(stat.st_size)


def _empty_triples_dataframe(is_quad: bool = False) -> pd.DataFrame:
    """Returns an empty result table with the expected RDF columns."""
    columns = ["subject", "predicate", "object", "graph"] if is_quad else ["subject", "predicate", "object"]
    return pd.DataFrame(columns=columns)


def _metadata_from_parquet(cottas_path: str) -> dict:
    """Best-effort metadata fallback for valid COTTAS files.

    Some pycottas versions may fail while reading metadata from an empty COTTAS
    file produced by a set difference. DuckDB can still inspect the underlying
    Parquet file, so this fallback keeps the UI usable for empty but valid
    results.
    """
    escaped = _escape_path(cottas_path)
    describe_df = duckdb.execute(
        f"DESCRIBE SELECT * FROM PARQUET_SCAN('{escaped}')"
    ).df()
    columns = set(describe_df["column_name"].astype(str)) if "column_name" in describe_df else set()
    is_quad = "g" in columns

    count_row = duckdb.execute(
        f"SELECT COUNT(*) AS triple_count FROM PARQUET_SCAN('{escaped}')"
    ).fetchone()
    num_triples = int(count_row[0]) if count_row and count_row[0] is not None else 0

    def _count_distinct(column: str) -> Optional[int]:
        if column not in columns or num_triples == 0:
            return 0 if column in columns else None
        row = duckdb.execute(
            f"SELECT COUNT(DISTINCT {column}) FROM PARQUET_SCAN('{escaped}')"
        ).fetchone()
        return int(row[0]) if row and row[0] is not None else None

    file_size_mb = os.path.getsize(cottas_path) / (1024 ** 2) if os.path.exists(cottas_path) else None
    return {
        "triples": num_triples,
        "index": "N/A",
        "properties": _count_distinct("p"),
        "distinct_subjects": _count_distinct("s"),
        "distinct_objects": _count_distinct("o"),
        "triples_groups": None,
        "compression": None,
        "issued": None,
        "size (MB)": file_size_mb,
        "quads": is_quad,
        "metadata_source": "duckdb.parquet_scan",
    }


def _normalize_metadata(cottas_path: str, raw: dict, metadata_source: str) -> dict:
    file_size_mb = (
        os.path.getsize(cottas_path) / (1024 ** 2)
        if os.path.exists(cottas_path)
        else raw.get("size (MB)")
    )
    return {
        "num_triples": raw.get("triples"),
        "index": str(raw.get("index", "N/A")).upper(),
        "num_properties": raw.get("properties"),
        "num_distinct_subjects": raw.get("distinct_subjects"),
        "num_distinct_objects": raw.get("distinct_objects"),
        "num_triples_groups": raw.get("triples_groups"),
        "compression": raw.get("compression"),
        "issued": raw.get("issued"),
        "file_size_mb": file_size_mb,
        "is_quad_table": bool(raw.get("quads", False)),
        "custom_metadata": {
            "duckdb_reported_size_mb_decimal": raw.get("size (MB)"),
            "metadata_source": metadata_source,
        },
    }


@lru_cache(maxsize=64)
def _get_metadata_cached(cottas_path: str, _mtime_ns: int, _size_bytes: int) -> dict:
    _require_pycottas()
    try:
        if not verify_cottas_file(cottas_path):
            raise COTTASError("The file is not a valid COTTAS file.")

        metadata_source = "pycottas.info"
        try:
            raw = pycottas.info(cottas_path)
            if not isinstance(raw, dict):
                raise TypeError(f"pycottas.info returned {type(raw).__name__}")
        except Exception as info_exc:
            logger.warning(
                "pycottas.info failed for %s; using DuckDB metadata fallback: %s",
                cottas_path,
                info_exc,
            )
            raw = _metadata_from_parquet(cottas_path)
            metadata_source = raw.get("metadata_source", "duckdb.parquet_scan")

        return _normalize_metadata(cottas_path, raw, metadata_source)
    except (ValidationError, COTTASError):
        raise
    except Exception as exc:
        logger.exception("Error reading metadata from %s", cottas_path)
        raise COTTASError(f"Error reading metadata: {exc}") from exc


@lru_cache(maxsize=32)
def _get_sample_triples_cached(cottas_path: str, _mtime_ns: int, _size_bytes: int, limit: int) -> pd.DataFrame:
    _require_pycottas()
    try:
        meta = _get_metadata_cached(cottas_path, _mtime_ns, _size_bytes)
        if meta.get("num_triples") == 0:
            return _empty_triples_dataframe(meta["is_quad_table"])

        doc = pycottas.COTTASDocument(cottas_path)
        pattern = build_triple_pattern(None, None, None, None) if meta["is_quad_table"] else build_triple_pattern(None, None, None)
        results = doc.search(pattern, limit=limit)
        return _to_dataframe(results)
    except Exception as exc:
        logger.exception("Error retrieving sample from %s", cottas_path)
        raise COTTASError(f"Error retrieving triple sample: {exc}") from exc


@lru_cache(maxsize=32)
def _get_predicate_distribution_cached(cottas_path: str, _mtime_ns: int, _size_bytes: int, top_n: int) -> pd.DataFrame:
    _require_pycottas()
    try:
        meta = _get_metadata_cached(cottas_path, _mtime_ns, _size_bytes)
        if meta.get("num_triples") == 0:
            return pd.DataFrame(columns=["predicate", "count"])

        escaped = _escape_path(cottas_path)
        query = (
            "SELECT p AS predicate, COUNT(*) AS count "
            f"FROM PARQUET_SCAN('{escaped}') "
            "GROUP BY p ORDER BY count DESC, predicate ASC "
            f"LIMIT {int(top_n)}"
        )
        return duckdb.execute(query).df()
    except Exception as exc:
        logger.exception("Error computing predicate distribution from %s", cottas_path)
        raise COTTASError(f"Error computing predicate distribution: {exc}") from exc


def verify_cottas_file(cottas_path: str) -> bool:
    _require_pycottas()
    try:
        return bool(pycottas.verify(cottas_path))
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Error verifying COTTAS file: %s", cottas_path)
        raise COTTASError(f"Could not verify COTTAS file: {exc}") from exc


def compress_rdf(
    input_path: str,
    output_path: str,
    index: str = "SPO",
    disk: bool = False,
) -> None:
    """Compress plain RDF into COTTAS.

    pycottas 1.1.x exposes `index` and `disk`; compression level and row-group
    size are library-internal defaults at the moment.
    """
    _require_pycottas()
    try:
        normalized_index = normalize_index(index).lower()
        pycottas.rdf2cottas(input_path, output_path, index=normalized_index, disk=bool(disk))
        _ensure_output_exists(output_path, "rdf2cottas")
    except ValidationError as exc:
        raise COTTASError(str(exc)) from exc
    except COTTASError:
        raise
    except Exception as exc:
        logger.exception("Error compressing %s", input_path)
        raise COTTASError(f"Error during compression: {exc}") from exc


def _serialize_with_rdflib(
    source_path: str,
    output_path: str,
    source_is_quad: bool,
    target_format: str,
) -> None:
    rdflib_format = RDFLIB_SERIALIZATION_FORMATS[target_format]

    if source_is_quad:
        graph = rdflib.Dataset()
        graph.parse(source_path, format="nquads")
    else:
        graph = rdflib.Graph()
        graph.parse(source_path, format="nt")

    graph.serialize(destination=output_path, format=rdflib_format)


def decompress_cottas(
    input_path: str,
    output_path: str,
    output_format: str = "ntriples",
) -> None:
    """Decompress a COTTAS file and optionally convert it with RDFLib.

    pycottas natively writes line-oriented RDF. For triple tables that is
    N-Triples; for quad tables it is N-Quads-like output. This helper handles the
    conversion layer so the UI can offer multiple formats.
    """
    _require_pycottas()
    try:
        metadata_dict = get_metadata(input_path)
        is_quad = bool(metadata_dict["is_quad_table"])

        if is_quad and not format_supports_named_graphs(output_format):
            raise COTTASError(
                "The file contains named graphs. The chosen format does not preserve named graphs; "
                "use N-Quads or TriG."
            )

        if metadata_dict.get("num_triples") == 0:
            if output_format in {"ntriples", "nquads"}:
                open(output_path, "w", encoding="utf-8").close()
            else:
                graph = rdflib.Dataset() if is_quad else rdflib.Graph()
                graph.serialize(destination=output_path, format=RDFLIB_SERIALIZATION_FORMATS[output_format])
            return

        with tempfile.NamedTemporaryFile(suffix=".nq", delete=False) as tmp:
            temp_rdf_path = tmp.name

        try:
            pycottas.cottas2rdf(input_path, temp_rdf_path)
            _ensure_output_exists(temp_rdf_path, "cottas2rdf")

            if output_format == "ntriples" and not is_quad:
                shutil.copyfile(temp_rdf_path, output_path)
            elif output_format == "nquads":
                shutil.copyfile(temp_rdf_path, output_path)
            else:
                _serialize_with_rdflib(
                    source_path=temp_rdf_path,
                    output_path=output_path,
                    source_is_quad=is_quad,
                    target_format=output_format,
                )
        finally:
            if os.path.exists(temp_rdf_path):
                os.remove(temp_rdf_path)

        _ensure_output_exists(output_path, "decompress")
    except (ValidationError, COTTASError):
        raise
    except Exception as exc:
        logger.exception("Error decompressing %s", input_path)
        raise COTTASError(f"Error during decompression: {exc}") from exc


def get_metadata(cottas_path: str) -> dict:
    token = _file_cache_token(cottas_path)
    return _get_metadata_cached(*token).copy()


def get_sample_triples(cottas_path: str, limit: int = 100) -> pd.DataFrame:
    token = _file_cache_token(cottas_path)
    return _get_sample_triples_cached(*token, int(limit)).copy()


def get_predicate_distribution(cottas_path: str, top_n: int = 20) -> pd.DataFrame:
    token = _file_cache_token(cottas_path)
    return _get_predicate_distribution_cached(*token, int(top_n)).copy()


def get_search_sql(
    cottas_path: str,
    subject: Optional[str] = None,
    predicate: Optional[str] = None,
    obj: Optional[str] = None,
    graph: Optional[str] = None,
    limit: Optional[int] = DEFAULT_LIMIT,
    offset: Optional[int] = 0,
) -> str:
    _require_pycottas()
    try:
        meta = get_metadata(cottas_path)
        if graph and not meta["is_quad_table"]:
            raise COTTASError("This file is not a quad table; you cannot filter by graph.")
        if meta.get("num_triples") == 0:
            return "-- Empty COTTAS file: no triples to search."
        pattern = (
            build_triple_pattern(subject, predicate, obj, graph)
            if meta["is_quad_table"]
            else build_triple_pattern(subject, predicate, obj)
        )
        return pycottas.translate_triple_pattern(cottas_path, pattern, limit=limit, offset=offset)
    except Exception as exc:
        raise COTTASError(f"Could not generate SQL for the pattern: {exc}") from exc


def search_triple_pattern(
    cottas_path: str,
    subject: Optional[str] = None,
    predicate: Optional[str] = None,
    obj: Optional[str] = None,
    graph: Optional[str] = None,
    limit: Optional[int] = DEFAULT_LIMIT,
    offset: Optional[int] = 0,
) -> pd.DataFrame:
    _require_pycottas()
    try:
        meta = get_metadata(cottas_path)
        if graph and not meta["is_quad_table"]:
            raise COTTASError("This file is not a quad table; you cannot filter by graph.")
        if meta.get("num_triples") == 0:
            return _empty_triples_dataframe(meta["is_quad_table"])
        pattern = (
            build_triple_pattern(
                subject=subject,
                predicate=predicate,
                obj=obj,
                graph=graph,
            )
            if meta["is_quad_table"]
            else build_triple_pattern(
                subject=subject,
                predicate=predicate,
                obj=obj,
            )
        )
        doc = pycottas.COTTASDocument(cottas_path)
        results = doc.search(pattern, limit=limit, offset=offset)
        return _to_dataframe(results)
    except (ValidationError, COTTASError):
        raise
    except Exception as exc:
        logger.exception("Error evaluating pattern on %s", cottas_path)
        raise COTTASError(f"Error evaluating triple pattern: {exc}") from exc


def run_sparql_select(cottas_path: str, query: str) -> pd.DataFrame:
    _require_pycottas()
    try:
        meta = get_metadata(cottas_path)
        if meta.get("num_triples") == 0:
            return pd.DataFrame()
        store = pycottas.COTTASStore(cottas_path)
        graph = rdflib.Graph(store=store)
        results = graph.query(query)
        columns = [str(var) for var in results.vars]
        rows = [["" if value is None else str(value) for value in row] for row in results]
        return pd.DataFrame(rows, columns=columns)
    except Exception as exc:
        logger.exception("Error running SPARQL query on %s", cottas_path)
        raise COTTASError(f"Error running SPARQL query: {exc}") from exc


def diff_cottas_files(path_a: str, path_b: str, output_path: str, index: str = "SPO") -> None:
    _require_pycottas()
    try:
        pycottas.diff(path_a, path_b, output_path, index=normalize_index(index).lower())
        _ensure_output_exists(output_path, "diff")
    except ValidationError as exc:
        raise COTTASError(str(exc)) from exc
    except COTTASError:
        raise
    except Exception as exc:
        logger.exception("Error computing diff between %s and %s", path_a, path_b)
        raise COTTASError(f"Error computing difference: {exc}") from exc


def merge_cottas_files(paths: list[str], output_path: str, index: str = "SPO") -> None:
    _require_pycottas()
    try:
        pycottas.cat(paths, output_path, index=normalize_index(index).lower())
        _ensure_output_exists(output_path, "cat")
    except ValidationError as exc:
        raise COTTASError(str(exc)) from exc
    except COTTASError:
        raise
    except Exception as exc:
        logger.exception("Error merging COTTAS files: %s", paths)
        raise COTTASError(f"Error merging files: {exc}") from exc


def _to_dataframe(results) -> pd.DataFrame:
    columns_3 = ["subject", "predicate", "object"]
    columns_4 = ["subject", "predicate", "object", "graph"]

    if results is None:
        return pd.DataFrame(columns=columns_3)
    if isinstance(results, pd.DataFrame):
        return results.copy()

    rows = []
    max_width = 3
    for triple in results:
        if isinstance(triple, dict):
            rows.append(triple)
            max_width = max(max_width, len(triple))
            continue

        if hasattr(triple, "_asdict"):
            triple = triple._asdict()
            rows.append(triple)
            max_width = max(max_width, len(triple))
            continue

        if isinstance(triple, (tuple, list)):
            max_width = max(max_width, len(triple))
            if len(triple) >= 4:
                rows.append(
                    {
                        "subject": str(triple[0]),
                        "predicate": str(triple[1]),
                        "object": str(triple[2]),
                        "graph": "" if triple[3] is None else str(triple[3]),
                    }
                )
            elif len(triple) == 3:
                rows.append(
                    {
                        "subject": str(triple[0]),
                        "predicate": str(triple[1]),
                        "object": str(triple[2]),
                    }
                )
            continue

        rows.append({"subject": str(triple), "predicate": "", "object": ""})

    if not rows:
        return pd.DataFrame(columns=columns_3)

    df = pd.DataFrame(rows)
    if max_width >= 4 or "graph" in df.columns:
        return df.reindex(columns=columns_4)
    return df.reindex(columns=columns_3)
