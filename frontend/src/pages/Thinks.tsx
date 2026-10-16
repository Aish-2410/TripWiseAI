import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { useTrip } from "../lib/store";
import { useMeta } from "../components/PrefsForm";
import { EMPTY_PREFS, type Prefs } from "../lib/types";
import { ErrorNote, PageHeader, Skeleton, ScoreBars } from "../components/ui";
import { inr } from "../lib/format";

const H = ({ n, title, children }: { n: string; title: string; children?: React.ReactNode }) => (
  <div className="mb-4"><p className="eyebrow">{n}</p><h2 className="font-display text-3xl text-royal">{title}</h2>{children && <p className="mt-2 max-w-3xl text-sm leading-relaxed text-ink/75">{children}</p>}</div>
);

export default function Thinks() {
  const { prefs } = useTrip();
  const { meta } = useMeta();
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [usedDemo, setUsedDemo] = useState(false);

  const effective: Prefs | null = useMemo(() => {
    if (prefs.origin) return prefs;
    if (!meta) return null;
    return { ...EMPTY_PREFS, origin: meta.origins[0]?.id ?? null, duration_days: 4, budget: 25000, travellers: 2, interests: ["nature", "mountains"], climate: "cool" };
  }, [prefs, meta]);

  useEffect(() => {
    if (!effective) return;
    setUsedDemo(!prefs.origin); setData(null); setErr(null);
    api.thinks(effective).then(setData).catch((e) => setErr(e.message));
  }, [effective, prefs.origin]);

  const top = data?.recommendation?.ranked?.[0];
  return (
    <>
      <PageHeader eyebrow="How TripWise thinks" title="Every decision, in the open">
        This page runs the real engine live. Nothing here is a mock-up: the numbers come from the same code that builds your itinerary.
      </PageHeader>
      <div className="mx-auto max-w-7xl space-y-16 px-5 py-12">
        {usedDemo && <p className="rounded-xl border border-gold/50 bg-champagne/30 p-3 text-sm text-plum">You have not entered preferences yet, so this page uses a demo traveller ({effective?.travellers} people, {inr(effective?.budget)}, {effective?.duration_days} days, nature &amp; mountains, cool climate). Fill the planner to see your own reasoning.</p>}
        {err && <ErrorNote message={err} />}
        {!data && !err && <Skeleton className="h-96" />}
        {data && (
          <>
            <section>
              <H n="01 · Pipeline" title="From preferences to a plan">Constraints filter first, then six weighted factors rank what is left, rules add explainable adjustments, search builds the itinerary, and the Budget Guardian checks the bill.</H>
              <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                {["Hard constraints", "Weighted scoring", "Rule inference", "Itinerary search (beam)", "Budget Guardian"].map((s, i) => <li key={s} className="card p-4"><span className="font-display text-3xl text-gold">{i + 1}</span><p className="font-semibold text-royal">{s}</p></li>)}
              </ol>
            </section>

            {top && (
              <section>
                <H n="02 · Recommendation" title={`Why ${top.name} ranks first`}>Each bar is one factor’s score; the weight shows how much it counts. Factors you did not specify are dropped and the rest re-normalised, so unknowns are never silently scored.</H>
                <div className="grid gap-6 lg:grid-cols-2"><div className="card p-6"><ScoreBars components={top.components} /></div>
                  <div className="card p-6"><p className="label">Weights in use</p><ul className="text-sm">{Object.entries(data.weights).map(([k, v]) => <li key={k} className="flex justify-between border-b border-royal/10 py-1"><span className="capitalize">{k.replace("_", " ")}</span><b>{Number(v).toFixed(2)}</b></li>)}</ul>
                    <p className="label mt-4">Rules fired for {top.name}</p><ul className="space-y-1.5 text-sm">{top.adjustments.filter((a: any) => a.fired).map((a: any) => <li key={a.rule_id}><b className="text-royal">{a.rule_id}</b> ({a.points > 0 ? "+" : ""}{a.points}): {a.reason}</li>)}{!top.adjustments.some((a: any) => a.fired) && <li className="text-ink/60">None fired.</li>}</ul></div></div>
              </section>
            )}

            <section>
              <H n="03 · Knowledge base" title="Facts with provenance">{data.kb_stats.n_facts} subject-predicate-object facts about {data.kb_stats.n_entities} entities. Sample for the top destination:</H>
              <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
                <div className="card overflow-x-auto p-4"><table className="w-full text-left text-xs"><thead><tr className="text-violet"><th className="p-1.5">Subject</th><th>Predicate</th><th>Object</th><th>Source</th><th>Conf.</th></tr></thead>
                  <tbody>{(data.kb_facts ?? []).map((f: any, i: number) => <tr key={i} className="border-t border-royal/10"><td className="p-1.5">{f.s}</td><td>{f.p}</td><td>{String(f.o)}</td><td>{f.source}</td><td>{f.confidence}</td></tr>)}</tbody></table></div>
                <div className="card p-4 text-xs"><p className="label">Facts per predicate</p>{Object.entries(data.kb_stats.predicates).map(([k, v]) => <div key={k} className="flex justify-between border-b border-royal/10 py-1"><span>{k}</span><b>{String(v)}</b></div>)}</div>
              </div>
            </section>

            <section>
              <H n="04 · Rule engine" title="IF / THEN rules you can read">Each rule is plain data with a condition and effect. Ranking rules adjust scores, itinerary rules shape the plan, budget rules trigger the Guardian.</H>
              <div className="grid gap-3 md:grid-cols-2">{data.rules.map((r: any) => <article key={r.id} className="card p-4 text-sm"><div className="flex justify-between"><b className="text-royal">{r.id}</b><span className="rounded-full bg-lavender px-2 text-[0.65rem] uppercase text-violet">{r.kind}</span></div><p className="font-semibold">{r.name}</p><p className="mt-1 text-xs"><b>IF</b> {r.if}</p><p className="text-xs"><b>THEN</b> {r.then}</p></article>)}</div>
            </section>

            {data.route && <RouteDemo route={data.route} />}

            {data.plan_summary && (
              <section>
                <H n="06 · Itinerary search" title="Beam search">{data.plan_summary.search.note}</H>
                <div className="grid gap-3 sm:grid-cols-4">{[["Beam width", data.plan_summary.search.beam_width], ["Expanded", data.plan_summary.search.expanded], ["Generated", data.plan_summary.search.generated], ["Eligible attractions", data.plan_summary.search.eligible_attractions]].map(([k, v]) => <div key={String(k)} className="card p-4"><p className="label !mb-1">{k}</p><p className="font-display text-3xl text-royal">{String(v)}</p></div>)}</div>
                <p className="mt-3 text-sm text-ink/70">Heuristic: {data.plan_summary.search.heuristic}. Not proven optimal.</p>
              </section>
            )}

            {data.budget_demo && (
              <section>
                <H n="07 · Budget Guardian" title="What happens when the budget is 30% too tight">A tighter budget is imposed on the plan above and the Guardian applies ranked, explainable moves. Allowing preference changes is switched on for this demo.</H>
                <div className="card p-6 text-sm"><p className="mb-3 font-semibold text-royal">{data.budget_demo.message}</p>
                  <ol className="list-decimal space-y-1 pl-5">{(data.budget_demo.steps ?? []).map((s: any, i: number) => <li key={i}>{s.description} <span className="text-ink/55">(saves {inr(s.saving)}, now {inr(s.new_total)})</span></li>)}</ol></div>
              </section>
            )}
            {data.replan_demo && !data.replan_demo.error && (
              <section>
                <H n="08 · Re-planning" title="Change your mind, keep what works">Demo: “no trekking, relaxed pace”. Unaffected activities are preserved.</H>
                <div className="card p-6 text-sm"><ul className="list-disc space-y-1 pl-5">{data.replan_demo.lines.map((l: string, i: number) => <li key={i}>{l}</li>)}</ul></div>
              </section>
            )}

            <MlSection ml={data.ml} />

            <section>
              <H n="10 · Honest limitations" title="What this system does not do" />
              <ul className="card list-disc space-y-2 p-6 pl-10 text-sm leading-relaxed">
                <li>The destination, attraction, stay and transport data is an <b>illustrative sample</b>. Coordinates are approximate; fees, fares and stays are estimates or fictional.</li>
                <li>No live prices, availability, weather or timetables. Nothing can be booked here.</li>
                <li>The chatbot is a deterministic rule-based system, not a language model, so unusual phrasing may be misunderstood. Use “What I understood” to correct it.</li>
                <li>Itinerary search is beam search: good, not guaranteed optimal. A* route search is optimal only on the modelled road graph.</li>
                <li>The Stravl preference model covers only 5 sample destinations, and is shown for information; it does not change the ranking.</li>
                {meta?.data_issues?.length ? <li>Dataset validation notes: {meta.data_issues.join("; ")}</li> : null}
              </ul>
            </section>
          </>
        )}
      </div>
    </>
  );
}

function RouteDemo({ route }: { route: any }) {
  const W = 640, Hh = 460, pad = 30;
  const lats = route.nodes.map((n: any) => n.lat), lons = route.nodes.map((n: any) => n.lon);
  const [minLa, maxLa, minLo, maxLo] = [Math.min(...lats), Math.max(...lats), Math.min(...lons), Math.max(...lons)];
  const P = (n: any) => [pad + ((n.lon - minLo) / (maxLo - minLo || 1)) * (W - 2 * pad), pad + ((maxLa - n.lat) / (maxLa - minLa || 1)) * (Hh - 2 * pad)];
  const by: Record<string, any> = Object.fromEntries(route.nodes.map((n: any) => [n.id, n]));
  const line = (path: string[]) => path.map((id) => P(by[id]).join(",")).join(" ");
  const a = route.astar, b = route.bfs;
  return (
    <section>
      <H n="05 · Route search" title="A* versus BFS on the modelled road graph">Nodes are your origin and every destination. Edges are modelled (straight-line × 1.3), not real roads. A* uses a haversine heuristic that was checked for consistency ({route.heuristic_check.consistent ? "0 violations" : `${route.heuristic_check.violations} violations`}) and matches a Dijkstra reference{route.dijkstra_reference ? ` (${route.dijkstra_reference.cost})` : ""}.</H>
      <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
        <svg viewBox={`0 0 ${W} ${Hh}`} className="card w-full bg-lavender/30" role="img" aria-label="Route graph">
          {route.edges.map((e: any, i: number) => <line key={i} x1={P(by[e.a])[0]} y1={P(by[e.a])[1]} x2={P(by[e.b])[0]} y2={P(by[e.b])[1]} stroke="#A99AB8" strokeOpacity={0.35} />)}
          {b.found && <polyline points={line(b.path)} fill="none" stroke="#5B347D" strokeWidth={3} strokeDasharray="7 6" />}
          {a.found && <polyline points={line(a.path)} fill="none" stroke="#C6A15B" strokeWidth={4} />}
          {route.nodes.map((n: any) => { const [x, y] = P(n); const on = a.path?.includes(n.id); return <g key={n.id}><circle cx={x} cy={y} r={on ? 6 : 4} fill={on ? "#C6A15B" : "#2B1748"} /><text x={x + 8} y={y + 4} fontSize={11} fill="#261D2D">{n.label}</text></g>; })}
        </svg>
        <div className="space-y-3 text-sm">
          <div className="card p-4"><p className="label">A* (gold line)</p>{a.found ? <><p>{a.labels.join(" → ")}</p><p className="text-xs text-ink/65">{a.total_km} km · {a.total_hours} h · expanded {a.expanded} nodes</p><p className="text-xs text-ink/65">{a.note}</p></> : <p>No route.</p>}</div>
          <div className="card p-4"><p className="label">BFS (purple dashes)</p>{b.found ? <><p>{b.path.map((id: string) => by[id].label).join(" → ")}</p><p className="text-xs text-ink/65">{b.hops} hops · {b.total_km} km · explored {b.explored.length} nodes</p><p className="text-xs text-ink/65">{b.note}</p></> : <p>No route.</p>}</div>
        </div>
      </div>
    </section>
  );
}

function MlSection({ ml }: { ml: any }) {
  return (
    <section>
      <H n="09 · Optional machine learning" title="Stravl swipe-preference model">Trained on the real Stravl-Data swipe dataset to predict a yes/no swipe. It is informational: it does <b>not</b> change the ranking, and it only knows 5 of the sample destinations.</H>
      {!ml ? <p className="text-sm text-ink/65">ML metrics have not been generated.</p> : (
        <div className="card overflow-x-auto p-5">
          <table className="w-full min-w-[28rem] text-left text-sm"><thead><tr className="text-violet"><th className="p-2">Model</th><th>ROC-AUC</th><th>Avg precision</th></tr></thead>
            <tbody>{Object.entries(ml.models).map(([k, v]: any) => <tr key={k} className="border-t border-royal/10"><td className="p-2">{k}</td><td>{v.roc_auc}</td><td>{v.avg_precision}</td></tr>)}</tbody></table>
          <p className="mt-3 text-xs text-ink/65">Held-out users: {ml.n_users_test?.toLocaleString()} · test pairs {ml.n_test_pairs?.toLocaleString()} · positive rate {ml.positive_rate_test}. The deployed logistic regression barely beats the popularity baseline: swipe behaviour is only weakly predictable from the available features.</p>
        </div>
      )}
    </section>
  );
}
