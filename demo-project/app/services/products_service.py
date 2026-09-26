from app.models.product import Product
from app.products.inventory import validate_quantity
from app.repositories.products import ProductsRepository


class ProductsService:
    def __init__(self, products: ProductsRepository | None = None) -> None:
        self.products = products or ProductsRepository()

    def get(self, product_id: str) -> Product | None:
        return self.products.get(product_id)

    def list(self) -> list[Product]:
        return self.products.list()

    def check_availability(self, product: Product, quantity: int) -> None:
        validate_quantity(product, quantity)
