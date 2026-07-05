"""Purchasing module service — orchestrates repositories + domain rules.

This is the only layer the Streamlit pages talk to for Purchasing data;
pages never import repositories or models directly.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.metrics import track
from app.database.models.purchasing import (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
)
from app.domain import purchasing_rules
from app.repositories.purchasing_repository import (
    PurchaseOrderRepository,
    SupplierRepository,
)

logger = get_logger("services.purchasing")


class PurchasingService:
    def __init__(self, session: Session):
        self.session = session
        self.orders = PurchaseOrderRepository(session)
        self.suppliers = SupplierRepository(session)

    @track("purchasing.create_purchase_order")
    def create_purchase_order(
        self,
        order_number: str,
        supplier_id: int,
        location_id: int,
        order_date: date,
        items: list[dict],
        expected_date: date | None = None,
    ) -> PurchaseOrder:
        for item in items:
            purchasing_rules.validate_line_item(item["quantity"], item["unit_cost"])

        order = PurchaseOrder(
            order_number=order_number,
            supplier_id=supplier_id,
            location_id=location_id,
            order_date=order_date,
            expected_date=expected_date,
            status=PurchaseOrderStatus.DRAFT,
            items=[PurchaseOrderItem(**item) for item in items],
        )
        self.orders.add(order)
        logger.info("Created purchase order %s with %d items", order_number, len(items))
        return order

    @track("purchasing.transition_purchase_order")
    def transition_purchase_order(
        self, purchase_order_id: int, target_status: PurchaseOrderStatus
    ) -> PurchaseOrder:
        order = self.orders.get(purchase_order_id)
        purchasing_rules.assert_transition(order.status, target_status)
        order.status = target_status
        self.session.flush()
        logger.info("Purchase order %s moved to %s", order.order_number, target_status.value)
        return order

    @track("purchasing.monthly_spend")
    def monthly_spend(self, start: date, end: date) -> list[tuple[str, float]]:
        return self.orders.spend_by_month(start, end)

    @track("purchasing.top_suppliers")
    def top_suppliers(self, start: date, end: date, limit: int = 10) -> list[tuple[str, float]]:
        return self.orders.top_suppliers(start, end, limit)

    @track("purchasing.spend_by_category")
    def spend_by_category(self, start: date, end: date) -> list[tuple[str, float]]:
        return self.orders.spend_by_supplier_category(start, end)
