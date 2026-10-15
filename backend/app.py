"""Vercel entrypoint: Vercel looks for an ``app`` object in app.py at the project root.

Locally run the API with ``uvicorn sleeper_assistant.api:app``; this file only exists so the
src/ layout package can be imported on Vercel without being installed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from sleeper_assistant.api import app

__all__ = ["app"]
