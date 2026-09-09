import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status as http_status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import UPLOAD_DIR
from app.db.session import get_db
from app.models.attachment import Attachment
from app.models.request import Request
from app.models.user import User
from app.scoping import request_scope_filter
from app.schemas.attachment import AttachmentRead
from app.users import current_active_user

router = APIRouter(prefix="/api/requests/{request_id}/attachments", tags=["requests"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
MAX_FILE_BYTES = 5 * 1024 * 1024


@router.post("", response_model=AttachmentRead, status_code=201)
async def upload_attachment(
    request_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_active_user),
):
    request = (await db.execute(select(Request).where(Request.id == request_id))).scalar_one_or_none()
    if request is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found")

    # Narrower than general read-scope on purpose: only the owning citizen or
    # the staff member currently assigned may attach a file.
    allowed = request.citizen_id == user.id or request.assigned_staff_id == user.id
    if not allowed:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Not allowed")

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=http_status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="File type not allowed"
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds 5 MB"
        )

    extension = Path(file.filename or "").suffix
    stored_name = f"{uuid.uuid4().hex}{extension}"
    (UPLOAD_DIR / stored_name).write_bytes(contents)

    attachment = Attachment(
        request_id=request.id,
        filename=file.filename or stored_name,
        stored_path=stored_name,
        mime_type=file.content_type,
        size_bytes=len(contents),
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return attachment


@router.get("/{attachment_id}")
async def download_attachment(
    request_id: int,
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_active_user),
):
    query = select(Request).where(Request.id == request_id)
    scope = request_scope_filter(user)
    if scope is not None:
        query = query.where(scope)
    request = (await db.execute(query)).scalar_one_or_none()
    if request is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found")

    attachment = (
        await db.execute(
            select(Attachment).where(Attachment.id == attachment_id, Attachment.request_id == request_id)
        )
    ).scalar_one_or_none()
    if attachment is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found")

    return FileResponse(
        UPLOAD_DIR / attachment.stored_path,
        media_type=attachment.mime_type,
        filename=attachment.filename,
    )