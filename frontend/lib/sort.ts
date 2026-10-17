export type SortDirection = "asc" | "desc";

/**
 * What clicking a sortable column does: the active column flips, another one starts at its
 * natural order. Each table says which columns start ascending.
 */
export function nextSort<K extends string>(
  current: { key: K; direction: SortDirection },
  key: K,
  startsAscending: (key: K) => boolean,
): { key: K; direction: SortDirection } {
  if (current.key === key) {
    return { key, direction: current.direction === "asc" ? "desc" : "asc" };
  }
  return { key, direction: startsAscending(key) ? "asc" : "desc" };
}
