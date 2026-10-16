import { Link } from "react-router-dom";
import { Brand } from "./Brand";

export default function Footer() {
  return (
    <footer className="no-print relative mt-24 overflow-hidden bg-plum text-ivory/80">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-gold to-transparent" />
      <div className="mx-auto grid max-w-7xl gap-10 px-5 py-14 md:grid-cols-[1.4fr_1fr_1fr_1.6fr]">
        <div>
          <Brand />
          <p className="mt-4 max-w-xs font-display text-lg italic text-champagne">The world, thoughtfully yours.</p>
          <p className="mt-3 max-w-xs text-sm text-mauve">An academic Artificial Intelligence project demonstrating search, knowledge representation, rule-based inference and budget optimisation.</p>
        </div>
        <div>
          <h3 className="eyebrow-light eyebrow mb-3">Explore</h3>
          <ul className="space-y-2 text-sm">
            {[["/discover", "Discover destinations"], ["/planner", "Trip planner"], ["/itinerary", "My itinerary"], ["/saved", "Saved trips"]].map(([to, t]) => (
              <li key={to}><Link className="hover:text-champagne" to={to}>{t}</Link></li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="eyebrow-light eyebrow mb-3">The AI</h3>
          <ul className="space-y-2 text-sm">
            <li><Link className="hover:text-champagne" to="/thinks">How TripWise thinks</Link></li>
            <li className="text-mauve">A* · BFS · Beam search</li>
            <li className="text-mauve">Knowledge base · Rule engine</li>
            <li className="text-mauve">Budget Guardian</li>
          </ul>
        </div>
        <div>
          <h3 className="eyebrow-light eyebrow mb-3">Data &amp; attribution</h3>
          <ul className="space-y-2 text-xs leading-relaxed text-mauve">
            <li><span className="text-ivory">Preference learning:</span> <a className="underline hover:text-champagne" href="https://github.com/Stravl/Stravl-Data" target="_blank" rel="noreferrer">Stravl-Data</a> (open travel-preference data, free for academic use).</li>
            <li><span className="text-ivory">Destinations, attractions, stays, transport model:</span> illustrative TripWise sample dataset. Prices are estimates; stays are fictional placeholders; nothing here is a live fare, timetable or booking.</li>
            <li><span className="text-ivory">Photographs:</span> Wikipedia / Wikimedia Commons (individual licences apply).</li>
            <li><span className="text-ivory">Maps:</span> © <a className="underline hover:text-champagne" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors.</li>
          </ul>
        </div>
      </div>
      <div className="border-t border-white/10 py-5 text-center text-xs text-mauve">TripWise AI · College AI assignment demonstration · All costs are estimates</div>
    </footer>
  );
}
