from app.models import Product
from app.repositories.products import ProductsRepository


class ProductsService:
    def __init__(self, products: ProductsRepository | None = None) -> None:
        self.products = products or ProductsRepository()

    def list_products(self) -> list[Product]:
        return self.products.list()
