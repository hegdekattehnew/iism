"""Public interface of the centres module (Sprint 95, ADR-102).

A leaf: depends on identity (the `Tenant` row), geography, analytics and operations' models (the
verification event a changed address writes); nothing depends on it except the app that includes
its router. Operations and privacy read centres through the tenant rows themselves.
"""

from api.modules.centres.routes import router

__all__ = ["router"]
