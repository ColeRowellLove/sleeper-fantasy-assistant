/** Public URL of the develop API's stable branch alias on Vercel (not a secret). */
const DEVELOP_API = "https://api-git-develop-cole-b6ee.vercel.app";

/**
 * Where the web app sends API calls. An explicit API_URL always wins. Without one, previews
 * (develop and PR branches) test against the develop API instead of production, and local
 * development uses a locally running API.
 */
export function resolveApiUrl(env: Record<string, string | undefined> = process.env): string {
  if (env.API_URL) return env.API_URL;
  if (env.VERCEL_ENV === "preview") return env.DEVELOP_API_URL ?? DEVELOP_API;
  return "http://localhost:8000";
}
