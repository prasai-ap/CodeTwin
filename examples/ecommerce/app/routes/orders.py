from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.orders.service import OrdersService
from app.repositories.orders import OrdersRepository

router = APIRouter(prefix="/orders", tags=["orders"])


class CheckoutRequest(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)


@router.post("/checkout")
def checkout(
    request: CheckoutRequest,
    x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
) -> dict[str, object]:
    try:
        order, payment = OrdersService().checkout(x_demo_user, request.product_id, request.quantity)
    except PermissionError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"order": order, "payment": payment}


@router.get("/{order_id}")
def read_order(order_id: str) -> dict[str, object]:
    order = OrdersRepository().get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"order": order}
