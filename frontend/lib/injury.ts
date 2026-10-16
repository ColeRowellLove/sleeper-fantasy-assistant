import type { InjuryInfo } from "./api";

type InjuryTone = "out" | "doubtful" | "questionable" | "other";

export interface InjuryLabel {
  tone: InjuryTone;
  /** Visible text. Status is never conveyed by color alone. */
  text: string;
  bodyPart: string | null;
}

const LABELS: Record<string, { text: string; tone: InjuryTone }> = {
  Out: { text: "Out", tone: "out" },
  IR: { text: "IR", tone: "out" },
  PUP: { text: "PUP", tone: "out" },
  Sus: { text: "Suspended", tone: "out" },
  DNR: { text: "Did not report", tone: "out" },
  Doubtful: { text: "Doubtful", tone: "doubtful" },
  Questionable: { text: "Questionable", tone: "questionable" },
};

/** Plain-language label and severity for a Sleeper injury designation (null when healthy). */
export function injuryLabel(injury: InjuryInfo | null | undefined): InjuryLabel | null {
  if (!injury?.status) return null;
  const known = LABELS[injury.status];
  // "Undisclosed" says nothing the status does not, so it is left out
  const bodyPart = injury.body_part && injury.body_part !== "Undisclosed" ? injury.body_part : null;
  return {
    tone: known?.tone ?? "other",
    text: known?.text ?? injury.status,
    bodyPart,
  };
}
