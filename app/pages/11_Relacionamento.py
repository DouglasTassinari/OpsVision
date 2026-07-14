"""Relacionamento com Cliente — SLA de cadência da carteira."""
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
from app.domain import relationship_rules
from app.services.relationship_service import RelationshipService

apply_branding("Relacionamento")

ensure_demo_data_once()

SEGMENTOS = {"retail": "Varejo", "wholesale": "Atacado", "enterprise": "Corporativo"}
_ORDEM_STATUS = ["Dentro do prazo", "Atenção", "Vencido"]
_COR_STATUS = {"Dentro do prazo": charts.POSITIVO, "Atenção": charts.ATENCAO, "Vencido": charts.NEGATIVO}

st.title("Relacionamento com Cliente")
st.caption(
    "Há quantos dias ninguém encosta em cada cliente — comparado ao prazo (SLA) "
    "que o porte dele exige. Quem estourou o prazo vira fila de ação."
)

hoje = date.today()
with session_scope() as session:
    carteira = RelationshipService(session).portfolio(hoje)

if not carteira:
    st.info("Ainda não há clientes com histórico de pedidos.")
    st.stop()

# --- Filtros (em memória) --------------------------------------------------
col_f1, col_f2 = st.columns([2, 3])
segs_disp = sorted({c["segmento"] for c in carteira})
sel_segs = col_f1.multiselect(
    "Segmento", segs_disp, format_func=lambda s: SEGMENTOS.get(s, s.title())
)
busca = col_f2.text_input("Cliente contém", placeholder="parte do nome do cliente")

filtrada = [
    c
    for c in carteira
    if (not sel_segs or c["segmento"] in sel_segs)
    and (not busca or busca.lower() in c["cliente"].lower())
]

if not filtrada:
    st.warning("Nenhum cliente atende aos filtros selecionados.")
    st.stop()

# --- KPIs -------------------------------------------------------------------
status_list = [c["status"] for c in filtrada]
saude = relationship_rules.indice_saude(status_list)
contagem = {s: status_list.count(s) for s in _ORDEM_STATUS}
vencidos = contagem["Vencido"]

k1, k2, k3, k4 = st.columns(4)
k1.metric("Clientes na carteira", len(filtrada))
k2.metric("Dentro do prazo", contagem["Dentro do prazo"])
k3.metric("Em atenção", contagem["Atenção"])
k4.metric("Vencidos", vencidos, help="Passaram do SLA de dias sem interação.")

st.divider()

# --- Saúde + distribuição ---------------------------------------------------
c_gauge, c_donut = st.columns(2)
with c_gauge:
    st.subheader("Saúde da carteira")
    charts.render(charts.gauge(saude, 100, target=80, suffix=""))
    st.caption(
        "0–100: cada cliente dentro do prazo vale 100, em atenção 50, vencido 0. "
        "A marca branca é a meta de 80."
    )
with c_donut:
    st.subheader("Como está a cadência?")
    valores = [contagem[s] for s in _ORDEM_STATUS]
    charts.render(
        charts.donut(_ORDEM_STATUS, valores, colors=[_COR_STATUS[s] for s in _ORDEM_STATUS])
    )
    st.caption("Quanto mais verde, mais da carteira está sendo acompanhada no prazo.")

# --- Cobertura por segmento (proxy do vendedor no modelo do sistema) ---------
st.subheader("Onde mora o risco?")
por_seg: dict[str, dict[str, int]] = {}
for c in filtrada:
    d = por_seg.setdefault(c["segmento"], {s: 0 for s in _ORDEM_STATUS})
    d[c["status"]] += 1
segs = sorted(por_seg, key=lambda s: por_seg[s]["Vencido"], reverse=True)
labels = [SEGMENTOS.get(s, s.title()) for s in segs]
charts.render(
    charts.stacked_hbar(
        labels,
        {
            "Dentro do prazo": ([por_seg[s]["Dentro do prazo"] for s in segs], charts.POSITIVO),
            "Atenção": ([por_seg[s]["Atenção"] for s in segs], charts.ATENCAO),
            "Vencido": ([por_seg[s]["Vencido"] for s in segs], charts.NEGATIVO),
        },
    )
)
st.caption("Distribuição do status de cadência por segmento de cliente.")

# --- Fila de ação -----------------------------------------------------------
st.subheader(f"Fila de ação — {vencidos} cliente(s) fora do prazo")
fora = [c for c in filtrada if c["status"] == "Vencido"]
if not fora:
    st.success("Nenhum cliente fora do prazo nos filtros atuais. Carteira em dia! 🎉")
else:
    fora.sort(key=lambda c: (c["dias"] is not None, c["dias"] or 0), reverse=True)
    df = pd.DataFrame(
        {
            "Cliente": [c["cliente"] for c in fora],
            "Segmento": [SEGMENTOS.get(c["segmento"], c["segmento"].title()) for c in fora],
            "Classe": [c["classe"] for c in fora],
            "Dias sem interação": [c["dias"] if c["dias"] is not None else "—" for c in fora],
            "SLA (dias)": [relationship_rules.SLA_POR_CLASSE[c["classe"]] for c in fora],
            "Faturamento 36m": [format_brl(c["faturamento_36m"]) for c in fora],
        }
    )
    st.dataframe(df, width="stretch", hide_index=True)
    st.caption(
        "Ordenada do mais esquecido para o menos. Classe A/A+ tem SLA de 90 dias; "
        "B, 180; C, 365 — cliente maior exige cadência mais apertada."
    )
