import { useEffect, useMemo } from "react";
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import type { Day, Stay } from "../lib/types";

const pin = (label: string, cls = "") => L.divIcon({ className: "", html: `<div class="tw-pin ${cls}"><span>${label}</span></div>`, iconSize: [30, 30], iconAnchor: [15, 30], popupAnchor: [0, -28] });

function Fit({ pts, focus }: { pts: [number, number][]; focus: [number, number] | null }) {
  const map = useMap();
  useEffect(() => {
    if (focus) { map.flyTo(focus, Math.max(map.getZoom(), 13), { duration: 0.6 }); return; }
    if (pts.length > 1) map.fitBounds(L.latLngBounds(pts), { padding: [36, 36], maxZoom: 14 });
    else if (pts.length === 1) map.setView(pts[0], 12);
  }, [pts, focus, map]);
  return null;
}

export default function MapView({ days, stay, activeId, onSelect, height = "h-[26rem]" }: {
  days: Day[]; stay?: Stay | null; activeId?: string | null; onSelect?: (id: string) => void; height?: string;
}) {
  const stops = useMemo(() => {
    let n = 0;
    return days.flatMap((d) => d.schedule.items.filter((i) => i.kind === "activity" && i.lat != null && i.lon != null).map((i) => ({ n: ++n, day: d.day, id: i.attraction_id!, title: i.title, pos: [i.lat!, i.lon!] as [number, number], time: i.start })));
  }, [days]);
  const pts = useMemo(() => [...stops.map((s) => s.pos), ...(stay ? [[stay.lat, stay.lon] as [number, number]] : [])], [stops, stay]);
  const focus = stops.find((s) => s.id === activeId)?.pos ?? null;
  if (!pts.length) return <div className={`grid place-items-center rounded-2xl bg-lavender text-sm text-ink/60 ${height}`}>No mappable stops yet.</div>;
  return (
    <div className={`${height} overflow-hidden rounded-2xl border border-royal/10 shadow-soft`}>
      <MapContainer center={pts[0]} zoom={11} scrollWheelZoom={false} className="h-full w-full" aria-label="Itinerary map">
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <Fit pts={pts} focus={focus} />
        {days.map((d) => {
          const line = stops.filter((s) => s.day === d.day).map((s) => s.pos);
          return line.length > 1 ? <Polyline key={d.day} positions={line} pathOptions={{ color: "#5B347D", weight: 3, dashArray: "6 6", opacity: 0.7 }} /> : null;
        })}
        {stops.map((s) => (
          <Marker key={`${s.day}-${s.id}`} position={s.pos} icon={pin(String(s.n), s.id === activeId ? "active" : "")} eventHandlers={{ click: () => onSelect?.(s.id) }}>
            <Popup><b>{s.n}. {s.title}</b><br />Day {s.day} · {s.time}</Popup>
          </Marker>
        ))}
        {stay && <Marker position={[stay.lat, stay.lon]} icon={pin("H", "stay")}><Popup><b>{stay.name}</b><br />Sample stay (illustrative)</Popup></Marker>}
      </MapContainer>
    </div>
  );
}
