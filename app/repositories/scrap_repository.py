"""Data access for the Scrap (Refugo) module."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

from app.database.models.machining import Machine, Operator
from app.database.models.scrap import ScrapPart, ScrapRecord
from app.repositories.base import BaseRepository


class ScrapPartRepository(BaseRepository[ScrapPart]):
    model = ScrapPart


class ScrapRecordRepository(BaseRepository[ScrapRecord]):
    model = ScrapRecord

    def active_between(self, start: date, end: date) -> list[ScrapRecord]:
        stmt = (
            select(ScrapRecord)
            .where(
                ScrapRecord.record_date >= start,
                ScrapRecord.record_date <= end,
                ScrapRecord.active.is_(True),
            )
            .order_by(ScrapRecord.record_date.desc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def total_by_period(self, start: date, end: date) -> int:
        stmt = (
            select(func.coalesce(func.sum(ScrapRecord.total_quantity), 0))
            .where(
                ScrapRecord.record_date >= start,
                ScrapRecord.record_date <= end,
                ScrapRecord.active.is_(True),
            )
        )
        return int(self.session.execute(stmt).scalar_one())

    def by_reason(self, start: date, end: date) -> list[tuple[str, int]]:
        """(reason, total_qty) — only reason_1 for simplicity."""
        stmt = (
            select(
                ScrapRecord.reason_1,
                func.sum(ScrapRecord.total_quantity).label("qty"),
            )
            .where(
                ScrapRecord.record_date >= start,
                ScrapRecord.record_date <= end,
                ScrapRecord.active.is_(True),
            )
            .group_by(ScrapRecord.reason_1)
            .order_by(func.sum(ScrapRecord.total_quantity).desc())
        )
        return [(r, int(q or 0)) for r, q in self.session.execute(stmt).all()]

    def by_machine(self, start: date, end: date) -> list[tuple[str, int]]:
        stmt = (
            select(
                Machine.name,
                func.sum(ScrapRecord.total_quantity).label("qty"),
            )
            .join(Machine, Machine.id == ScrapRecord.machine_id)
            .where(
                ScrapRecord.record_date >= start,
                ScrapRecord.record_date <= end,
                ScrapRecord.active.is_(True),
            )
            .group_by(Machine.id)
            .order_by(func.sum(ScrapRecord.total_quantity).desc())
        )
        return [(name, int(q or 0)) for name, q in self.session.execute(stmt).all()]

    def by_operator(self, start: date, end: date) -> list[tuple[str, int]]:
        stmt = (
            select(
                Operator.name,
                func.sum(ScrapRecord.total_quantity).label("qty"),
            )
            .join(Operator, Operator.id == ScrapRecord.operator_id)
            .where(
                ScrapRecord.record_date >= start,
                ScrapRecord.record_date <= end,
                ScrapRecord.active.is_(True),
            )
            .group_by(Operator.id)
            .order_by(func.sum(ScrapRecord.total_quantity).desc())
        )
        return [(name, int(q or 0)) for name, q in self.session.execute(stmt).all()]

    def usinagem_by_operator(self, start: date, end: date) -> list[tuple[str, int]]:
        """(operator_name, qty) só de refugo por **erro de usinagem**.

        O painel Operadores responsabiliza o operador apenas pelo refugo cuja
        causa raiz é a própria usinagem (``Dimensional Errado Usinagem``);
        defeito de fundição/fornecedor não entra na conta dele.
        """
        stmt = (
            select(
                Operator.name,
                func.sum(ScrapRecord.total_quantity).label("qty"),
            )
            .join(Operator, Operator.id == ScrapRecord.operator_id)
            .where(
                ScrapRecord.record_date >= start,
                ScrapRecord.record_date <= end,
                ScrapRecord.active.is_(True),
                ScrapRecord.reason_1 == "Dimensional Errado Usinagem",
            )
            .group_by(Operator.id)
        )
        return [(name, int(q or 0)) for name, q in self.session.execute(stmt).all()]

    def by_supplier(self, start: date, end: date) -> list[tuple[str, int]]:
        stmt = (
            select(
                ScrapRecord.supplier,
                func.sum(ScrapRecord.total_quantity).label("qty"),
            )
            .where(
                ScrapRecord.record_date >= start,
                ScrapRecord.record_date <= end,
                ScrapRecord.active.is_(True),
                ScrapRecord.supplier.isnot(None),
            )
            .group_by(ScrapRecord.supplier)
            .order_by(func.sum(ScrapRecord.total_quantity).desc())
        )
        return [(s, int(q or 0)) for s, q in self.session.execute(stmt).all()]

    def monthly_totals(self, start: date, end: date) -> list[tuple[str, int]]:
        stmt = (
            select(
                func.strftime("%Y-%m", ScrapRecord.record_date).label("month"),
                func.sum(ScrapRecord.total_quantity).label("qty"),
            )
            .where(
                ScrapRecord.record_date >= start,
                ScrapRecord.record_date <= end,
                ScrapRecord.active.is_(True),
            )
            .group_by("month")
            .order_by("month")
        )
        return [(m, int(q or 0)) for m, q in self.session.execute(stmt).all()]

    def by_origin(self, start: date, end: date) -> list[tuple[str, int]]:
        """Classify records by origin (R34): usinagem, fornecedor, indefinido."""
        records = self.active_between(start, end)
        totals: dict[str, int] = {}
        for rec in records:
            origin = rec.origin
            totals[origin] = totals.get(origin, 0) + rec.total_quantity
        return sorted(totals.items(), key=lambda x: x[1], reverse=True)
