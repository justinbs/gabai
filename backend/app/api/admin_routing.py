from fastapi import APIRouter, Depends, HTTPException, Request as HTTPRequest, status as http_status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit import write_audit
from app.db.session import get_db
from app.models.routing_rule import RoutingRule
from app.models.user import Role, User
from app.schemas.routing import RoutingRuleRead, RoutingRulesReplace
from app.users import require_role

router = APIRouter(prefix="/api/admin/routing-rules", tags=["admin"])


def _load_options():
    return (selectinload(RoutingRule.category), selectinload(RoutingRule.staff))


@router.get("", response_model=list[RoutingRuleRead])
async def list_routing_rules(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.admin)),
):
    result = await db.execute(select(RoutingRule).options(*_load_options()))
    return result.scalars().all()


@router.put("", response_model=list[RoutingRuleRead])
async def replace_routing_rules(
    payload: RoutingRulesReplace,
    http_request: HTTPRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.admin)),
):
    category_ids = [rule.category_id for rule in payload.rules]
    if len(category_ids) != len(set(category_ids)):
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="More than one active rule for the same category.",
        )

    await db.execute(update(RoutingRule).where(RoutingRule.is_active.is_(True)).values(is_active=False))

    for rule_in in payload.rules:
        db.add(RoutingRule(category_id=rule_in.category_id, staff_id=rule_in.staff_id, is_active=True))

    ip = http_request.client.host if http_request.client else None
    await write_audit(
        db,
        actor_id=user.id,
        action="routing_rules.replaced",
        object_type="routing_rules",
        object_id=None,
        detail={"rules": len(payload.rules)},
        ip_address=ip,
    )

    await db.commit()

    result = await db.execute(
        select(RoutingRule).where(RoutingRule.is_active.is_(True)).options(*_load_options())
    )
    return result.scalars().all()