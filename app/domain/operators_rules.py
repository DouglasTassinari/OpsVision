"""Pure business rules for the Operadores panel — no database, no I/O.

O painel Operadores é uma visão 360º por pessoa da usinagem: quanto cada
operador produziu, com que rendimento, quanto tempo economizou em ajustes e
quanto refugou por erro de usinagem. Este módulo transforma o material bruto
de apontamentos (uma linha por tipo de ocorrência) nos números derivados de
cada operador, reaproveitando as fórmulas industriais já centralizadas em
:mod:`app.domain.machining_rules` (rendimento, produtividade de setup,
índice de meritocracia).

Adaptação a esta base sintética: não há ponto eletrônico (batidas), então o
"tempo ocioso" e o "índice de meritocracia" do BI industrial — que medem
presença sem apontamento — são aproximados aqui pelo **tempo improdutivo
apontado** (paradas que não são espera de material). A estrutura e os cortes
(meta 85%, fator setup 0,85, limite 7%) permanecem os do original.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from app.domain import machining_rules

# Faixas de cor das colunas de rendimento (verde ≥ good, amarelo ≥ warn, senão vermelho).
SETUP_BAND_GOOD = 85.0
SETUP_BAND_WARN = 70.0

# Rótulos de ocorrência que são espera de material (comparados sem acento/caixa).
_NO_PART_MARKERS = ("sem peca", "esperando peca")


def _normalize(text: str) -> str:
    """Minúsculas sem acento — para casar rótulos escritos com/sem diacrítico."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip().lower()


def _is_no_part(description: str) -> bool:
    norm = _normalize(description)
    return any(marker in norm for marker in _NO_PART_MARKERS)


@dataclass(frozen=True)
class OperatorActivity:
    """Tempo e produção de um operador, já separados nas categorias do painel."""

    pieces: int
    production_hours: float
    setup_hours: float
    no_part_hours: float          # espera de material — não é culpa do operador
    unproductive_hours: float     # paradas reais (limpeza, reunião, etc.) — proxy de ociosidade
    setup_standard_min: float     # soma dos padrões nominais dos setups reconhecidos
    setup_actual_min: float       # tempo real gasto nesses mesmos setups

    @property
    def reported_hours(self) -> float:
        """Total de horas apontadas — a base do índice de improdutividade."""
        return round(
            self.production_hours + self.setup_hours
            + self.no_part_hours + self.unproductive_hours,
            2,
        )


def aggregate_activity(
    rows: list[tuple[str, str, int, float, int]],
) -> OperatorActivity:
    """Consolida ``(descrição, categoria, qtd_apontamentos, minutos, peças)`` de UM operador.

    A categoria produtivo/setup/improdutivo vem do tipo de ocorrência do banco;
    a descrição só separa "Sem Peça" (espera de material, gravada como
    improdutivo mas que não é ociosidade do operador) e fornece o tempo padrão
    do setup, lido do rótulo ("Setup 1h30" → 90 min) porque o ERP manda tempo
    padrão 0 para setup — mesma convenção do BI industrial.
    """
    pieces = 0
    production_hours = setup_hours = no_part_hours = unproductive_hours = 0.0
    setup_standard_min = setup_actual_min = 0.0

    for description, category, appt_count, minutes, row_pieces in rows:
        hours = minutes / 60.0
        if category == "productive":
            production_hours += hours
            pieces += row_pieces
        elif category == "semi_productive":
            setup_hours += hours
            standard = machining_rules.setup_standard_minutes(description)
            if standard is not None:
                setup_standard_min += standard * appt_count
                setup_actual_min += minutes
        elif _is_no_part(description):
            no_part_hours += hours
        else:
            unproductive_hours += hours

    return OperatorActivity(
        pieces=pieces,
        production_hours=round(production_hours, 2),
        setup_hours=round(setup_hours, 2),
        no_part_hours=round(no_part_hours, 2),
        unproductive_hours=round(unproductive_hours, 2),
        setup_standard_min=round(setup_standard_min, 2),
        setup_actual_min=round(setup_actual_min, 2),
    )


def setup_productivity(activity: OperatorActivity) -> float | None:
    """Produtividade de setup do operador (%), ou ``None`` se não fez setup reconhecido."""
    if activity.setup_actual_min <= 0:
        return None
    return machining_rules.setup_productivity(
        activity.setup_standard_min, activity.setup_actual_min
    )


def idle_index(activity: OperatorActivity) -> float:
    """Índice de improdutividade (%) — proxy do índice de meritocracia (R38).

    ``improdutivo / horas_apontadas × 100``. Sem ponto eletrônico não há falta
    para somar ao numerador nem jornada esperada no denominador, então a base é
    o tempo apontado e o numerador é só o tempo improdutivo real (excluindo
    espera de material).
    """
    return machining_rules.meritocracy_index(
        idle_hours=activity.unproductive_hours,
        unjustified_absence_hours=0.0,
        expected_hours=activity.reported_hours,
    )


def passes_meritocracy(index: float) -> bool:
    """Recebe bonificação se o índice de improdutividade está dentro do limite (≤ 7%)."""
    return machining_rules.passes_meritocracy(index)


def performance_band(pct: float, good: float, warn: float) -> str:
    """Classifica um percentual em ``good`` / ``warn`` / ``bad`` para colorir a célula."""
    if pct >= good:
        return "good"
    if pct >= warn:
        return "warn"
    return "bad"
