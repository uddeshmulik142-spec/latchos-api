"""LatchOS Compliance Intake API entrypoint.

This file provides backward compatibility for hosts running `uvicorn main:app`.
The modular implementation lives in the `app` package (`app.main:app`).
"""

from app.main import app

__all__ = ["app"]

