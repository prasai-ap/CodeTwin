from app.database import db
from app.models.payment import Payment


class PaymentsRepository:
    def create(self, order_id: str, user_id: str, amount_cents: int) -> Payment:
        db.payment_sequence += 1
        payment = Payment(f"payment-{db.payment_sequence:04d}", order_id, user_id, amount_cents)
        db.payments[payment.payment_id] = payment
        return payment

    def get(self, payment_id: str) -> Payment | None:
        return db.payments.get(payment_id)

    def save(self, payment: Payment) -> Payment:
        db.payments[payment.payment_id] = payment
        return payment
