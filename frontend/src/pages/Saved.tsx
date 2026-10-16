import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { BookmarkX, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import { useTrip } from "../lib/store";
import type { SavedTrip } from "../lib/types";
import { EmptyState, ErrorNote, PageHeader, Skeleton } from "../components/ui";
import { useToast } from "../components/Toast";
import { inr } from "../lib/format";

export default function Saved() {
  const [trips, setTrips] = useState<SavedTrip[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const { loadTrip, tripId } = useTrip();
  const nav = useNavigate();
  const toast = useToast();
  const load = () => { setErr(null); api.trips().then(setTrips).catch((e) => setErr(e.message)); };
  useEffect(load, []);
  const open = async (id: string) => { try { await loadTrip(id); nav("/itinerary"); } catch (e: any) { toast.err(e.message); } };
  const del = async (t: SavedTrip) => {
    if (!window.confirm(`Delete "${t.name}"? This cannot be undone.`)) return;
    try { await api.deleteTrip(t.id); toast.ok("Trip deleted."); load(); } catch (e: any) { toast.err(e.message); }
  };
  return (
    <>
      <PageHeader eyebrow="Saved trips" title="Your journeys">Trips are stored in this app's local database and can be reopened, edited and re-saved.</PageHeader>
      <div className="mx-auto max-w-5xl px-5 py-10">
        {err && <ErrorNote message={err} onRetry={load} />}
        {!trips && !err && <div className="space-y-4"><Skeleton className="h-24" /><Skeleton className="h-24" /></div>}
        {trips && trips.length === 0 && <EmptyState icon={<BookmarkX className="h-6 w-6" />} title="No saved trips yet" action={<Link to="/planner" className="btn-gold">Plan a trip</Link>}>Build an itinerary and press “Save trip” to keep it here.</EmptyState>}
        <ul className="space-y-4">
          {trips?.map((t) => (
            <li key={t.id} className="card flex flex-wrap items-center justify-between gap-4 p-5">
              <div>
                <h2 className="font-display text-2xl text-royal">{t.name}{t.id === tripId && <span className="ml-2 rounded-full bg-gold px-2 py-0.5 align-middle text-[0.65rem] font-sans font-bold text-plum">OPEN</span>}</h2>
                <p className="text-sm text-ink/65">{t.destination_name} · {t.days} days · {t.travellers} traveller(s) · est. {inr(t.total)} · updated {new Date(t.updated_at).toLocaleString()}</p>
              </div>
              <div className="flex gap-2"><button className="btn-gold btn-sm" onClick={() => open(t.id)}>Open</button><button className="btn-ghost btn-sm" aria-label={`Delete ${t.name}`} onClick={() => del(t)}><Trash2 className="h-3.5 w-3.5" /> Delete</button></div>
            </li>
          ))}
        </ul>
      </div>
    </>
  );
}
