"""Data access for the Finance module."""
from __future__ import annotations

from datetime import date

from sqlalchemy import case, func, select

from app.database.models.finance import (
    Account,
    Invoice,
    InvoiceDirection,
    InvoiceStatus,
    Transaction,
    TransactionType,
)
from app.repositories.base import BaseRepository


class AccountRepository(BaseRepository[Account]):
    model = Account


class InvoiceRepository(BaseRepository[Invoice]):
    model = Invoice

    def invoices_between(self, start: date, end: date) -> list[Invoice]:
        stmt = select(Invoice).where(Invoice.issue_date >= start, Invoice.issue_date <= end)
        return list(self.session.execute(stmt).scalars().all())

    def by_status(self, status: InvoiceStatus) -> list[Invoice]:
        stmt = select(Invoice).where(Invoice.status == status)
        return list(self.session.execute(stmt).scalars().all())

    def outstanding_receivables(self) -> float:
        stmt = select(func.sum(Invoice.amount)).where(
            Invoice.direction == InvoiceDirection.RECEIVABLE,
            Invoice.status.in_((InvoiceStatus.OPEN, InvoiceStatus.OVERDUE)),
        )
        return float(self.session.execute(stmt).scalar() or 0.0)

    def outstanding_payables(self) -> float:
        stmt = select(func.sum(Invoice.amount)).where(
            Invoice.direction == InvoiceDirection.PAYABLE,
            Invoice.status.in_((InvoiceStatus.OPEN, InvoiceStatus.OVERDUE)),
        )
        return float(self.session.execute(stmt).scalar() or 0.0)

    def amounts_by_direction_and_status(self) -> list[tuple[str, str, float]]:
        """Invoice totals grouped by (direction value, status value), cancelled excluded."""
        stmt = (
            select(Invoice.direction, Invoice.status, func.sum(Invoice.amount).label("total"))
            .where(Invoice.status != InvoiceStatus.CANCELLED)
            .group_by(Invoice.direction, Invoice.status)
            .order_by(Invoice.direction, Invoice.status)
        )
        return [
            (direction.value, status.value, round(float(total or 0), 2))
            for direction, status, total in self.session.execute(stmt).all()
        ]


class TransactionRepository(BaseRepository[Transaction]):
    model = Transaction

    def net_cashflow_by_month(self, start: date, end: date) -> list[tuple[str, float]]:
        signed_amount = func.sum(
            case(
                (Transaction.transaction_type == TransactionType.CREDIT, Transaction.amount),
                else_=-Transaction.amount,
            )
        )
        stmt = (
            select(
                func.strftime("%Y-%m", Transaction.transaction_date).label("month"),
                signed_amount.label("net"),
            )
            .where(Transaction.transaction_date >= start, Transaction.transaction_date <= end)
            .group_by("month")
            .order_by("month")
        )
        rows = self.session.execute(stmt).all()
        return [(month, round(float(net or 0), 2)) for month, net in rows]
