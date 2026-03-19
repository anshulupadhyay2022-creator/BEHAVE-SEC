"""
backend_api.py  –  backward-compatibility shim
================================================
The application logic has been moved into the `backend/` package.
This file re-exports `app` so that any existing script or Uvicorn
invocation that references `backend_api:app` continues to work.

  Old:  uvicorn backend_api:app
  New:  uvicorn backend.main:app   ← preferred going forward
"""

from backend.main import app  # noqa: F401  (re-export)

