"""Utilities for validating inputs and adapting them to pycottas 1.1.x."""

from __future__ import annotations

import re
from typing import Optional

_UNSET = object()

VALID_INDEXES = ("SPO", "SOP", "PSO", "POS", "OSP", "OPS")
QUAD_SAFE_OUTPUT_FORMATS = {"nquads", "trig"}


class ValidationError(ValueError):
    """Raised when user input is invalid for the requested operation."""


def normalize_index(index: str) -> str:
    value = (index or "").strip().upper()
    if value not in VALID_INDEXES:
        raise ValidationError(
            f"Índice no válido: {index!r}. Usa uno de: {', '.join(VALID_INDEXES)}."
        )
    return value


_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_output_stem(name: str, fallback: str = "output") -> str:
    cleaned = _SAFE_FILENAME_RE.sub("_", (name or "").strip()).strip("._-")
    return cleaned or fallback


def build_triple_pattern(
    subject: Optional[str] = None,
    predicate: Optional[str] = None,
    obj: Optional[str] = None,
    graph: Optional[str] | object = _UNSET,
) -> str:
    parts = [subject or "?s", predicate or "?p", obj or "?o"]
    if graph is not _UNSET:
        parts.append("?g" if graph is None else (graph or "?g"))
    return " ".join(part.strip() if isinstance(part, str) else part for part in parts)


_PREFIX_BASE_RE = re.compile(r"^\s*(PREFIX\s+[^\n]+\n|BASE\s+[^\n]+\n)+", re.IGNORECASE)


def is_select_query(query: str) -> bool:
    """Allow PREFIX/BASE declarations before SELECT."""
    if not query or not query.strip():
        return False
    stripped = _PREFIX_BASE_RE.sub("", query).lstrip()
    return stripped.upper().startswith("SELECT")



def format_supports_named_graphs(format_id: str) -> bool:
    return format_id in QUAD_SAFE_OUTPUT_FORMATS



def recommend_index(subject: Optional[str], predicate: Optional[str], obj: Optional[str]) -> str:
    """Simple heuristic aligned with the paper and pycottas query patterns.

    It is only a hint for the UI, not a hard rule.
    """
    has_s = bool(subject and subject.strip())
    has_p = bool(predicate and predicate.strip())
    has_o = bool(obj and obj.strip())

    if has_p and has_o:
        return "POS"
    if has_p:
        return "PSO"
    if has_o:
        return "OSP"
    if has_s:
        return "SPO"
    return "SPO"
