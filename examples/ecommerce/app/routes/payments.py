from fastapi import APIRouter, HTTPException

from app.payments.service import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/{payment_id}")
def read_payment(payment_id: str) -> dict[str, object]:
    payment = PaymentService().get(payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return {"payment": payment}
