import { useEffect, useState } from "react";

// Destination photography comes from the Wikipedia REST API (Wikimedia Commons images) at runtime, so each picture matches its place.
// Results are cached; failures fall back to a branded gradient plate (the UI never shows a broken image).
const mem = new Map<string, string | null>();
const KEY = "tripwise.img.v1";
let disk: Record<string, string | null> = {};
try { disk = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch { disk = {}; }

async function load(title: string): Promise<string | null> {
  if (mem.has(title)) return mem.get(title)!;
  if (title in disk) { mem.set(title, disk[title]); return disk[title]; }
  try {
    const r = await fetch(`https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(title)}`);
    if (!r.ok) throw new Error(String(r.status));
    const j = await r.json();
    const src: string | null = j.originalimage?.source || j.thumbnail?.source || null;
    const sized = src && src.includes("/commons/") && !src.includes("/thumb/") ? src : src;
    mem.set(title, sized); disk[title] = sized;
    try { localStorage.setItem(KEY, JSON.stringify(disk)); } catch { /* quota */ }
    return sized;
  } catch {
    mem.set(title, null);
    return null;
  }
}

export function useWikiImage(title?: string): { src: string | null; loading: boolean } {
  const [src, setSrc] = useState<string | null>(title && mem.get(title) ? mem.get(title)! : null);
  const [loading, setLoading] = useState(!!title && !mem.has(title));
  useEffect(() => {
    let live = true;
    if (!title) { setLoading(false); return; }
    setLoading(!mem.has(title));
    load(title).then((s) => { if (live) { setSrc(s); setLoading(false); } });
    return () => { live = false; };
  }, [title]);
  return { src, loading };
}
