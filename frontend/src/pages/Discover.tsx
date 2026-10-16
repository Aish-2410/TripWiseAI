import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Search } from "lucide-react";
import { api } from "../lib/api";
import { useTrip } from "../lib/store";
import type { DestinationLite } from "../lib/types";
import { DestImage, Disclaimer, EmptyState, ErrorNote, PageHeader, Skeleton } from "../components/ui";
import DestinationDrawer from "../components/DestinationDrawer";
import CompareTray from "../components/CompareTray";
import { useToast } from "../components/Toast";
import { cap } from "../lib/format";

export default function Discover() {
  const [all, setAll] = useState<DestinationLite[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [climate, setClimate] = useState("");
  const [tag, setTag] = useState("");
  const [detail, setDetail] = useState<string | null>(null);
  const { prefs, buildPlan, compareIds, toggleCompare } = useTrip();
  const nav = useNavigate();
  const [sp, setSp] = useSearchParams();
  useEffect(() => { const d = sp.get("dest"); if (d) { setDetail(d); setSp({}, { replace: true }); } }, [sp, setSp]);
  const toast = useToast();
  const load = () => { setErr(null); api.destinations().then(setAll).catch((e) => setErr(e.message)); };
  useEffect(load, []);

  const tags = useMemo(() => [...new Set((all ?? []).flatMap((d) => d.tags))].sort(), [all]);
  const shown = useMemo(() => (all ?? []).filter((d) =>
    (!q || `${d.name} ${d.state} ${d.description}`.toLowerCase().includes(q.toLowerCase())) && (!climate || d.climate === climate) && (!tag || d.tags.includes(tag))), [all, q, climate, tag]);
  const names = Object.fromEntries((all ?? []).map((d) => [d.id, d.name]));

  const plan = async (id: string) => {
    if (!prefs.origin) { toast.err("Choose where you are travelling from first."); nav("/planner"); return; }
    try { await buildPlan(id); nav("/itinerary"); } catch (e: any) { toast.err(e.message); }
  };

  return (
    <>
      <PageHeader eyebrow="Discover" title="The collection">Browse every destination in the dataset. For a ranking tailored to your budget, time and interests, use the Trip planner.</PageHeader>
      <div className="mx-auto max-w-7xl px-5 py-10">
        <div className="mb-8 grid gap-3 sm:grid-cols-[1fr_12rem_12rem]">
          <div className="relative"><Search className="pointer-events-none absolute left-3.5 top-3 h-4 w-4 text-mauve" /><input className="field !pl-10" placeholder="Search places, states, themes…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search destinations" /></div>
          <select className="field" value={climate} onChange={(e) => setClimate(e.target.value)} aria-label="Filter by climate"><option value="">Any climate</option>{["cold", "cool", "mild", "warm", "hot"].map((c) => <option key={c} value={c}>{cap(c)}</option>)}</select>
          <select className="field" value={tag} onChange={(e) => setTag(e.target.value)} aria-label="Filter by theme"><option value="">Any theme</option>{tags.map((c) => <option key={c} value={c}>{cap(c)}</option>)}</select>
        </div>
        {err && <ErrorNote message={err} onRetry={load} />}
        {!all && !err && <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-80" />)}</div>}
        {all && shown.length === 0 && <EmptyState title="No destinations match" action={<button className="btn-ghost" onClick={() => { setQ(""); setClimate(""); setTag(""); }}>Clear filters</button>}>Try a different search or remove a filter.</EmptyState>}
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {shown.map((d) => (
            <article key={d.id} className="card animate-rise overflow-hidden">
              <div className="relative"><DestImage wiki={d.wiki} name={d.name} className="h-48" />
                <div className="absolute bottom-3 left-4 text-ivory"><h2 className="font-display text-2xl">{d.name}</h2><p className="text-xs text-champagne">{d.state}{d.climate ? ` · ${cap(d.climate)} climate` : ""}</p></div></div>
              <div className="space-y-3 p-5">
                <p className="line-clamp-3 text-sm leading-relaxed text-ink/80">{d.description}</p>
                <div className="flex flex-wrap gap-1.5">{d.tags.slice(0, 5).map((t) => <span key={t} className="rounded-full bg-lavender px-2.5 py-0.5 text-[0.7rem] text-violet">{t}</span>)}</div>
                <p className="text-xs text-ink/60">Best: {d.best_seasons.join(", ")} · {d.min_days}-{d.max_days} days</p>
                <div className="flex flex-wrap gap-2 pt-1">
                  <button className="btn-gold btn-sm" onClick={() => plan(d.id)}>Plan this trip</button>
                  <button className="btn-ghost btn-sm" onClick={() => setDetail(d.id)}>Details</button>
                  <button className="btn-ghost btn-sm" aria-pressed={compareIds.includes(d.id)} onClick={() => toggleCompare(d.id)}>{compareIds.includes(d.id) ? "✓ Comparing" : "Compare"}</button>
                </div>
              </div>
            </article>
          ))}
        </div>
        <div className="mt-10"><Disclaimer>The sample dataset contains {all?.length ?? "…"} destinations. It is illustrative, not a complete or live catalogue.</Disclaimer></div>
      </div>
      <DestinationDrawer id={detail} onClose={() => setDetail(null)} onPlan={plan} />
      <CompareTray names={names} />
    </>
  );
}
