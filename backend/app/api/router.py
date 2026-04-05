from fastapi import APIRouter

from app.api.v1 import admin, auth, customers, public_plans, queue, services, settings, telegram, webhook

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/v1")
api_router.include_router(queue.router, prefix="/v1")
api_router.include_router(customers.router, prefix="/v1")
api_router.include_router(services.router, prefix="/v1")
api_router.include_router(settings.router, prefix="/v1")
api_router.include_router(telegram.router, prefix="/v1")
api_router.include_router(webhook.router, prefix="/v1")
api_router.include_router(admin.router, prefix="/v1")
api_router.include_router(public_plans.router, prefix="/v1")
