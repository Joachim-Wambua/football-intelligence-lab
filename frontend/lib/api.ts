import { z } from "zod";

const base = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000/api/v1").replace(/\/$/, "");

/** Validate Python-owned contracts at the network boundary; never compute analytics here. */
export async function apiGet<T>(path: string, schema: z.ZodType<T>): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, { signal: AbortSignal.timeout(30000), headers: { Accept: "application/json" } });
  } catch {
    throw new Error("Cannot reach the API. Check that FastAPI is running and try again.");
  }
  if (!response.ok) {
    const messages: Record<number, string> = {404: "This match, team or player is unavailable.", 422: "The API rejected the selection.", 502: "The data provider is temporarily unavailable.", 504: "The data provider timed out."};
    throw new Error(messages[response.status] || `API request failed (${response.status}).`);
  }
  let value: unknown;
  try { value = await response.json(); } catch { throw new Error("The API returned an invalid response."); }
  const parsed = schema.safeParse(value);
  if (!parsed.success) throw new Error("The API response does not match the expected contract.");
  return parsed.data;
}
