from fastapi import APIRouter, Depends, HTTPException

from app.auth.service import require_user
from app.models import PlaceOrderRequest
from app.orders.service import ProductUnavailable, place_order
from app.repositories.orders import get_order

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("")
def create_order(
    request: PlaceOrderRequest,
    user: dict[str, str] = Depends(require_user),
) -> dict[str, object]:
    try:
        return place_order(user["id"], request.product_id, request.quantity)
    except ProductUnavailable as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/{order_id}")
def read_order(order_id: str, user: dict[str, str] = Depends(require_user)) -> dict[str, object]:
    order = get_order(order_id)
    if order is None or order["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
