from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.inference import classifier
from app.models.user import User
from app.schemas.user import UserRead
from app.users import auth_backend, current_signed_in_user, fastapi_users
from app.api.auth_register import router as register_router
from app.api.auth_password import router as password_router
from app.api.categories import router as categories_router
from app.api.requests import router as requests_router
from app.api.admin_routing import router as routing_router
from app.api.review import router as review_router
from app.api.admin_users import router as admin_users_router
from app.api.admin_audit import router as audit_router
from app.api.notifications import router as notifications_router
from app.api.attachments import router as attachments_router
from app.api.registrations import router as registrations_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Once per worker, never per request. One worker on a small instance: each
    # holds its own copy of both models, and onnxruntime releases the GIL so a
    # single worker still handles concurrent requests.
    classifier.load()
    yield


app = FastAPI(
    title="GABAI API",
    description="Citizen service request classification and routing.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)

app.include_router(register_router)
app.include_router(password_router)
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/api/auth",
    tags=["auth"],
)
# Forgot and reset password, and email confirmation. Library routes, like login.
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/api/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_verify_router(UserRead),
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
app.include_router(registrations_router)


@app.get("/api/auth/me", response_model=UserRead, tags=["auth"])
async def me(user: User = Depends(current_signed_in_user)):
    return user


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}