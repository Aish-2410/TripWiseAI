export const inr = (n: number | null | undefined) => (n == null ? "-" : `₹${Math.round(n).toLocaleString("en-IN")}`);
export const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
export const hrs = (h: number | null | undefined) => (h == null ? "-" : h < 1 ? `${Math.round(h * 60)} min` : `${h.toFixed(h % 1 ? 1 : 0)} h`);
export const mins = (m: number) => (m >= 60 ? `${Math.floor(m / 60)} h${m % 60 ? ` ${m % 60} min` : ""}` : `${m} min`);
export const INTEREST_LABEL: Record<string, string> = {
  nature: "Nature & wildlife", mountains: "Mountains & hill stations", beaches: "Beaches", adventure: "Adventure & trekking", historical: "Historical landmarks",
  culture: "Culture & heritage", food: "Food & cuisine", shopping: "Shopping", photography: "Photography", wellness: "Relaxation & wellness",
};
export const SLOT_ICON: Record<string, string> = { morning: "Morning", afternoon: "Afternoon", evening: "Evening" };
export function planSummaryText(plan: any): string {
  const c = plan.costs;
  const lines = [`TripWise AI - ${plan.destination_name}, ${plan.days.length} days`, `Estimated total ${inr(c.total)} for ${c.travellers} traveller(s) (${inr(c.per_person)} per person) - estimate from sample data`, ""];
  for (const d of plan.days) {
    lines.push(`Day ${d.day}${d.date ? ` (${d.date})` : ""}`);
    for (const it of d.schedule.items) if (it.kind === "activity") lines.push(`  ${it.start} ${it.title}${it.fee_group ? ` - ${inr(it.fee_group)}` : ""}`);
  }
  lines.push("", `Transport: ${plan.transport.mode} (about ${plan.transport.one_way_hours} h each way)`, `Stay: ${plan.accommodation_tier} (sample record)`);
  return lines.join("\n");
}
