from app import database


def list_products() -> list[dict[str, object]]:
    return list(database.state["products"].values())


def get_product(product_id: str) -> dict[str, object] | None:
    return database.state["products"].get(product_id)


def reserve_stock(product_id: str, quantity: int) -> bool:
    product = get_product(product_id)
    if product is None or product["stock"] < quantity:
        return False
    product["stock"] -= quantity
    return True
