from datetime import date

import pytest

from app.database.models.production import ProductionLine, WorkOrder, WorkOrderStatus
from app.repositories.production_repository import ProductionLineRepository, WorkOrderRepository


@pytest.fixture()
def production_line(session, location) -> ProductionLine:
    line = ProductionLine(
        code="LINE-1",
        name="Assembly Line 1",
        location_id=location.id,
        capacity_units_per_hour=100,
    )
    session.add(line)
    session.flush()
    return line


def test_work_orders_between_filters_by_scheduled_date(session, location, product, production_line):
    in_range = WorkOrder(
        order_number="WO-1",
        product_id=product.id,
        production_line_id=production_line.id,
        status=WorkOrderStatus.PLANNED,
        planned_quantity=100,
        scheduled_date=date(2026, 1, 15),
    )
    out_of_range = WorkOrder(
        order_number="WO-2",
        product_id=product.id,
        production_line_id=production_line.id,
        status=WorkOrderStatus.PLANNED,
        planned_quantity=50,
        scheduled_date=date(2026, 3, 1),
    )
    session.add_all([in_range, out_of_range])
    session.flush()

    repo = WorkOrderRepository(session)
    rows = repo.work_orders_between(date(2026, 1, 1), date(2026, 1, 31))

    assert [row.order_number for row in rows] == ["WO-1"]


def test_by_status_filters_correctly(session, location, product, production_line):
    planned = WorkOrder(
        order_number="WO-3",
        product_id=product.id,
        production_line_id=production_line.id,
        status=WorkOrderStatus.PLANNED,
        planned_quantity=10,
        scheduled_date=date(2026, 1, 1),
    )
    completed = WorkOrder(
        order_number="WO-4",
        product_id=product.id,
        production_line_id=production_line.id,
        status=WorkOrderStatus.COMPLETED,
        planned_quantity=10,
        produced_quantity=10,
        scheduled_date=date(2026, 1, 2),
    )
    session.add_all([planned, completed])
    session.flush()

    repo = WorkOrderRepository(session)
    assert [wo.order_number for wo in repo.by_status(WorkOrderStatus.COMPLETED)] == ["WO-4"]
    assert [wo.order_number for wo in repo.by_status(WorkOrderStatus.PLANNED)] == ["WO-3"]


def test_yield_by_line_averages_completed_orders_only(session, location, product, production_line):
    completed = WorkOrder(
        order_number="WO-5",
        product_id=product.id,
        production_line_id=production_line.id,
        status=WorkOrderStatus.COMPLETED,
        planned_quantity=100,
        produced_quantity=90,
        scrap_quantity=10,
        scheduled_date=date(2026, 1, 10),
    )
    in_progress = WorkOrder(
        order_number="WO-6",
        product_id=product.id,
        production_line_id=production_line.id,
        status=WorkOrderStatus.IN_PROGRESS,
        planned_quantity=100,
        produced_quantity=50,
        scrap_quantity=50,
        scheduled_date=date(2026, 1, 12),
    )
    session.add_all([completed, in_progress])
    session.flush()

    repo = WorkOrderRepository(session)
    rows = repo.yield_by_line(date(2026, 1, 1), date(2026, 1, 31))

    assert rows == [("Assembly Line 1", 90.0)]


def test_scrap_by_month_excludes_cancelled(session, location, product, production_line):
    kept = WorkOrder(
        order_number="WO-7",
        product_id=product.id,
        production_line_id=production_line.id,
        status=WorkOrderStatus.COMPLETED,
        planned_quantity=100,
        produced_quantity=90,
        scrap_quantity=10,
        scheduled_date=date(2026, 2, 5),
    )
    cancelled = WorkOrder(
        order_number="WO-8",
        product_id=product.id,
        production_line_id=production_line.id,
        status=WorkOrderStatus.CANCELLED,
        planned_quantity=50,
        produced_quantity=0,
        scrap_quantity=20,
        scheduled_date=date(2026, 2, 10),
    )
    session.add_all([kept, cancelled])
    session.flush()

    repo = WorkOrderRepository(session)
    rows = repo.scrap_by_month(date(2026, 2, 1), date(2026, 2, 28))

    assert rows == [("2026-02", 10)]


def test_production_line_repository_get(session, location, production_line):
    repo = ProductionLineRepository(session)
    assert repo.get(production_line.id).code == "LINE-1"


def test_count_by_status_groups_within_period(session, location, product, production_line):
    session.add_all(
        [
            WorkOrder(
                order_number="WO-20",
                product_id=product.id,
                production_line_id=production_line.id,
                status=WorkOrderStatus.COMPLETED,
                planned_quantity=10,
                produced_quantity=10,
                scheduled_date=date(2026, 4, 1),
            ),
            WorkOrder(
                order_number="WO-21",
                product_id=product.id,
                production_line_id=production_line.id,
                status=WorkOrderStatus.COMPLETED,
                planned_quantity=10,
                produced_quantity=9,
                scheduled_date=date(2026, 4, 2),
            ),
            WorkOrder(
                order_number="WO-22",
                product_id=product.id,
                production_line_id=production_line.id,
                status=WorkOrderStatus.PLANNED,
                planned_quantity=10,
                scheduled_date=date(2026, 4, 3),
            ),
            WorkOrder(
                order_number="WO-23",
                product_id=product.id,
                production_line_id=production_line.id,
                status=WorkOrderStatus.PLANNED,
                planned_quantity=10,
                scheduled_date=date(2026, 5, 10),
            ),
        ]
    )
    session.flush()

    repo = WorkOrderRepository(session)
    rows = repo.count_by_status(date(2026, 4, 1), date(2026, 4, 30))

    assert rows == [("completed", 2), ("planned", 1)]
