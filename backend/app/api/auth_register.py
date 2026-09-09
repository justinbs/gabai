from fastapi import APIRouter, Depends, HTTPException, status as http_status
from fastapi_users.exceptions import InvalidPasswordException, UserAlreadyExists

from app.schemas.user import UserCreate, UserRead
from app.users import UserManager, get_user_manager

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=201)
async def register(
    payload: UserCreate,
    user_manager: UserManager = Depends(get_user_manager),
):
    try:
        user = await user_manager.create(payload, safe=True)
    except UserAlreadyExists:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )
    except InvalidPasswordException as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.reason,
        )
    return user