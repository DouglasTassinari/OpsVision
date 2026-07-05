"""Data access for the Production module."""
from __future__ import annotations

from datetime import date

from sqlalchemy import case, func, select

from app.database.models.production import ProductionLine, WorkOrder, WorkOrderStatus
from app.repositories.base import BaseRepository


class ProductionLineRepository(BaseRepository[ProductionLine]):
    model = ProductionLine


class WorkOrderRepository(BaseRepository[WorkOrder]):
    model = WorkOrder

    def work_orders_between(self, start: date, end: date) -> list[WorkOrder]:
        stmt = select(WorkOrder).where(
            WorkOrder.scheduled_date >= start, WorkOrder.scheduled_date <= end
        )
        return list(self.session.execute(stmt).scalars().all())

    def by_status(self, status: WorkOrderStatus) -> list[WorkOrder]:
        stmt = select(WorkOrder).where(WorkOrder.status == status)
        return list(self.session.execute(stmt).scalars().all())

    def count_by_status(self, start: date, end: date) -> list[tuple[str, int]]:
        """Work order count grouped by status (enum value, count) within the period."""
        stmt = (
            select(WorkOrder.status, func.count().label("total"))
            .where(WorkOrder.scheduled_date >= start, WorkOrder.scheduled_date <= end)
            .group_by(WorkOrder.status)
            .order_by(func.count().desc())
        )
        return [(status.value, int(count)) for status, count in self.session.execute(stmt).all()]

    def yield_by_line(self, start: date, end: date) -> list[tuple[str, float]]:
        stmt = (
            select(
                ProductionLine.name,
                func.avg(
                    case(
                        (
                            WorkOrder.produced_quantity + WorkOrder.scrap_quantity > 0,
                            100.0
                            * WorkOrder.produced_quantity
                            / (WorkOrder.produced_quantity + WorkOrder.scrap_quantity),
                        ),
                        else_=0.0,
                    )
                ).label("avg_yield"),
            )
            .join(ProductionLine, ProductionLine.id == WorkOrder.production_line_id)
            .where(WorkOrder.scheduled_date >= start, WorkOrder.scheduled_date <= end)
            .where(WorkOrder.status == WorkOrderStatus.COMPLETED)
            .group_by(ProductionLine.id)
        )
        rows = self.session.execute(stmt).all()
        return [(name, round(float(avg_yield or 0), 1)) for name, avg_yield in rows]

    def scrap_by_month(self, start: date, end: date) -> list[tuple[str, int]]:
        stmt = (
            select(
                func.strftime("%Y-%m", WorkOrder.scheduled_date).label("month"),
                func.sum(WorkOrder.scrap_quantity).label("total_scrap"),
            )
            .where(WorkOrder.scheduled_date >= start, WorkOrder.scheduled_date <= end)
            .where(WorkOrder.status != WorkOrderStatus.CANCELLED)
            .group_by("month")
            .order_by("month")
        )
        rows = self.session.execute(stmt).all()
        return [(month, int(total_scrap or 0)) for month, total_scrap in rows]
