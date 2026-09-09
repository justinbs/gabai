from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.models.user import User
from app.schemas.user import UserCreate, UserRead
from app.users import auth_backend, current_active_user, fastapi_users
from app.api.categories import router as categories_router
from app.api.requests import router as requests_router
from app.api.admin_routing import router as routing_router
from app.api.review import router as review_router
from app.api.admin_users import router as admin_users_router
from app.api.admin_audit import router as audit_router
from app.api.notifications import router as notifications_router
from app.api.attachments import router as attachments_router

settings = get_settings()

app = FastAPI(
    title="GABAI API",
    description="Citizen service request classification and routing.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)

from app.api.auth_register import router as register_router

app.include_router(register_router)
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/api/auth",
    tags=["auth"],
)
app.include_router(categories_router)
app.include_router(requests_router)
app.include_router(routing_router)
app.include_router(review_router)
app.include_router(admin_users_router)
app.include_router(notifications_router)
app.include_router(audit_router)
app.include_router(attachments_router)


@app.get("/api/auth/me", response_model=UserRead, tags=["auth"])
async def me(user: User = Depends(current_active_user)):
    return user


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}