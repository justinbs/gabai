"""Create the first admin, and optionally the demo accounts.

Run once after `alembic upgrade head`:

    python -m app.seed

Registration only ever makes citizens and every admin route needs an existing
admin, so without this a fresh database has no way in.
"""

import asyncio
import sys

from fastapi_users.password import PasswordHelper
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.eventloop import use_selector_loop_on_windows
from app.db.session import AsyncSessionLocal
from app.models.category import Category
from app.models.routing_rule import RoutingRule
from app.models.user import ApprovalStatus, Role, User

settings = get_settings()
password_helper = PasswordHelper()

# Same four accounts as the accepted prototype, so the evaluation instruments and
# the interface screens keep naming people who exist.
DEMO_ACCOUNTS = [
    ("maria.santos@example.com", "Maria Santos", Role.citizen),
    ("ramon.delgado@example.com", "Ramon Delgado", Role.staff),
    ("divina.bautista@example.com", "Divina Bautista", Role.staff),
    ("teresa.ocampo@example.com", "Teresa Ocampo", Role.admin),
]

# Who handles what, for the demo only. Mirrors the prototype's split so one staff
# member does not own every category.
DEMO_ROUTING = {
    "road_infrastructure": "ramon.delgado@example.com",
    "public_safety": "ramon.delgado@example.com",
    "other": "ramon.delgado@example.com",
    "public_health_sanitation": "divina.bautista@example.com",
    "utilities": "divina.bautista@example.com",
    "social_welfare": "divina.bautista@example.com",
    "neighbor_dispute": "divina.bautista@example.com",
}


async def _upsert_user(
    db: AsyncSession, email: str, name: str, role: Role, password: str
) -> tuple[User, bool]:
    email = email.lower()
    existing = (
        await db.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if existing:
        return existing, False

    user = User(
        email=email,
        hashed_password=password_helper.hash(password),
        full_name=name,
        role=role,
        is_active=True,
        is_verified=False,
        is_superuser=False,
        approval_status=ApprovalStatus.approved,
    )
    db.add(user)
    await db.flush()
    return user, True


async def _seed_demo_routing(db: AsyncSession, staff_by_email: dict[str, User]) -> int:
    categories = {c.slug: c for c in (await db.execute(select(Category))).scalars()}
    written = 0
    for slug, email in DEMO_ROUTING.items():
        category = categories.get(slug)
        staff = staff_by_email.get(email)
        if category is None or staff is None:
            continue
        existing = (
            await db.execute(
                select(RoutingRule).where(
                    RoutingRule.category_id == category.id,
                    RoutingRule.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if existing:
            continue
        db.add(RoutingRule(category_id=category.id, staff_id=staff.id, is_active=True))
        written += 1
    return written


async def seed() -> None:
    if not settings.seed_admin_email or not settings.seed_admin_password:
        sys.exit(
            "SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD must be set. There is no "
            "default admin password on purpose."
        )
    if settings.seed_demo and not settings.seed_demo_password:
        sys.exit("SEED_DEMO is on, so SEED_DEMO_PASSWORD must be set.")

    async with AsyncSessionLocal() as db:
        admin, created = await _upsert_user(
            db,
            settings.seed_admin_email,
            settings.seed_admin_name,
            Role.admin,
            settings.seed_admin_password,
        )
        print(f"admin {admin.email}: {'created' if created else 'already there'}")

        if settings.seed_demo:
            staff_by_email: dict[str, User] = {}
            for email, name, role in DEMO_ACCOUNTS:
                user, created = await _upsert_user(
                    db, email, name, role, settings.seed_demo_password
                )
                staff_by_email[user.email] = user
                print(f"demo {user.email}: {'created' if created else 'already there'}")
            rules = await _seed_demo_routing(db, staff_by_email)
            print(f"demo routing rules written: {rules}")

        await db.commit()


if __name__ == "__main__":
    use_selector_loop_on_windows()
    asyncio.run(seed())
