import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api } from "./api";
import { useTrip } from "./store";
import type { ChatReply, Understood } from "./types";

export interface Msg { id: string; role: "user" | "assistant"; text: string; reply?: ChatReply; error?: boolean; retryText?: string }
export interface ChatSummary { id: string; title: string; messages: number; updated_at: string }
type Focus = { id: string; name: string } | null;

interface Ctx {
  msgs: Msg[];
  busy: boolean;
  focus: Focus;
  chats: ChatSummary[];
  loadingHistory: boolean;
  lastUnderstood: Understood | undefined;
  suggestions: string[];
  send: (text: string) => Promise<void>;
  newChat: () => void;
  openChat: (id: string) => Promise<void>;
  deleteChat: (id: string) => Promise<void>;
  patchContext: (patch: Record<string, unknown>) => Promise<void>;
}

const IDS_KEY = "tripwise.chats.v1";
const readIds = (): string[] => { try { const v = JSON.parse(localStorage.getItem(IDS_KEY) || "[]"); return Array.isArray(v) ? v : []; } catch { return []; } };
const uid = () => Math.random().toString(36).slice(2, 10);

const ChatCtx = createContext<Ctx | null>(null);
export const useChat = () => { const c = useContext(ChatCtx); if (!c) throw new Error("ChatProvider missing"); return c; };

// All conversation state lives here (not inside the chat page) so it survives navigating to Discover, Itinerary, etc. and back.
// The backend stays the single source of understanding and recommendations; this provider only moves messages.
export function ChatProvider({ children }: { children: ReactNode }) {
  const { sessionId, setSessionId, plan, replacePrefs, adoptPlan, setPlan, newTrip } = useTrip();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [busy, setBusy] = useState(false);
  const [focus, setFocus] = useState<Focus>(null);
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const ids = useRef<string[]>(readIds());
  const booted = useRef(false);

  const remember = useCallback((id: string) => {
    ids.current = [id, ...ids.current.filter((x) => x !== id)].slice(0, 30);
    try { localStorage.setItem(IDS_KEY, JSON.stringify(ids.current)); } catch { /* storage blocked */ }
  }, []);
  const refresh = useCallback(async () => {
    if (!ids.current.length) { setChats([]); return; }
    try { setChats(await api.chatSummaries(ids.current)); } catch { /* sidebar history is optional; keep the last list */ }
  }, []);

  const toMsgs = (h: Awaited<ReturnType<typeof api.chatHistory>>): Msg[] =>
    h.messages.map((m) => ({
      id: uid(), role: m.role as Msg["role"], text: m.content,
      reply: m.role === "assistant" && m.payload ? { text: m.content, intent: m.payload.intent ?? "", entities: m.payload.entities ?? {}, understood: m.payload.understood, suggestions: m.payload.suggestions ?? [], actions: m.payload.actions ?? [] } : undefined,
    }));

  // Restore the open conversation after a reload.
  useEffect(() => {
    if (booted.current) return;
    booted.current = true;
    refresh();
    if (!sessionId) return;
    setLoadingHistory(true);
    api.chatHistory(sessionId).then((h) => { setMsgs(toMsgs(h)); setFocus(h.focus); }).catch(() => setSessionId(null)).finally(() => setLoadingHistory(false));
  }, [sessionId, setSessionId, refresh]);

  const send = useCallback(async (raw: string) => {
    const text = raw.trim();
    if (!text || busy) return;
    setBusy(true);
    setMsgs((m) => [...m.filter((x) => !x.error), { id: uid(), role: "user", text }]);
    try {
      const r = await api.chat(text, sessionId, plan);
      if (r.session_id !== sessionId) setSessionId(r.session_id);
      remember(r.session_id);
      replacePrefs(r.prefs); setFocus(r.focus);
      const planAct = r.reply.actions.find((a) => a.type === "plan");
      if (planAct?.plan) adoptPlan(planAct.plan);
      else if (r.plan && !plan) adoptPlan(r.plan, { push: false });
      setMsgs((m) => [...m, { id: uid(), role: "assistant", text: r.reply.text, reply: r.reply }]);
      refresh();
    } catch (e: any) {
      setMsgs((m) => [...m, { id: uid(), role: "assistant", error: true, retryText: text, text: e?.message?.includes("Cannot reach") ? e.message : `I could not complete that request (${e?.message ?? "unknown error"}). Your trip has not been changed.` }]);
    } finally { setBusy(false); }
  }, [busy, sessionId, plan, setSessionId, remember, replacePrefs, adoptPlan, refresh]);

  const newChat = useCallback(() => {
    newTrip();                 // clears the working trip context; earlier conversations stay saved server-side
    setSessionId(null); setMsgs([]); setFocus(null);
  }, [newTrip, setSessionId]);

  const openChat = useCallback(async (id: string) => {
    setLoadingHistory(true);
    try {
      const h = await api.chatHistory(id);
      setSessionId(id); remember(id); setMsgs(toMsgs(h)); setFocus(h.focus);
      replacePrefs(h.prefs); setPlan(h.plan);
    } catch (e: any) {
      setMsgs((m) => [...m, { id: uid(), role: "assistant", error: true, text: `I could not open that conversation (${e?.message ?? "error"}).` }]);
    } finally { setLoadingHistory(false); }
  }, [setSessionId, remember, replacePrefs, setPlan]);

  const deleteChat = useCallback(async (id: string) => {
    try { await api.chatReset(id); } catch { /* already gone */ }
    ids.current = ids.current.filter((x) => x !== id);
    try { localStorage.setItem(IDS_KEY, JSON.stringify(ids.current)); } catch { /* ignore */ }
    if (id === sessionId) { setSessionId(null); setMsgs([]); setFocus(null); }
    refresh();
  }, [sessionId, setSessionId, refresh]);

  const patchContext = useCallback(async (patch: Record<string, unknown>) => {
    if (!sessionId) throw new Error("Start a conversation first.");
    const r = await api.chatPrefs(sessionId, patch);
    replacePrefs(r.prefs); setFocus(r.focus);
  }, [sessionId, replacePrefs]);

  const lastReply = [...msgs].reverse().find((m) => m.role === "assistant" && m.reply)?.reply;
  const lastUnderstood = lastReply?.understood;
  const suggestions = lastReply?.suggestions ?? [];

  const value = useMemo(() => ({ msgs, busy, focus, chats, loadingHistory, lastUnderstood, suggestions, send, newChat, openChat, deleteChat, patchContext }),
    [msgs, busy, focus, chats, loadingHistory, lastUnderstood, suggestions, send, newChat, openChat, deleteChat, patchContext]);
  return <ChatCtx.Provider value={value}>{children}</ChatCtx.Provider>;
}
