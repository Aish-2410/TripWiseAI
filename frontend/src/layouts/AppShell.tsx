import { useEffect, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, Menu, MessageSquarePlus, PanelLeftClose, PanelLeftOpen, Route as RouteIcon } from "lucide-react";
import { Brand } from "../components/Brand";
import Sidebar from "../components/Sidebar";
import Footer from "../components/Footer";
import { useTrip } from "../lib/store";
import { useChat } from "../lib/chat";

const KEY = "tripwise.sidebar.v1";

export default function AppShell() {
  const [collapsed, setCollapsed] = useState(() => { try { return localStorage.getItem(KEY) === "1"; } catch { return false; } });
  const [drawer, setDrawer] = useState(false);
  const { pathname } = useLocation();
  const nav = useNavigate();
  const { plan } = useTrip();
  const { newChat } = useChat();
  const isChat = pathname === "/";
  useEffect(() => { try { localStorage.setItem(KEY, collapsed ? "1" : "0"); } catch { /* ignore */ } }, [collapsed]);
  useEffect(() => { setDrawer(false); }, [pathname]);
  useEffect(() => { if (!drawer) return; const f = (e: KeyboardEvent) => e.key === "Escape" && setDrawer(false); window.addEventListener("keydown", f); return () => window.removeEventListener("keydown", f); }, [drawer]);
  const w = collapsed ? "4.5rem" : "17rem";

  return (
    <div className="app-shell flex h-dvh flex-col bg-ivory" style={{ ["--sidebar-w" as string]: w }}>
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[100] focus:rounded-lg focus:bg-gold focus:px-4 focus:py-2 focus:text-plum">Skip to content</a>
      <header className="no-print z-30 flex h-14 shrink-0 items-center justify-between gap-3 border-b border-gold/20 bg-plum px-3 sm:px-4">
        <div className="flex items-center gap-2">
          <button className="rounded-lg p-2 text-ivory hover:bg-white/10 lg:hidden" aria-label="Open menu" aria-expanded={drawer} onClick={() => setDrawer(true)}><Menu className="h-5 w-5" /></button>
          <button className="hidden rounded-lg p-2 text-ivory hover:bg-white/10 lg:block" aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} aria-expanded={!collapsed} onClick={() => setCollapsed((c) => !c)}>
            {collapsed ? <PanelLeftOpen className="h-5 w-5" /> : <PanelLeftClose className="h-5 w-5" />}
          </button>
          <Brand />
        </div>
        <div className="flex items-center gap-2">
          {plan && <Link to="/itinerary" className="hidden items-center gap-1.5 rounded-full border border-gold/40 px-3 py-1.5 text-xs text-champagne hover:bg-white/10 sm:inline-flex"><RouteIcon className="h-3.5 w-3.5" /> {plan.destination_name} itinerary</Link>}
          <button className="btn-gold btn-sm" onClick={() => { newChat(); nav("/"); }} aria-label="New chat"><MessageSquarePlus className="h-3.5 w-3.5" /><span className="hidden sm:inline"> New chat</span></button>
        </div>
      </header>
      <div className="flex min-h-0 flex-1">
        <aside className="no-print hidden shrink-0 border-r border-gold/15 transition-[width] duration-200 lg:block" style={{ width: w }} aria-label="Sidebar"><Sidebar collapsed={collapsed} onNavigate={() => {}} /></aside>
        {drawer && (
          <div className="no-print fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Menu">
            <button aria-label="Close menu" className="absolute inset-0 bg-plum/60" onClick={() => setDrawer(false)} />
            <div className="animate-rise absolute inset-y-0 left-0 w-[17rem] max-w-[85vw] shadow-lift"><Sidebar collapsed={false} onNavigate={() => setDrawer(false)} onClose={() => setDrawer(false)} /></div>
          </div>
        )}
        <main id="main" tabIndex={-1} className="app-main relative min-w-0 flex-1 overflow-y-auto">
          <Outlet />
          {!isChat && <Footer />}
          {!isChat && <Link to="/" className="no-print fixed bottom-4 right-4 z-40 inline-flex items-center gap-2 rounded-full bg-royal px-4 py-2.5 text-sm text-ivory shadow-lift hover:bg-violet"><ArrowLeft className="h-4 w-4" /> Back to chat</Link>}
        </main>
      </div>
    </div>
  );
}
