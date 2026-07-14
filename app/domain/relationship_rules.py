"""Regras puras do módulo Relacionamento com Cliente — sem banco, sem I/O.

Responde à pergunta "minha carteira está sendo acompanhada dentro da cadência
esperada?". Para cada cliente medimos há quantos dias ninguém encosta nele
(última interação) e comparamos com um SLA de dias que varia conforme o porte
econômico do cliente. Quem passou do prazo cai numa fila de ação.

Mantido separado de :mod:`app.services.relationship_service` para poder ser
testado com objetos Python puros, sem sessão de banco.
"""
from __future__ import annotations

from bisect import bisect_left
from datetime import date

# SLA (dias sem interação tolerados) por classe econômica. Cliente maior,
# cadência mais apertada — perder o contato com ele custa mais caro.
SLA_POR_CLASSE: dict[str, int] = {"A+": 90, "A": 90, "B": 180, "C": 365}

# Semáforo BI (mesmas cores dos gráficos): verde/amarelo/vermelho.
_VERDE = "#4CAF50"
_AMARELO = "#F2A900"
_VERMELHO = "#E5484D"


def dias_desde(ultima: date | None, hoje: date) -> int | None:
    """Dias entre a última interação e hoje. Sem interação → ``None``."""
    if ultima is None:
        return None
    return (hoje - ultima).days


def classe_economica(faturamento_36m: float, faturamentos_ordenados: list[float]) -> str:
    """Classe por percentil do faturamento de 36 meses (busca binária).

    A+ = top 10% · A = 20% seguintes · B = 30% seguintes · C = resto.
    Cliente sem faturamento no período (ou vetor vazio) cai em C.
    ``faturamentos_ordenados`` é o vetor ASC só dos clientes com faturamento > 0.
    """
    if faturamento_36m <= 0 or not faturamentos_ordenados:
        return "C"
    n = len(faturamentos_ordenados)
    fracao_abaixo = bisect_left(faturamentos_ordenados, faturamento_36m) / n
    if fracao_abaixo >= 0.90:
        return "A+"
    if fracao_abaixo >= 0.70:
        return "A"
    if fracao_abaixo >= 0.40:
        return "B"
    return "C"


def status_sla(classe: str, dias: int | None) -> tuple[str, str]:
    """Semáforo de cadência: (rótulo, cor hex). Sem interação → Vencido.

    O limiar de "Atenção" é 2/3 do SLA — o último terço antes de estourar.
    """
    if dias is None:
        return "Vencido", _VERMELHO
    sla = SLA_POR_CLASSE.get(classe, 365)
    limite_atencao = round(sla * 2 / 3)
    if dias <= limite_atencao:
        return "Dentro do prazo", _VERDE
    if dias <= sla:
        return "Atenção", _AMARELO
    return "Vencido", _VERMELHO


def indice_saude(status: list[str]) -> float:
    """Saúde da carteira 0–100 = (Dentro×100 + Atenção×50) ÷ total."""
    if not status:
        return 0.0
    pontos = sum(
        100 if s == "Dentro do prazo" else 50 if s == "Atenção" else 0 for s in status
    )
    return round(pontos / len(status), 1)


def classificar_carteira(clientes: list[dict], hoje: date) -> list[dict]:
    """Enriquece cada cliente com dias/classe/status/cor.

    Cada item de ``clientes`` precisa das chaves ``faturamento_36m`` (float) e
    ``ultima_interacao`` (date | None). O percentil da classe é calculado sobre
    o vetor de faturamentos > 0 de toda a carteira, então a função é o ponto
    único onde a regra vive — dá para testá-la sem banco.
    """
    faturamentos = sorted(c["faturamento_36m"] for c in clientes if c["faturamento_36m"] > 0)
    resultado = []
    for c in clientes:
        dias = dias_desde(c.get("ultima_interacao"), hoje)
        classe = classe_economica(c["faturamento_36m"], faturamentos)
        status, cor = status_sla(classe, dias)
        resultado.append({**c, "dias": dias, "classe": classe, "status": status, "cor": cor})
    return resultado
