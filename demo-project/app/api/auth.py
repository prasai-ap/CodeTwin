from fastapi import APIRouter, Header, HTTPException

from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/session")
def create_demo_session(x_demo_user: str | None = Header(default=None)) -> dict[str, object]:
    try:
        user = AuthService().authenticate(x_demo_user)
    except LookupError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    return {"user_id": user.user_id, "name": user.name, "mode": "synthetic_demo"}
