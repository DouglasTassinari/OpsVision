"""Data access for the Sales module."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

from app.database.models.sales import Customer, OrderStatus, SalesOrder, SalesOrderItem
from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    model = Customer

    def find_by_code(self, code: str) -> Customer | None:
        stmt = select(Customer).where(Customer.code == code)
        return self.session.execute(stmt).scalar_one_or_none()

    def active_customers(self) -> list[Customer]:
        stmt = select(Customer).where(Customer.active.is_(True))
        return list(self.session.execute(stmt).scalars().all())


class SalesOrderRepository(BaseRepository[SalesOrder]):
    model = SalesOrder

    def orders_between(self, start: date, end: date) -> list[SalesOrder]:
        stmt = select(SalesOrder).where(
            SalesOrder.order_date >= start, SalesOrder.order_date <= end
        )
        return list(self.session.execute(stmt).scalars().all())

    def by_status(self, status: OrderStatus) -> list[SalesOrder]:
        stmt = select(SalesOrder).where(SalesOrder.status == status)
        return list(self.session.execute(stmt).scalars().all())

    def revenue_by_month(self, start: date, end: date) -> list[tuple[str, float]]:
        """Net revenue (gross minus discount) grouped by calendar month."""
        stmt = (
            select(
                func.strftime("%Y-%m", SalesOrder.order_date).label("month"),
                func.sum(SalesOrderItem.quantity * SalesOrderItem.unit_price).label("gross"),
                func.avg(SalesOrder.discount_pct).label("avg_discount"),
            )
            .join(SalesOrderItem, SalesOrderItem.order_id == SalesOrder.id)
            .where(SalesOrder.order_date >= start, SalesOrder.order_date <= end)
            .where(SalesOrder.status != OrderStatus.CANCELLED)
            .group_by("month")
            .order_by("month")
        )
        rows = self.session.execute(stmt).all()
        return [
            (month, round(float(gross or 0) * (1 - float(avg_discount or 0) / 100), 2))
            for month, gross, avg_discount in rows
        ]

    def revenue_by_segment(self, start: date, end: date) -> list[tuple[str, float]]:
        """Gross revenue grouped by customer segment (enum value, total)."""
        total = func.sum(SalesOrderItem.quantity * SalesOrderItem.unit_price)
        stmt = (
            select(Customer.segment, total.label("total"))
            .join(SalesOrder, SalesOrder.customer_id == Customer.id)
            .join(SalesOrderItem, SalesOrderItem.order_id == SalesOrder.id)
            .where(SalesOrder.order_date >= start, SalesOrder.order_date <= end)
            .where(SalesOrder.status != OrderStatus.CANCELLED)
            .group_by(Customer.segment)
            .order_by(total.desc())
        )
        return [(segment.value, round(float(amount), 2)) for segment, amount in self.session.execute(stmt).all()]

    def top_customers(self, start: date, end: date, limit: int = 10) -> list[tuple[str, float]]:
        stmt = (
            select(
                Customer.name,
                func.sum(SalesOrderItem.quantity * SalesOrderItem.unit_price).label("total"),
            )
            .join(SalesOrder, SalesOrder.customer_id == Customer.id)
            .join(SalesOrderItem, SalesOrderItem.order_id == SalesOrder.id)
            .where(SalesOrder.order_date >= start, SalesOrder.order_date <= end)
            .where(SalesOrder.status != OrderStatus.CANCELLED)
            .group_by(Customer.id)
            .order_by(func.sum(SalesOrderItem.quantity * SalesOrderItem.unit_price).desc())
            .limit(limit)
        )
        return [(name, round(float(total), 2)) for name, total in self.session.execute(stmt).all()]
