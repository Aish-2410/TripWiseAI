import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Costs } from "../lib/types";
import { inr, cap } from "../lib/format";

const COLORS = ["#2B1748", "#5B347D", "#C6A15B", "#E8D4A2", "#A99AB8", "#7A5C1E", "#EAE0F4"];

export default function BudgetPanel({ costs }: { costs: Costs }) {
  const pie = Object.entries(costs.breakdown).filter(([, v]) => v > 0).map(([k, v]) => ({ name: cap(k.replace(/_/g, " ")), value: v }));
  const bars = costs.daily.map((d) => ({ day: `Day ${d.day}`, Attractions: d.attractions, "Local transport": d.local_transport, Food: d.food, Stay: d.accommodation }));
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Estimated total" value={inr(costs.total)} />
        <Stat label="Per person" value={inr(costs.per_person)} />
        {costs.budget ? <Stat label={costs.over_budget ? "Over budget by" : "Remaining"} value={inr(costs.over_budget ? costs.overrun : costs.remaining)} tone={costs.over_budget ? "bad" : "good"} /> : <Stat label="Budget" value="not set" />}
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <figure>
          <figcaption className="label">Where the money goes</figcaption>
          <div className="h-64" role="img" aria-label={`Cost breakdown: ${pie.map((p) => `${p.name} ${inr(p.value)}`).join(", ")}`}>
            <ResponsiveContainer><PieChart><Pie data={pie} dataKey="value" nameKey="name" innerRadius="52%" outerRadius="82%" paddingAngle={2} stroke="none">{pie.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Pie><Tooltip formatter={(v) => inr(Number(v))} /><Legend verticalAlign="bottom" height={44} /></PieChart></ResponsiveContainer>
          </div>
        </figure>
        <figure>
          <figcaption className="label">Day-by-day spend (excl. travel to destination)</figcaption>
          <div className="h-64" role="img" aria-label="Daily spend bar chart">
            <ResponsiveContainer><BarChart data={bars}><CartesianGrid strokeDasharray="3 3" stroke="#EAE0F4" /><XAxis dataKey="day" fontSize={12} /><YAxis fontSize={12} tickFormatter={(v) => `${v / 1000}k`} /><Tooltip formatter={(v) => inr(Number(v))} /><Legend />
              <Bar dataKey="Attractions" stackId="a" fill="#C6A15B" /><Bar dataKey="Local transport" stackId="a" fill="#5B347D" /><Bar dataKey="Food" stackId="a" fill="#E8D4A2" /><Bar dataKey="Stay" stackId="a" fill="#2B1748" /></BarChart></ResponsiveContainer>
          </div>
        </figure>
      </div>
      <table className="w-full text-sm">
        <caption className="sr-only">Cost table</caption>
        <tbody>
          {Object.entries(costs.breakdown).map(([k, v]) => <tr key={k} className="border-b border-royal/10"><th scope="row" className="py-1.5 text-left font-medium">{cap(k.replace(/_/g, " "))}</th><td className="py-1.5 text-right">{inr(v)}</td></tr>)}
          <tr><th scope="row" className="py-2 text-left font-display text-lg text-royal">Total</th><td className="py-2 text-right font-display text-lg text-royal">{inr(costs.total)}</td></tr>
        </tbody>
      </table>
      <details className="text-xs text-ink/70"><summary className="cursor-pointer font-semibold text-violet">Assumptions behind these numbers</summary><ul className="mt-2 list-disc space-y-1 pl-5">{costs.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul></details>
    </div>
  );
}
function Stat({ label, value, tone }: { label: string; value: string; tone?: "bad" | "good" }) {
  return <div className={`rounded-2xl p-4 ${tone === "bad" ? "bg-red-50 text-red-900" : tone === "good" ? "bg-champagne/40 text-plum" : "bg-lavender/60 text-royal"}`}><p className="label !mb-1">{label}</p><p className="font-display text-3xl">{value}</p></div>;
}
