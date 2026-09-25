"""Request and service models for the synthetic shop."""

from pydantic import BaseModel, Field


class PlaceOrderRequest(BaseModel):
    product_id: str
    quantity: int = Field(gt=0, le=100)
