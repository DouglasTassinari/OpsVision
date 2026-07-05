"""Production module service — orchestrates repositories + domain rules.

This is the only layer the Streamlit pages talk to for Production data;
pages never import repositories or models directly.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.metrics import track
from app.database.models.production import (
    ProductionEvent,
    ProductionEventType,
    WorkOrder,
    WorkOrderStatus,
)
from app.domain import production_rules
from app.repositories.production_repository import ProductionLineRepository, WorkOrderRepository

logger = get_logger("services.production")


class ProductionService:
    def __init__(self, session: Session):
        self.session = session
        self.work_orders = WorkOrderRepository(session)
        self.lines = ProductionLineRepository(session)

    @track("production.create_work_order")
    def create_work_order(
        self,
        order_number: str,
        product_id: int,
        production_line_id: int,
        planned_quantity: int,
        scheduled_date: date,
        produced_quantity: int = 0,
        scrap_quantity: int = 0,
    ) -> WorkOrder:
        production_rules.validate_quantities(planned_quantity, produced_quantity, scrap_quantity)

        order = WorkOrder(
            order_number=order_number,
            product_id=product_id,
            production_line_id=production_line_id,
            status=WorkOrderStatus.PLANNED,
            planned_quantity=planned_quantity,
            produced_quantity=produced_quantity,
            scrap_quantity=scrap_quantity,
            scheduled_date=scheduled_date,
        )
        self.work_orders.add(order)
        logger.info("Created work order %s for product %s", order_number, product_id)
        return order

    @track("production.transition_work_order")
    def transition_work_order(self, work_order_id: int, target_status: WorkOrderStatus) -> WorkOrder:
        order = self.work_orders.get(work_order_id)
        production_rules.assert_transition(order.status, target_status)
        order.status = target_status
        self.session.flush()
        logger.info("Work order %s moved to %s", order.order_number, target_status.value)
        return order

    @track("production.record_event")
    def record_event(
        self,
        work_order_id: int,
        event_type: ProductionEventType,
        event_time: datetime,
        notes: str | None = None,
    ) -> ProductionEvent:
        order = self.work_orders.get(work_order_id)
        event = ProductionEvent(event_type=event_type, event_time=event_time, notes=notes)
        order.events.append(event)
        self.session.flush()
        logger.info("Recorded %s event for work order %s", event_type.value, order.order_number)
        return event

    @track("production.line_yield_report")
    def line_yield_report(self, start: date, end: date) -> list[tuple[str, float]]:
        return self.work_orders.yield_by_line(start, end)

    @track("production.monthly_scrap")
    def monthly_scrap(self, start: date, end: date) -> list[tuple[str, int]]:
        return self.work_orders.scrap_by_month(start, end)

    @track("production.status_breakdown")
    def status_breakdown(self, start: date, end: date) -> list[tuple[str, int]]:
        return self.work_orders.count_by_status(start, end)
