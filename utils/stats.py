"""
stats.py
Cálculo y representación de estadísticas de compresión de ficheros COTTAS.
"""

from __future__ import annotations

import os
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# Factores de estimación empíricos basados en los resultados del paper COTTAS
# (Arenas-Guerrero & Ferrada, 2025, Tabla 2)
_ACR_COTTAS_AVG = 0.041     # 4.1 % sobre N-Triples (WDBench, mejor índice ~SPO)
_ACR_HDT_AVG    = 0.086     # 8.6 % sobre N-Triples (WDBench)
_BYTES_PER_TRIPLE_NT = 100  # estimación media de bytes por tripleta en N-Triples


def estimate_nt_size_mb(num_triples: Optional[int]) -> Optional[float]:
    """Estima el tamaño en MB del equivalente N-Triples."""
    if num_triples is None:
        return None
    return (num_triples * _BYTES_PER_TRIPLE_NT) / (1024 ** 2)


def compression_ratio(cottas_size_mb: float, nt_size_mb: float) -> float:
    """ACR = tamaño_cottas / tamaño_nt."""
    if nt_size_mb == 0:
        return 0.0
    return cottas_size_mb / nt_size_mb


def estimate_hdt_size_mb(nt_size_mb: float) -> float:
    """Estima el tamaño HDT a partir del tamaño N-Triples."""
    return nt_size_mb * _ACR_HDT_AVG


def build_size_comparison_chart(
    cottas_size_mb: float,
    nt_size_mb: Optional[float],
    hdt_size_mb: Optional[float],
) -> go.Figure:
    """
    Gráfico de barras comparando tamaños: N-Triples, HDT y COTTAS.
    """
    labels, sizes, colors = [], [], []

    if nt_size_mb:
        labels.append("N-Triples (estimado)")
        sizes.append(nt_size_mb)
        colors.append("#64748B")

    if hdt_size_mb:
        labels.append("HDT (estimado)")
        sizes.append(hdt_size_mb)
        colors.append("#F59E0B")

    labels.append("COTTAS (real)")
    sizes.append(cottas_size_mb)
    colors.append("#2563EB")

    fig = go.Figure(
        go.Bar(
            x=labels,
            y=sizes,
            marker_color=colors,
            text=[f"{s:.2f} MB" for s in sizes],
            textposition="outside",
        )
    )
    fig.update_layout(
        title="Comparativa de tamaño de fichero",
        yaxis_title="Tamaño (MB)",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#F1F5F9",
        title_font_size=16,
        showlegend=False,
        margin=dict(t=60, b=40, l=40, r=40),
    )
    fig.update_yaxes(gridcolor="#334155")
    return fig


def build_predicate_bar_chart(df: pd.DataFrame) -> go.Figure:
    """
    Gráfico de barras horizontales con la distribución de predicados.
    """
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sin datos", showarrow=False)
        return fig

    fig = px.bar(
        df.sort_values("count"),
        x="count",
        y="predicate",
        orientation="h",
        color="count",
        color_continuous_scale=["#1E3A5F", "#2563EB", "#60A5FA"],
        labels={"count": "Frecuencia", "predicate": "Predicado"},
    )
    fig.update_layout(
        title="Distribución de predicados (top-N)",
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


def acr_gauge(acr_pct: float) -> go.Figure:
    """Indicador tipo gauge para el ratio de compresión ACR."""
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=acr_pct,
            number={"suffix": "%", "font": {"color": "#F1F5F9", "size": 36}},
            title={"text": "ACR (% sobre N-Triples estimado)", "font": {"color": "#94A3B8", "size": 13}},
            gauge={
                "axis": {"range": [0, 25], "tickcolor": "#64748B"},
                "bar": {"color": "#2563EB"},
                "bgcolor": "#1E293B",
                "bordercolor": "#334155",
                "steps": [
                    {"range": [0, 5], "color": "#052E16"},
                    {"range": [5, 15], "color": "#14532D"},
                    {"range": [15, 25], "color": "#7F1D1D"},
                ],
                "threshold": {
                    "line": {"color": "#F59E0B", "width": 3},
                    "thickness": 0.85,
                    "value": _ACR_HDT_AVG * 100,
                },
            },
        )
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#F1F5F9",
        height=280,
        margin=dict(t=40, b=20, l=20, r=20),
    )
    return fig
