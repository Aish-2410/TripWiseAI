import { Route, Routes, useLocation } from "react-router-dom";
import { useEffect } from "react";
import AppShell from "./layouts/AppShell";
import ChatHome from "./pages/ChatHome";
import Landing from "./pages/Landing";
import Discover from "./pages/Discover";
import Planner from "./pages/Planner";
import Itinerary from "./pages/Itinerary";
import Saved from "./pages/Saved";
import Thinks from "./pages/Thinks";
import NotFound from "./pages/NotFound";

function ScrollTop() {
  const { pathname } = useLocation();
  useEffect(() => { document.getElementById("main")?.scrollTo({ top: 0 }); }, [pathname]);
  return null;
}

export default function App() {
  return (
    <>
      <ScrollTop />
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<ChatHome />} />
          <Route path="about" element={<Landing />} />
          <Route path="discover" element={<Discover />} />
          <Route path="planner" element={<Planner />} />
          <Route path="itinerary" element={<Itinerary />} />
          <Route path="saved" element={<Saved />} />
          <Route path="thinks" element={<Thinks />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </>
  );
}
