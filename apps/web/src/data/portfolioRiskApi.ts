import type { XtbBook } from "./xtbApi";

export interface RiskHistory {
  symbol: string; currency: string; base_currency: string; source: string; source_url: string;
  fx_source: string; fetched_at: string; origin: "provider" | "user" | "synthetic";
  price_basis: "split_dividend_adjusted";
  rows: { date: string; close: string; adjusted_close: string; fx_to_base: string }[];
}
export interface RiskScenario {
  name: string; position_shocks: Record<string, string>; class_shocks: Record<string, string>;
  fx_shocks: Record<string, string>;
}
export interface PerformanceSummary {
  period_return: number | null; maximum_drawdown: number | null; current_drawdown: number | null;
  peak: string | null; trough: string | null; recovery: string | null;
  peak_to_trough_days: number | null; recovery_days: number | null;
  worst_month: string | null; worst_month_return: number | null; worst_year: string | null;
  worst_year_return: number | null; partial_months: string[]; partial_years: string[];
}
export interface RiskInput {
  scope?: "full_account" | "securities_only";
  asset_scope?: "all_supported" | "equities_only";
  book: XtbBook; base_currency: string; histories: RiskHistory[];
  cash: { symbol: string; currency: string; amount: string; as_of: string }[];
  cash_confirmed: boolean; confidence: string; start: string | null; end: string | null;
  benchmark: string | null; scenarios: RiskScenario[]; variant: Record<string, string> | null;
  tolerance_amount: string | null; tolerance_fraction: string | null;
  etf_compositions: unknown[]; metadata: unknown[];
}
export interface ScenarioResult {
  name: string; kind: string; status: string; pnl: string | null; fraction: string | null;
  value_after: string | null; impacts: Record<string, string>; largest_losses: string[];
  maximum_drawdown: number | null; exceeds_tolerance: boolean | null;
}
export interface AllocationResult {
  value: string; weights: Record<string, string>; largest_position: string; top_five: string;
  position_values: Record<string, string>; var_amount: string | null; es_amount: string | null;
  exposures: Record<string, Record<string, string>>;
  risk: { status: string; observations: number; required_observations: number;
    annual_volatility: number | null; var_fraction: number | null; es_fraction: number | null;
    tail_count: number; components: Record<string, number>; risk_shares: Record<string, number | null>;
    reconciliation_error: number | null; correlations: (number | null)[][] };
  performance: PerformanceSummary; curve: [string, string][]; scenarios: ScenarioResult[];
  diagnostics: EquityDiagnostics;
}
export interface EquityDiagnostics {
  methodology: string;
  concentration: { positions: number; groups: number; largest: string; top_three: string;
    top_five: string; hhi: string; effective_positions: string; issuer_identity_coverage: string };
  score: { status: "available" | "insufficient_data" | "stale_valuation" | "outside_equity_scope";
    value: number | null; band: "lower" | "moderate" | "elevated" | "high" | null;
    minimum_observations: number;
    components: { key: string; value: number | null; score: number | null; weight: number;
      lower_anchor: number; upper_anchor: number }[] };
  weighted_correlation: number | null;
  strongest_pairs: { left: string; right: string; correlation: number; combined_weight: string }[];
  diversification_ratio: number | null;
  position_volatilities: Record<string, number | null>;
  single_position_stress: { symbol: string; shock: string; pnl: string;
    portfolio_fraction: string; value_after: string }[];
  drawdown_curve: [string, number][];
}
export interface RiskResult {
  scope: "full_account" | "securities_only";
  asset_scope: "all_supported" | "equities_only";
  out_of_scope: Record<string, string>;
  methodology: string; status: string; base_currency: string; valuation_date: string | null;
  quantity_date: string | null;
  period_start: string | null; period_end: string | null; coverage_fraction: string | null;
  covered_value: string; excluded: Record<string, string>;
  positions: { symbol: string; name: string; asset_class: string; currency: string | null;
    listing_country: string | null; issuer_country: string | null; sector: string | null;
    economic_currency: string | null; value: string | null; weight: string | null; status: string }[];
  before: AllocationResult | null; after: AllocationResult | null;
  benchmark: PerformanceSummary | null; benchmark_status: string; history_dates: number;
  return_dates: number; skipped_pairs: number; history_coverage: Record<string, number>;
  etf_overlap: Record<string, string>[]; warnings: string[];
}
