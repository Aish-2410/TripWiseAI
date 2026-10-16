import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Frown, SlidersHorizontal } from "lucide-react";
import { useTrip } from "../lib/store";
import { api } from "../lib/api";
import PrefsForm, { useMeta } from "../components/PrefsForm";
import DestinationCard from "../components/DestinationCard";
import DestinationDrawer from "../components/DestinationDrawer";
import CompareTray from "../components/CompareTray";
import { Disclaimer, EmptyState, ErrorNote, PageHeader, Skeleton } from "../components/ui";
import { useToast } from "../components/Toast";
import { inr } from "../lib/format";

export default function Planner() {
  const { prefs, recs, recsLoading, recommend, buildPlan, compareIds, toggleCompare } = useTrip();
  const nav = useNavigate();
  const toast = useToast();
  const { meta } = useMeta();
  const [sort, setSort] = useState<"match" | "cost">("match");
  const [error, setError] = useState<string | null>(null);
  const [building, setBuilding] = useState<string | null>(null);
  const [detail, setDetail] = useState<string | null>(null);
  const [showW, setShowW] = useState(false);
  const [cfg, setCfg] = useState<any>(null);

  const run = async (s = sort) => {
    setError(null);
    try { await recommend(s); } catch (e: any) { setError(e.message); }
  };
  const plan = async (id: string) => {
    setBuilding(id); setDetail(null);
    try { await buildPlan(id); nav("/itinerary"); } catch (e: any) { toast.err(e.message); } finally { setBuilding(null); }
  };
  useEffect(() => { if (showW && !cfg) api.config().then(setCfg).catch((e) => toast.err(e.message)); }, [showW, cfg, toast]);

  const names: Record<string, string> = {};
  recs?.ranked.forEach((r) => (names[r.id] = r.name));
  const need = recs?.needs_info?.length ? recs : null;

  return (
    <>
      <PageHeader eyebrow="Trip planner" title="Tell us how you like to travel">
        Hard constraints (budget, time, accessibility, exclusions) filter first; the survivors are then ranked by a transparent weighted score. Leave a field empty and it is simply not used.
      </PageHeader>
      <div className="mx-auto grid max-w-7xl gap-8 px-5 py-10 lg:grid-cols-[24rem_1fr]">
        <aside className="card h-fit p-6 lg:sticky lg:top-4">
          <PrefsForm onSubmit={() => run()} busy={recsLoading} />
        </aside>
        <div className="space-y-6">
          {error && <ErrorNote message={error} onRetry={() => run()} />}
          {recsLoading && <div className="grid gap-5 md:grid-cols-2"><Skeleton className="h-96" /><Skeleton className="h-96" /></div>}
          {!recsLoading && !recs && !error && (
            <EmptyState title="Your matches will appear here">Choose where you start from, then add whichever details you know. Even just a starting city and a few interests works.</EmptyState>
          )}
          {need && !recsLoading && <ErrorNote message={need.message ?? `Please provide: ${need.needs_info.join(", ")}`} />}
          {recs && !need && !recsLoading && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-ink/70"><b className="text-royal">{recs.ranked.length}</b> of {recs.total_candidates ?? "?"} destinations passed your hard constraints.</p>
                <div className="flex items-center gap-2">
                  <label className="text-xs font-semibold text-violet" htmlFor="sort">Sort</label>
                  <select id="sort" className="field !w-auto !py-1.5" value={sort} onChange={(e) => { const s = e.target.value as "match" | "cost"; setSort(s); run(s); }}>
                    <option value="match">Best match</option><option value="cost">Lowest cost</option>
                  </select>
                  <button className="btn-ghost btn-sm" onClick={() => setShowW(!showW)} aria-expanded={showW}><SlidersHorizontal className="h-3.5 w-3.5" /> Weights</button>
                </div>
              </div>
              {showW && cfg && <WeightsEditor cfg={cfg} onChange={setCfg} onApply={() => run()} meta={!!meta} />}
              {recs.ranked.length === 0 ? (
                <EmptyState icon={<Frown className="h-6 w-6" />} title="Nothing satisfies every constraint">
                  <ul className="mt-2 space-y-1 text-left">{(recs.relaxation ?? []).map((t, i) => <li key={i}>• {t}</li>)}</ul>
                </EmptyState>
              ) : (
                <div className="grid gap-5 md:grid-cols-2">
                  {recs.ranked.map((r) => (
                    <DestinationCard key={r.id} r={r} comparing={compareIds.includes(r.id)} onCompare={() => toggleCompare(r.id)} onPlan={() => plan(r.id)} onDetails={() => setDetail(r.id)} busy={!!building} />
                  ))}
                </div>
              )}
              {building && <p className="text-sm text-violet" role="status">Searching itineraries for {building}…</p>}
              {recs.excluded.length > 0 && (
                <details className="card p-5">
                  <summary className="cursor-pointer font-semibold text-royal">{recs.excluded.length} destinations were excluded - and why</summary>
                  <ul className="mt-3 space-y-2 text-sm">{recs.excluded.map((e) => <li key={e.id}><b>{e.name}</b>, {e.state}{e.cost?.floor ? <span className="text-ink/50"> (cheapest est. {inr(e.cost.floor)})</span> : null}<ul className="ml-4 list-disc text-ink/70">{e.excluded_reasons.map((r, i) => <li key={i}>{r}</li>)}</ul></li>)}</ul>
                </details>
              )}
              <Disclaimer />
            </>
          )}
        </div>
      </div>
      <DestinationDrawer id={detail} onClose={() => setDetail(null)} onPlan={plan} />
      <CompareTray names={names} />
      <span className="sr-only">{prefs.origin}</span>
    </>
  );
}

function WeightsEditor({ cfg, onChange, onApply }: { cfg: any; onChange: (c: any) => void; onApply: () => void; meta: boolean }) {
  const toast = useToast();
  const w: Record<string, number> = cfg.weights;
  const set = (k: string, v: number) => onChange({ ...cfg, weights: { ...w, [k]: v } });
  const save = async () => {
    try { const r = await api.setWeights(w); onChange(r); toast.ok("Weights applied (normalised to sum to 1)."); onApply(); } catch (e: any) { toast.err(e.message); }
  };
  const reset = async () => { try { const r = await api.resetWeights(); onChange(r); toast.ok("Default weights restored."); onApply(); } catch (e: any) { toast.err(e.message); } };
  return (
    <div className="card animate-rise space-y-3 p-5">
      <h3 className="font-display text-xl text-royal">Scoring weights</h3>
      <p className="text-xs text-ink/65">Weights are normalised over the factors you actually specified. Change them to see the ranking react.</p>
      {Object.keys(w).map((k) => (
        <label key={k} className="grid grid-cols-[7rem_1fr_3rem] items-center gap-3 text-sm"><span className="capitalize text-royal">{k.replace("_", " ")}</span>
          <input type="range" min={0} max={1} step={0.05} value={w[k]} onChange={(e) => set(k, Number(e.target.value))} className="accent-violet" /><span className="text-right text-xs">{w[k].toFixed(2)}</span></label>
      ))}
      <div className="flex gap-2"><button className="btn-dark btn-sm" onClick={save}>Apply &amp; re-rank</button><button className="btn-ghost btn-sm" onClick={reset}>Reset</button></div>
    </div>
  );
}
