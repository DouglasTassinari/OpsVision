"""Data access for the Inventory module."""
from __future__ import annotations

from datetime import date

from sqlalchemy import case, func, select

from app.database.models.inventory import MovementType, Product, StockMovement, Warehouse
from app.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    model = Product

    def active_products(self) -> list[Product]:
        stmt = select(Product).where(Product.active.is_(True))
        return list(self.session.execute(stmt).scalars().all())


class WarehouseRepository(BaseRepository[Warehouse]):
    model = Warehouse


class StockMovementRepository(BaseRepository[StockMovement]):
    model = StockMovement

    def movements_between(self, start: date, end: date) -> list[StockMovement]:
        stmt = select(StockMovement).where(
            StockMovement.movement_date >= start, StockMovement.movement_date <= end
        )
        return list(self.session.execute(stmt).scalars().all())

    def on_hand_by_product(self) -> list[tuple[str, str, int]]:
        """(sku, name, on_hand) for active products.

        On-hand = inbound - outbound + signed adjustment. TRANSFER movements
        are excluded: in this simplified model they net to zero company-wide
        (stock leaving one warehouse arrives at another).
        """
        signed_quantity = case(
            (StockMovement.movement_type == MovementType.INBOUND, StockMovement.quantity),
            (StockMovement.movement_type == MovementType.OUTBOUND, -StockMovement.quantity),
            (StockMovement.movement_type == MovementType.ADJUSTMENT, StockMovement.quantity),
            else_=0,
        )
        stmt = (
            select(
                Product.sku,
                Product.name,
                func.coalesce(func.sum(signed_quantity), 0).label("on_hand"),
            )
            .select_from(Product)
            .outerjoin(StockMovement, StockMovement.product_id == Product.id)
            .where(Product.active.is_(True))
            .group_by(Product.id)
            .order_by(Product.sku)
        )
        return [(sku, name, int(on_hand)) for sku, name, on_hand in self.session.execute(stmt).all()]

    def on_hand_by_category(self) -> list[tuple[str, str, int]]:
        """(category value, product name, on_hand) for active products with stock > 0."""
        signed_quantity = case(
            (StockMovement.movement_type == MovementType.INBOUND, StockMovement.quantity),
            (StockMovement.movement_type == MovementType.OUTBOUND, -StockMovement.quantity),
            (StockMovement.movement_type == MovementType.ADJUSTMENT, StockMovement.quantity),
            else_=0,
        )
        on_hand = func.coalesce(func.sum(signed_quantity), 0)
        stmt = (
            select(Product.category, Product.name, on_hand.label("on_hand"))
            .select_from(Product)
            .outerjoin(StockMovement, StockMovement.product_id == Product.id)
            .where(Product.active.is_(True))
            .group_by(Product.id)
            .having(on_hand > 0)
            .order_by(Product.category, on_hand.desc())
        )
        return [
            (category.value, name, int(units))
            for category, name, units in self.session.execute(stmt).all()
        ]

    def low_stock_products(self) -> list[Product]:
        """Active products whose computed on-hand is below their reorder point."""
        signed_quantity = case(
            (StockMovement.movement_type == MovementType.INBOUND, StockMovement.quantity),
            (StockMovement.movement_type == MovementType.OUTBOUND, -StockMovement.quantity),
            (StockMovement.movement_type == MovementType.ADJUSTMENT, StockMovement.quantity),
            else_=0,
        )
        on_hand = func.coalesce(func.sum(signed_quantity), 0)
        stmt = (
            select(Product)
            .outerjoin(StockMovement, StockMovement.product_id == Product.id)
            .where(Product.active.is_(True))
            .group_by(Product.id)
            .having(on_hand < Product.reorder_point)
        )
        return list(self.session.execute(stmt).scalars().all())
