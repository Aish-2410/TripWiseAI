import { useState } from "react";
import { X } from "lucide-react";
import { useChat } from "../../lib/chat";
import { useTrip } from "../../lib/store";
import { useToast } from "../Toast";
import type { Prefs } from "../../lib/types";

const FIELDS: [keyof Prefs, string][] = [["origin", "From"], ["budget", "Trip budget"], ["duration_days", "Days"], ["travellers", "Travellers"], ["climate", "Climate"], ["interests", "Interests"], ["excluded_activities", "Avoiding"], ["pace", "Pace"]];

/** "What I understood": the plain-language reading of the latest request, plus corrections that apply to the next request. */
export default function UnderstoodPanel({ onClose }: { onClose: () => void }) {
  const { lastUnderstood, focus, patchContext } = useChat();
  const { prefs } = useTrip();
  const toast = useToast();
  const [fix, setFix] = useState(false);
  const save = async (patch: Record<string, unknown>) => {
    try { await patchContext(patch); toast.ok("Got it. I will use that from now on."); } catch (e: any) { toast.err(e.message); }
  };
  return (
    <div className="animate-rise rounded-2xl border border-gold/40 bg-white p-4 text-sm shadow-soft" role="region" aria-label="What I understood">
      <div className="flex items-start justify-between">
        <div>
          <p className="eyebrow">What I understood</p>
          {lastUnderstood ? <p className="font-display text-lg text-royal">{lastUnderstood.intent}</p> : <p className="text-ink/60">Send a message and I will show how I read it.</p>}
        </div>
        <button aria-label="Close" className="rounded-full p-1.5 hover:bg-lavender" onClick={onClose}><X className="h-4 w-4" /></button>
      </div>
      {lastUnderstood && lastUnderstood.items.length > 0 && (
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
          {lastUnderstood.items.map(([k, v], i) => <div key={i} className="contents"><dt className="font-semibold text-violet">{k}</dt><dd className={v === "Not specified" ? "text-ink/45" : "text-ink"}>{v}</dd></div>)}
        </dl>
      )}
      <button className="mt-3 text-xs font-semibold text-violet underline-offset-2 hover:underline" aria-expanded={fix} onClick={() => setFix(!fix)}>{fix ? "Hide corrections" : "Not right? Correct a detail"}</button>
      {fix && (
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          <label className="text-xs"><span className="label !mb-1">Destination</span>
            <input className="field !py-1.5 !text-xs" defaultValue={focus?.name ?? ""} key={`d-${focus?.id ?? ""}`} placeholder="not set" onBlur={(e) => { const v = e.target.value.trim(); if (v !== (focus?.name ?? "")) save({ destination: v || null }); }} /></label>
          {FIELDS.map(([k, label]) => {
            const v = prefs[k] as unknown;
            const shown = Array.isArray(v) ? v.join(", ") : v == null ? "" : String(v);
            return (
              <label key={k} className="text-xs"><span className="label !mb-1">{label}</span>
                <input className="field !py-1.5 !text-xs" defaultValue={shown} key={`${k}-${shown}`} placeholder="not set"
                  onBlur={(e) => { const nv = e.target.value.trim(); if (nv === shown) return; const arr = Array.isArray(v); const num = typeof v === "number" || k === "budget" || k === "duration_days";
                    save({ [k]: arr ? nv.split(",").map((x) => x.trim()).filter(Boolean) : nv === "" ? null : num ? Number(nv) : nv }); }} /></label>
            );
          })}
          <p className="text-[0.68rem] text-ink/55 sm:col-span-2">Edit a value and click away. Corrections apply to your next request.</p>
        </div>
      )}
    </div>
  );
}
