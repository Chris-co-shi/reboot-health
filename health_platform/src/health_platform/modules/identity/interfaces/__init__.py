"""Identity 进程边界入口（HTTP、CLI、Worker）。"""

from .http import build_identity_router

__all__ = ["build_identity_router"]
