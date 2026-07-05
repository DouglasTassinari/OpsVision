"""Sales module service — orchestrates repositories + domain rules.

This is the only layer the Streamlit pages talk to for Sales data; pages
never import repositories or models directly.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.metrics import track
from app.database.models.sales import OrderStatus, SalesOrder, SalesOrderItem
from app.domain import sales_rules
from app.repositories.sales_repository import CustomerRepository, SalesOrderRepository

logger = get_logger("services.sales")


class SalesService:
    def __init__(self, session: Session):
        self.session = session
        self.orders = SalesOrderRepository(session)
        self.customers = CustomerRepository(session)

    @track("sales.create_order")
    def create_order(
        self,
        order_number: str,
        customer_id: int,
        location_id: int,
        order_date: date,
        discount_pct: float,
        items: list[dict],
    ) -> SalesOrder:
        sales_rules.validate_discount(discount_pct)
        for item in items:
            sales_rules.validate_line_item(item["quantity"], item["unit_price"])

        order = SalesOrder(
            order_number=order_number,
            customer_id=customer_id,
            location_id=location_id,
            order_date=order_date,
            discount_pct=discount_pct,
            status=OrderStatus.DRAFT,
            items=[SalesOrderItem(**item) for item in items],
        )
        self.orders.add(order)
        logger.info("Created sales order %s with %d items", order_number, len(items))
        return order

    @track("sales.transition_order")
    def transition_order(self, order_id: int, target_status: OrderStatus) -> SalesOrder:
        order = self.orders.get(order_id)
        sales_rules.assert_transition(order.status, target_status)
        order.status = target_status
        self.session.flush()
        logger.info("Order %s moved to %s", order.order_number, target_status.value)
        return order

    @track("sales.monthly_revenue")
    def monthly_revenue(self, start: date, end: date) -> list[tuple[str, float]]:
        return self.orders.revenue_by_month(start, end)

    @track("sales.top_customers")
    def top_customers(self, start: date, end: date, limit: int = 10) -> list[tuple[str, float]]:
        return self.orders.top_customers(start, end, limit)

    @track("sales.revenue_by_segment")
    def revenue_by_segment(self, start: date, end: date) -> list[tuple[str, float]]:
        return self.orders.revenue_by_segment(start, end)

    def active_customers(self):
        return self.customers.active_customers()
