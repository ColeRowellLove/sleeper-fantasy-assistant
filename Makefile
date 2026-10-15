.PHONY: help setup check fmt backend-check frontend-check migrate dev-api dev-web hooks

help:
	@echo "make setup           install backend + frontend dependencies"
	@echo "make check           run everything CI runs (backend + frontend)"
	@echo "make fmt             auto-format backend code"
	@echo "make migrate         apply database migrations (DATABASE_URL, default SQLite)"
	@echo "make dev-api         run the API on :8000"
	@echo "make dev-web         run the web app on :3000"
	@echo "make hooks           install pre-commit hooks"

setup:
	cd backend && uv sync
	cd frontend && npm ci

check: backend-check frontend-check

backend-check:
	cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest

frontend-check:
	cd frontend && npm run typecheck && npm run lint && npm test && npm run build

fmt:
	cd backend && uv run ruff format . && uv run ruff check --fix .

migrate:
	cd backend && uv run alembic upgrade head

dev-api:
	cd backend && uv run uvicorn sleeper_assistant.api:app --reload

dev-web:
	cd frontend && npm run dev

hooks:
	uvx pre-commit install
