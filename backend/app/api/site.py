"""Site details, colour and logo. Reading is public; changes are admin only."""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request as HTTPRequest, UploadFile, status as http_status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import write_audit
from app.core.storage import UPLOAD_DIR
from app.db.session import get_db
from app.models.site_settings import SiteSettings
from app.models.user import Role, User
from app.schemas.site import SiteSettingsRead, SiteSettingsUpdate
from app.terms import TERMS_VERSION
from app.users import require_role

router = APIRouter(tags=["site"])

LOGO_DIR = UPLOAD_DIR / "site"
MAX_LOGO_BYTES = 1024 * 1024
# Checked against the file's first bytes, not just the declared type.
SIGNATURES = {
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/webp": (b"RIFF",),
}
EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
# Fields copied into the audit entry.
PUBLIC_FIELDS = ("barangay_name", "place", "address", "hotline", "office_hours", "theme")


async def _settings(db: AsyncSession) -> SiteSettings:
    row = await db.get(SiteSettings, 1)
    if row is None:
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Site settings missing")
    return row


def _read(row: SiteSettings) -> SiteSettingsRead:
    return SiteSettingsRead(
        barangay_name=row.barangay_name,
        place=row.place,
        address=row.address,
        hotline=row.hotline,
        office_hours=row.office_hours,
        theme=row.theme,
        logo_version=row.logo_version,
        terms_version=TERMS_VERSION,
        updated_at=row.updated_at,
    )


def _ip(http_request: HTTPRequest) -> str | None:
    return http_request.client.host if http_request.client else None


@router.get("/api/site", response_model=SiteSettingsRead)
async def get_site(db: AsyncSession = Depends(get_db)):
    return _read(await _settings(db))


@router.get("/api/site/logo")
async def get_logo(db: AsyncSession = Depends(get_db)):
    row = await _settings(db)
    if not row.logo_path or not (UPLOAD_DIR / row.logo_path).is_file():
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found")
    return FileResponse(UPLOAD_DIR / row.logo_path)


@router.patch("/api/admin/site", response_model=SiteSettingsRead)
async def update_site(
    payload: SiteSettingsUpdate,
    http_request: HTTPRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(Role.admin)),
):
    row = await _settings(db)
    sent = payload.model_dump(exclude_unset=True)
    for required in ("barangay_name", "place", "theme"):
        value = sent.get(required, "set")
        if value is None or (isinstance(value, str) and not value.strip()):
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{required.replace('_', ' ').capitalize()} can't be empty",
            )
    changed = {}
    for field in PUBLIC_FIELDS:
        if field not in sent:
            continue
        value = sent[field]
        if isinstance(value, str):
            value = value.strip() or None
        if getattr(row, field) != value:
            setattr(row, field, value)
            changed[field] = value
    if changed:
        await write_audit(
            db,
            actor_id=admin.id,
            action="site.updated",
            object_type="site",
            object_id="1",
            detail=changed,
            ip_address=_ip(http_request),
        )
        await db.commit()
        await db.refresh(row)
    return _read(row)


@router.put("/api/admin/site/logo", response_model=SiteSettingsRead)
async def upload_logo(
    http_request: HTTPRequest,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(Role.admin)),
):
    contents = await file.read(MAX_LOGO_BYTES + 1)
    if len(contents) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="The logo must be 1 MB or smaller")
    kind = file.content_type
    if kind not in SIGNATURES or not contents.startswith(SIGNATURES[kind]) or (
        kind == "image/webp" and contents[8:12] != b"WEBP"
    ):
        raise HTTPException(
            status_code=http_status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload a PNG, JPEG or WebP image",
        )

    row = await _settings(db)
    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    version = uuid.uuid4().hex
    stored = f"site/logo-{version}{EXTENSIONS[kind]}"
    (UPLOAD_DIR / stored).write_bytes(contents)
    previous = row.logo_path
    row.logo_path = stored
    row.logo_version = version
    await write_audit(
        db,
        actor_id=admin.id,
        action="site.logo_changed",
        object_type="site",
        object_id="1",
        detail={"size_bytes": len(contents), "type": kind},
        ip_address=_ip(http_request),
    )
    await db.commit()
    await db.refresh(row)
    # Delete the old file after the commit.
    _remove(previous)
    return _read(row)


@router.delete("/api/admin/site/logo", response_model=SiteSettingsRead)
async def remove_logo(
    http_request: HTTPRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(Role.admin)),
):
    row = await _settings(db)
    previous = row.logo_path
    if previous:
        row.logo_path = None
        row.logo_version = None
        await write_audit(
            db,
            actor_id=admin.id,
            action="site.logo_removed",
            object_type="site",
            object_id="1",
            ip_address=_ip(http_request),
        )
        await db.commit()
        await db.refresh(row)
        _remove(previous)
    return _read(row)


def _remove(stored: str | None) -> None:
    if stored:
        (UPLOAD_DIR / stored).unlink(missing_ok=True)
