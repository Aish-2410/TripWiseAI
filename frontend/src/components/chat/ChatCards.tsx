import { useNavigate } from "react-router-dom";
import { ArrowRight, BarChart3, GitCompareArrows, Hotel, ListChecks, Map as MapIcon, Route, SlidersHorizontal } from "lucide-react";
import { useTrip } from "../../lib/store";
import { inr, cap } from "../../lib/format";
import type { ChatReply } from "../../lib/types";

type Action = ChatReply["actions"][number];

const LinkBtn = ({ icon: I, children, onClick }: { icon: typeof Hotel; children: React.ReactNode; onClick: () => void }) => (
  <button className="btn-ghost btn-sm" onClick={onClick}><I className="h-3.5 w-3.5" /> {children}</button>
);

/** Plain-language lead for a reply: cards already show the list, so the list lines are dropped from the text. */
export function leadText(text: string, actions: Action[]): string {
  const hasCards = actions.some((a) => ["stays", "transport", "activities"].includes(a.type));
  if (!hasCards) return text;
  return text.split("\n").filter((l) => !/^\s*(\d+\.|-)\s/.test(l) && !l.startsWith("Sample data:")).join("\n").trim();
}

export default function ChatCards({ actions, onSend }: { actions: Action[]; onSend: (t: string) => void }) {
  return <>{actions.map((a, i) => <Card key={i} a={a} onSend={onSend} />)}</>;
}

function Card({ a, onSend }: { a: Action; onSend: (t: string) => void }) {
  const nav = useNavigate();
  const { plan, setCompare } = useTrip();

  if (a.type === "plan") {
    const p = a.plan ?? plan;
    if (!p) return null;
    const c = p.costs;
    return (
      <div className="mt-4 overflow-hidden rounded-2xl border border-gold/40 bg-white">
        <div className="flex flex-wrap items-center justify-between gap-2 bg-royal px-4 py-2.5 text-ivory">
          <p className="font-display text-lg">{p.destination_name} · {p.days.length} days</p>
          <p className="text-xs text-champagne">{inr(c.total)} total · {c.over_budget ? <b className="text-red-200">over budget by {inr(c.overrun)}</b> : "within budget"}</p>
        </div>
        <ol className="space-y-1 px-4 py-3 text-sm">
          {p.days.map((d) => (
            <li key={d.day} className="flex gap-3"><b className="w-12 shrink-0 text-violet">Day {d.day}</b><span className="text-ink/80">{d.schedule.items.filter((x) => x.kind === "activity").map((x) => x.title).join(" · ") || "Free day"}</span></li>
          ))}
        </ol>
        <div className="flex flex-wrap gap-2 border-t border-royal/10 px-4 py-3">
          <button className="btn-gold btn-sm" onClick={() => nav("/itinerary")}><MapIcon className="h-3.5 w-3.5" /> Open itinerary</button>
          <LinkBtn icon={BarChart3} onClick={() => nav("/itinerary?tab=budget")}>View budget breakdown</LinkBtn>
          <LinkBtn icon={Hotel} onClick={() => nav("/itinerary?tab=stay")}>Stays &amp; transport</LinkBtn>
        </div>
      </div>
    );
  }

  if (a.type === "recommendations") {
    const ranked = (a.data?.ranked ?? []) as any[];
    if (!ranked.length) return null;
    return (
      <div className="mt-4 space-y-2">
        {ranked.slice(0, 3).map((r) => (
          <div key={r.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-royal/10 bg-white p-3.5">
            <div>
              <p className="font-display text-lg text-royal">{r.name} <span className="ml-1 rounded-full bg-champagne px-2 py-0.5 align-middle font-sans text-[0.68rem] font-bold text-plum">{Math.round(r.match_score)}% match</span></p>
              <p className="text-xs text-ink/65">{r.state} · about {inr(r.cost?.typical)} · {r.one_way_hours} h by {r.transport_best}</p>
            </div>
            <button className="btn-ghost btn-sm" onClick={() => onSend(`Plan a trip to ${r.name}`)}>Plan this <ArrowRight className="h-3.5 w-3.5" /></button>
          </div>
        ))}
        <div className="flex flex-wrap gap-2 pt-1">
          <LinkBtn icon={GitCompareArrows} onClick={() => { setCompare(ranked.slice(0, 3).map((r) => r.id)); nav("/discover"); }}>Compare options</LinkBtn>
          <LinkBtn icon={SlidersHorizontal} onClick={() => nav("/planner")}>Refine in trip planner</LinkBtn>
        </div>
      </div>
    );
  }

  if (a.type === "stays" && a.data) {
    const d = a.data;
    const samePlan = plan?.destination_id === d.destination_id;
    return (
      <div className="mt-4 space-y-2.5">
        <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
          {d.results?.map((s: any) => (
            <div key={s.id} className="flex flex-col rounded-2xl border border-gold/40 bg-white p-3.5 text-xs text-ink shadow-soft">
              <div className="flex items-start justify-between gap-2">
                <p className="font-display text-base leading-tight text-royal">{s.name}</p>
                <span className="shrink-0 rounded-full bg-champagne px-2 py-0.5 text-[0.62rem] font-bold uppercase text-plum">{s.tier}</span>
              </div>
              <p className="mt-1.5 text-sm"><b>{inr(s.price_inr)}</b> <span className="text-ink/60">per {s.price_unit === "per_bed" ? "bed" : "room"} / night (est.)</span></p>
              <p className="text-ink/65">{inr(s.total_inr)} for {d.nights} night{d.nights > 1 ? "s" : ""}{d.nights_assumed ? " (assumed)" : ""}</p>
              <p className="mt-1 text-ink/65">Star rating: not recorded{s.match === "alternative" ? " · closest tier" : ""}</p>
              {s.distance_to_target_km != null ? <p className="text-ink/65">{s.distance_to_target_km} km from {s.target_name}</p> : s.avg_distance_to_planned_km != null ? <p className="text-ink/65">~{s.avg_distance_to_planned_km} km from the main sights</p> : null}
              {s.amenities?.length > 0 && <p className="mt-1.5 flex flex-wrap gap-1">{s.amenities.map((x: string) => <span key={x} className="rounded-full bg-lavender px-2 py-0.5 text-[0.62rem] text-violet">{x}</span>)}</p>}
              <p className="mt-auto pt-2 text-[0.62rem] text-gold-deep">Sample record · no booking link or availability</p>
            </div>
          ))}
        </div>
        {d.alternatives?.length > 0 && <div className="flex flex-wrap gap-2">{d.alternatives.map((n: any) => <button key={n.id} className="chip" onClick={() => onSend(`Find hotels in ${n.name}`)}>{n.name} (~{n.km} km)</button>)}</div>}
        <div className="flex flex-wrap items-center gap-2">
          {d.total_records > (d.results?.length ?? 0) && <LinkBtn icon={ListChecks} onClick={() => onSend(`Show all hotels in ${d.destination_name}`)}>View all {d.total_records} stays</LinkBtn>}
          {samePlan ? <LinkBtn icon={Hotel} onClick={() => nav("/itinerary?tab=stay")}>Compare in my itinerary</LinkBtn> : <LinkBtn icon={MapIcon} onClick={() => onSend(`Plan a trip to ${d.destination_name}`)}>Build an itinerary here</LinkBtn>}
        </div>
        <p className="text-[0.68rem] leading-snug text-gold-deep">{d.disclaimer}</p>
      </div>
    );
  }

  if (a.type === "transport" && a.data?.options?.length) {
    const d = a.data;
    const tag = (m: string) => [["cheapest", "Cheapest"], ["fastest", "Fastest"], ["most_comfortable", "Most comfortable"], ["best_overall", "Best overall"]].filter(([k]) => d[k] === m).map(([, l]) => l);
    const samePlan = plan?.destination_id === d.destination_id;
    return (
      <div className="mt-4 space-y-2.5">
        <div className="overflow-x-auto rounded-2xl border border-royal/10 bg-white">
          <table className="w-full min-w-[22rem] text-left text-sm">
            <thead className="bg-lavender/60 text-xs text-violet"><tr><th className="p-3">Mode</th><th>Each way</th><th>Return / person</th><th>Group total</th><th>Comfort</th></tr></thead>
            <tbody>
              {d.options.map((o: any) => (
                <tr key={o.mode} className="border-t border-royal/10 align-top">
                  <td className="p-3 font-semibold capitalize text-royal">{cap(o.mode)}<div className="mt-0.5 flex flex-wrap gap-1">{tag(o.mode).map((t) => <span key={t} className="rounded-full bg-champagne px-1.5 text-[0.58rem] font-bold uppercase text-plum">{t}</span>)}</div></td>
                  <td>{o.one_way_hours} h</td><td>{inr(o.per_person_round_trip_inr)}</td><td>{inr(o.round_trip_group_inr)}</td><td>{o.comfort}/5</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="border-t border-royal/10 p-2.5 text-[0.68rem] text-gold-deep">Modelled estimates from a distance model, not live fares or timetables.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {samePlan ? <LinkBtn icon={Route} onClick={() => nav("/itinerary?tab=stay")}>Compare in my itinerary</LinkBtn> : <LinkBtn icon={MapIcon} onClick={() => onSend(`Plan a trip to ${d.destination_name}`)}>Plan a trip to {d.destination_name}</LinkBtn>}
        </div>
      </div>
    );
  }

  if (a.type === "activities" && a.data?.items?.length) {
    const d = a.data;
    return (
      <div className="mt-4 space-y-2.5">
        <ul className="grid gap-2.5 sm:grid-cols-2">
          {d.items.map((x: any) => (
            <li key={x.id} className="rounded-2xl border border-royal/10 bg-white p-3.5 text-xs">
              <p className="font-display text-base leading-tight text-royal">{x.name}</p>
              <p className="mt-1 text-ink/75">{x.description}</p>
              <p className="mt-1.5 text-ink/55">~{Math.round(x.duration_min)} min · {x.fee_inr ? `entry ~${inr(x.fee_inr)}` : "no fee recorded"}{x.distance_km != null ? ` · ${x.distance_km} km away` : ""}{x.accessible === false ? " · not step-free" : ""}</p>
            </li>
          ))}
        </ul>
        <LinkBtn icon={ListChecks} onClick={() => nav(`/discover?dest=${d.destination_id}`)}>View all attractions in {d.destination_name}</LinkBtn>
      </div>
    );
  }

  if (a.type === "weather" && a.data) {
    const w = a.data;
    return (
      <div className="mt-4 rounded-2xl border border-royal/10 bg-white p-4 text-sm">
        <p className="font-display text-lg text-royal">{w.destination_name}</p>
        <p>Typical climate: <b>{w.climate ?? "not recorded"}</b></p>
        <p>Best seasons: <b>{w.best_seasons?.length ? w.best_seasons.join(", ") : "not recorded"}</b></p>
        <p className="mt-1 text-xs text-gold-deep">Dataset information only. There is no live weather or forecast source.</p>
      </div>
    );
  }

  if (a.type === "comparison" && a.data?.destinations) {
    const cols = a.data.destinations as any[];
    return (
      <div className="mt-4 space-y-2.5">
        <div className="overflow-x-auto rounded-2xl border border-royal/10 bg-white">
          <table className="w-full min-w-[22rem] text-left text-sm">
            <thead className="bg-lavender/60 text-xs text-violet"><tr><th className="p-3" />{cols.map((c) => <th key={c.id} className="p-3 font-display text-base text-royal">{c.name}</th>)}</tr></thead>
            <tbody>
              {([["Climate", (c: any) => (c.climate ? cap(c.climate) : "unknown")], ["Best seasons", (c: any) => c.best_seasons.join(", ")], ["Suggested days", (c: any) => c.recommended_days],
                ["Estimated cost", (c: any) => (c.estimated_cost ? inr(c.estimated_cost) : "add a starting city")], ["Themes", (c: any) => c.activities.join(", ")]] as [string, (c: any) => string][]).map(([k, f]) => (
                <tr key={k} className="border-t border-royal/10 align-top"><th scope="row" className="p-3 text-xs font-semibold uppercase tracking-wider text-violet">{k}</th>{cols.map((c) => <td key={c.id} className="p-3">{f(c)}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
        <LinkBtn icon={GitCompareArrows} onClick={() => { setCompare(cols.map((c) => c.id)); nav("/discover"); }}>Open full comparison</LinkBtn>
      </div>
    );
  }

  if (a.type === "savings" && Array.isArray(a.data)) {
    return <div className="mt-4 flex flex-col items-start gap-2">{(a.data as any[]).map((o, i) => <button key={i} className="chip !whitespace-normal !text-left" onClick={() => onSend(`Apply option ${i + 1}`)}>{i + 1}. {o.description} · save {inr(o.saving)}</button>)}</div>;
  }
  return null;
}
