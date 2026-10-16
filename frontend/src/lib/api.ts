import type { ChatReply, DestinationLite, Meta, Plan, Prefs, RecResult, SavedTrip, Stay, TransportOption, ChangeSummary } from "./types";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  } catch {
    throw new ApiError("Cannot reach the TripWise server. Is the backend running on port 8000?", 0);
  }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") msg = body.detail;
      else if (Array.isArray(body.detail)) msg = body.detail.map((d: any) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ");
    } catch { /* keep default */ }
    throw new ApiError(msg, res.status);
  }
  return res.json() as Promise<T>;
}
const post = <T,>(p: string, body: unknown) => req<T>(p, { method: "POST", body: JSON.stringify(body) });

export const api = {
  meta: () => req<Meta>("/meta"),
  destinations: () => req<DestinationLite[]>("/destinations"),
  destination: (id: string) => req<{ destination: any; attractions: any[]; accommodation: any[]; facts: any[] }>(`/destinations/${id}`),
  recommend: (prefs: Prefs, sort: "match" | "cost" = "match", top_n = 16) => post<RecResult>("/recommend", { prefs, sort, top_n }),
  compare: (ids: string[], prefs: Prefs) => post<{ destinations: any[]; note: string }>("/compare", { ids, prefs }),
  explain: (destination_id: string, prefs: Prefs) => post<any>("/explain", { destination_id, prefs }),
  plan: (prefs: Prefs, destination_id: string, extra: Record<string, unknown> = {}) => post<Plan>("/plan", { prefs, destination_id, ...extra }),
  edit: (plan: Plan, op: Record<string, unknown>) => post<{ plan: Plan; previous: Plan; warnings: string[]; summary: ChangeSummary }>("/plan/edit", { plan, op }),
  optimize: (plan: Plan, relax = false) => post<any>("/plan/optimize", { plan, relax }),
  replan: (plan: Plan, changes: Record<string, unknown>) => post<{ plan: Plan; previous: Plan; summary: ChangeSummary }>("/plan/replan", { plan, changes }),
  accommodation: (body: Record<string, unknown>) => post<Stay[]>("/accommodation", body),
  transport: (origin: string, destination: string, travellers: number, days?: number) =>
    req<TransportOption[]>(`/transport?origin=${origin}&destination=${destination}&travellers=${travellers}${days ? `&days=${days}` : ""}`),
  config: () => req<any>("/config"),
  setWeights: (weights: Record<string, number>) => req<any>("/config/weights", { method: "PUT", body: JSON.stringify({ weights }) }),
  resetWeights: () => req<any>("/config/weights", { method: "DELETE" }),
  trips: () => req<SavedTrip[]>("/trips"),
  trip: (id: string) => req<{ id: string; name: string; plan: Plan; versions: Plan[] }>(`/trips/${id}`),
  saveTrip: (name: string, plan: Plan, trip_id?: string | null, versions: Plan[] = []) => post<{ id: string; name: string }>("/trips", { name, plan, trip_id, versions }),
  deleteTrip: (id: string) => req<{ deleted: string }>(`/trips/${id}`, { method: "DELETE" }),
  chat: (message: string, session_id?: string | null, plan?: Plan | null) => post<{ session_id: string; reply: ChatReply; prefs: Prefs; plan: Plan | null; previous_plan: Plan | null; focus: { id: string; name: string } | null }>("/chat", { message, session_id, plan: plan ?? null }),
  chatHistory: (sid: string) => req<{ focus: { id: string; name: string } | null; session_id: string; messages: { role: string; content: string; payload: any }[]; prefs: Prefs; plan: Plan | null; previous_plan: Plan | null }>(`/chat/${sid}`),
  chatPrefs: (sid: string, prefs: Record<string, unknown>) => req<{ prefs: Prefs; focus: { id: string; name: string } | null }>(`/chat/${sid}/prefs`, { method: "PUT", body: JSON.stringify({ prefs }) }),
  chatSummaries: (ids: string[]) => req<{ id: string; title: string; messages: number; updated_at: string }[]>(`/chat/summaries?ids=${ids.join(",")}`),
  chatReset: (sid: string) => req<{ reset: boolean }>(`/chat/${sid}`, { method: "DELETE" }),
  kbFacts: (q: { s?: string; p?: string; o?: string; limit?: number }) => req<{ total: number; facts: any[] }>(`/kb/facts?${new URLSearchParams(Object.entries(q).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)]))}`),
  rules: () => req<any[]>("/kb/rules"),
  route: (start: string, goal: string, metric: "distance" | "time" = "distance") => req<any>(`/search/route?start=${start}&goal=${goal}&metric=${metric}`),
  thinks: (prefs: Prefs) => post<any>("/thinks", { prefs }),
  mlMetrics: () => req<any>("/ml/metrics"),
};
