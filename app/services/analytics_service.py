"""Cross-module KPI aggregation for the executive Dashboard.

Unlike the other services, ``AnalyticsService`` owns no tables of its
own — it composes the per-module services into a single read model.
This keeps every module free to evolve its own schema/queries while
the Dashboard gets one coherent snapshot to render.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.metrics import track
from app.services.finance_service import FinanceService
from app.services.maintenance_service import MaintenanceService
from app.services.people_service import PeopleService
from app.services.production_service import ProductionService
from app.services.projects_service import ProjectsService
from app.services.purchasing_service import PurchasingService
from app.services.quality_service import QualityService
from app.services.sales_service import SalesService

logger = get_logger("services.analytics")


class AnalyticsService:
    def __init__(self, session: Session):
        self.session = session
        self.sales = SalesService(session)
        self.production = ProductionService(session)
        self.purchasing = PurchasingService(session)
        self.finance = FinanceService(session)
        self.people = PeopleService(session)
        self.projects = ProjectsService(session)
        self.maintenance = MaintenanceService(session)
        self.quality = QualityService(session)

    @track("analytics.executive_summary")
    def executive_summary(self, start: date, end: date) -> dict:
        revenue_rows = self.sales.monthly_revenue(start, end)
        spend_rows = self.purchasing.monthly_spend(start, end)
        cashflow_rows = self.finance.cash_position(start, end)
        yield_rows = self.production.line_yield_report(start, end)
        defect_rows = self.quality.defect_rate_trend(start, end)
        open_maintenance = sum(count for _, count in self.maintenance.open_requests_by_priority())

        outstanding = self.finance.outstanding_summary()

        return {
            "total_revenue": round(sum(v for _, v in revenue_rows), 2),
            "total_spend": round(sum(v for _, v in spend_rows), 2),
            "net_cashflow": round(sum(v for _, v in cashflow_rows), 2),
            "avg_production_yield": round(
                sum(v for _, v in yield_rows) / len(yield_rows), 2
            ) if yield_rows else 0.0,
            "avg_defect_rate": round(
                sum(v for _, v in defect_rows) / len(defect_rows), 2
            ) if defect_rows else 0.0,
            "open_maintenance_requests": open_maintenance,
            "active_projects": len(self.projects.projects.active_projects()),
            "active_headcount": len(self.people.employees.active_employees()),
            "outstanding_receivables": outstanding["receivables"],
            "outstanding_payables": outstanding["payables"],
        }

    def revenue_trend(self, start: date, end: date) -> list[tuple[str, float]]:
        return self.sales.monthly_revenue(start, end)

    def spend_trend(self, start: date, end: date) -> list[tuple[str, float]]:
        return self.purchasing.monthly_spend(start, end)

    def cashflow_trend(self, start: date, end: date) -> list[tuple[str, float]]:
        return self.finance.cash_position(start, end)

    @track("analytics.period_totals")
    def period_totals(self, start: date, end: date) -> dict:
        """Totais financeiros do período, usados para comparações entre janelas."""
        return {
            "revenue": round(sum(v for _, v in self.sales.monthly_revenue(start, end)), 2),
            "spend": round(sum(v for _, v in self.purchasing.monthly_spend(start, end)), 2),
            "cashflow": round(sum(v for _, v in self.finance.cash_position(start, end)), 2),
        }
