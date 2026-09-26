from app.auth.service import AuthenticationService
from app.models import Order, Payment
from app.payments.service import PaymentService
from app.repositories.orders import OrdersRepository
from app.repositories.products import ProductsRepository


class OrdersService:
    def __init__(
        self,
        authentication: AuthenticationService | None = None,
        products: ProductsRepository | None = None,
        orders: OrdersRepository | None = None,
        payments: PaymentService | None = None,
    ) -> None:
        self.authentication = authentication or AuthenticationService()
        self.products = products or ProductsRepository()
        self.orders = orders or OrdersRepository()
        self.payments = payments or PaymentService()

    def checkout(self, user_id: str | None, product_id: str, quantity: int) -> tuple[Order, Payment]:
        user = self.authentication.authenticate_demo_user(user_id)
        product = self.products.get(product_id)
        if product is None:
            raise LookupError("Product not found")
        if quantity < 1 or product.stock < quantity:
            raise ValueError("Requested quantity is unavailable")

        total_cents = product.unit_price_cents * quantity
        order = self.orders.create(user.user_id, product.product_id, quantity, total_cents)
        self.products.reserve(product_id, quantity)
        payment = self.payments.create(order.order_id, user.user_id, total_cents)
        completed_payment = self.payments.capture(payment.payment_id)
        completed_order = self.orders.complete(order.order_id)
        return completed_order, completed_payment
