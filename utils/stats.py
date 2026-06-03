"""Predicate-distribution visualizations for COTTAS files."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def build_predicate_bar_chart(df: pd.DataFrame) -> go.Figure:
    """Builds a horizontal bar chart with the top predicate frequencies."""
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available", showarrow=False)
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#F1F5F9",
            height=280,
        )
        return fig

    fig = px.bar(
        df.sort_values("count"),
        x="count",
        y="predicate",
        orientation="h",
        color="count",
        color_continuous_scale=["#1E3A5F", "#2563EB", "#60A5FA"],
        labels={"count": "Frequency", "predicate": "Predicate"},
    )
    fig.update_layout(
        title="Predicate distribution (top-N)",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#F1F5F9",
        title_font_size=16,
        coloraxis_showscale=False,
        margin=dict(t=60, b=40, l=40, r=40),
        yaxis=dict(tickfont=dict(size=11)),
    )
    fig.update_xaxes(gridcolor="#334155")
    return fig
