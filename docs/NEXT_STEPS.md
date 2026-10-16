# Next steps

Where the project stands and what to build next. Written 2026-10-15; milestone dates are in
[PLAN.md](PLAN.md), and the issue list is the source of truth for status.

## Where we are

**Milestone 1 (Foundation) is effectively complete.** The league connects by username and shows
standings (sortable, with streaks and team names), rosters (injuries, game status, kickoff times in your
time zone, byes), weekly lineups and a Settings tab. It runs on Vercel, Neon and a GitHub Actions
worker, with CI, security scanning and branch protection.

What is left of M1:

- **v0.2.0 is merged to `main` but not deployed.** Vercel's free plan stopped the builds ("Deployment
  rate limited", 100 a day, resets about 24 hours later). Production serves the previous version until a
  redeploy goes through. Work branches no longer build on Vercel, which should keep us under the limit.
- **The scheduled worker has not been seen running on its own yet.** It was enabled on 2026-10-15 and
  GitHub's cron is best-effort. If scheduled runs do not appear within a day or two, add a fallback
  scheduler (a new issue).
- **#102 (visual design pass)** is largely delivered: dark and light themes, cards, bold numerals,
  responsive layout, accessibility and screenshot tests. Review its acceptance text and close it.

## Decisions needed from you

| Decision | Why it matters | Default if you do not decide |
|---|---|---|
| FantasyPros | **Decided 2026-10-16:** this is a personal project for the owner and friends, so use the free API key and no paid tier. Still to confirm once the key exists: that the free key returns stat-level projections and what its terms say about a site shared with friends. | Start with the free sources (Sleeper projections, FantasyCalc, nflverse) |
| Buy a domain | Email alerts (#21) must send from a domain you own. Also a nicer link. About $10 to $15 a year. | Alerts wait until you have one |
| League chat (#183) | Sleeper's public API has no chat, so it cannot be built as asked. | Link out to the league chat on Sleeper |
| Vercel Pro, or stay free | Only if the free deployment limit keeps getting in the way. | Stay free |

## Recommended order for milestone 2

M2 is done when a Tuesday waiver alert arrives with a ranked list and bid ranges. That needs a data
spine first, then the alerts, then a way to deliver them.

1. **#15 Ingest FantasyPros, FantasyCalc and nflverse.** Everything else depends on it. Start with
   Sleeper's projections (#211), FantasyCalc and nflverse; add FantasyPros on its free key (owner to request it). One parser and one recorded
   fixture test per source, following the `add-source-parser` skill. nflverse is already used for
   kickoff times, so its download code and attribution exist.
2. **#16 Scoring normalization to league rules.** Convert every source to the connected league's scoring.
   The league scoring is already stored and shown on the Settings tab.
3. **#17 Combined positional rankings with spread and tiers.** The first thing users can see from the
   data spine, and the input for waivers and trades.
4. **#109 Projected points per player and lineup.** Reuses the same data; shows on rosters and lineups.
5. **#18 Waiver wire alerts.** Scores each free agent against your worst starter or bench player.
6. **#19 FAAB bid advisor.** The family league uses priority waivers, not FAAB, so build the
   claim-order suggestions first and the bid ranges for FAAB leagues second.
7. **#21 Alert delivery.** Email first (needs the domain), then web push. SMS last, since it costs money
   and needs opt-in handling. Without delivery, M2's "alert arrives" test cannot pass.
8. **#20 Injury report and status-change alerts.** Injury status already syncs hourly and is shown; the
   new part is diffing each pull and alerting when a starter's status changes. Best after #21 exists.

Do alongside, not in sequence:

- **#22 Friends beta (rate limits, Sentry, `/status`, optional accounts).** Do the rate limits, Sentry and
  the `/status` page before telling anyone beyond family, because each league connect costs about 40 calls
  to Sleeper. Accounts are optional.
- **#146 Multi-user readiness.** Needed for the same reason: many leagues and visitors at once.
- **#153 Player pop-up.** A good self-contained project once #15 exists, since it reuses the same data.

Blocked until a decision: **#183 League chat.**

## Risks to keep in view

- **Unofficial sources can change without notice** (Sleeper's schedule and projections, FantasyCalc).
  Every parser needs a recorded fixture so a schema change fails CI instead of silently dropping data.
- **Licensing:** this is a personal, non-commercial project, so free tiers are used (FantasyPros on its free key). If it ever charges or runs ads, revisit FantasyPros and Vercel's terms. nflverse needs credit (CC BY 4.0).
- **Free-tier limits:** Vercel deployments per day, Neon compute that sleeps when idle, GitHub cron that
  can run late. The first two are documented in [DEPLOY.md](DEPLOY.md).
- **Trademark:** the app is unofficial. Do not use "Sleeper" in a domain or product name.
