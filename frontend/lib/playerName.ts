const PARTICLES = new Set(["st", "st.", "van", "von", "de", "del", "di", "da", "la", "le"]);
const SUFFIXES = new Set(["jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"]);

/**
 * A name as a small first part and a large last part, like Sleeper's header. A suffix stays with
 * the last name ("Odell Beckham Jr." is "Odell" and "Beckham Jr."); one word is all last.
 */
export function splitName(name: string): { first: string; last: string } {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length <= 1) return { first: "", last: parts[0] ?? "" };
  let keep = SUFFIXES.has(parts[parts.length - 1].toLowerCase()) && parts.length > 2 ? 2 : 1;
  // a particle before the surname belongs to it ("St. Brown", "Van Jefferson")
  while (keep < parts.length - 1 && PARTICLES.has(parts[parts.length - keep - 1].toLowerCase()))
    keep++;
  return {
    first: parts.slice(0, parts.length - keep).join(" "),
    last: parts.slice(parts.length - keep).join(" "),
  };
}
