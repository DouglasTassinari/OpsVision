"""Data access for the Machining (Usinagem) module."""
from __future__ import annotations

from datetime import date

from sqlalchemy import case, func, select

from app.database.models.machining import (
    Appointment,
    Machine,
    OccurrenceCategory,
    OccurrenceType,
    Operator,
)
from app.repositories.base import BaseRepository


class MachineRepository(BaseRepository[Machine]):
    model = Machine

    def active_machines(self) -> list[Machine]:
        stmt = select(Machine).where(Machine.active.is_(True)).order_by(Machine.code)
        return list(self.session.execute(stmt).scalars().all())


class OperatorRepository(BaseRepository[Operator]):
    model = Operator

    def active_operators(self) -> list[Operator]:
        stmt = select(Operator).where(Operator.active.is_(True)).order_by(Operator.name)
        return list(self.session.execute(stmt).scalars().all())


class OccurrenceTypeRepository(BaseRepository[OccurrenceType]):
    model = OccurrenceType


class AppointmentRepository(BaseRepository[Appointment]):
    model = Appointment

    def between(self, start: date, end: date) -> list[Appointment]:
        stmt = (
            select(Appointment)
            .where(Appointment.appointment_date >= start, Appointment.appointment_date <= end)
            .order_by(Appointment.appointment_date, Appointment.start_time)
        )
        return list(self.session.execute(stmt).scalars().all())

    def yield_by_operator(self, start: date, end: date) -> list[tuple[str, float, int]]:
        """(operator_name, yield_pct, total_pieces) for productive appointments.

        O rendimento é a eficiência média do operador ponderada por peças: um
        apontamento de 200 peças pesa o dobro de um de 100. Somar as eficiências
        sem dividir pelo peso total faria o número crescer a cada apontamento e
        estourar o teto — que era o bug que fixava todo operador em 200%.

        Não usa o peso ``quantity / total_production`` do R17 de propósito:
        ``total_production`` é gerado aleatoriamente por linha (não é o total do
        dia), então esse peso não tem significado sobre os dados atuais.
        """
        prod_subq = (
            select(OccurrenceType.id)
            .where(OccurrenceType.category == OccurrenceCategory.PRODUCTIVE)
        ).scalar_subquery()

        # Tetos repetidos como literais (e não importados de domain) porque
        # repositório não depende da camada de domínio — ver ARCHITECTURE.md.
        capped_efficiency = func.min(Appointment.efficiency_pct, 500.0)
        pieces = func.sum(Appointment.quantity)

        stmt = (
            select(
                Operator.name,
                (func.sum(capped_efficiency * Appointment.quantity) / func.nullif(pieces, 0)).label(
                    "weighted_efficiency"
                ),
                pieces.label("pieces"),
            )
            .join(Operator, Operator.id == Appointment.operator_id)
            .where(
                Appointment.appointment_date >= start,
                Appointment.appointment_date <= end,
                Appointment.occurrence_type_id.in_(prod_subq),
            )
            .group_by(Operator.id)
            .order_by(pieces.desc())
        )
        rows = self.session.execute(stmt).all()
        return [
            (name, min(round(float(eff or 0), 1), 200.0), int(qty or 0))
            for name, eff, qty in rows
        ]

    def operator_activity(
        self, start: date, end: date
    ) -> list[tuple[int, str, str, str, int, float, int]]:
        """Per (operator, occurrence type) activity in the period.

        Devolve tuplas ``(operator_id, operator_name, description, category,
        appt_count, total_minutes, total_pieces)`` — o material bruto do painel
        Operadores. A ``category`` (produção/setup/improdutivo) vem do tipo de
        ocorrência; a ``description`` é usada na camada de domínio para separar
        "Sem Peça" (espera de material) do improdutivo e para ler o tempo
        padrão embutido no rótulo do setup ("Setup 1h30" → 90 min).
        """
        stmt = (
            select(
                Operator.id,
                Operator.name,
                OccurrenceType.description,
                OccurrenceType.category,
                func.count(Appointment.id).label("appt_count"),
                func.sum(Appointment.duration_minutes).label("minutes"),
                func.sum(Appointment.quantity).label("pieces"),
            )
            .join(Operator, Operator.id == Appointment.operator_id)
            .join(OccurrenceType, OccurrenceType.id == Appointment.occurrence_type_id)
            .where(
                Appointment.appointment_date >= start,
                Appointment.appointment_date <= end,
            )
            .group_by(Operator.id, OccurrenceType.id)
        )
        rows = self.session.execute(stmt).all()
        return [
            (
                int(oid), name, desc,
                cat.value if hasattr(cat, "value") else str(cat),
                int(cnt or 0), float(mins or 0), int(pcs or 0),
            )
            for oid, name, desc, cat, cnt, mins, pcs in rows
        ]

    def time_by_category(self, start: date, end: date) -> list[tuple[str, float]]:
        """(category_value, total_hours) grouped by occurrence category."""
        stmt = (
            select(
                OccurrenceType.category,
                func.sum(Appointment.duration_minutes / 60.0).label("hours"),
            )
            .join(OccurrenceType, OccurrenceType.id == Appointment.occurrence_type_id)
            .where(
                Appointment.appointment_date >= start,
                Appointment.appointment_date <= end,
            )
            .group_by(OccurrenceType.category)
        )
        rows = self.session.execute(stmt).all()
        return [(cat.value if hasattr(cat, "value") else str(cat), round(float(h or 0), 1)) for cat, h in rows]

    def time_by_occurrence(self, start: date, end: date) -> list[tuple[str, float]]:
        """(occurrence_description, total_hours) for all appointments in range."""
        stmt = (
            select(
                OccurrenceType.description,
                func.sum(Appointment.duration_minutes / 60.0).label("hours"),
            )
            .join(OccurrenceType, OccurrenceType.id == Appointment.occurrence_type_id)
            .where(
                Appointment.appointment_date >= start,
                Appointment.appointment_date <= end,
            )
            .group_by(OccurrenceType.id)
            .order_by(func.sum(Appointment.duration_minutes).desc())
        )
        rows = self.session.execute(stmt).all()
        return [(desc, round(float(h or 0), 1)) for desc, h in rows]

    def production_by_day(self, start: date, end: date) -> list[tuple[str, int]]:
        """(date_str, total_pieces) per day for productive appointments."""
        prod_subq = (
            select(OccurrenceType.id)
            .where(OccurrenceType.category == OccurrenceCategory.PRODUCTIVE)
        ).scalar_subquery()
        stmt = (
            select(
                func.strftime("%Y-%m-%d", Appointment.appointment_date).label("day"),
                func.sum(Appointment.quantity).label("pieces"),
            )
            .where(
                Appointment.appointment_date >= start,
                Appointment.appointment_date <= end,
                Appointment.occurrence_type_id.in_(prod_subq),
            )
            .group_by("day")
            .order_by("day")
        )
        rows = self.session.execute(stmt).all()
        return [(day, int(pieces or 0)) for day, pieces in rows]

    def time_by_machine(self, start: date, end: date) -> list[tuple[str, float, float]]:
        """(machine_name, productive_hours, total_hours) per machine."""
        prod_subq = (
            select(OccurrenceType.id)
            .where(OccurrenceType.category == OccurrenceCategory.PRODUCTIVE)
        ).scalar_subquery()
        stmt = (
            select(
                Machine.name,
                func.sum(
                    case(
                        (Appointment.occurrence_type_id.in_(prod_subq), Appointment.duration_minutes / 60.0),
                        else_=0.0,
                    )
                ).label("prod_hours"),
                func.sum(Appointment.duration_minutes / 60.0).label("total_hours"),
            )
            .join(Machine, Machine.id == Appointment.machine_id)
            .where(
                Appointment.appointment_date >= start,
                Appointment.appointment_date <= end,
            )
            .group_by(Machine.id)
            .order_by(func.sum(Appointment.duration_minutes).desc())
        )
        rows = self.session.execute(stmt).all()
        return [
            (name, round(float(ph or 0), 1), round(float(th or 0), 1))
            for name, ph, th in rows
        ]

    def monthly_yield(self, start: date, end: date) -> list[tuple[str, float]]:
        """(month_str, avg_yield_pct) per month across all operators."""
        prod_subq = (
            select(OccurrenceType.id)
            .where(OccurrenceType.category == OccurrenceCategory.PRODUCTIVE)
        ).scalar_subquery()
        stmt = (
            select(
                func.strftime("%Y-%m", Appointment.appointment_date).label("month"),
                func.avg(
                    case(
                        (Appointment.total_production > 0, func.min(Appointment.efficiency_pct, 500.0)),
                        else_=0.0,
                    )
                ).label("avg_eff"),
            )
            .where(
                Appointment.appointment_date >= start,
                Appointment.appointment_date <= end,
                Appointment.occurrence_type_id.in_(prod_subq),
            )
            .group_by("month")
            .order_by("month")
        )
        rows = self.session.execute(stmt).all()
        return [(m, min(round(float(e or 0), 1), 200.0)) for m, e in rows]
