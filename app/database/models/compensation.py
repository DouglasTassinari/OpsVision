"""Compensation (Cargos e Salários) module schema — the read-only BASE tables.

This module is the source of the salary policy: positions, levels, seniority
(tempo de casa) bands, the union floor per year and each employee's placement
(enquadramento). Unlike the rest of the platform, user edits here **never** hit
the database: writes live in ``st.session_state`` per browser session (see
:mod:`app.core.comp_workset`), so a page reload (F5) restores this base and no
visitor's simulation dirties the shared data.

The salary is **decomposed** at read time rather than stored as one number:
``salário = base do nível + adicional de avaliação + ajuste por tempo de casa``.
Only the evaluation add-on is stored on the placement; the base comes from the
level and the seniority parcel from the rule in
:mod:`app.domain.compensation_rules`.

The roster is the existing :class:`app.database.models.people.Employee`
(``hire_date`` = admissão, ``base_salary`` = salário atual, ``job_title`` =
função). Placements reference employees by id.
"""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.core import TimestampMixin


class Position(TimestampMixin, Base):
    """Cargo — a job title within an area, optionally split into levels."""

    __tablename__ = "comp_positions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    area: Mapped[str] = mapped_column(String(120))
    code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    has_leadership: Mapped[bool] = mapped_column(Boolean, default=False)
    has_levels: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(10), default="active")


class PositionLevel(TimestampMixin, Base):
    """Nível — a step inside a position, carrying the official base salary."""

    __tablename__ = "comp_position_levels"

    id: Mapped[int] = mapped_column(primary_key=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("comp_positions.id"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # NULL = "a definir" (nível sem ocupante para calcular a média).
    base_salary: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(10), default="active")


class SeniorityBand(TimestampMixin, Base):
    """Faixa de reajuste por tempo de casa. ``position_id`` NULL = regra geral."""

    __tablename__ = "comp_seniority_bands"

    id: Mapped[int] = mapped_column(primary_key=True)
    position_id: Mapped[int | None] = mapped_column(
        ForeignKey("comp_positions.id"), nullable=True, index=True
    )
    min_months: Mapped[int] = mapped_column(Integer)  # anos * 12
    percent: Mapped[float] = mapped_column(Numeric(5, 2))  # % sobre o piso vigente
    note: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="active")


class UnionFloor(Base):
    """Piso do sindicato por ano. Base do tempo de casa e do dissídio (corte 01/05)."""

    __tablename__ = "comp_union_floor"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[float] = mapped_column(Numeric(10, 2))
    note: Mapped[str | None] = mapped_column(String(120), nullable=True)


class Placement(TimestampMixin, Base):
    """Enquadramento — vínculo do colaborador ao cargo/nível + parcela de avaliação.

    A decomposição completa (base + avaliação + tempo de casa) é derivada na
    leitura; aqui guardamos só o vínculo e o adicional de avaliação.
    """

    __tablename__ = "comp_placements"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("people_employees.id"), index=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("comp_positions.id"), index=True)
    level_id: Mapped[int | None] = mapped_column(
        ForeignKey("comp_position_levels.id"), nullable=True
    )
    evaluation_addon: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
