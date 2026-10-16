import { ArrowDown, ArrowUp, Footprints, MapPin, Trash2, Utensils, Car } from "lucide-react";
import type { Day } from "../lib/types";
import { inr, mins } from "../lib/format";

export default function DayCard({ day, total, editing, activeId, onActive, onRemove, onMove, busy }: {
  day: Day; total: number; editing: boolean; activeId: string | null; onActive: (id: string) => void;
  onRemove: (id: string) => void; onMove: (id: string, toDay: number) => void; busy?: boolean;
}) {
  const s = day.schedule;
  return (
    <section className="card break-inside-avoid overflow-hidden" aria-label={`Day ${day.day}`}>
      <header className="flex flex-wrap items-center justify-between gap-2 bg-royal px-5 py-3 text-ivory">
        <h3 className="font-display text-xl">Day {day.day}{day.date ? <span className="ml-2 text-sm text-champagne">{day.date}</span> : null}</h3>
        <p className="text-xs text-champagne">{mins(s.activity_minutes)} activities · {mins(s.travel_minutes)} travel · {Math.round(s.local_km)} km local</p>
      </header>
      <ol className="divide-y divide-royal/10">
        {s.items.map((it, i) => {
          const isAct = it.kind === "activity" && it.attraction_id;
          const active = isAct && activeId === it.attraction_id;
          return (
            <li key={i} className={`flex gap-4 px-5 py-3.5 transition ${active ? "bg-champagne/40" : ""}`}>
              <div className="w-14 shrink-0 pt-0.5 text-xs font-semibold text-violet">{it.start}</div>
              <div className="min-w-0 flex-1">
                {isAct ? (
                  <button className="flex items-center gap-1.5 text-left font-semibold text-royal hover:text-violet" onClick={() => onActive(it.attraction_id!)}>
                    <MapPin className="h-4 w-4 shrink-0 text-gold-deep" />{it.title}
                  </button>
                ) : (
                  <p className="flex items-center gap-1.5 font-medium text-ink/80">
                    {it.kind === "meal" ? <Utensils className="h-4 w-4 text-gold-deep" /> : it.kind === "travel" ? <Car className="h-4 w-4 text-gold-deep" /> : <Footprints className="h-4 w-4 text-gold-deep" />}{it.title}
                  </p>
                )}
                <p className="mt-0.5 text-xs text-ink/60">
                  {mins(it.minutes)}{it.fee_group ? ` · entry ${inr(it.fee_group)} (est.)` : isAct && !it.fee_known ? " · fee not recorded" : ""}
                  {it.accessible === false ? " · not step-free" : ""}
                </p>
                {isAct && it.description && <p className="mt-1 text-xs leading-relaxed text-ink/70">{it.description}</p>}
              </div>
              {editing && isAct && (
                <div className="no-print flex shrink-0 items-start gap-1">
                  {day.day > 1 && <button disabled={busy} className="rounded p-1.5 hover:bg-lavender" aria-label={`Move ${it.title} to day ${day.day - 1}`} onClick={() => onMove(it.attraction_id!, day.day - 1)}><ArrowUp className="h-4 w-4" /></button>}
                  {day.day < total && <button disabled={busy} className="rounded p-1.5 hover:bg-lavender" aria-label={`Move ${it.title} to day ${day.day + 1}`} onClick={() => onMove(it.attraction_id!, day.day + 1)}><ArrowDown className="h-4 w-4" /></button>}
                  <button disabled={busy} className="rounded p-1.5 text-red-700 hover:bg-red-50" aria-label={`Remove ${it.title}`} onClick={() => onRemove(it.attraction_id!)}><Trash2 className="h-4 w-4" /></button>
                </div>
              )}
            </li>
          );
        })}
        {s.items.length === 0 && <li className="px-5 py-4 text-sm text-ink/60">Free day.</li>}
      </ol>
    </section>
  );
}
