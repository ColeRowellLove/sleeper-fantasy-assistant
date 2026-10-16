"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { AlertItem, AlertsData, Dashboard } from "../lib/api";
import {
  ALERT_NOTES,
  ALERT_TYPES,
  alertAdvice,
  alertTime,
  newestAlertTime,
  serializeOff,
  unreadAlerts,
  visibleAlerts,
  waiverTargets,
  type WaiverTarget,
} from "../lib/alerts";
import { leaguePath } from "../lib/league";
import { alertsOffCookie, alertsSeenCookie, setCookie } from "../lib/myTeam";
import PlayerLink from "./PlayerLink";

const SHOWN_TARGETS = 3; // pickups shown at once; the rest are one click away

function TargetItem({ target: t }: { target: WaiverTarget }) {
  return (
    <li>
      <PlayerLink playerId={t.player_id}>{t.name}</PlayerLink>
      {t.detail !== undefined ? ` ${t.detail}` : t.line.replace(t.name, "")}
    </li>
  );
}

/** One alert: title, what happened, and for a waiver alert the pickups as a linked, numbered list. */
function AlertCard({ alert, isNew }: { alert: AlertItem; isNew: boolean }) {
  const targets = waiverTargets(alert);
  const advice = alertAdvice(alert);
  return (
    <li className={`card alert${isNew ? " unread" : ""}`}>
      <h3>
        {isNew && <span className="alert-new">New</span>}
        {alert.title}
      </h3>
      {advice && (
        <div className="alert-advice">
          <p className="alert-advice-label">Suggested by an AI assistant</p>
          <p>{advice.summary}</p>
          <ol>
            {advice.picks.map((pick) => (
              <li key={pick.player_id}>
                <PlayerLink playerId={pick.player_id}>{pick.name}</PlayerLink>
                {pick.position ? ` (${pick.position}${pick.team ? `, ${pick.team}` : ""})` : ""}
                {pick.action === "pickup" ? " — pick up" : " — start from your bench"}
                {pick.drop_name ? `, dropping ${pick.drop_name}` : ""}: {pick.reason}
              </li>
            ))}
          </ol>
        </div>
      )}
      {targets.length > 0 ? (
        <>
          <ol className="alert-targets">
            {targets.slice(0, SHOWN_TARGETS).map((t) => (
              <TargetItem key={t.player_id} target={t} />
            ))}
          </ol>
          {targets.length > SHOWN_TARGETS && (
            <details className="alert-more">
              <summary>Show {targets.length - SHOWN_TARGETS} more</summary>
              <ol className="alert-targets" start={SHOWN_TARGETS + 1}>
                {targets.slice(SHOWN_TARGETS).map((t) => (
                  <TargetItem key={t.player_id} target={t} />
                ))}
              </ol>
            </details>
          )}
        </>
      ) : (
        <p className="alert-why">{alert.why}</p>
      )}
      <p className="muted alert-meta">
        {alertTime(alert.created_at)}
        {alert.player_id && (
          <>
            {" · "}
            <PlayerLink playerId={alert.player_id}>View player</PlayerLink>
          </>
        )}
      </p>
    </li>
  );
}

/**
 * A team's alerts, newest first. Which team is a plain GET form (works without JavaScript). Read
 * state belongs to the viewer: it is a time kept in their own cookie for their own team, because
 * anyone can open this public page and must not be able to clear someone else's alerts.
 */
export default function AlertsPanel({
  data,
  rosters,
  leagueId,
  myRosterId,
  seen,
  off = [],
}: {
  data: AlertsData;
  rosters: Dashboard["rosters"];
  leagueId: string;
  myRosterId: number | null;
  /** When the viewer last cleared their alerts (from the cookie). */
  seen: string | null;
  /** The alert kinds the viewer has switched off (from their cookie). */
  off?: string[];
}) {
  const router = useRouter();
  const [startOpen] = useState(() => visibleAlerts(data.alerts, off).length === 0); // never re-folds
  const [switchedOff, setSwitchedOff] = useState<string[]>(off);
  const mine = myRosterId !== null && data.roster_id === myRosterId;
  const alerts = visibleAlerts(data.alerts, switchedOff);
  const hidden = data.alerts.length - alerts.length;
  const unread = mine ? unreadAlerts(alerts, seen) : [];
  const unreadIds = new Set(unread.map((a) => a.id));
  const newest = newestAlertTime(alerts); // hidden kinds are not marked as read

  const choose = (kind: string, wanted: boolean) => {
    const next = wanted ? switchedOff.filter((k) => k !== kind) : [...switchedOff, kind];
    setSwitchedOff(next);
    setCookie(alertsOffCookie(leagueId), serializeOff(next));
    router.refresh(); // the tab's new-alert count follows the choice
  };
  const team =
    rosters.find((r) => r.roster_id === data.roster_id)?.team ?? `Team ${data.roster_id}`;

  const markRead = () => {
    if (newest) setCookie(alertsSeenCookie(leagueId), newest);
    router.refresh();
  };

  return (
    <section aria-labelledby="alerts-heading">
      <h2 id="alerts-heading">Alerts</h2>
      <p className="note">
        Things worth knowing about {mine ? "your team" : team}, from the last 14 days.
      </p>

      <details className="alert-kinds" open={startOpen}>
        <summary>Which alerts do you want?</summary>
        <fieldset>
          <legend className="visually-hidden">Alert types to show</legend>
          <ul className="alert-choices">
            {ALERT_TYPES.map((t) => (
              <li key={t.kind}>
                <label>
                  <input
                    type="checkbox"
                    checked={!switchedOff.includes(t.kind)}
                    onChange={(event) => choose(t.kind, event.target.checked)}
                  />
                  <span>
                    <strong>{t.title}.</strong> {t.text}
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </fieldset>
        <ul className="alert-notes">
          {ALERT_NOTES.map((k) => (
            <li key={k.title}>
              <strong>{k.title}.</strong> {k.text}
            </li>
          ))}
        </ul>
        <p className="muted">Your choices are kept in this browser.</p>
      </details>

      <form method="get" action={leaguePath(leagueId)} className="inline-form">
        <input type="hidden" name="tab" value="alerts" />
        <label>
          Team{" "}
          <select name="roster" defaultValue={String(data.roster_id)}>
            {rosters.map((r) => (
              <option key={r.roster_id} value={r.roster_id}>
                {r.team}
                {r.roster_id === myRosterId ? " (you)" : ""}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="btn">
          Show alerts
        </button>
      </form>

      {mine && unread.length > 0 && (
        <p className="alerts-unread">
          {unread.length} new {unread.length === 1 ? "alert" : "alerts"}.{" "}
          <button type="button" className="btn btn-quiet" onClick={markRead}>
            Mark all as read
          </button>
        </p>
      )}

      {hidden > 0 && alerts.length > 0 && (
        <p className="note">
          {hidden} {hidden === 1 ? "alert is" : "alerts are"} hidden by your choices above.
        </p>
      )}

      {alerts.length === 0 ? (
        <p className="note">
          {hidden > 0
            ? `${hidden} ${hidden === 1 ? "alert is" : "alerts are"} hidden by your choices above.`
            : `No alerts yet for ${mine ? "your team" : team}. When one is raised it appears here, and the last 14 days are kept.`}
        </p>
      ) : (
        <ul className="alert-list">
          {alerts.map((alert) => (
            <AlertCard key={alert.id} alert={alert} isNew={unreadIds.has(alert.id)} />
          ))}
        </ul>
      )}
    </section>
  );
}
