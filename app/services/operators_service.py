"""Operadores panel service — a 360º per-operator view of the machining floor.

Cruza quatro fontes por operador — apontamentos de produção (peças,
rendimento, tempo por categoria), produtividade de setup, refugo por erro de
usinagem e saldo de tempo dos ajustes — e devolve uma linha por operador
pronta para a tabela densa e colorida do painel. Todos os números derivados
saem de :mod:`app.domain.operators_rules` (que por sua vez reaproveita as
fórmulas industriais de :mod:`app.domain.machining_rules`); o serviço só
orquestra repositórios e monta as linhas.

O **roster é fixo**: todo operador ativo aparece na tabela mesmo sem
apontamento no período (semeado zerado), para que ninguém "suma" do painel
por não ter produzido — igual ao BI industrial de origem.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.metrics import track
from app.domain import operators_rules
from app.domain.operators_rules import OperatorActivity
from app.repositories.adjustments_repository import TimeAdjustmentRepository
from app.repositories.machining_repository import AppointmentRepository, OperatorRepository
from app.repositories.scrap_repository import ScrapRecordRepository

logger = get_logger("services.operators")


@dataclass(frozen=True)
class OperatorPanelRow:
    """Uma linha do painel: um operador e todos os seus indicadores."""

    operator_id: int
    name: str
    shift: int
    pieces: int
    production_yield: float | None      # % rendimento produção (None se não produziu)
    setup_productivity: float | None    # % produtividade de setup (None se não fez setup)
    no_part_hours: float                # horas parado esperando peça
    idle_hours: float                   # horas improdutivas (proxy de ociosidade)
    idle_index: float                   # % improdutividade (proxy meritocracia)
    passes_meritocracy: bool            # recebe bonificação?
    scrap_usinagem: int                 # peças refugadas por erro de usinagem
    adjustments_balance_hours: float    # saldo de tempo dos ajustes (+ economizou / − perdeu)
    reported_hours: float               # total de horas apontadas


@dataclass(frozen=True)
class OperatorsPanelSummary:
    """Cartões-resumo da equipe no período."""

    operator_count: int
    total_pieces: int
    avg_production_yield: float
    avg_setup_productivity: float
    avg_idle_index: float
    production_hours: float
    setup_hours: float
    no_part_hours: float
    unproductive_hours: float


class OperatorsService:
    def __init__(self, session: Session):
        self.session = session
        self.operators = OperatorRepository(session)
        self.appointments = AppointmentRepository(session)
        self.scrap = ScrapRecordRepository(session)
        self.adjustments = TimeAdjustmentRepository(session)

    def _activity_by_operator(self, start: date, end: date) -> dict[int, OperatorActivity]:
        raw: dict[int, list[tuple[str, str, int, float, int]]] = {}
        for oid, _name, desc, cat, count, minutes, pieces in self.appointments.operator_activity(start, end):
            raw.setdefault(oid, []).append((desc, cat, count, minutes, pieces))
        return {oid: operators_rules.aggregate_activity(rows) for oid, rows in raw.items()}

    @track("operators.panel")
    def panel(self, start: date, end: date) -> list[OperatorPanelRow]:
        activity = self._activity_by_operator(start, end)
        yields = {name: pct for name, pct, _ in self.appointments.yield_by_operator(start, end)}
        scrap = dict(self.scrap.usinagem_by_operator(start, end))
        adj_balance = {
            name: round(total_diff_seconds / 3600.0, 2)
            for name, _imp, _wor, total_diff_seconds in self.adjustments.summary_by_operator(start, end)
        }

        rows: list[OperatorPanelRow] = []
        for op in self.operators.active_operators():
            act = activity.get(op.id)
            if act is None:
                act = operators_rules.aggregate_activity([])  # roster fixo: semeia zerado
            idle_index = operators_rules.idle_index(act) if act.reported_hours > 0 else 0.0
            rows.append(
                OperatorPanelRow(
                    operator_id=op.id,
                    name=op.name,
                    shift=op.shift,
                    pieces=act.pieces,
                    production_yield=yields.get(op.name) if act.production_hours > 0 else None,
                    setup_productivity=operators_rules.setup_productivity(act),
                    no_part_hours=act.no_part_hours,
                    idle_hours=act.unproductive_hours,
                    idle_index=idle_index,
                    passes_meritocracy=operators_rules.passes_meritocracy(idle_index),
                    scrap_usinagem=scrap.get(op.name, 0),
                    adjustments_balance_hours=adj_balance.get(op.name, 0.0),
                    reported_hours=act.reported_hours,
                )
            )
        rows.sort(key=lambda r: r.pieces, reverse=True)
        logger.info("Operadores panel built: %d operators, %s..%s", len(rows), start, end)
        return rows

    @track("operators.summary")
    def summary(self, start: date, end: date) -> OperatorsPanelSummary:
        rows = self.panel(start, end)
        activity = self._activity_by_operator(start, end)

        prod_yields = [r.production_yield for r in rows if r.production_yield is not None]
        idle_indexes = [r.idle_index for r in rows if r.reported_hours > 0]

        # Produtividade de setup da equipe: pooled (soma dos padrões ÷ soma dos realizados),
        # não a média das médias — igual ao cartão-resumo do BI industrial.
        std = sum(a.setup_standard_min for a in activity.values())
        actual = sum(a.setup_actual_min for a in activity.values())
        team_setup = operators_rules.machining_rules.setup_productivity(std, actual) if actual > 0 else 0.0

        return OperatorsPanelSummary(
            operator_count=len(rows),
            total_pieces=sum(r.pieces for r in rows),
            avg_production_yield=round(sum(prod_yields) / len(prod_yields), 1) if prod_yields else 0.0,
            avg_setup_productivity=team_setup,
            avg_idle_index=round(sum(idle_indexes) / len(idle_indexes), 2) if idle_indexes else 0.0,
            production_hours=round(sum(a.production_hours for a in activity.values()), 1),
            setup_hours=round(sum(a.setup_hours for a in activity.values()), 1),
            no_part_hours=round(sum(a.no_part_hours for a in activity.values()), 1),
            unproductive_hours=round(sum(a.unproductive_hours for a in activity.values()), 1),
        )
