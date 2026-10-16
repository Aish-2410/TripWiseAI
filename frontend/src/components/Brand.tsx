import { Link } from "react-router-dom";

export function CompassMark({ size = 36 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" role="img">
      <defs>
        <linearGradient id="g1" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stopColor="#E8D4A2" /><stop offset="1" stopColor="#C6A15B" /></linearGradient>
      </defs>
      <circle cx="32" cy="32" r="28" fill="none" stroke="url(#g1)" strokeWidth="1.6" />
      <circle cx="32" cy="32" r="22" fill="none" stroke="#C6A15B" strokeOpacity=".45" strokeWidth="1" strokeDasharray="2 4" />
      <path d="M32 9l6.2 20.8L32 55l-6.2-25.2z" fill="url(#g1)" />
      <path d="M9 32l20.8-6.2L55 32l-25.2 6.2z" fill="#C6A15B" fillOpacity=".5" />
      <circle cx="32" cy="32" r="3.2" fill="#1A1028" stroke="#E8D4A2" strokeWidth="1.2" />
    </svg>
  );
}

export function Brand({ light = true }: { light?: boolean }) {
  return (
    <Link to="/" className="group flex items-center gap-3" aria-label="TripWise AI home">
      <span className="transition-transform duration-700 group-hover:rotate-[24deg]"><CompassMark /></span>
      <span className="leading-none">
        <span className={`font-display text-xl font-semibold tracking-tight ${light ? "text-ivory" : "text-royal"}`}>TripWise <span className="text-gold">AI</span></span>
        <span className={`mt-1 block text-[0.6rem] uppercase tracking-[0.3em] ${light ? "text-mauve" : "text-violet"}`}>Travel concierge</span>
      </span>
    </Link>
  );
}
