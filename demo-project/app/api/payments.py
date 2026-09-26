from fastapi import APIRouter, Header, HTTPException

from app.services.auth_service import AuthService
from app.services.payments_service import PaymentsService

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/{payment_id}")
def read_payment(payment_id: str, x_demo_user: str | None = Header(default=None)) -> dict[str, object]:
    try:
        user = AuthService().authenticate(x_demo_user)
    except LookupError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    payment = PaymentsService().get_for_user(payment_id, user.user_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return {"payment": payment}


@router.post("/{payment_id}/complete")
def complete_payment(
    payment_id: str,
    x_demo_user: str | None = Header(default=None),
) -> dict[str, object]:
    try:
        user = AuthService().authenticate(x_demo_user)
        payment, order = PaymentsService().complete(payment_id, user.user_id)
    except LookupError as error:
        if "identity" in str(error):
            raise HTTPException(status_code=401, detail=str(error)) from error
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"payment": payment, "order": order}
