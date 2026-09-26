"""Payment state transitions for the revised authorization workflow."""

from dataclasses import replace

from app.models.payment import Payment, PaymentStatus


def authorize_payment(payment: Payment) -> Payment:
    if payment.status is not PaymentStatus.PENDING:
        raise ValueError("Only pending payments can be authorized")
    return replace(payment, status=PaymentStatus.AUTHORIZED)


def complete_payment(payment: Payment) -> Payment:
    if payment.status is not PaymentStatus.AUTHORIZED:
        raise ValueError("Only authorized payments can be completed")
    return replace(payment, status=PaymentStatus.COMPLETED)
