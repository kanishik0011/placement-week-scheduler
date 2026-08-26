const configuredApiBase = process.env.NEXT_PUBLIC_BACKEND_URL ?? process.env.NEXT_PUBLIC_API_BASE;
const localApiBase = configuredApiBase?.match(/^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/);
const API_BASE =
  process.env.NODE_ENV === "production" && (!configuredApiBase || localApiBase)
    ? "/api/backend"
    : (configuredApiBase ?? "http://127.0.0.1:8000");

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE.replace(/\/$/, "")}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store"
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function minuteLabel(value: number | null | undefined): string {
  if (value == null) return "-";
  const day = Math.floor(value / 1440) + 1;
  const minutes = value % 1440;
  return `D${day} ${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
}
