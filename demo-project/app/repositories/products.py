from dataclasses import replace

from app.database import db
from app.models.product import Product


class ProductsRepository:
    def get(self, product_id: str) -> Product | None:
        return db.products.get(product_id)

    def list(self) -> list[Product]:
        return list(db.products.values())

    def reserve(self, product_id: str, quantity: int) -> Product:
        product = db.products[product_id]
        if quantity > product.stock:
            raise ValueError("Requested quantity is unavailable")
        updated = replace(product, stock=product.stock - quantity)
        db.products[product_id] = updated
        return updated
