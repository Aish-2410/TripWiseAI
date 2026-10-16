import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { CheckCircle2, AlertTriangle, X } from "lucide-react";

interface T { id: number; kind: "ok" | "err"; text: string }
const Ctx = createContext<{ ok: (t: string) => void; err: (t: string) => void }>({ ok: () => {}, err: () => {} });
export const useToast = () => useContext(Ctx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<T[]>([]);
  const push = useCallback((kind: T["kind"], text: string) => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, kind, text }]);
    setTimeout(() => setItems((x) => x.filter((i) => i.id !== id)), kind === "err" ? 7000 : 3500);
  }, []);
  return (
    <Ctx.Provider value={{ ok: (t) => push("ok", t), err: (t) => push("err", t) }}>
      {children}
      <div className="no-print fixed bottom-24 left-1/2 z-[70] flex w-[min(92vw,26rem)] -translate-x-1/2 flex-col gap-2 sm:bottom-6 sm:left-auto sm:right-6 sm:translate-x-0" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`animate-rise flex items-start gap-3 rounded-xl border px-4 py-3 text-sm shadow-lift ${t.kind === "ok" ? "border-gold/50 bg-plum text-ivory" : "border-red-300 bg-white text-red-900"}`}>
            {t.kind === "ok" ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-gold" /> : <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />}
            <span className="flex-1">{t.text}</span>
            <button aria-label="Dismiss" onClick={() => setItems((x) => x.filter((i) => i.id !== t.id))}><X className="h-4 w-4 opacity-60" /></button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
