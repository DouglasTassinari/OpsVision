"""Inventory module service — orchestrates repositories + domain rules.

This is the only layer the Streamlit pages talk to for Inventory data;
pages never import repositories or models directly.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.metrics import track
from app.database.models.inventory import MovementType, Product, StockMovement
from app.domain import inventory_rules
from app.repositories.inventory_repository import (
    ProductRepository,
    StockMovementRepository,
    WarehouseRepository,
)

logger = get_logger("services.inventory")


class InventoryService:
    def __init__(self, session: Session):
        self.session = session
        self.products = ProductRepository(session)
        self.warehouses = WarehouseRepository(session)
        self.movements = StockMovementRepository(session)

    @track("inventory.record_movement")
    def record_movement(
        self,
        product_id: int,
        warehouse_id: int,
        movement_type: MovementType,
        quantity: int,
        movement_date: date,
        reference_note: str | None = None,
    ) -> StockMovement:
        inventory_rules.validate_movement(movement_type, quantity)

        movement = StockMovement(
            product_id=product_id,
            warehouse_id=warehouse_id,
            movement_type=movement_type,
            quantity=quantity,
            movement_date=movement_date,
            reference_note=reference_note,
        )
        self.movements.add(movement)
        logger.info(
            "Recorded %s movement of %d units for product %s", movement_type.value, quantity, product_id
        )
        return movement

    @track("inventory.on_hand_report")
    def on_hand_report(self) -> list[tuple[str, str, int]]:
        return self.movements.on_hand_by_product()

    @track("inventory.on_hand_by_category")
    def on_hand_by_category(self) -> list[tuple[str, str, int]]:
        return self.movements.on_hand_by_category()

    @track("inventory.low_stock_alert")
    def low_stock_alert(self) -> list[Product]:
        return self.movements.low_stock_products()
