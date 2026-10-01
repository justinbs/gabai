"""Admin edits to categories: name, description, on or off.

No create or delete, since the classifier only knows the existing seven. The
slug is the label the model returns, so it can't be changed.
"""

from fastapi import APIRouter, Depends, HTTPException, Request as HTTPRequest, status as http_status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import write_audit
from app.db.session import get_db
from app.models.category import Category
from app.models.user import Role, User
from app.schemas.category import CategoryRead, CategoryUpdate
from app.users import require_role

router = APIRouter(prefix="/api/admin/categories", tags=["admin"])


@router.get("", response_model=list[CategoryRead])
async def list_all_categories(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(Role.admin)),
):
    return (await db.execute(select(Category).order_by(Category.id))).scalars().all()


@router.patch("/{category_id}", response_model=CategoryRead)
async def update_category(
    category_id: int,
    payload: CategoryUpdate,
    http_request: HTTPRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(Role.admin)),
):
    category = await db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found")

    sent = payload.model_dump(exclude_unset=True)
    if "name" in sent and sent["name"] is None:
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name can't be empty")
    if "is_active" in sent and sent["is_active"] is None:
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Say whether it's on or off")

    if sent.get("is_active") is False and category.is_active:
        others_on = (
            await db.execute(
                select(func.count()).select_from(Category).where(
                    Category.is_active.is_(True), Category.id != category.id
                )
            )
        ).scalar_one()
        if others_on == 0:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="At least one category has to stay on",
            )

    changed = {}
    for field in ("name", "description", "is_active"):
        if field not in sent:
            continue
        value = sent[field]
        if isinstance(value, str):
            value = value.strip() or None
        if field == "name" and not value:
            raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name can't be empty")
        if getattr(category, field) != value:
            setattr(category, field, value)
            changed[field] = value

    if changed:
        await write_audit(
            db,
            actor_id=admin.id,
            action="category.updated",
            object_type="category",
            object_id=str(category.id),
            detail={"slug": category.slug, **changed},
            ip_address=http_request.client.host if http_request.client else None,
        )
        await db.commit()
        await db.refresh(category)
    return category
