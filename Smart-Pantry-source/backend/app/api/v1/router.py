from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    imports,
    meta,
    notifications,
    pantry,
    recipes,
    recommendations,
    shopping,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(pantry.router)
api_router.include_router(recipes.router)
api_router.include_router(recommendations.router)
api_router.include_router(shopping.router)
api_router.include_router(imports.router)
api_router.include_router(meta.router)
api_router.include_router(notifications.router)
