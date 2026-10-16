import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { Compass, Info, MapPinned, MessageSquarePlus, MessagesSquare, Route as RouteIcon, SlidersHorizontal, Bookmark, Trash2, X, Check } from "lucide-react";
import { useChat } from "../lib/chat";
import { useTrip } from "../lib/store";

const TOOLS = [
  { to: "/discover", label: "Destinations", icon: Compass },
  { to: "/planner", label: "Trip planner", icon: SlidersHorizontal },
  { to: "/itinerary", label: "My itinerary", icon: RouteIcon },
  { to: "/saved", label: "Saved trips", icon: Bookmark },
  { to: "/thinks", label: "How TripWise thinks", icon: Info },
];

interface Props { collapsed: boolean; onNavigate: () => void; onClose?: () => void }

export default function Sidebar({ collapsed, onNavigate, onClose }: Props) {
  const { chats, newChat, openChat, deleteChat } = useChat();
  const { plan, sessionId } = useTrip();
  const nav = useNavigate();
  const [confirm, setConfirm] = useState<string | null>(null);
  const item = (active: boolean) =>
    `group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors ${collapsed ? "justify-center" : ""} ${active ? "bg-white/10 text-champagne before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:rounded before:bg-gold" : "text-ivory/80 hover:bg-white/5 hover:text-champagne"}`;
  return (
    <div className="flex h-full flex-col bg-plum text-ivory">
      {onClose && <div className="flex justify-end p-2"><button aria-label="Close menu" className="rounded-lg p-2 hover:bg-white/10" onClick={onClose}><X className="h-5 w-5" /></button></div>}
      <div className="p-3">
        <button className={`btn-gold w-full ${collapsed ? "!px-0" : ""}`} aria-label="New chat" title="New chat" onClick={() => { newChat(); nav("/"); onNavigate(); }}>
          <MessageSquarePlus className="h-4 w-4" />{!collapsed && " New chat"}
        </button>
      </div>
      <nav className="flex-1 space-y-5 overflow-y-auto px-3 pb-4" aria-label="Primary">
        <div className="space-y-1">
          <NavLink to="/" end onClick={onNavigate} title="Chat" aria-label="Chat" className={({ isActive }) => item(isActive)}><MessagesSquare className="h-4.5 w-4.5 shrink-0" />{!collapsed && "Chat"}</NavLink>
        </div>
        {!collapsed && (
          <div>
            <p className="px-3 pb-1.5 text-[0.62rem] font-semibold uppercase tracking-[0.25em] text-mauve">Recent conversations</p>
            {chats.length === 0 ? <p className="px-3 text-xs text-mauve">Your conversations will appear here.</p> : (
              <ul className="space-y-0.5">
                {chats.slice(0, 12).map((c) => (
                  <li key={c.id} className="group/row flex items-center">
                    <button onClick={() => { openChat(c.id); nav("/"); onNavigate(); }} aria-current={c.id === sessionId ? "true" : undefined}
                      className={`min-w-0 flex-1 truncate rounded-lg px-3 py-2 text-left text-[0.82rem] transition-colors ${c.id === sessionId ? "bg-white/10 text-champagne" : "text-ivory/75 hover:bg-white/5 hover:text-champagne"}`} title={c.title}>{c.title || "Untitled chat"}</button>
                    {confirm === c.id ? (
                      <span className="flex shrink-0 gap-0.5">
                        <button aria-label="Confirm delete" className="rounded p-1.5 text-red-300 hover:bg-white/10" onClick={() => { deleteChat(c.id); setConfirm(null); }}><Check className="h-3.5 w-3.5" /></button>
                        <button aria-label="Cancel delete" className="rounded p-1.5 hover:bg-white/10" onClick={() => setConfirm(null)}><X className="h-3.5 w-3.5" /></button>
                      </span>
                    ) : <button aria-label={`Delete conversation ${c.title}`} className="shrink-0 rounded p-1.5 text-mauve opacity-60 hover:bg-white/10 hover:text-red-300 focus:opacity-100 group-hover/row:opacity-100" onClick={() => setConfirm(c.id)}><Trash2 className="h-3.5 w-3.5" /></button>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        <div className="space-y-1">
          {!collapsed && <p className="px-3 pb-1 text-[0.62rem] font-semibold uppercase tracking-[0.25em] text-mauve">Travel tools</p>}
          {TOOLS.map((t) => (
            <NavLink key={t.to} to={t.to} onClick={onNavigate} title={t.label} aria-label={t.label} className={({ isActive }) => item(isActive)}>
              <t.icon className="h-4.5 w-4.5 shrink-0" />{!collapsed && t.label}
              {t.to === "/itinerary" && plan && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-gold" aria-label="Itinerary ready" />}
            </NavLink>
          ))}
        </div>
      </nav>
      <div className="border-t border-gold/15 p-3">
        <NavLink to="/about" onClick={onNavigate} title="About TripWise" aria-label="About TripWise" className={({ isActive }) => item(isActive)}><MapPinned className="h-4.5 w-4.5 shrink-0" />{!collapsed && "About TripWise"}</NavLink>
      </div>
    </div>
  );
}
