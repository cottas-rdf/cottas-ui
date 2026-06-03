"""Unit tests for utils.stats."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from utils.stats import build_predicate_bar_chart


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "predicate": ["http://example.org/p1", "http://example.org/p2"],
            "count": [10, 5],
        }
    )


class TestBuildPredicateBarChart:
    def test_returns_figure_for_non_empty_dataframe(self):
        fig = build_predicate_bar_chart(_sample_df())
        assert isinstance(fig, go.Figure)

    def test_contains_one_bar_trace_for_non_empty_dataframe(self):
        fig = build_predicate_bar_chart(_sample_df())
        assert len(fig.data) == 1

    def test_uses_predicate_values_on_y_axis(self):
        fig = build_predicate_bar_chart(_sample_df())
        y_values = list(fig.data[0].y)
        assert "http://example.org/p1" in y_values
        assert "http://example.org/p2" in y_values

    def test_uses_counts_on_x_axis(self):
        fig = build_predicate_bar_chart(_sample_df())
        assert sorted(fig.data[0].x) == [5, 10]

    def test_empty_dataframe_returns_figure(self):
        fig = build_predicate_bar_chart(pd.DataFrame(columns=["predicate", "count"]))
        assert isinstance(fig, go.Figure)

    def test_empty_dataframe_has_no_bar_traces(self):
        fig = build_predicate_bar_chart(pd.DataFrame(columns=["predicate", "count"]))
        assert len(fig.data) == 0

    def test_empty_dataframe_contains_no_data_annotation(self):
        fig = build_predicate_bar_chart(pd.DataFrame(columns=["predicate", "count"]))
        assert any(annotation.text == "No data available" for annotation in fig.layout.annotations)
