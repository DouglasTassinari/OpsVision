from datetime import date

from app.database.models.sales import Customer, CustomerSegment, OrderStatus, SalesOrder, SalesOrderItem
from app.repositories.sales_repository import CustomerRepository, SalesOrderRepository


def _make_customer(session) -> Customer:
    customer = Customer(
        code="CUST-1",
        name="Acme Corp",
        segment=CustomerSegment.WHOLESALE,
        city="Metropolis",
        state="NY",
    )
    session.add(customer)
    session.flush()
    return customer


def test_find_by_code(session, location):
    customer = _make_customer(session)
    repo = CustomerRepository(session)
    assert repo.find_by_code("CUST-1").id == customer.id
    assert repo.find_by_code("MISSING") is None


def test_revenue_by_month_excludes_cancelled_orders(session, location, product):
    customer = _make_customer(session)
    kept = SalesOrder(
        order_number="SO-1",
        customer_id=customer.id,
        location_id=location.id,
        order_date=date(2026, 1, 15),
        discount_pct=10,
        status=OrderStatus.CONFIRMED,
        items=[SalesOrderItem(product_id=product.id, quantity=10, unit_price=100)],
    )
    cancelled = SalesOrder(
        order_number="SO-2",
        customer_id=customer.id,
        location_id=location.id,
        order_date=date(2026, 1, 20),
        discount_pct=0,
        status=OrderStatus.CANCELLED,
        items=[SalesOrderItem(product_id=product.id, quantity=5, unit_price=100)],
    )
    session.add_all([kept, cancelled])
    session.flush()

    repo = SalesOrderRepository(session)
    rows = repo.revenue_by_month(date(2026, 1, 1), date(2026, 1, 31))

    assert rows == [("2026-01", 900.0)]  # 10 * 100 * (1 - 10%)


def test_top_customers_orders_by_revenue_desc(session, location, product):
    big = _make_customer(session)
    small = Customer(
        code="CUST-2", name="Small Co", segment=CustomerSegment.RETAIL, city="Gotham", state="NJ"
    )
    session.add(small)
    session.flush()

    session.add_all(
        [
            SalesOrder(
                order_number="SO-10",
                customer_id=big.id,
                location_id=location.id,
                order_date=date(2026, 2, 1),
                discount_pct=0,
                status=OrderStatus.CONFIRMED,
                items=[SalesOrderItem(product_id=product.id, quantity=100, unit_price=10)],
            ),
            SalesOrder(
                order_number="SO-11",
                customer_id=small.id,
                location_id=location.id,
                order_date=date(2026, 2, 2),
                discount_pct=0,
                status=OrderStatus.CONFIRMED,
                items=[SalesOrderItem(product_id=product.id, quantity=5, unit_price=10)],
            ),
        ]
    )
    session.flush()

    repo = SalesOrderRepository(session)
    top = repo.top_customers(date(2026, 2, 1), date(2026, 2, 28))

    assert top[0] == ("Acme Corp", 1000.0)
    assert top[1] == ("Small Co", 50.0)


def test_revenue_by_segment_groups_and_excludes_cancelled(session, location, product):
    wholesale = _make_customer(session)
    retail = Customer(
        code="CUST-9", name="Retail Co", segment=CustomerSegment.RETAIL, city="Gotham", state="NJ"
    )
    session.add(retail)
    session.flush()
    session.add_all(
        [
            SalesOrder(
                order_number="SO-90",
                customer_id=wholesale.id,
                location_id=location.id,
                order_date=date(2026, 3, 1),
                discount_pct=0,
                status=OrderStatus.INVOICED,
                items=[SalesOrderItem(product_id=product.id, quantity=10, unit_price=100)],
            ),
            SalesOrder(
                order_number="SO-91",
                customer_id=retail.id,
                location_id=location.id,
                order_date=date(2026, 3, 2),
                discount_pct=0,
                status=OrderStatus.INVOICED,
                items=[SalesOrderItem(product_id=product.id, quantity=2, unit_price=100)],
            ),
            SalesOrder(
                order_number="SO-92",
                customer_id=retail.id,
                location_id=location.id,
                order_date=date(2026, 3, 3),
                discount_pct=0,
                status=OrderStatus.CANCELLED,
                items=[SalesOrderItem(product_id=product.id, quantity=50, unit_price=100)],
            ),
        ]
    )
    session.flush()

    repo = SalesOrderRepository(session)
    rows = repo.revenue_by_segment(date(2026, 3, 1), date(2026, 3, 31))

    assert rows == [("wholesale", 1000.0), ("retail", 200.0)]
