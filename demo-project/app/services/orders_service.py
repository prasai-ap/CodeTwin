from app.models.order import Order, OrderStatus
from app.models.payment import Payment
from app.orders.lifecycle import complete_order
from app.products.inventory import validate_quantity
from app.repositories.orders import OrdersRepository
from app.repositories.payments import PaymentsRepository
from app.repositories.products import ProductsRepository
from app.services.auth_service import AuthService
from app.services.notifications_service import NotificationsService


class OrdersService:
    def __init__(
        self,
        authentication: AuthService | None = None,
        products: ProductsRepository | None = None,
        orders: OrdersRepository | None = None,
        payments: PaymentsRepository | None = None,
        notifications: NotificationsService | None = None,
    ) -> None:
        self.authentication = authentication or AuthService()
        self.products = products or ProductsRepository()
        self.orders = orders or OrdersRepository()
        self.payments = payments or PaymentsRepository()
        self.notifications = notifications or NotificationsService()

    def place_order(self, user_id: str | None, product_id: str, quantity: int) -> tuple[Order, Payment]:
        user = self.authentication.authenticate(user_id)
        product = self.products.get(product_id)
        if product is None:
            raise LookupError("Product not found")
        validate_quantity(product, quantity)

        total_cents = product.unit_price_cents * quantity
        order = self.orders.create(user.user_id, product.product_id, quantity, total_cents)
        self.products.reserve(product.product_id, quantity)
        payment = self.payments.create(order.order_id, user.user_id, total_cents)
        return order, payment

    def get_for_user(self, order_id: str, user_id: str) -> Order | None:
        order = self.orders.get(order_id)
        return order if order is not None and order.user_id == user_id else None

    def validate_payment(self, payment: Payment) -> Order:
        order = self.orders.get(payment.order_id)
        if order is None or order.user_id != payment.user_id or order.total_cents != payment.amount_cents:
            raise LookupError("Payment does not match an order")
        if order.status is not OrderStatus.PENDING:
            raise ValueError("Order is not pending")
        return order

    def complete_for_payment(self, payment: Payment) -> Order:
        order = self.validate_payment(payment)
        completed = self.orders.save(complete_order(order))
        self.notifications.send_payment_completed(completed)
        return completed
