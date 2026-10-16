# Next steps

Where the project stands and what to build next. Updated 2026-10-16; milestone dates are in
[PLAN.md](PLAN.md), and the issue list is the source of truth for status.

## Where we are

**Milestone 1 (Foundation) is complete, and a good part of milestone 2 is built from free sources.**
A league connects by username and shows, with every number scored by that league's own rules:

- **Standings** (sortable, streaks, team names), **Rosters** (injuries, game status, points and
  projection for the week), **Lineups** (head-to-head with a win chance and a bar), **Players** (filter,
  search, sort by Sleeper adds and drops, ESPN owned and start percentages, rank, points, projection),
  **Teams** (full depth charts with injuries) and **Settings**.
- **Player pop-up** from any player: bio, rank, week-by-week stat table with team and opponent,
  projection, past seasons game by game. NFL team codes open that team's depth chart.
- **Projections** for every position including defenses, updated live during a game and equal to the
  score once it ends, with the frozen pre-game number kept for comparing. Live score, quarter and clock
  on game badges.

Data comes from Sleeper, ESPN's free endpoints (ownership, depth charts, live scoreboard) and nflverse,
refreshed by a scheduled worker. Production runs on Vercel, Neon and GitHub Actions.

What is left before this is live for everyone:

- **v0.3.0 is not released.** `main` is at v0.2.0 and `develop` holds a lot more (migrations 0008 to
  0016). Vercel's free plan stopped builds ("Deployment rate limited", 100 a day, resets about 24 hours
  after the first failure, around 23:00 UTC on 2026-10-15). Once builds work, release with the
  `release-to-main` skill, then check production.
- **The worker has now run on its own schedule** (a scheduled run succeeded on 2026-10-16), so the
  earlier worry about unattended sync is much smaller. Keep an eye on it for a few more days.
- **Review #102** (visual design pass); it looks delivered. **Close #109** once you agree that Sleeper's
  projections are enough for now (the consensus blend is still #15 to #17).

## Decisions needed from you

| Decision | Why it matters | Default if you do not decide |
|---|---|---|
| FantasyPros | **Decided:** personal project, so use the free key and no paid tier. Still to confirm once you have a key: that it returns stat-level projections and what its terms say about a site shared with friends. | Use Sleeper, ESPN and nflverse only |
| Buy a domain | Email alerts (#21) must send from a domain you own. Also a nicer link. About $10 to $15 a year. | Alerts wait until you have one |
| League chat (#183) | Sleeper's public API has no chat, so it cannot be built as asked. | Link out to the league chat on Sleeper |
| Vercel Pro, or stay free | Only if the daily deployment limit keeps getting in the way. | Stay free |

## What is next, in order

M2 is done when a Tuesday waiver alert arrives with a ranked list and bid ranges. The data now exists;
what is missing is the ranking, the page and the delivery.

1. **Release v0.3.0** (above). Everything built so far is only visible locally until then.
2. **#213 Waiver wire suggestions page** (with **#18 waiver alerts** and **#19 FAAB advisor**). Score each
   available player against your worst starter using the projections already built, Sleeper's add
   trends, ESPN ownership and the depth chart (an injured starter opens up his backup). The page resets
   on the league's waiver day. Your league uses priority waivers, so build the claim-order suggestion
   first and FAAB bid ranges for leagues that need them.
3. **#20 Injury status-change alerts**, using the depth chart's "next up" logic.
4. **#21 Alert delivery** (email first, which needs the domain; web push next; SMS last).
5. **#15 to #17 more sources and consensus rankings.** Sleeper, ESPN and nflverse are in. Add
   FantasyCalc, and FantasyPros on its free key if you get one, then blend with source spread and tiers.
6. **#22 Friends beta and #146 multi-user readiness** before you share the link widely: rate limits,
   Sentry, a `/status` page. Each league connect costs about 40 Sleeper calls, so this matters as
   soon as friends join.

Blocked until a decision: **#183 League chat.**

## Risks to keep in view

- **Unofficial sources can change without notice** (Sleeper's schedule, projections and stats; ESPN's
  endpoints). Every parser has a recorded fixture test and a failed pull keeps the last good data.
- **Free-tier limits:** Vercel deployments per day, Neon storage (the database grew by roughly 6 MB per
  stored season) and compute that sleeps when idle, GitHub cron that can run late.
- **Licensing:** this is a personal, non-commercial project, so free tiers and unofficial endpoints are
  used. If it ever charges or runs ads, revisit ESPN's and FantasyPros's terms and Vercel's plan.
  nflverse needs credit (CC BY 4.0).
- **Models are starting values, not measured:** the win chance spread (28 points) and the live
  projection's straight scaling should be checked against stored projections and results after a few
  weeks of games.
- **Trademark:** the app is unofficial. Do not use "Sleeper" in a domain or product name.
