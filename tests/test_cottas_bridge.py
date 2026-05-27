"""Unit tests for utils.cottas_bridge."""

from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock

import pandas as pd
import pytest


def _make_bridge_with_mock():
    fake = MagicMock()
    fake.verify.return_value = True
    fake.info.return_value = {
        "index": "spo",
        "triples": 100,
        "triples_groups": 1,
        "properties": 5,
        "distinct_subjects": 10,
        "distinct_objects": 12,
        "issued": "2026-03-18T00:00:00",
        "size (MB)": 1.0,
        "compression": "ZSTD",
        "quads": False,
    }

    sys.modules["pycottas"] = fake
    sys.modules.pop("utils.cottas_bridge", None)
    import utils.cottas_bridge as bridge

    importlib.reload(bridge)
    bridge.PYCOTTAS_AVAILABLE = True
    return bridge, fake


class _DuckResult:
    def __init__(self, dataframe=None, row=None):
        self._dataframe = dataframe
        self._row = row

    def df(self):
        return self._dataframe

    def fetchone(self):
        return self._row


def _patch_empty_parquet(monkeypatch, bridge, columns=None):
    columns = columns or ["s", "p", "o"]

    def _execute(query):
        if query.startswith("DESCRIBE"):
            return _DuckResult(dataframe=pd.DataFrame({"column_name": columns}))
        if "COUNT(*)" in query:
            return _DuckResult(row=(0,))
        raise AssertionError(f"Unexpected DuckDB query: {query}")

    monkeypatch.setattr(bridge.duckdb, "execute", _execute)


class TestCompressRdf:
    def test_calls_rdf2cottas_with_normalized_index(self, tmp_path):
        bridge, fake = _make_bridge_with_mock()
        inp = str(tmp_path / "in.nt")
        out = str(tmp_path / "out.cottas")
        open(out, "wb").close()

        bridge.compress_rdf(inp, out, index="PSO", disk=True)

        fake.rdf2cottas.assert_called_once_with(inp, out, index="pso", disk=True)

    def test_invalid_index_raises(self, tmp_path):
        bridge, _ = _make_bridge_with_mock()
        with pytest.raises(bridge.COTTASError):
            bridge.compress_rdf(str(tmp_path / "in.nt"), str(tmp_path / "out.cottas"), index="ABC")


class TestGetMetadata:
    def test_returns_normalized_metadata(self, tmp_path):
        bridge, fake = _make_bridge_with_mock()
        inp = str(tmp_path / "g.cottas")
        with open(inp, "wb") as handle:
            handle.write(b"X" * (1024 * 1024))

        meta = bridge.get_metadata(inp)

        assert meta["num_triples"] == 100
        assert meta["index"] == "SPO"
        assert meta["num_properties"] == 5
        assert meta["is_quad_table"] is False
        fake.verify.assert_called()
        fake.info.assert_called_once_with(inp)

    def test_falls_back_to_duckdb_when_pycottas_info_returns_none(self, tmp_path, monkeypatch):
        bridge, fake = _make_bridge_with_mock()
        fake.info.return_value = None
        inp = tmp_path / "empty.cottas"
        inp.write_bytes(b"PAR1")
        _patch_empty_parquet(monkeypatch, bridge)

        meta = bridge.get_metadata(str(inp))

        assert meta["num_triples"] == 0
        assert meta["is_quad_table"] is False
        assert meta["custom_metadata"]["metadata_source"] == "duckdb.parquet_scan"

    def test_fallback_detects_quad_table_schema(self, tmp_path, monkeypatch):
        bridge, fake = _make_bridge_with_mock()
        fake.info.return_value = None
        inp = tmp_path / "empty_quad.cottas"
        inp.write_bytes(b"PAR1")
        _patch_empty_parquet(monkeypatch, bridge, columns=["s", "p", "o", "g"])

        meta = bridge.get_metadata(str(inp))

        assert meta["num_triples"] == 0
        assert meta["is_quad_table"] is True


class TestSampleAndSearch:
    def test_get_sample_triples_uses_default_pattern(self, tmp_path):
        bridge, fake = _make_bridge_with_mock()
        doc = MagicMock()
        doc.search.return_value = [("s1", "p1", "o1"), ("s2", "p2", "o2")]
        fake.COTTASDocument.return_value = doc

        df = bridge.get_sample_triples(str(tmp_path / "g.cottas"), limit=2)

        assert list(df.columns) == ["subject", "predicate", "object"]
        assert len(df) == 2
        doc.search.assert_called_once_with("?s ?p ?o", limit=2)

    def test_sample_from_empty_result_does_not_call_document(self, monkeypatch):
        bridge, fake = _make_bridge_with_mock()
        monkeypatch.setattr(
            bridge,
            "_get_metadata_cached",
            lambda *_args: {"num_triples": 0, "is_quad_table": False},
        )

        df = bridge._get_sample_triples_cached("empty.cottas", 0, 0, 20)

        assert list(df.columns) == ["subject", "predicate", "object"]
        assert df.empty
        fake.COTTASDocument.assert_not_called()

    def test_search_triple_pattern_builds_pattern(self, tmp_path):
        bridge, fake = _make_bridge_with_mock()
        doc = MagicMock()
        doc.search.return_value = [("s1", "p1", "o1")]
        fake.COTTASDocument.return_value = doc

        df = bridge.search_triple_pattern(
            str(tmp_path / "g.cottas"),
            subject="<http://ex.org/s>",
            predicate=None,
            obj='"lit"',
            limit=10,
            offset=20,
        )

        assert len(df) == 1
        doc.search.assert_called_once_with('<http://ex.org/s> ?p "lit"', limit=10, offset=20)


    def test_search_sql_from_empty_result_does_not_call_pycottas_translate(self, monkeypatch):
        bridge, fake = _make_bridge_with_mock()
        monkeypatch.setattr(
            bridge,
            "get_metadata",
            lambda _path: {"num_triples": 0, "is_quad_table": False},
        )

        sql = bridge.get_search_sql("empty.cottas", limit=10, offset=0)

        assert sql == "-- Empty COTTAS file: no triples to search."
        fake.translate_triple_pattern.assert_not_called()

    def test_search_from_empty_result_does_not_call_document(self, monkeypatch):
        bridge, fake = _make_bridge_with_mock()
        monkeypatch.setattr(
            bridge,
            "get_metadata",
            lambda _path: {"num_triples": 0, "is_quad_table": False},
        )

        df = bridge.search_triple_pattern("empty.cottas", limit=10, offset=0)

        assert list(df.columns) == ["subject", "predicate", "object"]
        assert df.empty
        fake.COTTASDocument.assert_not_called()

    def test_quad_results_include_graph_column(self):
        bridge, _ = _make_bridge_with_mock()
        df = bridge._to_dataframe([("s", "p", "o", "g")])
        assert list(df.columns) == ["subject", "predicate", "object", "graph"]
        assert df.iloc[0]["graph"] == "g"


class TestPredicateDistribution:
    def test_duckdb_dataframe_passthrough(self, monkeypatch):
        bridge, _ = _make_bridge_with_mock()
        expected = pd.DataFrame({"predicate": ["p1"], "count": [3]})

        class _Result:
            def df(self):
                return expected

        monkeypatch.setattr(bridge.duckdb, "execute", lambda query: _Result())
        result = bridge.get_predicate_distribution("/tmp/x.cottas", top_n=5)
        pd.testing.assert_frame_equal(result, expected)

    def test_empty_distribution_returns_expected_columns(self, monkeypatch):
        bridge, _ = _make_bridge_with_mock()
        monkeypatch.setattr(
            bridge,
            "_get_metadata_cached",
            lambda *_args: {"num_triples": 0, "is_quad_table": False},
        )

        df = bridge._get_predicate_distribution_cached("empty.cottas", 0, 0, 10)

        assert list(df.columns) == ["predicate", "count"]
        assert df.empty


class TestSparql:
    def test_sparql_on_empty_result_returns_empty_dataframe(self, monkeypatch):
        bridge, fake = _make_bridge_with_mock()
        monkeypatch.setattr(
            bridge,
            "get_metadata",
            lambda _path: {"num_triples": 0, "is_quad_table": False},
        )

        df = bridge.run_sparql_select("empty.cottas", "SELECT ?s WHERE { ?s ?p ?o }")

        assert df.empty
        fake.COTTASStore.assert_not_called()


class TestDecompress:
    def test_decompress_empty_result_writes_empty_ntriples(self, tmp_path, monkeypatch):
        bridge, fake = _make_bridge_with_mock()
        out = tmp_path / "empty.nt"
        monkeypatch.setattr(
            bridge,
            "get_metadata",
            lambda _path: {"num_triples": 0, "is_quad_table": False},
        )

        bridge.decompress_cottas("empty.cottas", str(out), output_format="ntriples")

        assert out.exists()
        assert out.read_text(encoding="utf-8") == ""
        fake.cottas2rdf.assert_not_called()


class TestDiffAndMerge:
    def test_diff_calls_pycottas(self, tmp_path):
        bridge, fake = _make_bridge_with_mock()
        out = str(tmp_path / "out.cottas")
        open(out, "wb").close()
        bridge.diff_cottas_files("a.cottas", "b.cottas", out, index="OPS")
        fake.diff.assert_called_once_with("a.cottas", "b.cottas", out, index="ops")

    def test_merge_calls_pycottas(self, tmp_path):
        bridge, fake = _make_bridge_with_mock()
        out = str(tmp_path / "out.cottas")
        open(out, "wb").close()
        bridge.merge_cottas_files(["a.cottas", "b.cottas"], out, index="SPO")
        fake.cat.assert_called_once_with(["a.cottas", "b.cottas"], out, index="spo")
