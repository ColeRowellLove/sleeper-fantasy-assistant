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

type Step =
  | { kind: "username" }
  | { kind: "pick"; leagues: LeagueSummary[] }
  | { kind: "connected"; league: ConnectedLeague };

export default function ConnectForm() {
  const [username, setUsername] = useState("");
  const [step, setStep] = useState<Step>({ kind: "username" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const pickRef = useRef<HTMLParagraphElement>(null);
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
      const leagues = await listLeagues(name);
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
    <section aria-labelledby="connect-heading">
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
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            aria-describedby={error ? "username-help connect-error" : "username-help"}
            aria-invalid={error ? true : undefined}
          />
          <p id="username-help">No password needed. We only read public league data.</p>
          <button type="submit" aria-disabled={busy}>
            {busy ? "Looking…" : "Find my leagues"}
          </button>
        </form>
      )}

      {step.kind === "pick" && (
        <div>
          <p id="pick-help" ref={pickRef} tabIndex={-1}>
            Choose a league to connect:
          </p>
          <ul aria-labelledby="pick-help">
            {step.leagues.map((league) => (
              <li key={league.league_id}>
                <button type="button" aria-disabled={busy} onClick={() => connect(league.league_id)}>
                  {league.name} ({league.season}, {league.total_rosters} teams)
                </button>
              </li>
            ))}
          </ul>
          <button type="button" onClick={() => setStep({ kind: "username" })}>
            Use a different username
          </button>
        </div>
      )}

      {step.kind === "connected" && (
        <div>
          <p ref={connectedRef} tabIndex={-1}>
            Connected <strong>{step.league.name}</strong>. Reception scoring:{" "}
            {step.league.rules.reception_scoring}; {step.league.rules.uses_faab ? "FAAB" : "priority"}{" "}
            waivers.
          </p>
          <a href={`/league/${encodeURIComponent(step.league.league_id)}`}>Open league dashboard</a>
        </div>
      )}

      <p id="connect-error" role="alert">
        {error}
      </p>
      <p role="status" aria-live="polite">
        {busy ? "Working…" : ""}
      </p>
    </section>
  );
}
