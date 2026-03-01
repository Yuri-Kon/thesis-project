"""ProtGPT2 REST service package."""

from services.plm_rest_server.app import app, create_app

__all__ = ["app", "create_app"]
