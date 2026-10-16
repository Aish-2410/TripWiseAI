import { useState } from "react";
import { GitCompareArrows, X } from "lucide-react";
import { useTrip } from "../lib/store";
import { api } from "../lib/api";
import { inr, cap } from "../lib/format";
import { Modal, ErrorNote, Skeleton } from "./ui";

export default function CompareTray({ names }: { names: Record<string, string> }) {
  const { compareIds, toggleCompare, clearCompare, prefs } = useTrip();
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<any[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const run = async () => {
    setOpen(true); setData(null); setErr(null);
    try { setData((await api.compare(compareIds, prefs)).destinations); } catch (e: any) { setErr(e.message); }
  };
  if (!compareIds.length) return null;
  const rows: [string, (d: any) => string][] = [
    ["Match score", (d) => (d.match_score != null ? `${Math.round(d.match_score)}%` : "set origin to score")],
    ["Typical cost", (d) => (d.estimated_cost ? inr(d.estimated_cost) : "-")],
    ["Cheapest option", (d) => (d.cheapest_cost ? inr(d.cheapest_cost) : "-")],
    ["Climate", (d) => (d.climate ? cap(d.climate) : "unknown")],
    ["Best seasons", (d) => d.best_seasons.join(", ")],
    ["Suggested days", (d) => d.recommended_days],
    ["Activities", (d) => d.activities.join(", ")],
    ["Getting there", (d) => d.transport.join("\n") || "-"],
    ["Pace", (d) => d.pace_note],
    ["Accessibility", (d) => d.accessibility ?? "unknown"],
    ["Hard constraints", (d) => (d.excluded?.length ? "Excluded: " + d.excluded.join("; ") : "Passes")],
  ];
  return (
    <>
      <div className="no-print fixed inset-x-0 bottom-0 z-40 border-t border-gold/40 bg-plum/95 px-4 py-3 backdrop-blur sm:bottom-4 sm:left-[calc(var(--sidebar-w,0px)+1rem)] sm:right-auto sm:rounded-2xl sm:border">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs font-semibold uppercase tracking-wider text-champagne">Compare ({compareIds.length}/3)</span>
          {compareIds.map((id) => (
            <span key={id} className="inline-flex items-center gap-1 rounded-full bg-white/10 px-3 py-1 text-xs text-ivory">{names[id] ?? id}<button aria-label={`Remove ${names[id] ?? id}`} onClick={() => toggleCompare(id)}><X className="h-3 w-3" /></button></span>
          ))}
          <button className="btn-gold btn-sm" disabled={compareIds.length < 2} onClick={run}><GitCompareArrows className="h-3.5 w-3.5" /> Compare</button>
          <button className="text-xs text-mauve underline" onClick={clearCompare}>Clear</button>
        </div>
      </div>
      <Modal open={open} onClose={() => setOpen(false)} title="Side-by-side comparison" wide>
        {err && <ErrorNote message={err} />}
        {!data && !err && <Skeleton className="h-64" />}
        {data && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[34rem] text-left text-sm">
              <thead><tr><th className="p-2" />{data.map((d) => <th key={d.id} className="p-2 font-display text-xl text-royal">{d.name}<div className="text-xs font-normal text-ink/60">{d.state}</div></th>)}</tr></thead>
              <tbody>
                {rows.map(([label, f]) => (
                  <tr key={label} className="border-t border-royal/10 align-top">
                    <th scope="row" className="p-2 text-xs font-semibold uppercase tracking-wider text-violet">{label}</th>
                    {data.map((d) => <td key={d.id} className="whitespace-pre-line p-2">{f(d)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-xs text-ink/60">Costs are estimates from sample data.</p>
          </div>
        )}
      </Modal>
    </>
  );
}
