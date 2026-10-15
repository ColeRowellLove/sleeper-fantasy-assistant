# Build plan

Condensed from the "Sleeper Fantasy Assistant — Build Plan" doc. Milestones and features are tracked
as GitHub milestones and issues.

## Principles

1. **Consensus over any single source** — show the source spread, not just the average.
2. **Calibrated numbers** — odds come from simulation with stated uncertainty; track accuracy.
3. **League-aware** — scoring, roster slots, other managers' needs and byes feed everything.
4. **Explain every recommendation** — one-line why plus the numbers behind it.

## Architecture

Python data/modeling core writes to one Postgres store; dashboard, alerts and recaps only read.
Ingest and modeling are scheduled batch jobs (Postgres-backed queue + worker).

- Core: Python 3.12, Polars, NumPy, Pydantic
- Storage: Postgres (Neon/Supabase), raw JSON snapshots for replay/backtests
- API + web: FastAPI + Next.js
- LLM: Claude API for recaps and the later chat assistant
- Alerts: email (Resend/Postmark), Web Push (PWA), SMS (Twilio, opt-in)

## Data sources

Sleeper (system of record), Sleeper projections (unofficial), FantasyPros (commercial tier needed
for a public site), FantasyCalc, KeepTradeCut, nflverse/nflreadpy, Vegas lines, expert sites, news RSS.
Build the player ID crosswalk first. Treat unofficial endpoints as fragile.

## Milestones

| # | Name | Dates | Done when |
|---|------|-------|-----------|
| M1 | Foundation | Oct 15–25, 2026 | CI green on main, league syncs unattended through Week 7, page shows correct standings |
| M2 | Rankings + waivers | Oct 26–Nov 8 | Tuesday waiver alert arrives with ranked list and bid ranges |
| M3 | Trade engine | Nov 9–18 | Suggests at least one trade per opponent you'd actually send |
| M4 | Simulator + odds | Nov 19–Dec 6 | Odds page updates nightly; backtest calibration within ~5 pts |
| M5 | Recaps + accuracy | Dec 7–15 | First recap posts before playoff week 1 |
| M6 | Offseason | Jan–Aug 2027 | Draft assistant ready before Aug 2027 drafts |

If the league's trade deadline lands after mid-November, swap M3 and M4.

## Success metrics (end of 2026 regular season)

- Sync runs unattended every game day with no missed weeks
- Weekly projections match or beat FantasyPros ECR on lineup accuracy
- Title-odds calibration within ~5 pts across 2024–2025 backtests
- At least 3 friends' leagues using it weekly
