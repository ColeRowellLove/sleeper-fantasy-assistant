/**
 * How numbers are written everywhere. A missing number is always a dash, never 0 (a zero would be
 * a claim), so every table and card goes through these instead of writing its own.
 */

export const NONE = "–";

type Maybe = number | null | undefined;

/** A number with a fixed count of decimals ("13.5"), a dash when there is none. */
export function fixed(n: Maybe, digits = 1): string {
  return n === null || n === undefined ? NONE : n.toFixed(digits);
}

/** A share already in percent ("88.0%"), a dash when there is none. */
export function percent(n: Maybe, digits = 1): string {
  return n === null || n === undefined ? NONE : `${n.toFixed(digits)}%`;
}

/** A share already in percent, rounded to a whole number ("88%"). */
export function percentWhole(n: Maybe): string {
  return n === null || n === undefined ? NONE : `${Math.round(n)}%`;
}

/** A 0 to 1 fraction as a percent ("52.0%"). */
export function fractionPercent(n: Maybe, digits = 1): string {
  return n === null || n === undefined ? NONE : `${(n * 100).toFixed(digits)}%`;
}

/** A whole count with thousands separators ("1,204"). */
export function count(n: Maybe): string {
  return n === null || n === undefined ? NONE : n.toLocaleString("en-US");
}
