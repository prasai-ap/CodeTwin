from app.models.order import Order
from app.models.payment import Payment
from app.payments.lifecycle import authorize_payment, complete_payment
from app.repositories.payments import PaymentsRepository
from app.services.orders_service import OrdersService


class PaymentsService:
    def __init__(
        self,
        payments: PaymentsRepository | None = None,
        orders: OrdersService | None = None,
    ) -> None:
        self.payments = payments or PaymentsRepository()
        self.orders = orders or OrdersService()

    def get_for_user(self, payment_id: str, user_id: str) -> Payment | None:
        payment = self.payments.get(payment_id)
        return payment if payment is not None and payment.user_id == user_id else None

    def complete(self, payment_id: str, user_id: str) -> tuple[Payment, Order]:
        payment = self.get_for_user(payment_id, user_id)
        if payment is None:
            raise LookupError("Payment not found")
        self.orders.validate_payment(payment)
        authorized_payment = self.payments.save(authorize_payment(payment))
        self.orders.on_payment_transition(payment, authorized_payment)

        completed_payment = self.payments.save(complete_payment(authorized_payment))
        completed_order = self.orders.on_payment_transition(authorized_payment, completed_payment)
        return completed_payment, completed_order
