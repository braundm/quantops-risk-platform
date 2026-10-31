export interface TreasuryBond {
  id: string; name: string; face: string; quantity: string; coupon_rate: string;
  yield_rate: string; years: number; frequency: number;
}
export interface LiquidityPosition {
  id: string; name: string; quantity: string; reference_price: string; price_date: string;
  sessions: { date: string; volume: string }[];
}
export interface TreasuryRequest {
  currency: string; valuation_date: string; origin: "synthetic" | "user_supplied"; source_note: string;
  bonds: TreasuryBond[]; liquidity_positions: LiquidityPosition[]; participation: string;
  max_abs_dv01: string | null; max_liquidation_days: number;
}
export interface TreasuryResult {
  methodology_version: string; generated_at: string; origin: string; currency: string;
  net_value: string; gross_value: string; signed_dv01: string; gross_dv01: string;
  dv01_limit_status: string;
  bonds: { id: string; name: string; value: string; signed_dv01: string; metrics: {
    price: string; macaulay_duration: string; modified_duration: string; convexity: string;
  } }[];
  scenarios: { shock_bp: number; before: string; after: string; pnl: string; pnl_by_position: Record<string, string> }[];
  liquidity: { id: string; name: string; status: string; limit_status: string; first_date: string | null; last_date: string | null;
    estimate: { observations: number; adv: string | null; position_to_adv: string | null; days: number | null } }[];
  liquidity_coverage_pct: string | null; liquidatable_one_day_pct: string | null; liquidatable_five_days_pct: string | null;
  assumptions: string[];
}

export async function treasuryRequest(path: "analyze" | "report", input: TreasuryRequest): Promise<Response> {
  const response = await fetch(`/api/v1/treasury/${path}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input),
  });
  if (!response.ok) {
    const problem = await response.json() as { detail?: string };
    throw new Error(problem.detail ?? "Treasury analysis unavailable. Check the inputs and local API.");
  }
  return response;
}

export function treasuryExample(kind: "ladder" | "long" | "offset"): TreasuryRequest {
  const bond = (name: string, years: number, quantity: string): TreasuryBond => ({
    id: crypto.randomUUID(), name, years, quantity, face: "1000", coupon_rate: "0.04", yield_rate: "0.04", frequency: 2,
  });
  const sessions: LiquidityPosition["sessions"] = [];
  for (let day = 7; day <= 32; day += 1) {
    const date = new Date(Date.UTC(2026, 8, day));
    if (date.getUTCDay() !== 0 && date.getUTCDay() !== 6) sessions.push({ date: date.toISOString().slice(0, 10), volume: "10000" });
  }
  return {
    currency: "USD", valuation_date: "2026-10-02", origin: "synthetic",
    source_note: `Synthetic educational ${kind} case; invented bond terms, holdings and volume, not market observations.`,
    bonds: kind === "ladder" ? [bond("Synthetic 2-year", 2, "100"), bond("Synthetic 5-year", 5, "100"), bond("Synthetic 10-year", 10, "100")]
      : kind === "long" ? [bond("Synthetic 20-year", 20, "300")]
        : [bond("Synthetic 5-year long", 5, "100"), bond("Synthetic 5-year short", 5, "-100")],
    liquidity_positions: [{ id: crypto.randomUUID(), name: "Synthetic equity volume example", quantity: "8000", reference_price: "25", price_date: "2026-10-02", sessions }],
    participation: "0.1", max_abs_dv01: "150", max_liquidation_days: 5,
  };
}
