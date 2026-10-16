import { useState } from "react";
import { ChevronDown, GitCompareArrows, Wallet, Clock, Check, Info } from "lucide-react";
import type { Recommendation } from "../lib/types";
import { inr, hrs, cap } from "../lib/format";
import { DestImage, ScoreBars } from "./ui";

export default function DestinationCard({ r, comparing, onCompare, onPlan, onDetails, busy }: {
  r: Recommendation; comparing: boolean; onCompare: () => void; onPlan: () => void; onDetails: () => void; busy?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const fired = r.adjustments.filter((a) => a.fired);
  return (
    <article className="card animate-rise flex flex-col overflow-hidden">
      <div className="relative">
        <DestImage wiki={r.wiki} name={r.name} className="h-44" />
        <span className="absolute left-3 top-3 rounded-full bg-plum/85 px-3 py-1 text-xs font-semibold text-champagne">#{r.rank}</span>
        <span className="absolute right-3 top-3 rounded-full bg-gold px-3 py-1 text-sm font-bold text-plum" title="Weighted match score">{Math.round(r.match_score)}% match</span>
        <div className="absolute bottom-3 left-4 right-4 text-ivory">
          <h3 className="font-display text-2xl leading-tight">{r.name}</h3>
          <p className="text-xs text-champagne">{r.state} · {cap(r.type)}</p>
        </div>
      </div>
      <div className="flex flex-1 flex-col gap-3 p-5">
        <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-royal">
          <span className="inline-flex items-center gap-1.5"><Wallet className="h-4 w-4 text-gold-deep" /> {r.cost.typical ? `~${inr(r.cost.typical)}` : "cost unknown"}{r.cost.floor && r.cost.typical && r.cost.floor !== r.cost.typical ? <span className="text-ink/55"> (from {inr(r.cost.floor)})</span> : null}</span>
          <span className="inline-flex items-center gap-1.5"><Clock className="h-4 w-4 text-gold-deep" /> {hrs(r.one_way_hours)} {r.transport_best ? `by ${r.transport_best}` : ""}</span>
        </div>
        <p className="text-sm leading-relaxed text-ink/80">{r.explanation}</p>
        {r.attractions_preview.length > 0 && <p className="text-xs text-ink/60">Highlights: {r.attractions_preview.join(" · ")}</p>}
        {r.limitations.length > 0 && (
          <ul className="space-y-1 text-xs text-gold-deep">{r.limitations.map((l, i) => <li key={i} className="flex gap-1.5"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />{l}</li>)}</ul>
        )}
        <button className="mt-1 inline-flex items-center gap-1 self-start text-xs font-semibold text-violet" aria-expanded={open} onClick={() => setOpen(!open)}>
          <ChevronDown className={`h-4 w-4 transition ${open ? "rotate-180" : ""}`} /> Why this score?
        </button>
        {open && (
          <div className="animate-rise space-y-4 rounded-xl bg-lavender/40 p-4">
            <ScoreBars components={r.components} />
            {fired.length > 0 && (
              <div>
                <p className="label">Rules that fired</p>
                <ul className="space-y-1.5 text-xs">{fired.map((a) => <li key={a.rule_id}><b className="text-royal">{a.rule_id}</b> {a.points > 0 ? "+" : ""}{a.points} pts: {a.reason}</li>)}</ul>
              </div>
            )}
            {r.stravl_affinity?.available && (
              <p className="text-xs text-ink/70"><b className="text-royal">Stravl signal (informational, not in score):</b> {r.stravl_affinity.note ?? `estimated ${Math.round((r.stravl_affinity.p_yes ?? 0) * 100)}% chance of a "yes" swipe`}</p>
            )}
          </div>
        )}
        <div className="mt-auto flex flex-wrap gap-2 pt-2">
          <button className="btn-gold btn-sm" onClick={onPlan} disabled={busy}>Build itinerary</button>
          <button className="btn-ghost btn-sm" onClick={onDetails}>Details</button>
          <button className="btn-ghost btn-sm" aria-pressed={comparing} onClick={onCompare}>{comparing ? <Check className="h-3.5 w-3.5" /> : <GitCompareArrows className="h-3.5 w-3.5" />} {comparing ? "Added" : "Compare"}</button>
        </div>
      </div>
    </article>
  );
}
