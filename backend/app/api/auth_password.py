from fastapi import APIRouter, Depends, HTTPException, status as http_status
from fastapi_users.exceptions import InvalidPasswordException

from app.models.user import User
from app.schemas.user import PasswordChange
from app.users import UserManager, current_signed_in_user, get_user_manager

router = APIRouter(prefix="/api/auth", tags=["auth"])


# No audit row. Changing your own password crosses no privilege boundary.
@router.put("/password", status_code=204)
async def change_password(
    payload: PasswordChange,
    user: User = Depends(current_signed_in_user),
    user_manager: UserManager = Depends(get_user_manager),
):
    verified, _ = user_manager.password_helper.verify_and_update(
        payload.current_password, user.hashed_password
    )
    if not verified:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="That's not your current password",
        )

    # Otherwise a temporary password could be "changed" to itself, and the admin
    # who issued it would still know it.
    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="That's your current one, pick a new one",
        )

    try:
        await user_manager.validate_password(payload.new_password, user)
    except InvalidPasswordException as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.reason,
        )

    await user_manager.user_db.update(
        user,
        {
            "hashed_password": user_manager.password_helper.hash(payload.new_password),
            "must_change_password": False,
        },
    )
