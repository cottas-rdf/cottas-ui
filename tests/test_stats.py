"""
test_stats.py
Pruebas unitarias del módulo utils/stats.py.
"""

import pandas as pd
import pytest
import plotly.graph_objects as go

from utils.stats import (
    estimate_nt_size_mb,
    estimate_hdt_size_mb,
    compression_ratio,
    build_size_comparison_chart,
    build_predicate_bar_chart,
    acr_gauge,
    _BYTES_PER_TRIPLE_NT,
    _ACR_HDT_AVG,
)


# ─── estimate_nt_size_mb ─────────────────────────────────────────────────────

class TestEstimateNtSizeMb:
    def test_zero_triples_returns_zero(self):
        assert estimate_nt_size_mb(0) == 0.0

    def test_none_returns_none(self):
        assert estimate_nt_size_mb(None) is None

    def test_one_million_triples(self):
        expected = (1_000_000 * _BYTES_PER_TRIPLE_NT) / (1024 ** 2)
        result = estimate_nt_size_mb(1_000_000)
        assert abs(result - expected) < 1e-6

    def test_positive_input_gives_positive_output(self):
        assert estimate_nt_size_mb(100) > 0


# ─── estimate_hdt_size_mb ────────────────────────────────────────────────────

class TestEstimateHdtSizeMb:
    def test_proportional_to_nt(self):
        nt = 100.0
        expected = nt * _ACR_HDT_AVG
        assert abs(estimate_hdt_size_mb(nt) - expected) < 1e-9

    def test_zero_input_gives_zero(self):
        assert estimate_hdt_size_mb(0.0) == 0.0

    def test_hdt_smaller_than_nt(self):
        nt = 500.0
        assert estimate_hdt_size_mb(nt) < nt


# ─── compression_ratio ───────────────────────────────────────────────────────

class TestCompressionRatio:
    def test_same_size_is_one(self):
        assert compression_ratio(10.0, 10.0) == 1.0

    def test_half_size_is_half(self):
        assert abs(compression_ratio(5.0, 10.0) - 0.5) < 1e-9

    def test_zero_denominator_returns_zero(self):
        assert compression_ratio(5.0, 0.0) == 0.0

    def test_cottas_smaller_than_one(self):
        # Un buen ratio de compresión debería ser < 1
        assert compression_ratio(4.0, 100.0) < 1.0

    def test_non_negative(self):
        assert compression_ratio(3.0, 50.0) >= 0.0


# ─── build_size_comparison_chart ─────────────────────────────────────────────

class TestBuildSizeComparisonChart:
    def test_returns_figure(self):
        fig = build_size_comparison_chart(5.0, 120.0, 10.0)
        assert isinstance(fig, go.Figure)

    def test_contains_three_bars_when_all_provided(self):
        fig = build_size_comparison_chart(5.0, 120.0, 10.0)
        assert len(fig.data) >= 1
        # La traza bar debe tener 3 puntos
        assert len(fig.data[0].x) == 3

    def test_works_without_nt_size(self):
        fig = build_size_comparison_chart(5.0, None, None)
        assert isinstance(fig, go.Figure)
        # Solo debería haber COTTAS
        assert len(fig.data[0].x) == 1

    def test_works_without_hdt_size(self):
        fig = build_size_comparison_chart(5.0, 120.0, None)
        assert isinstance(fig, go.Figure)
        assert len(fig.data[0].x) == 2


# ─── build_predicate_bar_chart ───────────────────────────────────────────────

class TestBuildPredicateBarChart:
    def _sample_df(self):
        return pd.DataFrame({
            "predicate": ["rdf:type", "schema:name", "owl:sameAs"],
            "count": [1000, 500, 200],
        })

    def test_returns_figure(self):
        df = self._sample_df()
        fig = build_predicate_bar_chart(df)
        assert isinstance(fig, go.Figure)

    def test_empty_df_returns_figure(self):
        fig = build_predicate_bar_chart(pd.DataFrame())
        assert isinstance(fig, go.Figure)

    def test_figure_has_data(self):
        df = self._sample_df()
        fig = build_predicate_bar_chart(df)
        assert len(fig.data) > 0


# ─── acr_gauge ───────────────────────────────────────────────────────────────

class TestAcrGauge:
    def test_returns_figure(self):
        fig = acr_gauge(4.1)
        assert isinstance(fig, go.Figure)

    def test_value_is_set_correctly(self):
        fig = acr_gauge(7.5)
        # El indicador debe contener el valor especificado
        assert fig.data[0].value == 7.5

    def test_zero_acr(self):
        fig = acr_gauge(0.0)
        assert isinstance(fig, go.Figure)

    def test_high_acr(self):
        fig = acr_gauge(25.0)
        assert isinstance(fig, go.Figure)
