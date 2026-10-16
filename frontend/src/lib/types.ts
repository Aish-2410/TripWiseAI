export type Climate = "cold" | "cool" | "mild" | "warm" | "hot";
export type Pace = "relaxed" | "balanced" | "packed";
export type Tier = "hostel" | "budget" | "homestay" | "midrange" | "premium";
export type Mode = "bus" | "train" | "car" | "flight";

export interface Prefs {
  origin: string | null;
  destination: string | null;
  budget: number | null;
  duration_days: number | null;
  start_date: string | null;
  travellers: number;
  climate: Climate | null;
  season: string | null;
  interests: string[];
  excluded_activities: string[];
  excluded_destinations: string[];
  travel_style: "solo" | "couple" | "family" | "friends" | null;
  elderly: boolean;
  children: boolean;
  transport: Mode[];
  accommodation: Tier | null;
  dietary: string[];
  accessibility_required: boolean;
  pace: Pace;
  randomize: boolean;
  seed: number;
}

export const EMPTY_PREFS: Prefs = {
  origin: null, destination: null, budget: null, duration_days: null, start_date: null, travellers: 1, climate: null, season: null,
  interests: [], excluded_activities: [], excluded_destinations: [], travel_style: null, elderly: false, children: false, transport: [],
  accommodation: null, dietary: [], accessibility_required: false, pace: "balanced", randomize: false, seed: 0,
};

export interface Component { score: number; weight: number; status: "ok" | "missing_data" | "not_specified"; note: string }
export interface Adjustment { rule_id: string; name: string; fired: boolean; points: number; reason: string; if_text: string }
export interface Recommendation {
  id: string; name: string; state: string; country: string; region: string; type: string; description: string; climate: Climate | null; best_seasons: string[];
  min_days: number; max_days: number; tags: string[]; accessibility: string | null; wiki?: string; lat: number; lon: number; rank: number;
  match_score: number; base_score: number; components: Record<string, Component>; adjustments: Adjustment[];
  cost: { floor: number | null; typical: number | null; tier_assumed?: string; food_assumed?: string };
  transport_best: string | null; one_way_hours: number | null; fastest_one_way_hours: number | null; attractions_preview: string[];
  explanation: string; limitations: string[]; stravl_affinity?: { available: boolean; p_yes?: number; destination_base_rate?: number; n_swipes?: number; stravl_destination?: string; note?: string; reason?: string } | null;
}
export interface Excluded { id: string; name: string; state: string; excluded_reasons: string[]; cost?: { floor: number | null } }
export interface RecResult {
  needs_info: string[]; message?: string; ranked: Recommendation[]; excluded: Excluded[]; total_candidates?: number; relaxation?: string[];
  trace: { prefs: Prefs; weights: Record<string, number> };
}

export interface ScheduleItem {
  kind: "activity" | "travel" | "meal" | "rest"; title: string; start: string; end: string; minutes: number; attraction_id?: string; slot?: string;
  lat?: number; lon?: number; tags?: string[]; fee_per_person?: number; fee_group?: number; fee_known?: boolean; intensity?: number; accessible?: boolean | null;
  description?: string; km?: number; mode?: string;
}
export interface Day {
  day: number; activity_ids: string[]; date?: string | null;
  schedule: { items: ScheduleItem[]; activity_minutes: number; travel_minutes: number; local_km: number; local_cost: number; fee_total: number; end_time: string };
}
export interface Costs {
  currency: string; label: string; breakdown: Record<string, number>; subtotal: number; total: number; per_person: number; travellers: number; nights: number;
  budget: number | null; remaining: number | null; over_budget: boolean; overrun: number; assumptions: string[];
  daily: { day: number; attractions: number; local_transport: number; food: number; accommodation: number; activity_minutes: number; travel_minutes: number }[];
}
export interface TransportOption {
  mode: string; one_way_hours: number; price_inr: number; price_basis: string; round_trip_group_inr: number; per_person_round_trip_inr: number; comfort: number;
  distance_km: number; accessibility_note?: string; label: string; score: number; eats_trip?: boolean;
}
export interface Plan {
  prefs: Prefs; destination_id: string; destination_name: string; transport: TransportOption; accommodation_tier: Tier; stay_id: string; food_tier: string;
  days: Day[]; costs: Costs; search: any; notes: string[]; pinned: string[]; rules_fired: string[]; disclaimer?: string; version?: number; activity_total: number;
}
export interface Attraction {
  id: string; destination_id: string; name: string; tags: string[]; lat: number; lon: number; duration_min: number; fee_inr: number; intensity: number;
  accessible: boolean | null; best_slot: string; significance: number; description: string;
}
export interface Stay {
  id: string; name: string; tier: Tier; price_inr: number; price_unit: string; total_inr: number; nights: number; amenities: string[]; comfort: number;
  accessible: boolean | null; lat: number; lon: number; avg_distance_to_planned_km: number | null; score: number; note?: string;
}
export interface DestinationLite {
  id: string; name: string; state: string; region: string; type: string; climate: Climate | null; tags: string[]; wiki?: string; min_days: number; max_days: number;
  description: string; lat: number; lon: number; accessibility: string | null; best_seasons: string[];
}
export interface Meta {
  dataset: { dataset: string; disclaimer: string }; counts: Record<string, number>; data_issues: string[]; kb: any; ml: { available: boolean }; chat?: { understanding: string; llm_enabled: boolean };
  options: { interests: string[]; climates: string[]; seasons: string[]; tiers: string[]; modes: string[] }; origins: { id: string; name: string }[]; sources: { name: string; url: string | null; use: string; status: string }[];
}
export interface Understood { intent: string; items: [string, string][] }
export interface ChatReply {
  understood?: Understood; focus?: string | null;
  text: string; intent: string; entities: Record<string, unknown>; suggestions: string[]; actions: { type: string; data?: any; plan?: Plan; summary?: any }[];
}
export interface SavedTrip { id: string; name: string; destination_id: string; destination_name: string; created_at: string; updated_at: string; days: number; total: number; travellers: number }
export interface ChangeSummary { added: string[]; removed: string[]; unchanged: number; cost_before: number; cost_after: number; cost_delta: number; lines: string[]; optimiser?: any; impacts?: string[] }
