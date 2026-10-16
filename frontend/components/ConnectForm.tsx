"use client";

import { useEffect, useRef, useState } from "react";

import {
  ApiError,
  connectLeague,
  isValidUsername,
  listLeagues,
  type ConnectedLeague,
  type LeagueSummary,
} from "../lib/api";
import { leaguePath, ruleChips } from "../lib/league";
import { USER_COOKIE, setCookie } from "../lib/myTeam";

type Step =
  | { kind: "username" }
  | { kind: "pick"; leagues: LeagueSummary[] }
  | { kind: "connected"; league: ConnectedLeague };

export default function ConnectForm() {
  const [username, setUsername] = useState("");
  const [step, setStep] = useState<Step>({ kind: "username" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const pickRef = useRef<HTMLHeadingElement>(null);
  const connectedRef = useRef<HTMLParagraphElement>(null);
  const usernameRef = useRef<HTMLInputElement>(null);

  // Moving to a new step replaces the controls the user was on, so move focus to the new content.
  useEffect(() => {
    if (step.kind === "pick") pickRef.current?.focus();
    if (step.kind === "connected") connectedRef.current?.focus();
  }, [step.kind]);

  async function run(action: () => Promise<void>) {
    if (busy) return; // aria-disabled buttons stay focusable, so guard against double submits
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  function findLeagues(event: React.FormEvent) {
    event.preventDefault();
    const name = username.trim();
    if (!isValidUsername(name)) {
      setError("Enter your Sleeper username (letters, numbers, underscores or periods).");
      usernameRef.current?.focus();
      return;
    }
    void run(async () => {
      const { user_id: userId, leagues } = await listLeagues(name);
      if (userId) setCookie(USER_COOKIE, userId); // lets the league pages find your team
      if (leagues.length === 0) {
        setError("No leagues found for that username this season.");
        return;
      }
      setStep({ kind: "pick", leagues });
    });
  }

  function connect(leagueId: string) {
    void run(async () => setStep({ kind: "connected", league: await connectLeague(leagueId) }));
  }

  return (
    <section className="card" aria-labelledby="connect-heading">
      <h2 id="connect-heading">Connect your league</h2>

      {step.kind === "username" && (
        <form onSubmit={findLeagues} noValidate>
          <label htmlFor="username">Sleeper username</label>
          <input
            id="username"
            name="username"
            ref={usernameRef}
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
            placeholder="your_username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            aria-describedby={error ? "username-help connect-error" : "username-help"}
            aria-invalid={error ? true : undefined}
          />
          <p id="username-help" className="help">
            No password needed. We only read public league data.
          </p>
          <button type="submit" className="btn" aria-disabled={busy}>
            {busy ? "Looking…" : "Find my leagues"}
          </button>
        </form>
      )}

      {step.kind === "pick" && (
        <div>
          <p id="pick-help" ref={pickRef} tabIndex={-1} className="help">
            Choose a league to connect:
          </p>
          <ul aria-labelledby="pick-help" className="league-list">
            {step.leagues.map((league) => (
              <li key={league.league_id}>
                <button
                  type="button"
                  className="league-option"
                  aria-disabled={busy}
                  onClick={() => connect(league.league_id)}
                >
                  <span>
                    {league.name} ({league.season}, {league.total_rosters} teams)
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <button
            type="button"
            className="btn btn-quiet"
            onClick={() => setStep({ kind: "username" })}
          >
            Use a different username
          </button>
        </div>
      )}

      {step.kind === "connected" && (
        <div>
          <div className="connected-card">
            <h3 ref={connectedRef} tabIndex={-1} className="connected-name">
              <span className="connected-label">Connected</span>
              {step.league.name.trim()}
            </h3>
            <p className="league-meta">
              {step.league.season} season, {step.league.total_rosters} teams
            </p>
            <ul className="rule-chips" aria-label="League rules">
              {ruleChips(step.league.rules).map((chip) => (
                <li key={chip}>{chip}</li>
              ))}
            </ul>
          </div>
          <a className="btn" href={leaguePath(step.league.league_id)}>
            Open league dashboard
          </a>
        </div>
      )}

      <p id="connect-error" role="alert" className="error">
        {error}
      </p>
      <p role="status" aria-live="polite" className="status">
        {busy ? "Working…" : ""}
      </p>
    </section>
  );
}
