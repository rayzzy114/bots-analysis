from .admin import build_admin_router as build_admin_router
from .user import build_user_router as build_user_router

__all__ = ["build_admin_router", "build_user_router"]
