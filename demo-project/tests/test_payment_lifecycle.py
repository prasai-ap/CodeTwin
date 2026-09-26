from app.models.payment import Payment, PaymentStatus
from app.payments.lifecycle import authorize_payment, complete_payment


def test_payment_lifecycle_moves_through_authorized_before_completed():
    pending = Payment("payment-demo", "order-demo", "user-ada", 8900)

    authorized = authorize_payment(pending)
    completed = complete_payment(authorized)

    assert pending.status is PaymentStatus.PENDING
    assert authorized.status is PaymentStatus.AUTHORIZED
    assert completed.status is PaymentStatus.COMPLETED
