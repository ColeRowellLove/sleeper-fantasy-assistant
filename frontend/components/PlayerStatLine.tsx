/**
 * One line under a player: what he did ("18 car, 92 yds, 1 TD"), or before his game what he is
 * projected to do, marked "Proj" so a forecast is never read as a result.
 */
export default function PlayerStatLine({
  line,
  projected = false,
}: {
  line?: string | null;
  projected?: boolean;
}) {
  if (!line) return null;
  return (
    <span className={`stat-line${projected ? " stat-line-proj" : ""}`}>
      {projected ? (
        <>
          <span className="stat-line-tag" aria-hidden="true">
            Proj
          </span>
          <span className="visually-hidden">Projected stats: </span>
        </>
      ) : (
        <span className="visually-hidden">Stats this week: </span>
      )}
      {line}
    </span>
  );
}
