import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Copy, Edit3, Printer, Save, Undo2, Wand2, Map as MapIcon } from "lucide-react";
import { useTrip } from "../lib/store";
import { api } from "../lib/api";
import type { ChangeSummary, Plan, RecResult, Stay, TransportOption } from "../lib/types";
import { EmptyState, ErrorNote, Modal, PageHeader, Skeleton, Disclaimer } from "../components/ui";
import DayCard from "../components/DayCard";
import MapView from "../components/MapView";
import BudgetPanel from "../components/BudgetPanel";
import { useToast } from "../components/Toast";
import { cap, hrs, inr, planSummaryText } from "../lib/format";

const TABS = ["Itinerary", "Budget", "Stay & travel", "Adjust trip", "How it was built"] as const;
type Tab = (typeof TABS)[number];

export default function Itinerary() {
  const { plan, versions, adoptPlan, undo, saveCurrent, tripId, buildPlan, prefs } = useTrip();
  const toast = useToast();
  const [qs] = useSearchParams();
  const fromQuery = ({ budget: "Budget", stay: "Stay & travel", adjust: "Adjust trip" } as Record<string, Tab>)[(qs.get("tab") || "").toLowerCase()];
  const [tab, setTab] = useState<Tab>(fromQuery ?? "Itinerary");
  useEffect(() => { if (fromQuery) setTab(fromQuery); }, [fromQuery]);
  const [active, setActive] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [change, setChange] = useState<ChangeSummary | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [name, setName] = useState("");
  const [stays, setStays] = useState<Stay[] | null>(null);
  const [trans, setTrans] = useState<TransportOption[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const pid = plan?.destination_id;
  useEffect(() => {
    if (!plan) return;
    setStays(null); setTrans(null);
    const planned = plan.days.flatMap((d) => d.activity_ids);
    api.accommodation({ destination_id: plan.destination_id, travellers: plan.prefs.travellers, nights: plan.costs.nights, accessibility_required: plan.prefs.accessibility_required, planned_attraction_ids: planned }).then(setStays).catch((e) => setErr(e.message));
    if (plan.prefs.origin) api.transport(plan.prefs.origin, plan.destination_id, plan.prefs.travellers, plan.days.length).then(setTrans).catch((e) => setErr(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid, plan?.accommodation_tier, plan?.costs.nights]);

  if (!plan) {
    return (
      <>
        <PageHeader eyebrow="My itinerary" title="Your journey, day by day" />
        <div className="px-5 py-16"><EmptyState title="No itinerary yet" action={<><Link to="/planner" className="btn-gold">Plan a trip</Link><Link to="/saved" className="btn-ghost">Open a saved trip</Link></>}>Pick a destination in the planner, or open a saved trip.</EmptyState></div>
      </>
    );
  }
  const stay = stays?.find((s) => s.id === plan.stay_id) ?? null;
  const c = plan.costs;

  const edit = async (op: Record<string, unknown>) => {
    setBusy(true);
    try {
      const r = await api.edit(plan, op);
      adoptPlan(r.plan); setWarnings(r.warnings); setChange(r.summary);
    } catch (e: any) { toast.err(e.message); } finally { setBusy(false); }
  };
  const doSave = async () => {
    try { await saveCurrent(name.trim() || `${plan.destination_name} trip`); toast.ok("Trip saved."); setSaveOpen(false); } catch (e: any) { toast.err(e.message); }
  };
  const copy = async () => {
    try { await navigator.clipboard.writeText(planSummaryText(plan)); toast.ok("Summary copied to clipboard."); } catch { toast.err("Clipboard is blocked by your browser."); }
  };

  return (
    <>
      <div className="no-print"><PageHeader eyebrow="My itinerary" title={`${plan.destination_name}, ${plan.days.length} days`}>
        {plan.prefs.travellers} traveller(s) from {plan.prefs.origin} · {plan.transport.mode} · {cap(plan.accommodation_tier)} stay · version {plan.version ?? 1}
      </PageHeader></div>
      <div className="print-only mb-4"><h1 className="font-display text-3xl">TripWise AI · {plan.destination_name}, {plan.days.length} days</h1><p className="text-sm">Estimated total {inr(c.total)}. Sample-data estimate, not a booking.</p></div>

      <div className="mx-auto max-w-7xl px-5 py-8">
        <div className="no-print mb-6 flex flex-wrap items-center gap-2">
          <button className="btn-gold btn-sm" onClick={() => { setName(`${plan.destination_name} trip`); setSaveOpen(true); }}><Save className="h-3.5 w-3.5" /> {tripId ? "Save changes" : "Save trip"}</button>
          <button className="btn-ghost btn-sm" onClick={() => window.print()}><Printer className="h-3.5 w-3.5" /> Print / PDF</button>
          <button className="btn-ghost btn-sm" onClick={copy}><Copy className="h-3.5 w-3.5" /> Copy summary</button>
          <button className="btn-ghost btn-sm" aria-pressed={editing} onClick={() => { setEditing(!editing); setTab("Itinerary"); }}><Edit3 className="h-3.5 w-3.5" /> {editing ? "Done editing" : "Edit days"}</button>
          <button className="btn-ghost btn-sm" disabled={!versions.length} onClick={() => { undo(); toast.ok("Reverted to the previous version."); setChange(null); }}><Undo2 className="h-3.5 w-3.5" /> Undo ({versions.length})</button>
          <button className="btn-ghost btn-sm" onClick={async () => { setBusy(true); try { await buildPlan(plan.destination_id); toast.ok("Rebuilt from your current preferences."); } catch (e: any) { toast.err(e.message); } finally { setBusy(false); } }}><Wand2 className="h-3.5 w-3.5" /> Rebuild from scratch</button>
          <span className={`ml-auto rounded-full px-3 py-1 text-xs font-bold ${c.over_budget ? "bg-red-100 text-red-900" : "bg-champagne text-plum"}`}>{inr(c.total)} {c.budget ? (c.over_budget ? `· over by ${inr(c.overrun)}` : "· within budget") : ""}</span>
        </div>

        {err && <div className="mb-4"><ErrorNote message={err} /></div>}
        {warnings.length > 0 && <div className="no-print mb-4 rounded-xl border border-gold/50 bg-champagne/40 p-4 text-sm text-plum" role="alert"><b>Heads up:</b><ul className="ml-5 list-disc">{warnings.map((w, i) => <li key={i}>{w}</li>)}</ul></div>}
        {change && <ChangeBox s={change} onClose={() => setChange(null)} />}

        <div role="tablist" aria-label="Itinerary sections" className="no-print mb-6 flex gap-1 overflow-x-auto border-b border-royal/10">
          {TABS.map((t) => (
            <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className={`whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-semibold transition ${tab === t ? "border-gold text-royal" : "border-transparent text-ink/60 hover:text-royal"}`}>{t}</button>
          ))}
        </div>

        <div role="tabpanel" className={`tab-panel ${tab === "Itinerary" ? "" : "hidden"}`}>
          <div className="grid gap-6 lg:grid-cols-[1fr_26rem]">
            <div className="space-y-5">
              {plan.days.map((d) => <DayCard key={d.day} day={d} total={plan.days.length} editing={editing} activeId={active} onActive={setActive} busy={busy}
                onRemove={(id) => edit({ type: "remove", activity_id: id })} onMove={(id, to) => edit({ type: "move", activity_id: id, day: to })} />)}
              {editing && <AddActivity plan={plan} onAdd={(id, day) => edit({ type: "add", activity_id: id, day })} busy={busy} />}
              {plan.notes.length > 0 && <div className="card p-5"><h3 className="font-display text-xl text-royal">Planner notes</h3><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink/75">{plan.notes.map((n, i) => <li key={i}>{n}</li>)}</ul></div>}
            </div>
            <div className="lg:sticky lg:top-4 lg:self-start">
              <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-violet no-print"><MapIcon className="h-4 w-4" /> Numbered stops follow the itinerary order; H marks the sample stay.</div>
              <MapView days={plan.days} stay={stay} activeId={active} onSelect={setActive} height="h-[30rem]" />
            </div>
          </div>
        </div>

        <div role="tabpanel" className={`tab-panel ${tab === "Budget" ? "" : "hidden"}`}>
          <BudgetPanel costs={c} />
          <OptimizerPanel plan={plan} onApply={(p) => { adoptPlan(p); toast.ok("Optimised plan applied. Undo is available."); }} />
        </div>

        <div role="tabpanel" className={`tab-panel ${tab === "Stay & travel" ? "" : "hidden"}`}>
          <StayTravel plan={plan} stays={stays} trans={trans} />
        </div>

        <div role="tabpanel" className={`tab-panel no-print ${tab === "Adjust trip" ? "" : "hidden"}`}>
          <ReplanPanel plan={plan} onResult={(p, s) => { adoptPlan(p); setChange(s); setTab("Itinerary"); window.scrollTo({ top: 0, behavior: "smooth" }); }} />
        </div>

        <div role="tabpanel" className={`tab-panel ${tab === "How it was built" ? "" : "hidden"}`}>
          <HowBuilt plan={plan} />
        </div>
        <div className="mt-10"><Disclaimer>{plan.disclaimer}</Disclaimer></div>
        <span className="sr-only">{prefs.origin}</span>
      </div>

      <Modal open={saveOpen} onClose={() => setSaveOpen(false)} title="Save this trip">
        <label className="label" htmlFor="tn">Trip name</label>
        <input id="tn" className="field" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} autoFocus onKeyDown={(e) => e.key === "Enter" && doSave()} />
        <p className="mt-2 text-xs text-ink/60">{tripId ? "This updates your existing saved trip." : "A new saved trip is created."} Version history ({versions.length}) is saved too.</p>
        <div className="mt-5 flex justify-end gap-2"><button className="btn-ghost" onClick={() => setSaveOpen(false)}>Cancel</button><button className="btn-gold" onClick={doSave}>Save</button></div>
      </Modal>
    </>
  );
}

function ChangeBox({ s, onClose }: { s: ChangeSummary; onClose: () => void }) {
  return (
    <div className="no-print animate-rise mb-5 rounded-2xl border border-gold/50 bg-champagne/30 p-4 text-sm text-plum" role="status">
      <div className="flex justify-between"><b>What changed</b><button className="text-xs underline" onClick={onClose}>Dismiss</button></div>
      <ul className="mt-1 list-disc pl-5">{s.lines.map((l, i) => <li key={i}>{l}</li>)}</ul>
      {s.optimiser?.message && <p className="mt-2 text-xs">Budget Guardian: {s.optimiser.message}</p>}
    </div>
  );
}

function AddActivity({ plan, onAdd, busy }: { plan: Plan; onAdd: (id: string, day: number) => void; busy: boolean }) {
  const [list, setList] = useState<{ id: string; name: string }[]>([]);
  const [sel, setSel] = useState("");
  const [day, setDay] = useState(1);
  useEffect(() => {
    api.destination(plan.destination_id).then((d) => { const used = new Set(plan.days.flatMap((x) => x.activity_ids)); setList(d.attractions.filter((a: any) => !used.has(a.id)).map((a: any) => ({ id: a.id, name: a.name }))); }).catch(() => undefined);
  }, [plan]);
  return (
    <div className="card no-print flex flex-wrap items-end gap-3 p-5">
      <div className="min-w-48 flex-1"><label className="label" htmlFor="addsel">Add an attraction</label>
        <select id="addsel" className="field" value={sel} onChange={(e) => setSel(e.target.value)}><option value="">Choose…</option>{list.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></div>
      <div><label className="label" htmlFor="addday">Day</label><select id="addday" className="field" value={day} onChange={(e) => setDay(Number(e.target.value))}>{plan.days.map((d) => <option key={d.day} value={d.day}>Day {d.day}</option>)}</select></div>
      <button className="btn-dark" disabled={!sel || busy} onClick={() => { onAdd(sel, day); setSel(""); }}>Add</button>
    </div>
  );
}

function OptimizerPanel({ plan, onApply }: { plan: Plan; onApply: (p: Plan) => void }) {
  const [res, setRes] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const run = async (relax: boolean) => { setBusy(true); setErr(null); try { setRes(await api.optimize(plan, relax)); } catch (e: any) { setErr(e.message); } finally { setBusy(false); } };
  useEffect(() => setRes(null), [plan]);
  return (
    <section className="no-print card mt-8 p-6">
      <h3 className="font-display text-2xl text-royal">Budget Guardian</h3>
      {!plan.costs.budget ? <p className="mt-2 text-sm text-ink/70">Set a budget in the planner to let the Guardian optimise this plan.</p> : (
        <>
          <p className="mt-2 text-sm text-ink/75">{plan.costs.over_budget ? `This plan is ${inr(plan.costs.overrun)} over your ${inr(plan.costs.budget)} budget. The Guardian tries ranked, explainable cost cuts and never changes your stated preferences unless you allow it.` : "This plan fits your budget. You can still ask for cheaper alternatives."}</p>
          <div className="mt-4 flex flex-wrap gap-2"><button className="btn-gold btn-sm" disabled={busy} onClick={() => run(false)}>{busy ? "Optimising…" : "Fit to budget"}</button><button className="btn-ghost btn-sm" disabled={busy} onClick={() => run(true)}>Allow relaxing my preferences</button></div>
        </>
      )}
      {err && <div className="mt-3"><ErrorNote message={err} /></div>}
      {res && (
        <div className="animate-rise mt-5 space-y-3 text-sm">
          <p className={`rounded-xl p-3 ${res.resolved ? "bg-champagne/40 text-plum" : "bg-red-50 text-red-900"}`}>{res.message}</p>
          {res.steps?.length > 0 && <ol className="list-decimal space-y-1 pl-5">{res.steps.map((s: any, i: number) => <li key={i}>{s.description} <span className="text-ink/55">(saves {inr(s.saving)}, now {inr(s.new_total)})</span>{s.violates_preference && <b className="text-red-800"> · changes a stated preference</b>}</li>)}</ol>}
          {res.steps?.length > 0 && res.plan && <button className="btn-dark btn-sm" onClick={() => onApply(res.plan)}>Apply this optimised plan ({inr(res.final_total)})</button>}
          {!res.steps?.length && res.ranked_options?.length > 0 && <div><p className="label">Options considered</p><ul className="list-disc pl-5">{res.ranked_options.map((o: any, i: number) => <li key={i}>{o.description} (saves {inr(o.saving)}){o.violates_preference ? " · changes a stated preference" : ""}</li>)}</ul></div>}
        </div>
      )}
    </section>
  );
}

function StayTravel({ plan, stays, trans }: { plan: Plan; stays: Stay[] | null; trans: TransportOption[] | null }) {
  const { adoptPlan } = useTrip();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const swap = async (changes: Record<string, unknown>, ok: string) => {
    setBusy(true);
    try { const r = await api.replan(plan, changes); adoptPlan(r.plan); toast.ok(ok + " " + (r.summary.lines.at(-1) ?? "")); } catch (e: any) { toast.err(e.message); } finally { setBusy(false); }
  };
  return (
    <div className="grid gap-8 lg:grid-cols-2">
      <section>
        <h3 className="font-display text-2xl text-royal">Getting there</h3>
        <p className="mb-3 text-xs text-ink/60">Modelled estimates (distance model), not timetables or live fares.</p>
        {!trans ? <Skeleton className="h-40" /> : (
          <ul className="space-y-3">
            {trans.map((t) => {
              const cur = t.mode === plan.transport.mode;
              return (
                <li key={t.mode} className={`card p-4 ${cur ? "!border-gold ring-1 ring-gold" : ""}`}>
                  <div className="flex items-center justify-between"><b className="font-display text-xl capitalize text-royal">{t.mode}{cur && <span className="ml-2 rounded-full bg-gold px-2 py-0.5 text-[0.65rem] font-sans font-bold text-plum">SELECTED</span>}</b><span className="text-sm">{inr(t.per_person_round_trip_inr)} pp return</span></div>
                  <p className="text-xs text-ink/65">{hrs(t.one_way_hours)} each way · {Math.round(t.distance_km)} km · comfort {t.comfort}/5 · group total {inr(t.round_trip_group_inr)} · {t.price_basis.replace("_", " ")}</p>
                  {t.accessibility_note && <p className="text-xs text-gold-deep">{t.accessibility_note}</p>}
                  {t.eats_trip && <p className="text-xs text-red-800">Travel time takes a large share of this trip.</p>}
                  {!cur && <button className="btn-ghost btn-sm mt-2 no-print" disabled={busy} onClick={() => swap({ transport: [t.mode] }, `Switched to ${t.mode}.`)}>Use {t.mode}</button>}
                </li>
              );
            })}
          </ul>
        )}
      </section>
      <section>
        <h3 className="font-display text-2xl text-royal">Where to stay</h3>
        <p className="mb-3 text-xs text-ink/60">Fictional sample records for demonstration; not real properties or availability.</p>
        {!stays ? <Skeleton className="h-40" /> : (
          <ul className="space-y-3">
            {stays.map((s) => (
              <li key={s.id} className={`card p-4 ${s.id === plan.stay_id ? "!border-gold ring-1 ring-gold" : ""}`}>
                <div className="flex items-center justify-between"><b className="font-display text-xl text-royal">{s.name}</b><span className="text-sm">{inr(s.total_inr)} total</span></div>
                <p className="text-xs text-ink/65">{cap(s.tier)} · {inr(s.price_inr)} {s.price_unit.replace("_", " ")} · {s.nights} night(s) · comfort {s.comfort}/5{s.avg_distance_to_planned_km != null ? ` · ~${s.avg_distance_to_planned_km.toFixed(1)} km from planned stops` : ""}</p>
                <p className="text-xs text-ink/55">{s.amenities.join(", ")}{s.accessible === false ? " · not step-free" : ""}</p>
                {s.id !== plan.stay_id && <button className="btn-ghost btn-sm mt-2 no-print" disabled={busy} onClick={() => swap({ accommodation: s.tier }, `Switched to ${s.tier} stay.`)}>Use {s.tier} tier</button>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function ReplanPanel({ plan, onResult }: { plan: Plan; onResult: (p: Plan, s: ChangeSummary) => void }) {
  const toast = useToast();
  const { adoptPlan, prefs, recommend } = useTrip();
  const [busy, setBusy] = useState(false);
  const [budget, setBudget] = useState(String(plan.prefs.budget ?? ""));
  const [alts, setAlts] = useState<RecResult | null>(null);
  const [interest, setInterest] = useState("");
  const go = async (changes: Record<string, unknown>) => {
    setBusy(true);
    try { const r = await api.replan(plan, changes); onResult(r.plan, r.summary); } catch (e: any) { toast.err(e.message); } finally { setBusy(false); }
  };
  const planB = async () => {
    setBusy(true);
    try { setAlts(await recommend("match", { excluded_destinations: [...prefs.excluded_destinations, plan.destination_id], destination: null })); } catch (e: any) { toast.err(e.message); } finally { setBusy(false); }
  };
  const useAlt = async (id: string) => {
    setBusy(true);
    try { const p = await api.plan({ ...plan.prefs, destination: id }, id); adoptPlan(p); toast.ok(`Switched to ${p.destination_name}. Undo returns to the previous destination.`); } catch (e: any) { toast.err(e.message); } finally { setBusy(false); }
  };
  const d = plan.days.length;
  const INTS = ["nature", "mountains", "beaches", "adventure", "historical", "culture", "food", "shopping", "photography", "wellness"];
  const B = ({ children, onClick, disabled }: { children: React.ReactNode; onClick: () => void; disabled?: boolean }) => <button className="chip !py-2" disabled={busy || disabled} onClick={onClick}>{children}</button>;
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="card space-y-4 p-6">
        <div><h3 className="font-display text-2xl text-royal">Re-plan, keep what still works</h3><p className="text-xs text-ink/65">Still-valid activities stay in place; only what must change is rebuilt. Every change is undoable.</p></div>
        <div className="flex flex-wrap gap-2">
          <B disabled={d <= 1} onClick={() => go({ duration_days: d - 1 })}>Shorten by a day</B>
          <B disabled={d >= 14} onClick={() => go({ duration_days: d + 1 })}>Add a day</B>
          <B onClick={() => go({ pace: "relaxed" })}>Slower pace</B>
          <B onClick={() => go({ pace: "packed" })}>Faster pace</B>
          <B onClick={() => go({ exclude_activities: ["trekking"] })}>No trekking</B>
          <B onClick={() => go({ exclude_activities: ["temples"] })}>No temples</B>
          <B onClick={() => go({ elderly: true })}>Elderly traveller joins</B>
          <B onClick={() => go({ accessibility_required: true })}>Need step-free access</B>
        </div>
        <div className="flex items-end gap-2"><div className="flex-1"><label className="label" htmlFor="rb">New budget (₹)</label><input id="rb" className="field" type="number" min={1000} step={500} value={budget} onChange={(e) => setBudget(e.target.value)} /></div><button className="btn-dark" disabled={busy || !budget} onClick={() => go({ budget: Number(budget) })}>Apply</button></div>
        <div className="flex items-end gap-2"><div className="flex-1"><label className="label" htmlFor="ri">Add an interest</label><select id="ri" className="field" value={interest} onChange={(e) => setInterest(e.target.value)}><option value="">Choose…</option>{INTS.map((i) => <option key={i} value={i}>{cap(i)}</option>)}</select></div><button className="btn-dark" disabled={busy || !interest} onClick={() => go({ add_interests: [interest] })}>Add</button></div>
      </section>
      <section className="card space-y-4 p-6">
        <div><h3 className="font-display text-2xl text-royal">Plan B destinations</h3><p className="text-xs text-ink/65">Re-ranks everything except {plan.destination_name} using your current preferences.</p></div>
        <button className="btn-gold btn-sm" disabled={busy} onClick={planB}>Show alternatives</button>
        {alts && alts.ranked.length === 0 && <p className="text-sm text-ink/70">No alternative passes your constraints. {(alts.relaxation ?? []).join(" ")}</p>}
        <ul className="space-y-2">{alts?.ranked.slice(0, 3).map((r) => (
          <li key={r.id} className="rounded-xl bg-lavender/50 p-3 text-sm"><b className="font-display text-lg text-royal">{r.name}</b> <span className="text-gold-deep">{Math.round(r.match_score)}%</span><p className="text-xs text-ink/65">{r.explanation}</p><button className="btn-dark btn-sm mt-2" disabled={busy} onClick={() => useAlt(r.id)}>Switch to {r.name}</button></li>
        ))}</ul>
      </section>
    </div>
  );
}

function HowBuilt({ plan }: { plan: Plan }) {
  const s = plan.search;
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="card p-6">
        <h3 className="font-display text-2xl text-royal">Itinerary search</h3>
        <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
          {[["Algorithm", s.algorithm], ["Beam width", s.beam_width], ["States expanded", s.expanded], ["States generated", s.generated], ["Eligible attractions", s.eligible_attractions], ["Best score", s.best_score]].map(([k, v]) => <div key={String(k)} className="rounded-xl bg-lavender/50 p-3"><dt className="label !mb-0.5">{k}</dt><dd className="text-royal">{String(v)}</dd></div>)}
        </dl>
        <p className="mt-3 text-xs text-ink/65"><b>Heuristic:</b> {s.heuristic}. {s.note}</p>
      </section>
      <section className="card p-6">
        <h3 className="font-display text-2xl text-royal">Rules that shaped this plan</h3>
        {plan.rules_fired.length === 0 ? <p className="mt-2 text-sm text-ink/65">No itinerary rules fired.</p> : <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{plan.rules_fired.map((r, i) => <li key={i}>{r}</li>)}</ul>}
        <Link to="/thinks" className="mt-4 inline-block text-sm font-semibold text-violet underline">See every rule and algorithm →</Link>
      </section>
    </div>
  );
}
