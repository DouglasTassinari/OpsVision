"""Gráficos Plotly com o tema visual OpsVision.

Todos os builders devolvem figuras prontas para ``render()``: fundo
transparente (herda o carvão do tema), fonte Poppins, separadores
numéricos pt-BR ("1.000.000,00") e a paleta bordô da identidade.
As cores semânticas (verde/vermelho, prioridade, severidade) existem
para que qualquer leitor entenda o gráfico sem conhecer os dados.
"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from app.core.branding import BRANCO, CINZA, CINZA_CLARO

# Variações de bordô + neutros, legíveis sobre o fundo escuro.
CATEGORICAL = ["#A83248", "#7A1E2D", "#C9647A", "#A7A7AD", "#6E6E76", "#4B0F18", "#8C8C93", "#5C1622"]
BORDO_CLARO = "#A83248"
POSITIVO = "#3AA76D"
NEGATIVO = "#C4455A"
NEUTRO = "#6E6E76"
GRID = "#26262C"


def _layout(fig: go.Figure, height: int = 340, **overrides) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Poppins, sans-serif", color=BRANCO, size=13),
        separators=",.",
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        hoverlabel=dict(bgcolor=CINZA, font=dict(family="Poppins, sans-serif", color=BRANCO)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID),
        yaxis=dict(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID),
        **overrides,
    )
    return fig


def render(fig: go.Figure) -> None:
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _money_axis(fig: go.Figure) -> go.Figure:
    fig.update_yaxes(tickprefix="R$ ", tickformat="~s")
    return fig


def area(x, y, name: str = "", money: bool = False, color: str = BORDO_CLARO) -> go.Figure:
    hover = "%{x} · R$ %{y:,.2f}<extra></extra>" if money else "%{x} · %{y:,.0f}<extra></extra>"
    fig = go.Figure(
        go.Scatter(
            x=list(x), y=list(y), mode="lines", name=name,
            line=dict(color=color, width=2.5),
            fill="tozeroy", fillcolor="rgba(122,30,45,0.28)",
            hovertemplate=hover,
        )
    )
    _layout(fig, showlegend=False)
    return _money_axis(fig) if money else fig


def lines_compare(x, series: dict[str, tuple[list, str]], money: bool = False) -> go.Figure:
    """Linhas comparativas. ``series`` mapeia nome -> (valores, cor)."""
    hover = "%{x} · R$ %{y:,.2f}<extra>%{fullData.name}</extra>" if money \
        else "%{x} · %{y:,.0f}<extra>%{fullData.name}</extra>"
    fig = go.Figure()
    for name, (values, color) in series.items():
        fig.add_trace(
            go.Scatter(x=list(x), y=list(values), mode="lines", name=name,
                       line=dict(color=color, width=2.5), hovertemplate=hover)
        )
    _layout(fig)
    return _money_axis(fig) if money else fig


def hbar(categories, values, money: bool = False, colors=None, suffix: str = "") -> go.Figure:
    """Ranking horizontal (maior no topo). ``colors``: cor única, lista ou None (bordô)."""
    if money:
        text, hover = "R$ %{x:,.0f}", "%{y} · R$ %{x:,.2f}<extra></extra>"
    else:
        text, hover = f"%{{x:,.0f}}{suffix}", f"%{{y}} · %{{x:,.1f}}{suffix}<extra></extra>"
    fig = go.Figure(
        go.Bar(
            x=list(values), y=list(categories), orientation="h",
            marker_color=colors or BORDO_CLARO,
            texttemplate=text, textposition="auto", textfont=dict(size=12),
            hovertemplate=hover,
        )
    )
    height = max(300, 34 * len(list(categories)) + 60)
    _layout(fig, height=height, showlegend=False)
    fig.update_yaxes(autorange="reversed")
    if money:
        fig.update_xaxes(tickprefix="R$ ", tickformat="~s")
    return fig


def donut(labels, values, colors=None, money: bool = False) -> go.Figure:
    hover = "%{label} · R$ %{value:,.2f} (%{percent})<extra></extra>" if money \
        else "%{label} · %{value:,.0f} (%{percent})<extra></extra>"
    fig = go.Figure(
        go.Pie(
            labels=list(labels), values=list(values), hole=0.58, sort=False,
            marker=dict(colors=colors or CATEGORICAL, line=dict(color="#0F0F12", width=2)),
            textinfo="percent", textfont=dict(size=13, family="Poppins, sans-serif"),
            hovertemplate=hover,
        )
    )
    return _layout(fig)


def gauge(value: float, max_value: float, target: float | None = None, suffix: str = "%") -> go.Figure:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number=dict(suffix=suffix, font=dict(size=40, family="Poppins, sans-serif")),
            gauge=dict(
                axis=dict(range=[0, max_value], tickcolor=CINZA_CLARO,
                          tickfont=dict(color=CINZA_CLARO, size=11)),
                bar=dict(color=BORDO_CLARO, thickness=0.7),
                bgcolor=CINZA,
                borderwidth=0,
                threshold=dict(line=dict(color=BRANCO, width=3), thickness=0.85, value=target)
                if target is not None else None,
            ),
        )
    )
    return _layout(fig, height=260)


def cashflow(months, values, money: bool = True) -> go.Figure:
    """Barras mensais verde/vermelho + linha do acumulado: a história do caixa."""
    values = [float(v) for v in values]
    cumulative, total = [], 0.0
    for v in values:
        total += v
        cumulative.append(round(total, 2))
    bar_colors = [POSITIVO if v >= 0 else NEGATIVO for v in values]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(x=list(months), y=values, name="Fluxo do mês", marker_color=bar_colors,
               hovertemplate="%{x} · R$ %{y:,.2f}<extra>Fluxo do mês</extra>")
    )
    fig.add_trace(
        go.Scatter(x=list(months), y=cumulative, name="Acumulado", mode="lines",
                   line=dict(color=CINZA_CLARO, width=2, dash="dot"),
                   hovertemplate="%{x} · R$ %{y:,.2f}<extra>Acumulado</extra>")
    )
    _layout(fig)
    return _money_axis(fig)


def treemap(parents_labels: list[tuple[str, str, float]], money: bool = False) -> go.Figure:
    """Treemap de dois níveis a partir de tuplas (grupo, item, valor)."""
    groups: dict[str, float] = {}
    for group, _, value in parents_labels:
        groups[group] = groups.get(group, 0) + float(value)

    ids, labels, parents, values = [], [], [], []
    group_colors: dict[str, str] = {}
    for i, (group, total) in enumerate(groups.items()):
        ids.append(group)
        labels.append(group)
        parents.append("")
        values.append(total)
        group_colors[group] = CATEGORICAL[i % len(CATEGORICAL)]
    colors = [group_colors[g] for g in groups]
    for group, item, value in parents_labels:
        ids.append(f"{group}/{item}")
        labels.append(item)
        parents.append(group)
        values.append(float(value))
        colors.append(group_colors[group])

    hover = "%{label} · R$ %{value:,.2f}<extra></extra>" if money \
        else "%{label} · %{value:,.0f}<extra></extra>"
    fig = go.Figure(
        go.Treemap(
            ids=ids, labels=labels, parents=parents, values=values,
            branchvalues="total",
            marker=dict(colors=colors, line=dict(color="#0F0F12", width=1.5)),
            textfont=dict(family="Poppins, sans-serif", size=13),
            hovertemplate=hover,
        )
    )
    return _layout(fig, height=420)


def line_with_target(x, y, target: float, target_label: str, suffix: str = "%") -> go.Figure:
    fig = go.Figure(
        go.Scatter(x=list(x), y=list(y), mode="lines+markers", name="",
                   line=dict(color=BORDO_CLARO, width=2.5), marker=dict(size=6),
                   hovertemplate=f"%{{x}} · %{{y:,.2f}}{suffix}<extra></extra>")
    )
    fig.add_hline(
        y=target, line_dash="dash", line_color=CINZA_CLARO, line_width=1.5,
        annotation_text=target_label, annotation_font=dict(color=CINZA_CLARO, size=12),
    )
    return _layout(fig, showlegend=False)


def stacked_hbar(categories, series: dict[str, tuple[list, str]], money: bool = False) -> go.Figure:
    """Barras horizontais empilhadas. ``series`` mapeia nome -> (valores, cor)."""
    hover = "%{y} · R$ %{x:,.2f}<extra>%{fullData.name}</extra>" if money \
        else "%{y} · %{x:,.0f}<extra>%{fullData.name}</extra>"
    fig = go.Figure()
    for name, (values, color) in series.items():
        fig.add_trace(
            go.Bar(x=list(values), y=list(categories), orientation="h", name=name,
                   marker_color=color, hovertemplate=hover)
        )
    _layout(fig, height=280, barmode="stack")
    if money:
        fig.update_xaxes(tickprefix="R$ ", tickformat="~s")
    return fig
