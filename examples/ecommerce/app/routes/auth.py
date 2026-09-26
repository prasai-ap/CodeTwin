from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.auth.service import AuthenticationService

router = APIRouter(prefix="/auth", tags=["authentication"])


class DemoSessionRequest(BaseModel):
    user_id: str


@router.post("/session")
def create_demo_session(request: DemoSessionRequest) -> dict[str, object]:
    try:
        user = AuthenticationService().authenticate_demo_user(request.user_id)
    except PermissionError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    return {"authenticated": True, "user": user}
