"""Data access for the Purchasing module."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

from app.database.models.purchasing import (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    Supplier,
    SupplierCategory,
)
from app.repositories.base import BaseRepository


class SupplierRepository(BaseRepository[Supplier]):
    model = Supplier

    def top_rated(self, limit: int = 10) -> list[Supplier]:
        stmt = select(Supplier).order_by(Supplier.rating.desc()).limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def by_category(self, category: SupplierCategory) -> list[Supplier]:
        stmt = select(Supplier).where(Supplier.category == category)
        return list(self.session.execute(stmt).scalars().all())


class PurchaseOrderRepository(BaseRepository[PurchaseOrder]):
    model = PurchaseOrder

    def orders_between(self, start: date, end: date) -> list[PurchaseOrder]:
        stmt = select(PurchaseOrder).where(
            PurchaseOrder.order_date >= start, PurchaseOrder.order_date <= end
        )
        return list(self.session.execute(stmt).scalars().all())

    def by_status(self, status: PurchaseOrderStatus) -> list[PurchaseOrder]:
        stmt = select(PurchaseOrder).where(PurchaseOrder.status == status)
        return list(self.session.execute(stmt).scalars().all())

    def spend_by_month(self, start: date, end: date) -> list[tuple[str, float]]:
        stmt = (
            select(
                func.strftime("%Y-%m", PurchaseOrder.order_date).label("month"),
                func.sum(
                    PurchaseOrderItem.quantity * PurchaseOrderItem.unit_cost
                ).label("total"),
            )
            .join(PurchaseOrderItem, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id)
            .where(PurchaseOrder.order_date >= start, PurchaseOrder.order_date <= end)
            .where(PurchaseOrder.status != PurchaseOrderStatus.CANCELLED)
            .group_by("month")
            .order_by("month")
        )
        rows = self.session.execute(stmt).all()
        return [(month, round(float(total or 0), 2)) for month, total in rows]

    def spend_by_supplier_category(self, start: date, end: date) -> list[tuple[str, float]]:
        """Spend grouped by supplier category (enum value, total)."""
        total = func.sum(PurchaseOrderItem.quantity * PurchaseOrderItem.unit_cost)
        stmt = (
            select(Supplier.category, total.label("total"))
            .join(PurchaseOrder, PurchaseOrder.supplier_id == Supplier.id)
            .join(PurchaseOrderItem, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id)
            .where(PurchaseOrder.order_date >= start, PurchaseOrder.order_date <= end)
            .where(PurchaseOrder.status != PurchaseOrderStatus.CANCELLED)
            .group_by(Supplier.category)
            .order_by(total.desc())
        )
        return [(category.value, round(float(amount), 2)) for category, amount in self.session.execute(stmt).all()]

    def top_suppliers(self, start: date, end: date, limit: int = 10) -> list[tuple[str, float]]:
        stmt = (
            select(
                Supplier.name,
                func.sum(
                    PurchaseOrderItem.quantity * PurchaseOrderItem.unit_cost
                ).label("total"),
            )
            .join(PurchaseOrder, PurchaseOrder.supplier_id == Supplier.id)
            .join(PurchaseOrderItem, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id)
            .where(PurchaseOrder.order_date >= start, PurchaseOrder.order_date <= end)
            .where(PurchaseOrder.status != PurchaseOrderStatus.CANCELLED)
            .group_by(Supplier.id)
            .order_by(
                func.sum(PurchaseOrderItem.quantity * PurchaseOrderItem.unit_cost).desc()
            )
            .limit(limit)
        )
        return [(name, round(float(total), 2)) for name, total in self.session.execute(stmt).all()]
