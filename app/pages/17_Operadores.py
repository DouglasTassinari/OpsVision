"""Operadores — visão 360º por operador da usinagem.

Uma linha por operador, cada indicador numa coluna colorida (verde = na
meta, amarelo = atenção, vermelho = abaixo): peças, rendimento de produção
e de setup, tempo esperando peça, tempo improdutivo, refugo por erro de
usinagem, saldo de tempo dos ajustes e o índice de improdutividade que
define a bonificação. A cor conta a história para quem quase não lê número.
"""
# ruff: noqa: E402
from __future__ import annotations

import sys
from pathlib import Path as _Path

_PROJECT_ROOT = str(_Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from datetime import date

import streamlit as st

from app.core import charts
from app.core.bootstrap import ensure_demo_data_once
from app.core.branding import CINZA_CLARO, CINZA_MEDIO, GRAFITE, MARINHO, apply_branding
from app.database.base import session_scope
from app.domain import operators_rules
from app.domain.machining_rules import MERITOCRACY_LIMIT_PCT, YIELD_TARGET_PCT
from app.services.operators_service import OperatorsService

apply_branding("Operadores")
ensure_demo_data_once()

# Cores das células (alinhadas à paleta dos gráficos da marca).
_COR = {"good": charts.POSITIVO, "warn": charts.ATENCAO, "bad": charts.NEGATIVO, "neutro": CINZA_MEDIO}


def _fmt_horas(horas: float) -> str:
    """Horas decimais → ``H:MM`` (ex.: 1.5 → '1:30')."""
    total_min = round(horas * 60)
    return f"{total_min // 60}:{total_min % 60:02d}"


def _fmt_int(valor: float) -> str:
    return f"{valor:,.0f}".replace(",", ".")


def _cell(texto: str, cor: str | None = None, bold: bool = False) -> str:
    estilo = "padding:6px 10px;border-bottom:1px solid #1E3247;white-space:nowrap;"
    if cor:
        estilo += f"color:{cor};"
    if bold:
        estilo += "font-weight:600;"
    return f'<td style="{estilo}">{texto}</td>'


st.title("Operadores")
st.caption(
    "Visão por pessoa da usinagem: produção, rendimento, refugo e o índice que define a "
    "bonificação. Verde atinge a meta, amarelo pede atenção, vermelho está abaixo."
)

col1, col2 = st.columns(2)
default_start = date.today().replace(day=1)
start = col1.date_input("De", value=default_start)
end = col2.date_input("Até", value=date.today())

with session_scope() as session:
    svc = OperatorsService(session)
    rows = svc.panel(start, end)
    resumo = svc.summary(start, end)

# ── Cartões-resumo ──
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Operadores", str(resumo.operator_count))
k2.metric(
    "Peças produzidas",
    _fmt_int(resumo.total_pieces),
    help="Total da equipe no período.",
)
k3.metric(
    "Rendimento produção",
    f"{resumo.avg_production_yield:.1f}%",
    delta=f"meta {YIELD_TARGET_PCT:.0f}%",
    delta_color="off",
)
k4.metric(
    "Produtividade setup",
    f"{resumo.avg_setup_productivity:.1f}%",
    delta="meta 85%",
    delta_color="off",
)
k5.metric(
    "Índice improdutividade",
    f"{resumo.avg_idle_index:.1f}%",
    delta=f"limite {MERITOCRACY_LIMIT_PCT:.0f}%",
    delta_color="off",
)

# ── Tabela densa colorida ──
st.subheader("Relatório por operador")

if not rows:
    st.info("Nenhum operador ativo cadastrado.")
else:
    cabecalho = [
        "Operador", "Turno", "Peças", "Rend. produção", "Prod. setup",
        "Sem peça", "Improdutivo", "Refugo usin.", "Ajustes (saldo)", "Índice / bonif.",
    ]
    th = "".join(
        f'<th style="padding:8px 10px;text-align:left;border-bottom:2px solid #4A90D9;'
        f'color:{CINZA_CLARO};font-weight:600;position:sticky;top:0;background:{MARINHO};">{c}</th>'
        for c in cabecalho
    )

    linhas_html = []
    for r in rows:
        # Rendimento produção: meta 85% (binário verde/vermelho).
        if r.production_yield is None:
            prod_cell = _cell("—", _COR["neutro"])
        else:
            band = "good" if r.production_yield >= YIELD_TARGET_PCT else "bad"
            prod_cell = _cell(f"{r.production_yield:.0f}%", _COR[band], bold=True)

        # Produtividade de setup: faixas 85 / 70.
        if r.setup_productivity is None:
            setup_cell = _cell("—", _COR["neutro"])
        else:
            band = operators_rules.performance_band(
                r.setup_productivity, operators_rules.SETUP_BAND_GOOD, operators_rules.SETUP_BAND_WARN
            )
            setup_cell = _cell(f"{r.setup_productivity:.0f}%", _COR[band], bold=True)

        # Ajustes: verde se economizou tempo (saldo +), vermelho se perdeu.
        if abs(r.adjustments_balance_hours) < 0.01:
            adj_cell = _cell("—", _COR["neutro"])
        else:
            adj_cor = _COR["good"] if r.adjustments_balance_hours > 0 else _COR["bad"]
            sinal = "+" if r.adjustments_balance_hours > 0 else "−"
            adj_cell = _cell(f"{sinal}{_fmt_horas(abs(r.adjustments_balance_hours))}", adj_cor)

        # Índice de improdutividade + selo de bonificação.
        if r.reported_hours <= 0:
            merito_cell = _cell("—", _COR["neutro"])
        elif r.passes_meritocracy:
            merito_cell = _cell(f"✓ {r.idle_index:.1f}%", _COR["good"], bold=True)
        else:
            merito_cell = _cell(f"{r.idle_index:.1f}%", _COR["bad"], bold=True)

        refugo_cor = _COR["bad"] if r.scrap_usinagem > 0 else _COR["neutro"]

        linha = (
            "<tr>"
            + _cell(r.name, CINZA_CLARO, bold=True)
            + _cell(f"T{r.shift}", CINZA_MEDIO)
            + _cell(_fmt_int(r.pieces), CINZA_CLARO)
            + prod_cell
            + setup_cell
            + _cell(_fmt_horas(r.no_part_hours) if r.no_part_hours > 0 else "—",
                    CINZA_MEDIO if r.no_part_hours else _COR["neutro"])
            + _cell(_fmt_horas(r.idle_hours) if r.idle_hours > 0 else "—",
                    CINZA_CLARO if r.idle_hours else _COR["neutro"])
            + _cell(_fmt_int(r.scrap_usinagem) if r.scrap_usinagem else "—", refugo_cor)
            + adj_cell
            + merito_cell
            + "</tr>"
        )
        linhas_html.append(linha)

    tabela = (
        f'<div style="overflow-x:auto;border-radius:8px;background:{GRAFITE};padding:2px;">'
        f'<table style="border-collapse:collapse;width:100%;font-size:13px;'
        f'font-family:Poppins,sans-serif;color:{CINZA_CLARO};">'
        f"<thead><tr>{th}</tr></thead><tbody>{''.join(linhas_html)}</tbody></table></div>"
    )
    st.markdown(tabela, unsafe_allow_html=True)
    st.caption(
        "Rendimento de produção com meta de 85%; produtividade de setup em faixas 85% / 70%. "
        "«Sem peça» é espera de material (não conta como ociosidade). «✓» marca quem está "
        "dentro do limite de improdutividade e recebe bonificação."
    )

# ── Onde o tempo da equipe vai ──
st.subheader("Onde o tempo da equipe vai")
total = resumo.production_hours + resumo.setup_hours + resumo.no_part_hours + resumo.unproductive_hours
if total <= 0:
    st.info("Sem apontamentos no período selecionado.")
else:
    labels = ["Produção", "Setup", "Sem peça", "Improdutivo"]
    values = [resumo.production_hours, resumo.setup_hours, resumo.no_part_hours, resumo.unproductive_hours]
    cores = [charts.POSITIVO, charts.ATENCAO, charts.NEUTRO, charts.NEGATIVO]
    bar_col, leg_col = st.columns([3, 2])
    with bar_col:
        charts.render(charts.donut(labels, values, colors=cores))
    with leg_col:
        st.markdown("**Horas apontadas por categoria**")
        for lbl, val in zip(labels, values):
            pct = 100 * val / total
            st.text(f"{lbl}: {val:,.0f}h ({pct:.0f}%)".replace(",", "."))

st.caption(
    "Nota: esta base é sintética e não inclui ponto eletrônico, então o "
    "«índice de improdutividade» aproxima o índice de meritocracia do BI "
    "industrial pelo tempo improdutivo apontado. Estrutura e cortes (meta 85%, "
    "fator de setup 0,85, limite 7%) são os do sistema de origem."
)
