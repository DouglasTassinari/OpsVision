from datetime import date

from app.database.models.finance import (
    Account,
    AccountType,
    Invoice,
    InvoiceDirection,
    InvoiceStatus,
    Transaction,
    TransactionType,
)
from app.repositories.finance_repository import (
    InvoiceRepository,
    TransactionRepository,
)


def _make_account(session) -> Account:
    account = Account(code="1000", name="Cash", account_type=AccountType.ASSET)
    session.add(account)
    session.flush()
    return account


def test_invoices_between_filters_by_issue_date(session):
    in_range = Invoice(
        invoice_number="INV-1",
        direction=InvoiceDirection.RECEIVABLE,
        counterparty_name="Acme Corp",
        amount=500,
        issue_date=date(2026, 1, 10),
        due_date=date(2026, 2, 10),
        status=InvoiceStatus.OPEN,
    )
    out_of_range = Invoice(
        invoice_number="INV-2",
        direction=InvoiceDirection.RECEIVABLE,
        counterparty_name="Acme Corp",
        amount=300,
        issue_date=date(2026, 3, 1),
        due_date=date(2026, 4, 1),
        status=InvoiceStatus.OPEN,
    )
    session.add_all([in_range, out_of_range])
    session.flush()

    repo = InvoiceRepository(session)
    rows = repo.invoices_between(date(2026, 1, 1), date(2026, 1, 31))

    assert [row.invoice_number for row in rows] == ["INV-1"]


def test_by_status_filters_correctly(session):
    open_invoice = Invoice(
        invoice_number="INV-10",
        direction=InvoiceDirection.PAYABLE,
        counterparty_name="Supplier Co",
        amount=200,
        issue_date=date(2026, 1, 1),
        due_date=date(2026, 2, 1),
        status=InvoiceStatus.OPEN,
    )
    paid_invoice = Invoice(
        invoice_number="INV-11",
        direction=InvoiceDirection.PAYABLE,
        counterparty_name="Supplier Co",
        amount=400,
        issue_date=date(2026, 1, 1),
        due_date=date(2026, 2, 1),
        status=InvoiceStatus.PAID,
    )
    session.add_all([open_invoice, paid_invoice])
    session.flush()

    repo = InvoiceRepository(session)
    rows = repo.by_status(InvoiceStatus.OPEN)

    assert [row.invoice_number for row in rows] == ["INV-10"]


def test_outstanding_receivables_sums_open_and_overdue_only(session):
    session.add_all(
        [
            Invoice(
                invoice_number="INV-20",
                direction=InvoiceDirection.RECEIVABLE,
                counterparty_name="Acme Corp",
                amount=100,
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 2, 1),
                status=InvoiceStatus.OPEN,
            ),
            Invoice(
                invoice_number="INV-21",
                direction=InvoiceDirection.RECEIVABLE,
                counterparty_name="Acme Corp",
                amount=50,
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 2, 1),
                status=InvoiceStatus.OVERDUE,
            ),
            Invoice(
                invoice_number="INV-22",
                direction=InvoiceDirection.RECEIVABLE,
                counterparty_name="Acme Corp",
                amount=999,
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 2, 1),
                status=InvoiceStatus.PAID,
            ),
            Invoice(
                invoice_number="INV-23",
                direction=InvoiceDirection.PAYABLE,
                counterparty_name="Supplier Co",
                amount=999,
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 2, 1),
                status=InvoiceStatus.OPEN,
            ),
        ]
    )
    session.flush()

    repo = InvoiceRepository(session)
    assert repo.outstanding_receivables() == 150.0


def test_outstanding_receivables_zero_when_none(session):
    repo = InvoiceRepository(session)
    assert repo.outstanding_receivables() == 0.0


def test_outstanding_payables_sums_open_and_overdue_only(session):
    session.add_all(
        [
            Invoice(
                invoice_number="INV-30",
                direction=InvoiceDirection.PAYABLE,
                counterparty_name="Supplier Co",
                amount=120,
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 2, 1),
                status=InvoiceStatus.OVERDUE,
            ),
            Invoice(
                invoice_number="INV-31",
                direction=InvoiceDirection.PAYABLE,
                counterparty_name="Supplier Co",
                amount=999,
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 2, 1),
                status=InvoiceStatus.CANCELLED,
            ),
        ]
    )
    session.flush()

    repo = InvoiceRepository(session)
    assert repo.outstanding_payables() == 120.0


def test_net_cashflow_by_month_nets_debits_and_credits(session):
    account = _make_account(session)
    session.add_all(
        [
            Transaction(
                account_id=account.id,
                transaction_type=TransactionType.CREDIT,
                amount=500,
                transaction_date=date(2026, 1, 5),
                description="Payment received",
            ),
            Transaction(
                account_id=account.id,
                transaction_type=TransactionType.DEBIT,
                amount=200,
                transaction_date=date(2026, 1, 20),
                description="Expense paid",
            ),
            Transaction(
                account_id=account.id,
                transaction_type=TransactionType.CREDIT,
                amount=100,
                transaction_date=date(2026, 2, 1),
                description="Payment received",
            ),
        ]
    )
    session.flush()

    repo = TransactionRepository(session)
    rows = repo.net_cashflow_by_month(date(2026, 1, 1), date(2026, 2, 28))

    assert rows == [("2026-01", 300.0), ("2026-02", 100.0)]


def test_amounts_by_direction_and_status_excludes_cancelled(session):
    session.add_all(
        [
            Invoice(
                invoice_number="INV-40",
                direction=InvoiceDirection.RECEIVABLE,
                counterparty_name="A",
                amount=100,
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 2, 1),
                status=InvoiceStatus.OPEN,
            ),
            Invoice(
                invoice_number="INV-41",
                direction=InvoiceDirection.RECEIVABLE,
                counterparty_name="B",
                amount=50,
                issue_date=date(2026, 1, 2),
                due_date=date(2026, 2, 2),
                status=InvoiceStatus.OPEN,
            ),
            Invoice(
                invoice_number="INV-42",
                direction=InvoiceDirection.PAYABLE,
                counterparty_name="C",
                amount=70,
                issue_date=date(2026, 1, 3),
                due_date=date(2026, 2, 3),
                status=InvoiceStatus.PAID,
            ),
            Invoice(
                invoice_number="INV-43",
                direction=InvoiceDirection.PAYABLE,
                counterparty_name="D",
                amount=999,
                issue_date=date(2026, 1, 4),
                due_date=date(2026, 2, 4),
                status=InvoiceStatus.CANCELLED,
            ),
        ]
    )
    session.flush()

    repo = InvoiceRepository(session)
    rows = repo.amounts_by_direction_and_status()

    assert ("receivable", "open", 150.0) in rows
    assert ("payable", "paid", 70.0) in rows
    assert all(status != "cancelled" for _, status, _ in rows)
