from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request as HTTPRequest, status as http_status
from fastapi_users.exceptions import InvalidPasswordException, UserAlreadyExists
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import write_audit
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import TermsAcceptance, UserCreate, UserRead
from app.terms import TERMS_VERSION
from app.users import UserManager, current_signed_in_user, get_user_manager

router = APIRouter(prefix="/api/auth", tags=["auth"])

OUTDATED = {"code": "TERMS_OUTDATED"}


@router.post("/register", response_model=UserRead, status_code=201)
async def register(
    payload: UserCreate,
    http_request: HTTPRequest,
    db: AsyncSession = Depends(get_db),
    user_manager: UserManager = Depends(get_user_manager),
):
    # Reject an outdated terms version.
    if payload.terms_version != TERMS_VERSION:
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail=OUTDATED)
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
    await _record_acceptance(db, user, http_request)
    await db.commit()
    return user


@router.post("/terms", response_model=UserRead)
async def accept_terms(
    payload: TermsAcceptance,
    http_request: HTTPRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_signed_in_user),
):
    if payload.version != TERMS_VERSION:
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail=OUTDATED)
    user.terms_accepted_version = TERMS_VERSION
    user.terms_accepted_at = datetime.now(timezone.utc)
    await _record_acceptance(db, user, http_request)
    await db.commit()
    await db.refresh(user)
    return user


async def _record_acceptance(db: AsyncSession, user: User, http_request: HTTPRequest) -> None:
    # The audit log keeps the history of accepted versions.
    await write_audit(
        db,
        actor_id=user.id,
        action="user.terms_accepted",
        object_type="user",
        object_id=str(user.id),
        detail={"version": TERMS_VERSION},
        ip_address=http_request.client.host if http_request.client else None,
    )
