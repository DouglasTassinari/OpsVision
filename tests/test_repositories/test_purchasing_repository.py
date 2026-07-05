from datetime import date

from app.database.models.purchasing import (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    Supplier,
    SupplierCategory,
)
from app.repositories.purchasing_repository import (
    PurchaseOrderRepository,
    SupplierRepository,
)


def _make_supplier(session, code: str = "SUP-1", name: str = "Acme Materials", rating: float = 4.0) -> Supplier:
    supplier = Supplier(
        code=code,
        name=name,
        category=SupplierCategory.RAW_MATERIAL,
        city="Metropolis",
        state="NY",
        rating=rating,
    )
    session.add(supplier)
    session.flush()
    return supplier


def test_top_rated_orders_by_rating_desc(session, location):
    low = _make_supplier(session, code="SUP-1", name="Low Rated", rating=2.0)
    high = _make_supplier(session, code="SUP-2", name="High Rated", rating=4.8)

    repo = SupplierRepository(session)
    top = repo.top_rated()

    assert top[0].id == high.id
    assert top[1].id == low.id


def test_by_category_filters(session, location):
    raw = _make_supplier(session, code="SUP-1", name="Raw Co")
    services = Supplier(
        code="SUP-2",
        name="Services Co",
        category=SupplierCategory.SERVICES,
        city="Gotham",
        state="NJ",
        rating=3.0,
    )
    session.add(services)
    session.flush()

    repo = SupplierRepository(session)
    raw_suppliers = repo.by_category(SupplierCategory.RAW_MATERIAL)

    assert [s.id for s in raw_suppliers] == [raw.id]


def test_spend_by_month_excludes_cancelled_orders(session, location, product):
    supplier = _make_supplier(session)
    kept = PurchaseOrder(
        order_number="PO-1",
        supplier_id=supplier.id,
        location_id=location.id,
        order_date=date(2026, 1, 15),
        status=PurchaseOrderStatus.CONFIRMED,
        items=[PurchaseOrderItem(product_id=product.id, quantity=10, unit_cost=100)],
    )
    cancelled = PurchaseOrder(
        order_number="PO-2",
        supplier_id=supplier.id,
        location_id=location.id,
        order_date=date(2026, 1, 20),
        status=PurchaseOrderStatus.CANCELLED,
        items=[PurchaseOrderItem(product_id=product.id, quantity=5, unit_cost=100)],
    )
    session.add_all([kept, cancelled])
    session.flush()

    repo = PurchaseOrderRepository(session)
    rows = repo.spend_by_month(date(2026, 1, 1), date(2026, 1, 31))

    assert rows == [("2026-01", 1000.0)]  # 10 * 100


def test_top_suppliers_orders_by_spend_desc(session, location, product):
    big = _make_supplier(session, code="SUP-1", name="Big Supplier")
    small = _make_supplier(session, code="SUP-2", name="Small Supplier")

    session.add_all(
        [
            PurchaseOrder(
                order_number="PO-10",
                supplier_id=big.id,
                location_id=location.id,
                order_date=date(2026, 2, 1),
                status=PurchaseOrderStatus.CONFIRMED,
                items=[PurchaseOrderItem(product_id=product.id, quantity=100, unit_cost=10)],
            ),
            PurchaseOrder(
                order_number="PO-11",
                supplier_id=small.id,
                location_id=location.id,
                order_date=date(2026, 2, 2),
                status=PurchaseOrderStatus.CONFIRMED,
                items=[PurchaseOrderItem(product_id=product.id, quantity=5, unit_cost=10)],
            ),
        ]
    )
    session.flush()

    repo = PurchaseOrderRepository(session)
    top = repo.top_suppliers(date(2026, 2, 1), date(2026, 2, 28))

    assert top[0] == ("Big Supplier", 1000.0)
    assert top[1] == ("Small Supplier", 50.0)


def test_spend_by_supplier_category_groups_and_excludes_cancelled(session, location, product):
    raw = _make_supplier(session, code="SUP-8", name="Raw Co")
    services = Supplier(
        code="SUP-9",
        name="Services Co",
        category=SupplierCategory.SERVICES,
        city="Gotham",
        state="NJ",
        rating=3.5,
    )
    session.add(services)
    session.flush()
    session.add_all(
        [
            PurchaseOrder(
                order_number="PO-80",
                supplier_id=raw.id,
                location_id=location.id,
                order_date=date(2026, 3, 1),
                status=PurchaseOrderStatus.RECEIVED,
                items=[PurchaseOrderItem(product_id=product.id, quantity=10, unit_cost=50)],
            ),
            PurchaseOrder(
                order_number="PO-81",
                supplier_id=services.id,
                location_id=location.id,
                order_date=date(2026, 3, 2),
                status=PurchaseOrderStatus.RECEIVED,
                items=[PurchaseOrderItem(product_id=product.id, quantity=2, unit_cost=50)],
            ),
            PurchaseOrder(
                order_number="PO-82",
                supplier_id=services.id,
                location_id=location.id,
                order_date=date(2026, 3, 3),
                status=PurchaseOrderStatus.CANCELLED,
                items=[PurchaseOrderItem(product_id=product.id, quantity=99, unit_cost=50)],
            ),
        ]
    )
    session.flush()

    repo = PurchaseOrderRepository(session)
    rows = repo.spend_by_supplier_category(date(2026, 3, 1), date(2026, 3, 31))

    assert rows == [("raw_material", 500.0), ("services", 100.0)]
