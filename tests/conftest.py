"""
conftest.py
Fixtures compartidas entre los módulos de test.
"""

import os
import tempfile
import shutil
import pytest


@pytest.fixture(scope="session")
def tmp_dir():
    """Temporary directory persisted for the whole test session."""
    d = tempfile.mkdtemp(prefix="cottas_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def sample_nt_file(tmp_dir):
    """Minimal N-Triples test file."""
    content = (
        "<http://example.org/Alice> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> "
        "<http://schema.org/Person> .\n"
        "<http://example.org/Alice> <http://schema.org/name> \"Alice\" .\n"
        "<http://example.org/Bob>   <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> "
        "<http://schema.org/Person> .\n"
        "<http://example.org/Bob>   <http://schema.org/name> \"Bob\" .\n"
        "<http://example.org/Alice> <http://schema.org/knows> <http://example.org/Bob> .\n"
    )
    path = os.path.join(tmp_dir, "sample.nt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


@pytest.fixture
def sample_cottas_file(tmp_dir, sample_nt_file):
    """COTTAS file generated from the test N-Triples file (requires pycottas)."""
    pycottas = pytest.importorskip("pycottas", reason="pycottas not installed")
    output = os.path.join(tmp_dir, "sample.cottas")
    pycottas.rdf2cottas(sample_nt_file, output, index="spo", disk=False)
    return output
