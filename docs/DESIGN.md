# Design direction

The app takes **inspiration from Sleeper and theScore**: familiar, friendly, quick to read, never
cluttered. This is a hobby project for a friends league, nothing is sold, and no money is made.
Inspiration only: no logos, names, fonts or assets from those apps.

## Principles

1. **One thing per screen.** A screen answers one question (how is my team doing, who should I add,
   how is this game going). Detail sits one tap away (a disclosure, a toggle or a tab inside the
   page), not all at once.
2. **Scores and names are big, everything else is small.** Team logos, scores and player names lead;
   chips, badges and numbers support them.
3. **Faces and logos make rows scannable.** Every player row has a face, a position chip and the
   game; every team has its logo.
4. **Phone first.** Design the narrow layout first. Wide screens get the same content with more room
   (never a wider table with the same cramped cells). Tables scroll inside their card, names stay.
5. **Colour carries meaning, words carry the rest.** Position colours, "You" highlight and injury
   states always have text as well (accessibility rule in CLAUDE.md).
6. **Dark first, light supported.** Both themes must pass contrast checks.
7. **No dead ends and no jargon.** An empty state says why and what to do. Every recommendation has a
   one-line why with the numbers (CLAUDE.md).
8. **Few tabs.** Sections are ordered by how often they are used; related views are merged behind
   toggles, filters and presets rather than new tabs (see the tab structure issue).

## Patterns to reuse (do not invent a new one per tab)

- **Score header:** team logos, score, state and clock, conditions. Used for NFL games and for
  fantasy matchups.
- **Player row:** face, name, position chip, team, injury, game and matchup, owner label, one number.
- **Stat table:** compact, sticky name column, right-aligned numbers, sortable, an empty state, and
  projected values clearly marked.
- **Filter chips:** position, availability, week; same look and keyboard behaviour everywhere.
- **Cards and disclosure:** one spacing scale; detail in a native `<details>` where it helps.

## Checking a change

Look at it before it ships: screenshots at phone and desktop width in both themes, the
`a11y-enforcer` and `perf-profiler` skills, and (once the sandbox can reach it) the production site.
UI pull requests include before and after screenshots when feasible.
