from app.models import Payment, PaymentStatus
from app.notifications.service import NotificationsService
from app.repositories.payments import PaymentsRepository


class PaymentService:
    def __init__(
        self,
        payments: PaymentsRepository | None = None,
        notifications: NotificationsService | None = None,
    ) -> None:
        self.payments = payments or PaymentsRepository()
        self.notifications = notifications or NotificationsService()

    def create(self, order_id: str, user_id: str, amount_cents: int) -> Payment:
        return self.payments.create(order_id, user_id, amount_cents)

    def get(self, payment_id: str) -> Payment | None:
        return self.payments.get(payment_id)

    def capture(self, payment_id: str) -> Payment:
        previous, completed = self.payments.transition(payment_id, PaymentStatus.COMPLETED)
        self.notifications.on_payment_transition(previous, completed)
        return completed
