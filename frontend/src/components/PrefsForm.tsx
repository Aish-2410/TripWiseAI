import { useEffect, useState } from "react";
import { useTrip } from "../lib/store";
import { INTEREST_LABEL, cap } from "../lib/format";
import type { Meta, Mode } from "../lib/types";
import { api } from "../lib/api";

let metaCache: Meta | null = null;
export function useMeta() {
  const [m, setM] = useState<Meta | null>(metaCache);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (!metaCache) api.meta().then((x) => { metaCache = x; setM(x); }).catch((e) => setError(e.message)); }, []);
  return { meta: m, error };
}

const num = (v: string) => (v === "" ? null : Math.max(0, Number(v)));

export default function PrefsForm({ onSubmit, busy, submitLabel = "Find destinations" }: { onSubmit: () => void; busy?: boolean; submitLabel?: string }) {
  const { prefs, setPrefs } = useTrip();
  const { meta } = useMeta();
  const [adv, setAdv] = useState(false);
  const toggle = (k: "interests" | "excluded_activities" | "transport" | "dietary", v: string) => {
    const cur = prefs[k] as string[];
    setPrefs({ [k]: cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v] } as never);
  };
  const T = ({ k, v, children }: { k: "interests" | "excluded_activities" | "transport" | "dietary"; v: string; children: React.ReactNode }) => (
    <button type="button" className="chip" aria-pressed={(prefs[k] as string[]).includes(v)} onClick={() => toggle(k, v)}>{children}</button>
  );
  return (
    <form className="space-y-6" onSubmit={(e) => { e.preventDefault(); onSubmit(); }}>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="label" htmlFor="origin">Travelling from</label>
          <select id="origin" className="field" value={prefs.origin ?? ""} onChange={(e) => setPrefs({ origin: e.target.value || null })} required>
            <option value="">Choose your city…</option>
            {meta?.origins.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="budget">Total budget (₹, whole group)</label>
          <input id="budget" className="field" type="number" min={0} step={500} placeholder="e.g. 30000" value={prefs.budget ?? ""} onChange={(e) => setPrefs({ budget: num(e.target.value) })} />
        </div>
        <div>
          <label className="label" htmlFor="days">Trip length (days)</label>
          <input id="days" className="field" type="number" min={1} max={14} placeholder="e.g. 4" value={prefs.duration_days ?? ""} onChange={(e) => setPrefs({ duration_days: num(e.target.value) })} />
        </div>
        <div>
          <label className="label" htmlFor="trav">Travellers</label>
          <input id="trav" className="field" type="number" min={1} max={12} value={prefs.travellers} onChange={(e) => setPrefs({ travellers: Math.min(12, Math.max(1, Number(e.target.value) || 1)) })} />
        </div>
        <div>
          <label className="label" htmlFor="climate">Preferred climate</label>
          <select id="climate" className="field" value={prefs.climate ?? ""} onChange={(e) => setPrefs({ climate: (e.target.value || null) as never })}>
            <option value="">No preference</option>
            {meta?.options.climates.map((c) => <option key={c} value={c}>{cap(c)}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="season">Travel season</label>
          <select id="season" className="field" value={prefs.season ?? ""} onChange={(e) => setPrefs({ season: e.target.value || null })}>
            <option value="">Flexible</option>
            {meta?.options.seasons.map((c) => <option key={c} value={c}>{cap(c)}</option>)}
          </select>
        </div>
      </div>

      <fieldset>
        <legend className="label">Interests</legend>
        <div className="flex flex-wrap gap-2">{(meta?.options.interests ?? []).map((i) => <T key={i} k="interests" v={i}>{INTEREST_LABEL[i] ?? cap(i)}</T>)}</div>
      </fieldset>

      <fieldset>
        <legend className="label">Who is travelling?</legend>
        <div className="flex flex-wrap gap-2">
          {(["solo", "couple", "family", "friends"] as const).map((s) => (
            <button type="button" key={s} className="chip" aria-pressed={prefs.travel_style === s} onClick={() => setPrefs({ travel_style: prefs.travel_style === s ? null : s })}>{cap(s)}</button>
          ))}
          <button type="button" className="chip" aria-pressed={prefs.elderly} onClick={() => setPrefs({ elderly: !prefs.elderly })}>Elderly traveller</button>
          <button type="button" className="chip" aria-pressed={prefs.children} onClick={() => setPrefs({ children: !prefs.children })}>Children</button>
          <button type="button" className="chip" aria-pressed={prefs.accessibility_required} onClick={() => setPrefs({ accessibility_required: !prefs.accessibility_required })}>Step-free access required</button>
        </div>
      </fieldset>

      <button type="button" className="text-sm font-semibold text-violet underline-offset-4 hover:underline" aria-expanded={adv} onClick={() => setAdv(!adv)}>{adv ? "Hide" : "Show"} advanced preferences</button>
      {adv && (
        <div className="animate-rise space-y-5 rounded-2xl bg-lavender/50 p-5">
          <fieldset>
            <legend className="label">Pace</legend>
            <div className="flex gap-2">{(["relaxed", "balanced", "packed"] as const).map((p) => <button type="button" key={p} className="chip" aria-pressed={prefs.pace === p} onClick={() => setPrefs({ pace: p })}>{cap(p)}</button>)}</div>
          </fieldset>
          <fieldset>
            <legend className="label">Transport you accept</legend>
            <div className="flex flex-wrap gap-2">{(["bus", "train", "car", "flight"] as Mode[]).map((m) => <T key={m} k="transport" v={m}>{cap(m)}</T>)}</div>
            <p className="mt-1 text-xs text-ink/60">Leave empty to allow all.</p>
          </fieldset>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="acc">Accommodation</label>
              <select id="acc" className="field" value={prefs.accommodation ?? ""} onChange={(e) => setPrefs({ accommodation: (e.target.value || null) as never })}>
                <option value="">Let TripWise choose</option>
                {meta?.options.tiers.map((t) => <option key={t} value={t}>{cap(t)}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="start">Start date (optional)</label>
              <input id="start" type="date" className="field" value={prefs.start_date ?? ""} onChange={(e) => setPrefs({ start_date: e.target.value || null })} />
            </div>
          </div>
          <fieldset>
            <legend className="label">Activities to avoid</legend>
            <div className="flex flex-wrap gap-2">{["trekking", "temples", "nightlife", "water sports", "shopping"].map((a) => <T key={a} k="excluded_activities" v={a}>{cap(a)}</T>)}</div>
          </fieldset>
          <fieldset>
            <legend className="label">Dietary</legend>
            <div className="flex flex-wrap gap-2">{["vegetarian", "vegan", "jain", "halal"].map((a) => <T key={a} k="dietary" v={a}>{cap(a)}</T>)}</div>
          </fieldset>
          <label className="flex items-center gap-2 text-sm text-royal">
            <input type="checkbox" checked={prefs.randomize} onChange={(e) => setPrefs({ randomize: e.target.checked })} className="h-4 w-4 accent-violet" />
            Surprise me (adds small seeded variety; same seed gives the same result)
          </label>
        </div>
      )}
      <button className="btn-gold w-full py-3 text-base" disabled={busy}>{busy ? "Thinking…" : submitLabel}</button>
    </form>
  );
}
