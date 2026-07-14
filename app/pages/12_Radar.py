"""Radar de Oportunidades — follow-up térmico das propostas em aberto."""
# ruff: noqa: E402  -- sys.path bootstrap below must run before the app.* imports
from __future__ import annotations

import sys
from pathlib import Path as _Path

# Streamlit only adds this script's own folder to sys.path, not the project
# root, so the "app.*" imports below would fail without this.
_PROJECT_ROOT = str(_Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from datetime import date

import pandas as pd
import streamlit as st

from app.core import charts
from app.core.bootstrap import ensure_demo_data_once
from app.core.branding import apply_branding
from app.core.formatting import format_brl
from app.database.base import session_scope
from app.domain import opportunity_rules
from app.services.opportunity_service import OpportunityService

apply_branding("Radar de Oportunidades")

ensure_demo_data_once()

SEGMENTOS = {"retail": "Varejo", "wholesale": "Atacado", "enterprise": "Corporativo"}
STATUS_PT = {"draft": "Rascunho", "confirmed": "Confirmada"}
_ORDEM_FAIXA = ["Quente", "Morna", "Fria", "Vencida"]

st.title("Radar de Oportunidades")
st.caption(
    "Cada proposta em aberto (pedido ainda não faturado) ganha uma temperatura "
    "pela idade dela. Serve para nenhuma proposta envelhecer sem follow-up."
)

hoje = date.today()
with session_scope() as session:
    propostas = OpportunityService(session).radar(hoje)

if not propostas:
    st.info("Nenhuma proposta em aberto no momento.")
    st.stop()

# --- Filtros (em memória) --------------------------------------------------
col_a, col_b, col_c = st.columns(3)
segs_disp = sorted({p["segmento"] for p in propostas})
sel_segs = col_a.multiselect(
    "Segmento", segs_disp, format_func=lambda s: SEGMENTOS.get(s, s.title())
)
sel_faixas = col_b.multiselect("Temperatura", _ORDEM_FAIXA)
busca = col_c.text_input("Cliente contém", placeholder="parte do nome do cliente")

filtradas = [
    p
    for p in propostas
    if (not sel_segs or p["segmento"] in sel_segs)
    and (not sel_faixas or p["faixa"] in sel_faixas)
    and (not busca or busca.lower() in p["cliente"].lower())
]

if not filtradas:
    st.warning("Nenhuma proposta atende aos filtros selecionados.")
    st.stop()

# --- KPIs por faixa + Pipeline Inflado -------------------------------------
def _agg(faixa: str) -> tuple[int, float]:
    itens = [p for p in filtradas if p["faixa"] == faixa]
    return len(itens), sum(p["valor"] for p in itens)


inflado = opportunity_rules.pipeline_inflado(filtradas)
cols = st.columns(5)
for col, faixa in zip(cols, _ORDEM_FAIXA):
    qtd, valor = _agg(faixa)
    col.metric(faixa, qtd, help=f"Valor aberto: {format_brl(valor)}")
cols[4].metric(
    "Pipeline inflado", f"{inflado:.1f}%",
    help="Fatia do valor aberto que já está vencida (> 30 dias).",
)

st.divider()

# --- Distribuição térmica + ranking ----------------------------------------
c_donut, c_rank = st.columns(2)
with c_donut:
    st.subheader("Termômetro do pipeline")
    valores = [_agg(f)[1] for f in _ORDEM_FAIXA]
    charts.render(
        charts.donut(
            _ORDEM_FAIXA, valores,
            colors=[opportunity_rules.cor_faixa(f) for f in _ORDEM_FAIXA], money=True,
        )
    )
    st.caption("Valor aberto por temperatura. Vermelho grande = pipeline envelhecendo.")

with c_rank:
    st.subheader("Quem está deixando esfriar?")
    # Ranking por segmento (proxy do vendedor no modelo do sistema), por % vencida.
    por_seg: dict[str, dict[str, float]] = {}
    for p in filtradas:
        d = por_seg.setdefault(p["segmento"], {"abertas": 0, "vencidas": 0})
        d["abertas"] += 1
        if p["faixa"] == "Vencida":
            d["vencidas"] += 1
    segs = sorted(por_seg, key=lambda s: por_seg[s]["vencidas"] / por_seg[s]["abertas"], reverse=True)
    labels = [SEGMENTOS.get(s, s.title()) for s in segs]
    pct = [round(por_seg[s]["vencidas"] / por_seg[s]["abertas"] * 100, 1) for s in segs]
    charts.render(charts.hbar(labels, pct, suffix="%"))
    st.caption("% de propostas vencidas por segmento — maior no topo é onde agir primeiro.")

# --- Tabela de propostas ----------------------------------------------------
st.subheader(f"Propostas em aberto — {len(filtradas)}")
df = pd.DataFrame(
    {
        "Proposta": [p["numero"] for p in filtradas],
        "Cliente": [p["cliente"] for p in filtradas],
        "Segmento": [SEGMENTOS.get(p["segmento"], p["segmento"].title()) for p in filtradas],
        "Situação": [STATUS_PT.get(p["status"], p["status"].title()) for p in filtradas],
        "Temperatura": [p["faixa"] for p in filtradas],
        "Idade (dias)": [p["dias"] if p["dias"] is not None else "—" for p in filtradas],
        "Valor": [format_brl(p["valor"]) for p in filtradas],
    }
)
st.dataframe(df, width="stretch", hide_index=True)
st.caption(
    "Ordenada por prioridade: vencidas primeiro, depois a mais antiga, depois a de maior valor. "
    "Quente ≤ 10 dias · Morna ≤ 20 · Fria ≤ 30 · Vencida > 30."
)
