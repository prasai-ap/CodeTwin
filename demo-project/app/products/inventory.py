"""Deterministic inventory checks used before creating an order."""

from app.models.product import Product


def validate_quantity(product: Product, quantity: int) -> None:
    if quantity < 1:
        raise ValueError("Quantity must be at least one")
    if quantity > product.stock:
        raise ValueError("Requested quantity is unavailable")
