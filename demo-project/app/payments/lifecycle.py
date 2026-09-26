"""Payment state transitions in the baseline: pending directly to completed."""

from dataclasses import replace

from app.models.payment import Payment, PaymentStatus


def complete_payment(payment: Payment) -> Payment:
    if payment.status is not PaymentStatus.PENDING:
        raise ValueError("Only pending payments can be completed")
    return replace(payment, status=PaymentStatus.COMPLETED)
