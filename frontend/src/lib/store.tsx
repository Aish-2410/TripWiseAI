import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api } from "./api";
import { EMPTY_PREFS, type Plan, type Prefs, type RecResult } from "./types";

interface Persisted { prefs: Prefs; plan: Plan | null; versions: Plan[]; tripId: string | null; sessionId: string | null; compareIds: string[] }
interface Ctx extends Persisted {
  recs: RecResult | null;
  recsLoading: boolean;
  setPrefs: (patch: Partial<Prefs>) => void;
  replacePrefs: (p: Prefs) => void;
  recommend: (sort?: "match" | "cost", override?: Partial<Prefs>) => Promise<RecResult>;
  buildPlan: (destId: string, extra?: Record<string, unknown>) => Promise<Plan>;
  adoptPlan: (p: Plan, opts?: { push?: boolean }) => void;
  undo: () => boolean;
  toggleCompare: (id: string) => void;
  clearCompare: () => void;
  newTrip: () => void;
  loadTrip: (id: string) => Promise<void>;
  saveCurrent: (name: string) => Promise<string>;
  setSessionId: (id: string | null) => void;
  setPlan: (p: Plan | null) => void;
  setCompare: (ids: string[]) => void;
}

const KEY = "tripwise.state.v1";
const blank: Persisted = { prefs: EMPTY_PREFS, plan: null, versions: [], tripId: null, sessionId: null, compareIds: [] };
function read(): Persisted {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || "null");
    return raw ? { ...blank, ...raw, prefs: { ...EMPTY_PREFS, ...raw.prefs } } : blank;
  } catch { return blank; }
}

const TripCtx = createContext<Ctx | null>(null);
export const useTrip = () => { const c = useContext(TripCtx); if (!c) throw new Error("TripProvider missing"); return c; };

export function TripProvider({ children }: { children: ReactNode }) {
  const [s, setS] = useState<Persisted>(read);
  const [recs, setRecs] = useState<RecResult | null>(null);
  const [recsLoading, setRecsLoading] = useState(false);
  const seq = useRef(0);

  useEffect(() => { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* storage full or blocked */ } }, [s]);

  const setPrefs = useCallback((patch: Partial<Prefs>) => setS((p) => ({ ...p, prefs: { ...p.prefs, ...patch } })), []);
  const replacePrefs = useCallback((prefs: Prefs) => setS((p) => ({ ...p, prefs: { ...EMPTY_PREFS, ...prefs } })), []);

  const recommend = useCallback(async (sort: "match" | "cost" = "match", override: Partial<Prefs> = {}) => {
    const my = ++seq.current;
    setRecsLoading(true);
    try {
      const r = await api.recommend({ ...s.prefs, ...override }, sort);
      if (my === seq.current) setRecs(r);
      return r;
    } finally {
      if (my === seq.current) setRecsLoading(false);
    }
  }, [s.prefs]);

  const buildPlan = useCallback(async (destId: string, extra: Record<string, unknown> = {}) => {
    const plan = await api.plan({ ...s.prefs, destination: destId }, destId, extra);
    setS((p) => ({ ...p, plan, versions: [], tripId: null, prefs: { ...p.prefs, destination: destId, duration_days: plan.prefs.duration_days } }));
    return plan;
  }, [s.prefs]);

  const adoptPlan = useCallback((plan: Plan, opts: { push?: boolean } = { push: true }) => {
    setS((p) => ({ ...p, plan, versions: opts.push !== false && p.plan ? [...p.versions, p.plan].slice(-8) : p.versions, prefs: { ...p.prefs, ...plan.prefs } }));
  }, []);

  const undo = useCallback(() => {
    let ok = false;
    setS((p) => {
      if (!p.versions.length) return p;
      ok = true;
      const prev = p.versions[p.versions.length - 1];
      return { ...p, plan: prev, versions: p.versions.slice(0, -1), prefs: { ...p.prefs, ...prev.prefs } };
    });
    return ok;
  }, []);

  const toggleCompare = useCallback((id: string) => setS((p) => ({ ...p, compareIds: p.compareIds.includes(id) ? p.compareIds.filter((x) => x !== id) : [...p.compareIds, id].slice(-3) })), []);
  const clearCompare = useCallback(() => setS((p) => ({ ...p, compareIds: [] })), []);

  const newTrip = useCallback(() => {
    setRecs(null);        // a new chat never deletes earlier conversations; they stay in the sidebar
    setS({ ...blank, prefs: { ...EMPTY_PREFS, origin: s.prefs.origin } });
  }, [s.prefs.origin]);

  const loadTrip = useCallback(async (id: string) => {
    const t = await api.trip(id);
    setS((p) => ({ ...p, plan: t.plan, versions: t.versions || [], tripId: t.id, prefs: { ...p.prefs, ...t.plan.prefs } }));
  }, []);

  const saveCurrent = useCallback(async (name: string) => {
    if (!s.plan) throw new Error("There is no itinerary to save yet.");
    const r = await api.saveTrip(name, s.plan, s.tripId, s.versions);
    setS((p) => ({ ...p, tripId: r.id }));
    return r.id;
  }, [s.plan, s.tripId, s.versions]);

  const setSessionId = useCallback((id: string | null) => setS((p) => ({ ...p, sessionId: id })), []);

  const setPlan = useCallback((plan: Plan | null) => setS((p) => ({ ...p, plan, versions: [], tripId: plan ? p.tripId : null })), []);
  const setCompare = useCallback((ids: string[]) => setS((p) => ({ ...p, compareIds: ids.slice(0, 3) })), []);

  const value = useMemo<Ctx>(() => ({ ...s, recs, recsLoading, setPrefs, replacePrefs, recommend, buildPlan, adoptPlan, undo, toggleCompare, clearCompare, newTrip, loadTrip, saveCurrent, setSessionId, setPlan, setCompare }),
    [s, recs, recsLoading, setPrefs, replacePrefs, recommend, buildPlan, adoptPlan, undo, toggleCompare, clearCompare, newTrip, loadTrip, saveCurrent, setSessionId, setPlan, setCompare]);
  return <TripCtx.Provider value={value}>{children}</TripCtx.Provider>;
}
