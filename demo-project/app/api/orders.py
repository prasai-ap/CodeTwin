from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.services.orders_service import OrdersService

router = APIRouter(prefix="/orders", tags=["orders"])


class PlaceOrderRequest(BaseModel):
    product_id: str
    quantity: int = Field(ge=1, le=20)


@router.post("")
def place_order(
    request: PlaceOrderRequest,
    x_demo_user: str | None = Header(default=None),
) -> dict[str, object]:
    try:
        order, payment = OrdersService().place_order(x_demo_user, request.product_id, request.quantity)
    except LookupError as error:
        status = 401 if "identity" in str(error) else 404
        raise HTTPException(status_code=status, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"order": order, "payment": payment}


@router.get("/{order_id}")
def read_order(order_id: str, x_demo_user: str | None = Header(default=None)) -> dict[str, object]:
    orders = OrdersService()
    try:
        user = orders.authentication.authenticate(x_demo_user)
    except LookupError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    order = orders.get_for_user(order_id, user.user_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"order": order}
