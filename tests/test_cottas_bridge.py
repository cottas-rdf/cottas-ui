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
