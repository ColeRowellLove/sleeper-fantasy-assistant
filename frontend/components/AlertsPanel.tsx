"use client";

import { useRouter } from "next/navigation";

import type { AlertsData, Dashboard } from "../lib/api";
import { alertTime, newestAlertTime, unreadAlerts } from "../lib/alerts";
import { leaguePath } from "../lib/league";
import { alertsSeenCookie, setCookie } from "../lib/myTeam";
import PlayerLink from "./PlayerLink";

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
}: {
  data: AlertsData;
  rosters: Dashboard["rosters"];
  leagueId: string;
  myRosterId: number | null;
  /** When the viewer last cleared their alerts (from the cookie). */
  seen: string | null;
}) {
  const router = useRouter();
  const mine = myRosterId !== null && data.roster_id === myRosterId;
  const unread = mine ? unreadAlerts(data.alerts, seen) : [];
  const unreadIds = new Set(unread.map((a) => a.id));
  const newest = newestAlertTime(data.alerts);
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

      <form method="get" action={leaguePath(leagueId)} className="players-controls">
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

      {data.alerts.length === 0 ? (
        <p className="note">
          No alerts yet. Alerts for this team appear here as they are raised, and the last 14 days
          are kept.
        </p>
      ) : (
        <ul className="alert-list">
          {data.alerts.map((alert) => (
            <li key={alert.id} className={`card alert${unreadIds.has(alert.id) ? " unread" : ""}`}>
              <h3>
                {unreadIds.has(alert.id) && <span className="alert-new">New</span>}
                {alert.title}
              </h3>
              <p className="alert-why">{alert.why}</p>
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
          ))}
        </ul>
      )}
    </section>
  );
}
