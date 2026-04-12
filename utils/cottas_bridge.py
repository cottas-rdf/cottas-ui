"""Typed bridge between the Streamlit UI and pycottas 1.1.x.

The original project used speculative API names. This bridge is aligned with the
current documented API of pycottas and centralises format conversions,
validation, metadata access and query helpers.
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


PYCOTTAS_VERSION = metadata.version("pycottas") if PYCOTTAS_AVAILABLE else None


def _file_cache_token(path: str) -> tuple[str, int, int]:
    if not os.path.exists(path):
        return os.path.abspath(path), 0, 0
    stat = os.stat(path)
    return os.path.abspath(path), int(stat.st_mtime_ns), int(stat.st_size)


@lru_cache(maxsize=64)
def _get_metadata_cached(cottas_path: str, _mtime_ns: int, _size_bytes: int) -> dict:
    _require_pycottas()
    try:
        if not verify_cottas_file(cottas_path):
            raise COTTASError("El fichero no es un COTTAS válido.")

        raw = pycottas.info(cottas_path)
        file_size_mb = (
            os.path.getsize(cottas_path) / (1024 ** 2)
            if os.path.exists(cottas_path)
            else raw.get("size (MB)")
        )
        meta = {
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
            },
        }
        return meta
    except (ValidationError, COTTASError):
        raise
    except Exception as exc:
        logger.exception("Error al leer metadatos de %s", cottas_path)
        raise COTTASError(f"Error al leer metadatos: {exc}") from exc


@lru_cache(maxsize=32)
def _get_sample_triples_cached(cottas_path: str, _mtime_ns: int, _size_bytes: int, limit: int) -> pd.DataFrame:
    _require_pycottas()
    try:
        doc = pycottas.COTTASDocument(cottas_path)
        meta = _get_metadata_cached(cottas_path, _mtime_ns, _size_bytes)
        pattern = build_triple_pattern(None, None, None, None) if meta["is_quad_table"] else build_triple_pattern(None, None, None)
        results = doc.search(pattern, limit=limit)
        return _to_dataframe(results)
    except Exception as exc:
        logger.exception("Error al obtener muestra de %s", cottas_path)
        raise COTTASError(f"Error al obtener muestra de tripletas: {exc}") from exc


@lru_cache(maxsize=32)
def _get_predicate_distribution_cached(cottas_path: str, _mtime_ns: int, _size_bytes: int, top_n: int) -> pd.DataFrame:
    _require_pycottas()
    try:
        escaped = _escape_path(cottas_path)
        query = (
            "SELECT p AS predicate, COUNT(*) AS count "
            f"FROM PARQUET_SCAN('{escaped}') "
            "GROUP BY p ORDER BY count DESC, predicate ASC "
            f"LIMIT {int(top_n)}"
        )
        return duckdb.execute(query).df()
    except Exception as exc:
        logger.exception("Error al calcular distribución de predicados de %s", cottas_path)
        raise COTTASError(f"Error al calcular distribución de predicados: {exc}") from exc

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
            "La librería pycottas no está instalada en el entorno activo. "
            "Instálala con `pip install pycottas` y reinicia la aplicación."
        )



def _ensure_output_exists(path: str, operation: str) -> None:
    if not os.path.exists(path):
        raise COTTASError(
            f"La operación {operation} terminó sin generar el fichero esperado: {path}"
        )



def _escape_path(path: str) -> str:
    return path.replace("'", "''")



def verify_cottas_file(cottas_path: str) -> bool:
    _require_pycottas()
    try:
        return bool(pycottas.verify(cottas_path))
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Error verificando fichero COTTAS: %s", cottas_path)
        raise COTTASError(f"No se pudo verificar el fichero COTTAS: {exc}") from exc



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
        logger.exception("Error al comprimir %s", input_path)
        raise COTTASError(f"Error durante la compresión: {exc}") from exc



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

        if is_quad and output_format == "ntriples":
            raise COTTASError(
                "El fichero contiene named graphs. N-Triples no puede representar quads; "
                "usa N-Quads o TriG."
            )
        if is_quad and not format_supports_named_graphs(output_format) and output_format != "ntriples":
            raise COTTASError(
                "El fichero contiene named graphs. El formato elegido no preserva grafos nombrados; "
                "usa N-Quads o TriG."
            )

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
        logger.exception("Error al descomprimir %s", input_path)
        raise COTTASError(f"Error durante la descompresión: {exc}") from exc



def get_metadata(cottas_path: str) -> dict:
    token = _file_cache_token(cottas_path)
    return _get_metadata_cached(*token).copy()



def _default_pattern_for_file(cottas_path: str) -> str:
    meta = get_metadata(cottas_path)
    if meta["is_quad_table"]:
        return build_triple_pattern(None, None, None, None)
    return build_triple_pattern(None, None, None)



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
            raise COTTASError("Este fichero no es un quad table; no puedes filtrar por grafo.")
        pattern = (
            build_triple_pattern(subject, predicate, obj, graph)
            if meta["is_quad_table"]
            else build_triple_pattern(subject, predicate, obj)
        )
        return pycottas.translate_triple_pattern(cottas_path, pattern, limit=limit, offset=offset)
    except Exception as exc:
        raise COTTASError(f"No se pudo generar el SQL del patrón: {exc}") from exc



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
            raise COTTASError("Este fichero no es un quad table; no puedes filtrar por grafo.")
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
        logger.exception("Error al evaluar patrón sobre %s", cottas_path)
        raise COTTASError(f"Error al evaluar el patrón de tripleta: {exc}") from exc



def run_sparql_select(cottas_path: str, query: str) -> pd.DataFrame:
    _require_pycottas()
    try:
        store = pycottas.COTTASStore(cottas_path)
        graph = rdflib.Graph(store=store)
        results = graph.query(query)
        columns = [str(var) for var in results.vars]
        rows = [["" if value is None else str(value) for value in row] for row in results]
        return pd.DataFrame(rows, columns=columns)
    except Exception as exc:
        logger.exception("Error al ejecutar SPARQL sobre %s", cottas_path)
        raise COTTASError(f"Error al ejecutar la consulta SPARQL: {exc}") from exc



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
        logger.exception("Error calculando diff entre %s y %s", path_a, path_b)
        raise COTTASError(f"Error al calcular la diferencia: {exc}") from exc



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
        logger.exception("Error fusionando ficheros COTTAS: %s", paths)
        raise COTTASError(f"Error al fusionar ficheros: {exc}") from exc



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
            elif len(triple) >= 3:
                rows.append(
                    {
                        "subject": str(triple[0]),
                        "predicate": str(triple[1]),
                        "object": str(triple[2]),
                    }
                )
            else:
                rows.append({"subject": str(triple), "predicate": "", "object": ""})
            continue

        rows.append({"subject": str(triple), "predicate": "", "object": ""})

    if not rows:
        return pd.DataFrame(columns=columns_3)

    df = pd.DataFrame(rows)
    target_columns = columns_4 if max_width >= 4 or "graph" in df.columns else columns_3
    for column in target_columns:
        if column not in df.columns:
            df[column] = ""
    return df[target_columns]
