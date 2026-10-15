import type { GameInfo } from "../lib/api";
import { gameLabel } from "../lib/game";

/** Whether a player's NFL game is upcoming, live, played, or the team is on a bye. */
export default function GameBadge({ game }: { game?: GameInfo | null }) {
  const label = gameLabel(game);
  if (!label) return null;
  return (
    <span className={`game game-${label.state}`}>
      <span className="game-state">{label.text}</span>
      {label.detail && <span className="game-detail">{label.detail}</span>}
    </span>
  );
}
