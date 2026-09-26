from dataclasses import replace

from app.database import db
from app.models import Product


class ProductsRepository:
    def list(self) -> list[Product]:
        return sorted(db.products.values(), key=lambda product: product.product_id)

    def get(self, product_id: str) -> Product | None:
        return db.products.get(product_id)

    def reserve(self, product_id: str, quantity: int) -> Product:
        product = self.get(product_id)
        if product is None:
            raise LookupError("Product not found")
        if quantity < 1 or product.stock < quantity:
            raise ValueError("Requested quantity is unavailable")
        updated = replace(product, stock=product.stock - quantity)
        db.products[product_id] = updated
        return updated
