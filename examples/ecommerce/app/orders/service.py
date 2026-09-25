"""Order checkout orchestration."""

from app.notifications.service import send_order_confirmation
from app.payments.service import capture_payment
from app.repositories import orders, products


class ProductUnavailable(ValueError):
    """Raised when a product is missing or has insufficient stock."""


def place_order(user_id: str, product_id: str, quantity: int) -> dict[str, object]:
    product = products.get_product(product_id)
    if product is None or product["stock"] < quantity:
        raise ProductUnavailable("Product is unavailable in the requested quantity")

    total_cents = int(product["price_cents"]) * quantity
    order = orders.create_order(user_id, product_id, quantity, total_cents)
    if not products.reserve_stock(product_id, quantity):
        raise ProductUnavailable("Product stock changed during checkout")

    payment = capture_payment(order["id"], total_cents)
    orders.update_order(order["id"], status="paid", payment_id=payment["id"])
    send_order_confirmation(user_id, order["id"])
    return orders.get_order(order["id"])
