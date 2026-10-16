import { useEffect, type ReactNode } from "react";
import { AlertTriangle, Compass, X } from "lucide-react";
import { useWikiImage } from "../lib/images";
import type { Component } from "../lib/types";

export function Skeleton({ className = "h-24" }: { className?: string }) { return <div className={`skeleton ${className}`} aria-hidden="true" />; }

export function EmptyState({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="card mx-auto max-w-xl p-10 text-center">
      <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-full bg-lavender text-violet">{icon ?? <Compass className="h-6 w-6" />}</div>
      <h3 className="font-display text-2xl text-royal">{title}</h3>
      <div className="mt-2 text-sm leading-relaxed text-ink/70">{children}</div>
      {action && <div className="mt-6 flex justify-center gap-3">{action}</div>}
    </div>
  );
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-900">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex-1">{message}</div>
      {onRetry && <button className="font-semibold underline" onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function PageHeader({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <div className="bg-royal text-ivory">
      <div className="mx-auto max-w-7xl px-5 py-12 on-dark">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="mt-2 font-display text-4xl font-semibold sm:text-5xl">{title}</h1>
        <div className="gold-rule mt-4" />
        {children && <div className="mt-4 max-w-3xl text-sm leading-relaxed text-ivory/75">{children}</div>}
      </div>
    </div>
  );
}

export function DestImage({ wiki, name, className = "h-44" }: { wiki?: string; name: string; className?: string }) {
  const { src, loading } = useWikiImage(wiki || name);
  return (
    <div className={`relative overflow-hidden bg-gradient-to-br from-royal via-violet to-plum ${className}`}>
      {src && <img src={src} alt={`${name}`} loading="lazy" className="absolute inset-0 h-full w-full object-cover transition duration-700 hover:scale-105" onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }} />}
      {!src && (
        <div className="absolute inset-0 grid place-items-center text-center">
          <span className={`font-display text-3xl text-champagne/80 ${loading ? "animate-pulse" : ""}`}>{name}</span>
        </div>
      )}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-plum/70 to-transparent" />
    </div>
  );
}

const LABELS: Record<string, string> = { interests: "Interests", budget: "Budget fit", climate: "Climate", season: "Season", travel_time: "Travel time", duration: "Trip length" };
export function ScoreBars({ components }: { components: Record<string, Component> }) {
  return (
    <ul className="space-y-2.5">
      {Object.entries(components).map(([k, c]) => (
        <li key={k}>
          <div className="mb-1 flex items-baseline justify-between text-xs">
            <span className="font-semibold text-royal">{LABELS[k] ?? k}</span>
            <span className="text-ink/60">
              {c.status === "not_specified" ? "not specified" : c.status === "missing_data" ? "missing data" : `${Math.round(c.score * 100)}%`} · weight {Math.round(c.weight * 100)}%
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-lavender" role="img" aria-label={`${LABELS[k] ?? k} ${Math.round(c.score * 100)} percent`}>
            <div className={`h-full rounded-full ${c.status === "ok" ? "bg-gradient-to-r from-violet to-gold" : "bg-mauve/50"}`} style={{ width: `${c.status === "not_specified" ? 0 : Math.max(3, c.score * 100)}%` }} />
          </div>
          <p className="mt-1 text-[0.72rem] leading-snug text-ink/60">{c.note}</p>
        </li>
      ))}
    </ul>
  );
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", h); document.body.style.overflow = ""; };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="no-print fixed inset-0 z-[80] flex items-end justify-center bg-plum/70 p-0 backdrop-blur-sm sm:items-center sm:p-6" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label={title} className={`animate-rise max-h-[92vh] w-full overflow-y-auto rounded-t-3xl bg-ivory shadow-lift sm:rounded-3xl ${wide ? "sm:max-w-5xl" : "sm:max-w-2xl"}`}>
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-royal/10 bg-ivory/95 px-6 py-4 backdrop-blur">
          <h2 className="font-display text-2xl text-royal">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="rounded-full p-2 hover:bg-lavender"><X className="h-5 w-5" /></button>
        </div>
        <div className="p-6">{children}</div>
      </div>
    </div>
  );
}

export const Disclaimer = ({ children }: { children?: ReactNode }) => (
  <p className="rounded-lg border border-gold/40 bg-champagne/30 px-3 py-2 text-xs leading-relaxed text-gold-deep">{children ?? "Illustrative sample data: prices, fees and stays are estimates, not live quotes or availability."}</p>
);
