import uuid

from fastapi import Depends, HTTPException, status
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.exceptions import InvalidPasswordException
from fastapi_users.authentication import AuthenticationBackend, CookieTransport, JWTStrategy
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app import mail, passwords
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import ApprovalStatus, Role, User

settings = get_settings()


async def get_user_db(session: AsyncSession = Depends(get_db)):
    yield SQLAlchemyUserDatabase(session, User)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.secret_key
    verification_token_secret = settings.secret_key
    # Residents may not check email the same day. Reset links stay at the
    # library's hour, and they die anyway once the password changes.
    verification_token_lifetime_seconds = 60 * 60 * 24

    async def on_after_register(self, user: User, request=None) -> None:
        await self.request_verify(user, request)

    async def on_after_request_verify(self, user: User, token: str, request=None) -> None:
        if mail.allowed("verify", user.email):
            mail.send_later(user.email, *mail.verify_email(user.full_name, mail.link("verify-email", token)))

    async def on_after_forgot_password(self, user: User, token: str, request=None) -> None:
        # An unconfirmed address could be a typo that belongs to someone else,
        # and this link takes over the account. They can still use the office.
        if user.is_verified and mail.allowed("reset", user.email):
            mail.send_later(user.email, *mail.reset_email(user.full_name, mail.link("reset-password", token)))

    async def on_after_reset_password(self, user: User, request=None) -> None:
        # They chose this one, so any temporary password is gone.
        if user.must_change_password:
            await self.user_db.update(user, {"must_change_password": False})

    async def validate_password(self, password: str, user) -> None:
        reason = passwords.problem(password, getattr(user, "email", None))
        if reason:
            raise InvalidPasswordException(reason=reason)


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


cookie_transport = CookieTransport(
    cookie_name="gabai_session",
    cookie_max_age=3600 * 24 * 7,
    cookie_secure=settings.environment != "development",
    cookie_samesite="lax",
)


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.secret_key, lifetime_seconds=3600 * 24 * 7)


auth_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

# Signed in, even while pending approval or on a temporary password. Only /me,
# password change and logout use this one.
current_signed_in_user = fastapi_users.current_user(active=True)


# What every other route uses. Restricting the default rather than opting routes
# in means a new router can't forget the check.
async def current_active_user(user: User = Depends(current_signed_in_user)) -> User:
    if user.approval_status != ApprovalStatus.approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Waiting for the barangay to approve your account",
        )
    if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Change your temporary password first",
        )
    return user


def require_role(*roles: Role):
    async def checker(user: User = Depends(current_active_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed for this role")
        return user

    return checker