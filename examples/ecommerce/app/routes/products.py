from fastapi import APIRouter

from app.products.service import ProductsService

router = APIRouter(prefix="/products", tags=["products"])


@router.get("")
def list_products() -> dict[str, object]:
    return {"products": ProductsService().list_products()}
