"""API routers."""

from app.routers.admin import router as admin_router
from app.routers.public import router as public_router
from app.routers.trader import router as trader_router

__all__ = ["admin_router", "public_router", "trader_router"]
