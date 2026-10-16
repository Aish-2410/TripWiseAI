import { useEffect, useRef, useState } from "react";
import { ArrowUp, Eye, RotateCcw, Sparkles } from "lucide-react";
import { useChat } from "../lib/chat";
import ChatCards, { leadText } from "../components/chat/ChatCards";
import UnderstoodPanel from "../components/chat/UnderstoodPanel";
import { api } from "../lib/api";

const CHIPS = ["Find budget hotels", "Plan a weekend getaway", "Build my itinerary", "Compare transport options"];

function Composer({ onSend, busy, big }: { onSend: (t: string) => void; busy: boolean; big?: boolean }) {
  const [v, setV] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => { const el = ref.current; if (!el) return; el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 180) + "px"; }, [v]);
  const go = () => { if (!v.trim() || busy) return; onSend(v); setV(""); };
  return (
    <form onSubmit={(e) => { e.preventDefault(); go(); }} className={`flex items-end gap-2 rounded-3xl border border-gold/50 bg-white p-2 shadow-lift focus-within:border-gold focus-within:ring-2 focus-within:ring-gold/30 ${big ? "sm:p-3" : ""}`}>
      <textarea ref={ref} rows={big ? 2 : 1} value={v} onChange={(e) => setV(e.target.value)} aria-label="Message TripWise AI" autoFocus
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); go(); } }}
        placeholder="Ask about hotels, transport, or a whole trip…" style={{ outline: "none", boxShadow: "none" }} className="max-h-44 min-h-[2.5rem] flex-1 resize-none bg-transparent px-3 py-2 text-[0.95rem] text-ink outline-none placeholder:text-ink/40" />
      <button type="submit" aria-label="Send message" disabled={!v.trim() || busy} className="mb-0.5 grid h-10 w-10 shrink-0 place-items-center rounded-full bg-gold text-plum transition hover:bg-champagne disabled:opacity-40"><ArrowUp className="h-5 w-5" /></button>
    </form>
  );
}

export default function ChatHome() {
  const { msgs, busy, send, suggestions, lastUnderstood, loadingHistory } = useChat();
  const [showU, setShowU] = useState(false);
  const [engine, setEngine] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { api.meta().then((m: any) => setEngine(m?.chat?.llm_enabled ? "Gemini-assisted understanding · results come from the dataset" : "Rule-based understanding · not a language model")).catch(() => {}); }, []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs.length, busy]);
  const empty = msgs.length === 0 && !loadingHistory;
  const last = msgs[msgs.length - 1];

  if (empty) {
    return (
      <section className="mx-auto flex min-h-full max-w-2xl flex-col justify-center px-4 py-8 text-center" aria-label="Chat">
        <Sparkles className="mx-auto mb-3 h-6 w-6 text-gold" aria-hidden />
        <h1 className="font-display text-4xl text-royal sm:text-5xl">Where would you like to go?</h1>
        <p className="mx-auto mt-3 max-w-lg text-ink/70">Tell me your destination, budget, travel dates, or the kind of experience you're dreaming of. Let's plan your next adventure.</p>
        <div className="mt-7 text-left"><Composer onSend={send} busy={busy} big /></div>
        <div className="mt-4 flex flex-wrap justify-center gap-2">{CHIPS.map((c) => <button key={c} className="chip" onClick={() => send(c)}>{c}</button>)}</div>
        {engine && <p className="mt-6 text-[0.7rem] text-ink/45">{engine}</p>}
      </section>
    );
  }
  return (
    <section className="flex min-h-full flex-col" aria-label="Chat">
      <div className="mx-auto w-full max-w-3xl flex-1 space-y-4 px-4 py-6" role="log" aria-live="polite">
        {loadingHistory && <p className="text-center text-sm text-ink/55">Opening conversation…</p>}
        {msgs.map((m) => (
          <div key={m.id} className={m.role === "user" ? "flex justify-end" : "flex"}>
            {m.role === "user" ? (
              <div className="max-w-[85%] whitespace-pre-line rounded-2xl rounded-br-md bg-royal px-4 py-2.5 text-[0.95rem] text-ivory">{m.text}</div>
            ) : (
              <div className={`w-full max-w-full rounded-2xl rounded-bl-md border px-4 py-3 text-[0.95rem] leading-relaxed ${m.error ? "border-red-300 bg-red-50 text-red-900" : "border-royal/10 bg-white text-ink"}`}>
                <p className="whitespace-pre-line">{m.reply ? leadText(m.text, m.reply.actions) : m.text}</p>
                {m.reply && <ChatCards actions={m.reply.actions} onSend={send} />}
                {m.error && m.retryText && <button className="btn-ghost btn-sm mt-2" onClick={() => send(m.retryText!)}><RotateCcw className="h-3.5 w-3.5" /> Retry</button>}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="flex"><div className="flex items-center gap-1.5 rounded-2xl border border-royal/10 bg-white px-4 py-3" role="status" aria-label="TripWise is thinking">{[0, 1, 2].map((i) => <span key={i} className="h-2 w-2 animate-bounce rounded-full bg-gold" style={{ animationDelay: `${i * 0.15}s` }} />)}</div></div>}
        {showU && <UnderstoodPanel onClose={() => setShowU(false)} />}
        <div ref={end} />
      </div>
      <div className="sticky bottom-0 border-t border-gold/20 bg-ivory/95 px-4 pb-3 pt-2 backdrop-blur">
        <div className="mx-auto max-w-3xl space-y-2">
          {!busy && last?.role === "assistant" && suggestions.length > 0 && <div className="flex gap-2 overflow-x-auto pb-1">{suggestions.slice(0, 5).map((s) => <button key={s} className="chip shrink-0" onClick={() => send(s)}>{s}</button>)}</div>}
          <Composer onSend={send} busy={busy} />
          <div className="flex items-center justify-between text-[0.68rem] text-ink/45">
            <span>{engine}</span>
            {lastUnderstood && <button className="inline-flex items-center gap-1 font-semibold text-violet hover:underline" aria-expanded={showU} onClick={() => setShowU((s) => !s)}><Eye className="h-3 w-3" /> What I understood</button>}
          </div>
        </div>
      </div>
    </section>
  );
}
