from datetime import date

from app.database.models.inventory import MovementType, Product, ProductCategory, StockMovement, Warehouse
from app.repositories.inventory_repository import StockMovementRepository


def _make_warehouse(session, location) -> Warehouse:
    warehouse = Warehouse(code="WH-1", name="Main Warehouse", location_id=location.id, capacity_units=1000)
    session.add(warehouse)
    session.flush()
    return warehouse


def test_movements_between_filters_by_date(session, location, product):
    warehouse = _make_warehouse(session, location)
    in_range = StockMovement(
        product_id=product.id,
        warehouse_id=warehouse.id,
        movement_type=MovementType.INBOUND,
        quantity=10,
        movement_date=date(2026, 1, 15),
    )
    out_of_range = StockMovement(
        product_id=product.id,
        warehouse_id=warehouse.id,
        movement_type=MovementType.INBOUND,
        quantity=5,
        movement_date=date(2026, 3, 1),
    )
    session.add_all([in_range, out_of_range])
    session.flush()

    repo = StockMovementRepository(session)
    rows = repo.movements_between(date(2026, 1, 1), date(2026, 1, 31))

    assert len(rows) == 1
    assert rows[0].id == in_range.id


def test_on_hand_by_product_applies_sign_convention(session, location, product):
    warehouse = _make_warehouse(session, location)
    session.add_all(
        [
            StockMovement(
                product_id=product.id,
                warehouse_id=warehouse.id,
                movement_type=MovementType.INBOUND,
                quantity=100,
                movement_date=date(2026, 1, 1),
            ),
            StockMovement(
                product_id=product.id,
                warehouse_id=warehouse.id,
                movement_type=MovementType.OUTBOUND,
                quantity=30,
                movement_date=date(2026, 1, 2),
            ),
            StockMovement(
                product_id=product.id,
                warehouse_id=warehouse.id,
                movement_type=MovementType.ADJUSTMENT,
                quantity=-5,
                movement_date=date(2026, 1, 3),
            ),
            StockMovement(
                product_id=product.id,
                warehouse_id=warehouse.id,
                movement_type=MovementType.TRANSFER,
                quantity=20,
                movement_date=date(2026, 1, 4),
            ),
        ]
    )
    session.flush()

    repo = StockMovementRepository(session)
    rows = repo.on_hand_by_product()

    assert rows == [(product.sku, product.name, 65)]  # 100 - 30 - 5, transfer excluded


def test_on_hand_by_product_excludes_inactive_products(session, location):
    inactive = Product(
        sku="SKU-INACTIVE",
        name="Retired Product",
        category=ProductCategory.FINISHED_GOOD,
        unit_cost=1.0,
        unit_price=2.0,
        reorder_point=0,
        active=False,
    )
    session.add(inactive)
    session.flush()

    repo = StockMovementRepository(session)
    rows = repo.on_hand_by_product()

    assert rows == []


def test_low_stock_products_returns_products_below_reorder_point(session, location, product):
    warehouse = _make_warehouse(session, location)
    # product.reorder_point == 50 (conftest default); on_hand ends at 20, below reorder point.
    session.add(
        StockMovement(
            product_id=product.id,
            warehouse_id=warehouse.id,
            movement_type=MovementType.INBOUND,
            quantity=20,
            movement_date=date(2026, 1, 1),
        )
    )
    session.flush()

    repo = StockMovementRepository(session)
    low_stock = repo.low_stock_products()

    assert [p.sku for p in low_stock] == [product.sku]


def test_low_stock_products_excludes_products_above_reorder_point(session, location, product):
    warehouse = _make_warehouse(session, location)
    session.add(
        StockMovement(
            product_id=product.id,
            warehouse_id=warehouse.id,
            movement_type=MovementType.INBOUND,
            quantity=100,
            movement_date=date(2026, 1, 1),
        )
    )
    session.flush()

    repo = StockMovementRepository(session)
    low_stock = repo.low_stock_products()

    assert low_stock == []


def test_on_hand_by_category_groups_and_skips_zero_stock(session, location, product):
    warehouse = _make_warehouse(session, location)
    raw = Product(
        sku="SKU-0002",
        name="Steel Coil",
        category=ProductCategory.RAW_MATERIAL,
        unit_cost=5.0,
        unit_price=8.0,
        reorder_point=10,
    )
    empty = Product(
        sku="SKU-0003",
        name="Ghost",
        category=ProductCategory.PACKAGING,
        unit_cost=1.0,
        unit_price=2.0,
        reorder_point=5,
    )
    session.add_all([raw, empty])
    session.flush()
    session.add_all(
        [
            StockMovement(
                product_id=product.id,
                warehouse_id=warehouse.id,
                movement_type=MovementType.INBOUND,
                quantity=30,
                movement_date=date(2026, 1, 5),
            ),
            StockMovement(
                product_id=raw.id,
                warehouse_id=warehouse.id,
                movement_type=MovementType.INBOUND,
                quantity=12,
                movement_date=date(2026, 1, 6),
            ),
        ]
    )
    session.flush()

    repo = StockMovementRepository(session)
    rows = repo.on_hand_by_category()

    assert ("finished_good", "Sample Product", 30) in rows
    assert ("raw_material", "Steel Coil", 12) in rows
    assert all(name != "Ghost" for _, name, _ in rows)
