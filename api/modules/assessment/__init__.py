"""Public interface of the assessment module (ADR-017, Sprint 35, BL-3.1).

A leaf module, the `operations/` shape: depends on `identity`, `marketplace`
and `skills`; nothing depends on it. No model of its own -- see
`service.py`'s docstring for why nothing new is persisted here.
"""

from api.modules.assessment.routes import router

__all__ = ["router"]
