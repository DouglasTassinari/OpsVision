"""Regras puras do módulo Radar de Oportunidades — sem banco, sem I/O.

Responde à pergunta "minhas propostas em aberto estão sendo acompanhadas, ou
pararam?". Cada proposta ganha uma temperatura pela IDADE dela (dias desde a
criação) para o vendedor não deixar proposta envelhecer sem follow-up.

Nomes próprios (Quente/Morna/Fria/Vencida) de propósito — não reusar
Dentro do prazo/Atenção do Relacionamento: são universos diferentes.
"""
from __future__ import annotations

from datetime import date

# Faixas de idade (dias desde a criação da proposta).
QUENTE_ATE, MORNA_ATE, FRIA_ATE = 10, 20, 30

_CORES: dict[str, str] = {
    "Quente": "#4CAF50",   # 🔥 fresca, acompanhar é fácil
    "Morna": "#F2A900",    # 🟡 começando a esfriar
    "Fria": "#E8833A",     # 🧊 21–30 dias, risco
    "Vencida": "#E5484D",  # 🔴 pior caso: > 30 dias ou sem data
}

# Ordem de prioridade na tela: vencidas no topo.
_ORDEM_FAIXA = {"Vencida": 0, "Fria": 1, "Morna": 2, "Quente": 3}


def dias_desde(criacao: date | None, hoje: date) -> int | None:
    if criacao is None:
        return None
    return (hoje - criacao).days


def faixa_status(dias: int | None) -> str:
    """Temperatura pela idade. Sem data ou > 30 dias → Vencida (pior caso)."""
    if dias is None or dias > FRIA_ATE:
        return "Vencida"
    if dias <= QUENTE_ATE:
        return "Quente"
    if dias <= MORNA_ATE:
        return "Morna"
    return "Fria"


def cor_faixa(faixa: str) -> str:
    return _CORES.get(faixa, _CORES["Vencida"])


def classificar_propostas(propostas: list[dict], hoje: date) -> list[dict]:
    """Enriquece cada proposta com dias/faixa/cor e ordena para a tela.

    Cada item precisa das chaves ``data_criacao`` (date | None) e ``valor``
    (float). Ordenação: vencidas primeiro → proposta mais antiga → maior valor.
    """
    enriquecidas = []
    for p in propostas:
        dias = dias_desde(p.get("data_criacao"), hoje)
        faixa = faixa_status(dias)
        enriquecidas.append({**p, "dias": dias, "faixa": faixa, "cor": _CORES[faixa]})
    enriquecidas.sort(
        key=lambda x: (
            _ORDEM_FAIXA[x["faixa"]],
            -(x["dias"] if x["dias"] is not None else 10**6),
            -x["valor"],
        )
    )
    return enriquecidas


def pipeline_inflado(propostas: list[dict]) -> float:
    """% do valor aberto que já está vencido — o quanto o pipeline está 'inflado'."""
    total = sum(p["valor"] for p in propostas)
    vencido = sum(p["valor"] for p in propostas if p["faixa"] == "Vencida")
    return round(vencido / total * 100, 1) if total else 0.0
