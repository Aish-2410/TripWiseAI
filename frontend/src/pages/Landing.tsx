import { Link } from "react-router-dom";
import { Brain, Compass, Map as MapIcon, MessageCircle, Scale, Wallet, ArrowRight } from "lucide-react";
import { useWikiImage } from "../lib/images";
import { CompassMark } from "../components/Brand";

const FEATURES = [
  { icon: Compass, t: "Reasoned recommendations", d: "Hard constraints first, then a transparent weighted score. Every ranking explains itself." },
  { icon: MapIcon, t: "Day-by-day itineraries", d: "Beam search groups nearby places and respects pace, age and accessibility." },
  { icon: Wallet, t: "Budget Guardian", d: "Group-aware costing, with ranked, explainable ways to bring an over-budget plan back in line." },
  { icon: Scale, t: "Re-plan without starting over", d: "Change days, pace or interests; what still works is kept, and every change is undoable." },
  { icon: MessageCircle, t: "A concierge you can talk to", d: "Rule-based chat that shows what it understood and lets you correct it." },
  { icon: Brain, t: "Nothing hidden", d: "See the rules, the knowledge base, A* and BFS, and the ML metrics, live." },
];

export default function Landing() {
  const hero = useWikiImage("Ooty");
  return (
    <>
      <section className="grain relative overflow-hidden bg-plum text-ivory">
        {hero.src && <img src={hero.src} alt="" className="absolute inset-0 h-full w-full object-cover opacity-30" />}
        <div className="absolute inset-0 bg-gradient-to-br from-plum via-royal/90 to-violet/60" />
        <div className="relative mx-auto grid max-w-7xl gap-10 px-5 py-24 lg:grid-cols-[1.3fr_1fr] lg:py-32 on-dark">
          <div className="animate-rise">
            <p className="eyebrow">India · Curated by reasoning</p>
            <h1 className="mt-4 font-display text-5xl font-semibold leading-[1.05] sm:text-7xl">Travel planned <span className="italic text-gold">with</span> you, not at you.</h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-ivory/80">Tell TripWise your budget, time and tastes. It shortlists destinations, explains why, builds a day-by-day itinerary and defends your budget.</p>
            <div className="mt-9 flex flex-wrap gap-3"><Link to="/planner" className="btn-gold px-7 py-3 text-base">Plan my journey <ArrowRight className="h-4 w-4" /></Link><Link to="/discover" className="btn-ghost-light px-7 py-3 text-base">Browse destinations</Link></div>
            <p className="mt-6 text-xs text-mauve">Prototype running on an illustrative sample dataset. Prices and stays are estimates, nothing can be booked.</p>
          </div>
          <div className="hidden items-center justify-center lg:flex"><div className="animate-[spin_90s_linear_infinite] opacity-90"><CompassMark size={300} /></div></div>
        </div>
      </section>
      <section className="mx-auto max-w-7xl px-5 py-20">
        <p className="eyebrow">What you get</p>
        <h2 className="mt-2 font-display text-4xl text-royal">A concierge that shows its work</h2>
        <div className="gold-rule mt-4" />
        <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: I, t, d }) => (
            <div key={t} className="card p-6 transition hover:-translate-y-1 hover:shadow-lift"><div className="mb-4 grid h-11 w-11 place-items-center rounded-full bg-royal text-gold"><I className="h-5 w-5" /></div><h3 className="font-display text-xl text-royal">{t}</h3><p className="mt-2 text-sm leading-relaxed text-ink/75">{d}</p></div>
          ))}
        </div>
      </section>
      <section className="bg-lavender/60 py-16">
        <div className="mx-auto grid max-w-5xl gap-6 px-5 text-center sm:grid-cols-3">
          {[["1", "Tell us", "Origin, budget, days, interests."], ["2", "Compare", "Ranked matches with scores and reasons."], ["3", "Refine", "Edit, re-plan, undo, save, print."]].map(([n, t, d]) => <div key={n}><p className="font-display text-5xl text-gold-deep">{n}</p><h3 className="font-display text-xl text-royal">{t}</h3><p className="text-sm text-ink/70">{d}</p></div>)}
        </div>
      </section>
    </>
  );
}
