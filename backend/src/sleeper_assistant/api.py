"""FastAPI application."""

from fastapi import FastAPI

from sleeper_assistant import __version__

app = FastAPI(title="Sleeper Fantasy Assistant", version=__version__)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
