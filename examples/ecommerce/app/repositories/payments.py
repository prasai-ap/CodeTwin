from dataclasses import replace

from app.database import db
from app.models import Payment, PaymentStatus


class PaymentsRepository:
    def create(self, order_id: str, user_id: str, amount_cents: int) -> Payment:
        db.payment_sequence += 1
        payment = Payment(f"payment-{db.payment_sequence}", order_id, user_id, amount_cents)
        db.payments[payment.payment_id] = payment
        return payment

    def get(self, payment_id: str) -> Payment | None:
        return db.payments.get(payment_id)

    def transition(self, payment_id: str, status: PaymentStatus) -> tuple[Payment, Payment]:
        previous = db.payments[payment_id]
        updated = replace(previous, status=status)
        db.payments[payment_id] = updated
        return previous, updated
