from fastapi import APIRouter, Depends, HTTPException

from app.auth.service import require_user
from app.repositories.orders import get_order
from app.repositories.payments import get_payment

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/{payment_id}")
def read_payment(payment_id: str, user: dict[str, str] = Depends(require_user)) -> dict[str, object]:
    payment = get_payment(payment_id)
    order = get_order(payment["order_id"]) if payment else None
    if payment is None or order is None or order["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment
