"""Sign-in and sign-out, with a limit on failed attempts.

The same steps as the fastapi-users routes, plus: after too many failures for
one account, or from one address, sign-in is refused for a while even with the
right password. Each sign-in, failure and lockout is written to the audit log.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users.exceptions import UserNotExists
from fastapi_users.router.common import ErrorCode
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import write_audit
from app.core.config import get_settings
from app.db.session import get_db
from app.models.sign_in_failure import SignInFailure
from app.models.user import User
from app.users import UserManager, auth_backend, fastapi_users, get_jwt_strategy, get_user_manager

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()

current_user_token = fastapi_users.authenticator.current_user_token(active=True)


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _failures(db: AsyncSession, user: User | None, ip: str | None, since: datetime) -> tuple[int, int]:
    by_account = 0
    if user is not None:
        by_account = (
            await db.execute(
                select(func.count()).select_from(SignInFailure).where(
                    SignInFailure.user_id == user.id, SignInFailure.created_at >= since
                )
            )
        ).scalar_one()
    by_address = 0
    if ip:
        by_address = (
            await db.execute(
                select(func.count()).select_from(SignInFailure).where(
                    SignInFailure.ip_address == ip, SignInFailure.created_at >= since
                )
            )
        ).scalar_one()
    return by_account, by_address


@router.post("/login", name="auth:cookie.login")
async def login(
    request: Request,
    credentials: OAuth2PasswordRequestForm = Depends(),
    user_manager: UserManager = Depends(get_user_manager),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    window = timedelta(minutes=settings.sign_in_window_minutes)
    since = now - window
    ip = _ip(request)

    try:
        known = await user_manager.get_by_email(credentials.username)
    except UserNotExists:
        known = None

    by_account, by_address = await _failures(db, known, ip, since)
    if by_account >= settings.sign_in_account_limit or by_address >= settings.sign_in_address_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many tries. Wait {settings.sign_in_window_minutes} minutes and try again",
        )

    user = await user_manager.authenticate(credentials)
    if user is None or not user.is_active:
        db.add(SignInFailure(user_id=known.id if known else None, ip_address=ip))
        await write_audit(
            db,
            actor_id=None,
            action="user.sign_in_failed",
            object_type="user",
            object_id=str(known.id) if known else None,
            detail=None,
            ip_address=ip,
        )
        # One lockout entry when a limit is first reached, not one per refusal.
        if (known and by_account + 1 == settings.sign_in_account_limit) or (
            by_address + 1 == settings.sign_in_address_limit
        ):
            await write_audit(
                db,
                actor_id=None,
                action="user.sign_in_locked",
                object_type="user",
                object_id=str(known.id) if known else None,
                detail={"by": "account" if known and by_account + 1 == settings.sign_in_account_limit else "address"},
                ip_address=ip,
            )
        # Old rows are no longer counted, so they're cleared as we go.
        await db.execute(delete(SignInFailure).where(SignInFailure.created_at < since))
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ErrorCode.LOGIN_BAD_CREDENTIALS)

    # A correct password starts the account's count again.
    await db.execute(
        delete(SignInFailure).where((SignInFailure.user_id == user.id) | (SignInFailure.created_at < since))
    )
    await write_audit(
        db,
        actor_id=user.id,
        action="user.signed_in",
        object_type="user",
        object_id=str(user.id),
        detail=None,
        ip_address=ip,
    )
    await db.commit()
    response = await auth_backend.login(get_jwt_strategy(), user)
    await user_manager.on_after_login(user, request, response)
    return response


@router.post("/logout", name="auth:cookie.logout")
async def logout(user_token: tuple[User, str] = Depends(current_user_token)):
    user, token = user_token
    return await auth_backend.logout(get_jwt_strategy(), user, token)
