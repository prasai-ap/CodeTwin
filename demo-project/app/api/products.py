from fastapi import APIRouter, HTTPException

from app.services.products_service import ProductsService

router = APIRouter(prefix="/products", tags=["products"])


@router.get("")
def list_products() -> dict[str, object]:
    return {"products": ProductsService().list()}


@router.get("/{product_id}")
def read_product(product_id: str) -> dict[str, object]:
    product = ProductsService().get(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"product": product}
