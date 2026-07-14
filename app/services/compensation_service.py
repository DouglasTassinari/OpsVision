"""Compensation service — loads the base snapshot the session working-set copies.

Reads the base tables, joins each active employee's placement, and decomposes the
salary (base + avaliação + tempo de casa) using the pure rules. Returns plain
dataclasses so the UI adapter can cache them in ``st.session_state`` and mutate a
copy per session without touching the database.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.metrics import track
from app.domain import compensation_rules as rules
from app.repositories.compensation_repository import (
    PlacementRepository,
    PositionLevelRepository,
    PositionRepository,
    SeniorityBandRepository,
    UnionFloorRepository,
)

logger = get_logger("services.compensation")


def _dec(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass
class LevelDTO:
    id: int
    position_id: int
    name: str
    description: str | None
    base_salary: Decimal | None
    display_order: int


@dataclass
class PositionDTO:
    id: int
    name: str
    area: str
    code: str | None
    has_leadership: bool
    has_levels: bool
    levels: list[LevelDTO] = field(default_factory=list)


@dataclass
class EmployeeCompDTO:
    employee_id: int
    name: str
    area: str
    position_id: int
    position: str
    level_id: int | None
    level: str | None
    hire_date: date
    current_salary: Decimal
    base: Decimal | None
    evaluation: Decimal
    seniority: Decimal
    final: Decimal | None
    is_leader: bool
    leadership_bonus: Decimal


@dataclass
class CompensationSnapshot:
    reference: date
    floors: dict[int, Decimal]
    bands: list[tuple[int, Decimal]]  # (anos, percent)
    positions: list[PositionDTO]
    employees: list[EmployeeCompDTO]


class CompensationService:
    def __init__(self, session: Session):
        self.session = session
        self.positions = PositionRepository(session)
        self.levels = PositionLevelRepository(session)
        self.bands = SeniorityBandRepository(session)
        self.floors = UnionFloorRepository(session)
        self.placements = PlacementRepository(session)

    @track("compensation.load_snapshot")
    def load_snapshot(self, reference: date | None = None) -> CompensationSnapshot:
        reference = reference or date.today()

        floors = {row.year: _dec(row.value) for row in self.floors.all_floors()}
        bands = [(band.min_months // 12, _dec(band.percent)) for band in self.bands.general_bands()]
        bands_tuple = tuple(bands) if bands else rules.DEFAULT_BANDS

        levels_by_position: dict[int, list[LevelDTO]] = {}
        level_lookup: dict[int, LevelDTO] = {}
        for level in self.levels.active():
            dto = LevelDTO(
                id=level.id,
                position_id=level.position_id,
                name=level.name,
                description=level.description,
                base_salary=_dec(level.base_salary) if level.base_salary is not None else None,
                display_order=level.display_order,
            )
            levels_by_position.setdefault(level.position_id, []).append(dto)
            level_lookup[level.id] = dto

        positions: list[PositionDTO] = []
        position_lookup: dict[int, PositionDTO] = {}
        for position in self.positions.active():
            dto = PositionDTO(
                id=position.id,
                name=position.name,
                area=position.area,
                code=position.code,
                has_leadership=position.has_leadership,
                has_levels=position.has_levels,
                levels=levels_by_position.get(position.id, []),
            )
            positions.append(dto)
            position_lookup[position.id] = dto

        employees: list[EmployeeCompDTO] = []
        for placement, employee in self.placements.with_active_employees():
            position = position_lookup.get(placement.position_id)
            level = level_lookup.get(placement.level_id) if placement.level_id else None
            base = level.base_salary if level else None
            seniority = rules.seniority_addon(employee.hire_date, reference, floors, bands_tuple)
            evaluation = _dec(placement.evaluation_addon)
            final = rules.compose_salary(base, evaluation, seniority) if base is not None else None
            is_leader = bool(position and position.has_leadership)
            bonus = (
                rules.leadership_bonus(base) if (is_leader and base is not None) else Decimal("0.00")
            )
            employees.append(
                EmployeeCompDTO(
                    employee_id=employee.id,
                    name=employee.full_name,
                    area=position.area if position else "—",
                    position_id=placement.position_id,
                    position=position.name if position else "—",
                    level_id=placement.level_id,
                    level=level.name if level else None,
                    hire_date=employee.hire_date,
                    current_salary=_dec(employee.base_salary),
                    base=base,
                    evaluation=evaluation,
                    seniority=seniority,
                    final=final,
                    is_leader=is_leader,
                    leadership_bonus=bonus,
                )
            )

        logger.info(
            "compensation snapshot loaded: %d positions, %d employees",
            len(positions),
            len(employees),
        )
        return CompensationSnapshot(
            reference=reference,
            floors=floors,
            bands=list(bands_tuple),
            positions=positions,
            employees=employees,
        )
