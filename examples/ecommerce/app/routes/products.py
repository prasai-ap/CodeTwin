from fastapi import APIRouter

from app.repositories.products import list_products

router = APIRouter(prefix="/products", tags=["products"])


@router.get("")
def read_products() -> list[dict[str, object]]:
    return list_products()
