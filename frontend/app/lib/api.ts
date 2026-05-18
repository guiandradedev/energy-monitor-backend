export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { error?: string } | null;
    throw new Error(body?.error || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  del: (path: string) => request<void>(path, { method: "DELETE" }),
};

export type Priority = { id: number; label: string; rank: number };

export type DeviceState = {
  state: "on" | "off" | "unknown";
  source: "auto" | "manual";
  last_seen: string | null;
  last_changed_at: string | null;
};

export type Device = {
  id: number;
  device_id: string;
  name: string;
  priority: Priority;
  state: DeviceState;
};

export type SafetyLimit = {
  id: number;
  breaker_id: string;
  nominal_current_a: number;
  shed_threshold_pct: number;
  restore_threshold_pct: number;
};

export type Parameter = {
  key: string;
  value: string;
  description: string | null;
  updated_at: string;
};

export type TelemetryPoint = {
  timestamp: string;
  breaker_id?: string;
  rms_sct1: number;
  rms_sct2: number;
  rms_zmpt1: number;
  rms_zmpt2: number;
};

export type TelemetryListResponse = {
  data: TelemetryPoint[];
  total: number;
  limit: number;
  offset: number;
};

export type EventItem = {
  id: number;
  ts: string;
  type: string;
  device:
    | { id: number; device_id: string; name: string }
    | null;
  payload: Record<string, unknown> | null;
};
