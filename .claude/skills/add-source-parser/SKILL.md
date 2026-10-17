---
name: add-source-parser
description: Add a parser/ingest for a new external data source (FantasyPros, FantasyCalc, nflverse, odds, news RSS, etc.) following this repo's rules - Pydantic model, recorded fixture test, crosswalk link, raw snapshot, licensing check. Use when integrating any new source.
---

# Add a data source

Unofficial endpoints are fragile; a schema change must fail CI, not silently drop data.

1. **Licensing first.** Confirm the source allows public use (FantasyPros personal keys do not).
   If unsure, stop and ask the user. Keep request rates low; prefer APIs over scraping.
2. **Pydantic model(s)** for the payload in `backend/src/sleeper_assistant/sources/` (the code that stores it goes in `sync/`) (extra fields ignored,
   required fields strict so drift raises).
3. **Fixture test.** Record a small real payload under `backend/tests/fixtures/<source>_*.json`
   (no secrets, no personal data) and test the parser against it, including odd cases (nulls, missing optional fields).
4. **Player IDs.** Map to Sleeper ids through `crosswalk.link/resolve`; unmatched players must show up
   in the unmatched report, never be dropped silently.
5. **Raw snapshots.** Keep raw responses (`RawSnapshotRow`) for replay unless the payload is huge.
6. **Normalize to league scoring** using rules from `rules.derive_rules`, never hard-coded values.
7. **Failure behavior.** Parse failures raise and surface in the job queue/`/status`; the app degrades to
   the remaining sources.
8. **Secrets.** API keys come from environment variables; add the name to the README configuration table,
   never the value.
9. Ship with the `ship-pr` skill, one issue per source.
