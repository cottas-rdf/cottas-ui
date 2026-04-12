"""Tests de integración para flujos completos: compress→search→sparql→diff→merge."""
import os, pytest
pytest.importorskip("pycottas")
from utils import cottas_bridge as cb

TTL_A = """@prefix ex: <http://example.org/> .
ex:alice ex:knows ex:bob .
ex:alice ex:age "30" .
ex:bob ex:knows ex:carol .
"""
TTL_B = """@prefix ex: <http://example.org/> .
ex:alice ex:knows ex:bob .
ex:dave ex:knows ex:eve .
"""

@pytest.fixture
def cottas_a(tmp_path):
    ttl = tmp_path / "a.ttl"; ttl.write_text(TTL_A)
    out = tmp_path / "a.cottas"
    cb.compress_rdf(str(ttl), str(out), index="SPO", disk=False)
    return str(out)

@pytest.fixture
def cottas_b(tmp_path):
    ttl = tmp_path / "b.ttl"; ttl.write_text(TTL_B)
    out = tmp_path / "b.cottas"
    cb.compress_rdf(str(ttl), str(out), index="SPO", disk=False)
    return str(out)

def test_compress_creates_file(cottas_a):
    assert os.path.exists(cottas_a) and os.path.getsize(cottas_a) > 0

def test_sparql_select(cottas_a):
    df = cb.run_sparql_select(cottas_a, "SELECT ?s WHERE { ?s ?p ?o } LIMIT 10")
    assert len(df) > 0

def test_diff_and_merge(cottas_a, cottas_b, tmp_path):
    diff_out = tmp_path / "diff.cottas"
    cb.diff_cottas_files(cottas_a, cottas_b, str(diff_out))
    assert diff_out.exists()
    merge_out = tmp_path / "merge.cottas"
    cb.merge_cottas_files([cottas_a, cottas_b], str(merge_out))
    assert merge_out.exists()
