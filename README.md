# Sleeper Fantasy Assistant

[![CI](https://github.com/ColeRowellLove/sleeper-fantasy-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/ColeRowellLove/sleeper-fantasy-assistant/actions/workflows/ci.yml)

A public web app that connects to any [Sleeper](https://sleeper.com) league by username, blends
several ranking and projection sources into one consensus, and turns it into waiver alerts, trade
ideas, rankings, playoff odds and weekly league recaps.

The Sleeper API is public and read-only: the assistant recommends, you make the move in Sleeper.

See [docs/PLAN.md](docs/PLAN.md) for the build plan and milestones, and
[CLAUDE.md](CLAUDE.md) for contributor/agent guidance.

## Quick start

```bash
# backend
cd backend && uv sync && uv run uvicorn sleeper_assistant.api:app --reload

# frontend
cd frontend && npm ci && npm run dev
```

## Branching

`main` = releases, `develop` = integration. Open PRs into `develop`.

## License

MIT
