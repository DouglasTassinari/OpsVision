"""Data access for the Compensation module — reads the base tables only.

The module never writes: edits live in the session working-set. These queries
load the synthetic base that a page load / F5 restores.
"""
from __future__ import annotations

from sqlalchemy import select

from app.database.models.compensation import (
    Placement,
    Position,
    PositionLevel,
    SeniorityBand,
    UnionFloor,
)
from app.database.models.people import Employee, EmploymentStatus
from app.repositories.base import BaseRepository


class PositionRepository(BaseRepository[Position]):
    model = Position

    def active(self) -> list[Position]:
        stmt = select(Position).where(Position.status == "active").order_by(Position.area, Position.name)
        return list(self.session.execute(stmt).scalars().all())


class PositionLevelRepository(BaseRepository[PositionLevel]):
    model = PositionLevel

    def active(self) -> list[PositionLevel]:
        stmt = (
            select(PositionLevel)
            .where(PositionLevel.status == "active")
            .order_by(PositionLevel.position_id, PositionLevel.display_order)
        )
        return list(self.session.execute(stmt).scalars().all())


class SeniorityBandRepository(BaseRepository[SeniorityBand]):
    model = SeniorityBand

    def general_bands(self) -> list[SeniorityBand]:
        """Faixas de tempo de casa da regra geral (position_id NULL), por tempo mínimo."""
        stmt = (
            select(SeniorityBand)
            .where(SeniorityBand.position_id.is_(None), SeniorityBand.status == "active")
            .order_by(SeniorityBand.min_months)
        )
        return list(self.session.execute(stmt).scalars().all())


class UnionFloorRepository(BaseRepository[UnionFloor]):
    model = UnionFloor

    def all_floors(self) -> list[UnionFloor]:
        stmt = select(UnionFloor).order_by(UnionFloor.year)
        return list(self.session.execute(stmt).scalars().all())


class PlacementRepository(BaseRepository[Placement]):
    model = Placement

    def with_active_employees(self) -> list[tuple[Placement, Employee]]:
        """Enquadramentos de colaboradores ativos, com o funcionário carregado."""
        stmt = (
            select(Placement, Employee)
            .join(Employee, Employee.id == Placement.employee_id)
            .where(Employee.employment_status == EmploymentStatus.ACTIVE)
            .order_by(Employee.full_name)
        )
        return [(placement, employee) for placement, employee in self.session.execute(stmt).all()]
