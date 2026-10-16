import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { inr, cap, mins } from "../lib/format";
import { DestImage, ErrorNote, Modal, Skeleton, Disclaimer } from "./ui";

export default function DestinationDrawer({ id, onClose, onPlan }: { id: string | null; onClose: () => void; onPlan: (id: string) => void }) {
  const [d, setD] = useState<Awaited<ReturnType<typeof api.destination>> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!id) return;
    setD(null); setErr(null);
    api.destination(id).then(setD).catch((e) => setErr(e.message));
  }, [id]);
  return (
    <Modal open={!!id} onClose={onClose} title={d?.destination.name ?? "Destination"} wide>
      {err && <ErrorNote message={err} />}
      {!d && !err && <Skeleton className="h-72" />}
      {d && (
        <div className="space-y-6">
          <div className="overflow-hidden rounded-2xl"><DestImage wiki={d.destination.wiki} name={d.destination.name} className="h-56" /></div>
          <p className="leading-relaxed text-ink/85">{d.destination.description}</p>
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            {[["State", d.destination.state], ["Climate", d.destination.climate ? cap(d.destination.climate) : "unknown"], ["Best seasons", d.destination.best_seasons.join(", ")], ["Suggested stay", `${d.destination.min_days}-${d.destination.max_days} days`]].map(([k, v]) => (
              <div key={k} className="rounded-xl bg-lavender/50 p-3"><dt className="label !mb-0.5">{k}</dt><dd className="text-royal">{v}</dd></div>
            ))}
          </dl>
          <section>
            <h3 className="font-display text-xl text-royal">Attractions in the dataset</h3>
            <ul className="mt-2 grid gap-2 sm:grid-cols-2">
              {d.attractions.map((a) => (
                <li key={a.id} className="rounded-xl border border-royal/10 p-3 text-sm">
                  <b className="text-royal">{a.name}</b>
                  <div className="text-xs text-ink/60">{mins(a.duration_min)} · {a.fee_inr ? `${inr(a.fee_inr)} entry (est.)` : "free / fee not recorded"} · {a.tags.join(", ")}</div>
                </li>
              ))}
            </ul>
          </section>
          <section>
            <h3 className="font-display text-xl text-royal">Sample stays</h3>
            <ul className="mt-2 grid gap-2 sm:grid-cols-2">
              {d.accommodation.map((s: any) => <li key={s.id} className="rounded-xl border border-royal/10 p-3 text-sm"><b className="text-royal">{s.name}</b><div className="text-xs text-ink/60">{cap(s.tier)} · {inr(s.price_inr)} {s.price_unit.replace("_", " ")} (est.)</div></li>)}
            </ul>
          </section>
          <Disclaimer />
          <div className="flex justify-end"><button className="btn-gold" onClick={() => onPlan(d.destination.id)}>Build itinerary for {d.destination.name}</button></div>
        </div>
      )}
    </Modal>
  );
}
