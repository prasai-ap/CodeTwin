from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    product_id: str
    name: str
    unit_price_cents: int
    stock: int
    category: str
