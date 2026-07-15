"""Tests for the Operadores panel service layer."""
from datetime import date, datetime, time

import pytest

from app.database.models.machining import Machine, OccurrenceCategory, OccurrenceType, Operator
from app.database.models.people import Department, Employee, EmploymentStatus
from app.database.models.production import ProductionLine
from app.services.adjustments_service import AdjustmentsService
from app.services.machining_service import MachiningService
from app.services.operators_service import OperatorsService
from app.services.scrap_service import ScrapService

START = date(2026, 1, 1)
END = date(2026, 1, 31)
DAY = date(2026, 1, 10)


@pytest.fixture()
def department(session):
    dept = Department(code="MFG", name="Manufatura", cost_center="CC-200")
    session.add(dept)
    session.flush()
    return dept


@pytest.fixture()
def employee(session, location, department):
    emp = Employee(
        employee_code="EMP-1", full_name="Fulano", department_id=department.id,
        location_id=location.id, job_title="Operador CNC", hire_date=date(2020, 1, 1),
        employment_status=EmploymentStatus.ACTIVE, base_salary=3500,
    )
    session.add(emp)
    session.flush()
    return emp


@pytest.fixture()
def machine(session, location):
    line = ProductionLine(code="L1", name="Linha 1", location_id=location.id, capacity_units_per_hour=100)
    session.add(line)
    session.flush()
    m = Machine(code="CNC-01", name="Torno 01", production_line_id=line.id)
    session.add(m)
    session.flush()
    return m


@pytest.fixture()
def operators(session, employee):
    ops = [
        Operator(employee_id=employee.id, code="OP-01", name="Ana", shift=1),
        Operator(employee_id=employee.id, code="OP-02", name="Bruno", shift=2),
    ]
    session.add_all(ops)
    session.flush()
    return ops


@pytest.fixture()
def occurrences(session):
    occs = {
        "prod": OccurrenceType(code="PRODUCAO", description="Produção",
                               category=OccurrenceCategory.PRODUCTIVE),
        "setup": OccurrenceType(code="SETUP_1H", description="Setup 1h",
                                category=OccurrenceCategory.SEMI_PRODUCTIVE),
        "sem_peca": OccurrenceType(code="SEM_PECA", description="Sem Peça",
                                   category=OccurrenceCategory.UNPRODUCTIVE),
        "limpeza": OccurrenceType(code="LIMPEZA", description="Limpeza",
                                  category=OccurrenceCategory.UNPRODUCTIVE),
    }
    session.add_all(occs.values())
    session.flush()
    return occs


def _appt(svc, op_id, machine_id, occ_id, minutes, qty=0, eff=0.0):
    svc.create_appointment(
        appointment_date=DAY, machine_id=machine_id, operator_id=op_id,
        occurrence_type_id=occ_id, start_time=time(8, 0), end_time=time(9, 0),
        duration_minutes=minutes, quantity=qty, efficiency_pct=eff,
    )


def test_panel_row_shape_and_roster(session, machine, operators, occurrences):
    m = MachiningService(session)
    ana, bruno = operators
    # Ana produz e faz setup; Bruno não aponta nada (deve aparecer zerado — roster fixo).
    _appt(m, ana.id, machine.id, occurrences["prod"].id, 540, qty=100, eff=90.0)
    _appt(m, ana.id, machine.id, occurrences["setup"].id, 150)   # padrão 120, real 150
    _appt(m, ana.id, machine.id, occurrences["sem_peca"].id, 60)
    _appt(m, ana.id, machine.id, occurrences["limpeza"].id, 30)
    session.flush()

    panel = OperatorsService(session).panel(START, END)
    by_name = {r.name: r for r in panel}

    assert set(by_name) == {"Ana", "Bruno"}
    ana_row = by_name["Ana"]
    assert ana_row.pieces == 100
    assert ana_row.production_yield == 90.0
    assert ana_row.setup_productivity == 34.0     # padrão 60min * 0.85 / 150 real * 100
    assert ana_row.no_part_hours == 1.0
    assert ana_row.idle_hours == 0.5              # só limpeza; sem peça não conta
    assert ana_row.idle_index == 3.85             # 0.5h / 13h apontadas
    assert ana_row.passes_meritocracy is True

    bruno_row = by_name["Bruno"]
    assert bruno_row.pieces == 0
    assert bruno_row.production_yield is None
    assert bruno_row.setup_productivity is None
    assert bruno_row.passes_meritocracy is True   # sem apontamento → índice 0


def test_panel_joins_scrap_and_adjustments(session, machine, operators, occurrences):
    m, s, a = MachiningService(session), ScrapService(session), AdjustmentsService(session)
    ana = operators[0]
    _appt(m, ana.id, machine.id, occurrences["prod"].id, 480, qty=80, eff=88.0)

    # Refugo por erro de usinagem (conta) + defeito de fornecedor (não conta).
    s.create_record(record_date=DAY, operator_id=ana.id, machine_id=machine.id,
                    reason_1="Dimensional Errado Usinagem", quantity_1=7, total_quantity=7)
    s.create_record(record_date=DAY, operator_id=ana.id, machine_id=machine.id,
                    reason_1="Porosidade", quantity_1=99, total_quantity=99)
    # Ajuste que economiza 1h (3600s).
    a.create_adjustment(record_date=datetime(2026, 1, 10, 9, 0), operator_id=ana.id,
                        machine_id=machine.id, operation="Desbaste",
                        previous_time_seconds=7200, current_time_seconds=3600,
                        justification="Melhoria de ferramenta")
    session.flush()

    ana_row = {r.name: r for r in OperatorsService(session).panel(START, END)}["Ana"]
    assert ana_row.scrap_usinagem == 7                 # só o erro de usinagem
    assert ana_row.adjustments_balance_hours == 1.0    # 3600s economizados


def test_summary_aggregates_team(session, machine, operators, occurrences):
    m = MachiningService(session)
    ana, bruno = operators
    _appt(m, ana.id, machine.id, occurrences["prod"].id, 300, qty=50, eff=80.0)
    _appt(m, bruno.id, machine.id, occurrences["prod"].id, 300, qty=70, eff=100.0)
    _appt(m, ana.id, machine.id, occurrences["setup"].id, 120)   # padrão 60min, real 120
    session.flush()

    resumo = OperatorsService(session).summary(START, END)
    assert resumo.operator_count == 2
    assert resumo.total_pieces == 120
    assert resumo.avg_production_yield == 90.0        # (80 + 100) / 2
    assert resumo.avg_setup_productivity == 42.5      # 60*0.85/120*100
    assert resumo.production_hours == 10.0
    assert resumo.setup_hours == 2.0
