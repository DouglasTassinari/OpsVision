"""Finance module service — orchestrates repositories + domain rules.

This is the only layer the Streamlit pages talk to for Finance data; pages
never import repositories or models directly.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.metrics import track
from app.database.models.finance import (
    Invoice,
    InvoiceDirection,
    InvoiceStatus,
    Transaction,
    TransactionType,
)
from app.domain import finance_rules
from app.repositories.finance_repository import (
    AccountRepository,
    InvoiceRepository,
    TransactionRepository,
)

logger = get_logger("services.finance")


class FinanceService:
    def __init__(self, session: Session):
        self.session = session
        self.accounts = AccountRepository(session)
        self.invoices = InvoiceRepository(session)
        self.transactions = TransactionRepository(session)

    @track("finance.create_invoice")
    def create_invoice(
        self,
        invoice_number: str,
        direction: InvoiceDirection,
        counterparty_name: str,
        amount: float,
        issue_date: date,
        due_date: date,
        source_sales_order_id: int | None = None,
        source_purchase_order_id: int | None = None,
    ) -> Invoice:
        finance_rules.validate_amount(amount)

        invoice = Invoice(
            invoice_number=invoice_number,
            direction=direction,
            counterparty_name=counterparty_name,
            amount=amount,
            issue_date=issue_date,
            due_date=due_date,
            status=InvoiceStatus.OPEN,
            source_sales_order_id=source_sales_order_id,
            source_purchase_order_id=source_purchase_order_id,
        )
        self.invoices.add(invoice)
        logger.info("Created invoice %s (%s) for %.2f", invoice_number, direction.value, amount)
        return invoice

    @track("finance.transition_invoice")
    def transition_invoice(self, invoice_id: int, target_status: InvoiceStatus) -> Invoice:
        invoice = self.invoices.get(invoice_id)
        finance_rules.assert_transition(invoice.status, target_status)
        invoice.status = target_status
        self.session.flush()
        logger.info("Invoice %s moved to %s", invoice.invoice_number, target_status.value)
        return invoice

    @track("finance.record_transaction")
    def record_transaction(
        self,
        account_id: int,
        transaction_type: TransactionType,
        amount: float,
        transaction_date: date,
        description: str,
        invoice_id: int | None = None,
    ) -> Transaction:
        finance_rules.validate_amount(amount)

        transaction = Transaction(
            account_id=account_id,
            invoice_id=invoice_id,
            transaction_type=transaction_type,
            amount=amount,
            transaction_date=transaction_date,
            description=description,
        )
        self.transactions.add(transaction)
        logger.info("Recorded %s transaction of %.2f on account %s", transaction_type.value, amount, account_id)
        return transaction

    @track("finance.outstanding_summary")
    def outstanding_summary(self) -> dict:
        return {
            "receivables": self.invoices.outstanding_receivables(),
            "payables": self.invoices.outstanding_payables(),
        }

    @track("finance.cash_position")
    def cash_position(self, start: date, end: date) -> list[tuple[str, float]]:
        return self.transactions.net_cashflow_by_month(start, end)

    @track("finance.invoice_breakdown")
    def invoice_breakdown(self) -> list[tuple[str, str, float]]:
        return self.invoices.amounts_by_direction_and_status()
