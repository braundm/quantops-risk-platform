export type InstrumentKind = "equity" | "etf" | "forex" | "future";
export type Action = "buy" | "sell" | "deposit" | "withdrawal" | "dividend" | "fee";
export interface Instrument { symbol: string; name: string; kind: InstrumentKind; sector: string; currency: string; multiplier: string; margin_rate: string; expiry?: string | null; spec_url?: string | null }
export interface MarketSeries { url: string; history_url: string; rows: { date: string; close: string }[] }
export interface Market { version: 1; provider: string; fetched_at: string; as_of: string; price_basis: string; catalog: Instrument[]; series: Record<string, MarketSeries> }
export interface Transaction { id: string; date: string; action: Action; symbol: string; quantity: string; price: string; amount_pln: string; fee_pln: string; source: "synthetic" | "user" }
export interface SavedScenario { id: string; name: string; price_shock: string; fx_shock: string; oil_shock: string; forex_shock: string }
export interface InvestorWorkspace { version: 1; name: string; market: Market; transactions: Transaction[]; scenarios: SavedScenario[] }
export interface Position { symbol: string; name: string; kind: InstrumentKind; sector: string; quantity: string; average_price: string; price: string; opened: string; holding_days: number; value: string; notional: string; unrealized_pnl: string; margin: string; weight: number; expiry: string | null }
export interface CurvePoint { day: string; equity: string; net_deposits: string; profit: string; return_index: number | null; drawdown: number | null }
export interface MarketPoint { symbol: string; name: string; period_return: number; annual_volatility: number; risk_contribution: number | null }
export interface BookResult {
  model_version: string; as_of: string; equity: string; cash: string; net_deposits: string; profit: string;
  fees: string; dividends: string; realized_pnl: string; gross_exposure: string; leverage: number | null;
  margin_estimate: string; cash_after_margin: string; twr: number | null; max_drawdown: number | null;
  effective_positions: number | null; top_weight: number | null; risk_status: string; var95: number | null;
  es95: number | null; annual_volatility: number | null; observations: number; positions: Position[];
  curve: CurvePoint[]; market_points: MarketPoint[]; correlation_symbols: string[]; correlations: (number | null)[][]; warnings: string[];
}
export interface WorkspaceResult {
  result: BookResult;
  scenarios: { scenario: SavedScenario; result: { pnl: string; equity_after: string; loss_fraction: number | null; impacts: Record<string, string> } }[];
  price_provenance: "provider_snapshot" | "user_supplied";
  transaction_provenance: "synthetic" | "user" | "mixed";
}
export interface TransactionPreview { rows: Transaction[]; errors: { row: number; message: string }[]; importable: boolean }
export const actionLabels: Record<Action, string> = { buy: "Kupno / zwiększenie long", sell: "Sprzedaż / zwiększenie short", deposit: "Wpłata", withdrawal: "Wypłata", dividend: "Dywidenda netto", fee: "Koszt / podatek / finansowanie" };
export const kindLabels: Record<InstrumentKind, string> = { equity: "Akcje", etf: "ETF", forex: "Forex · model", future: "Futures" };
export const money = (value: string | number | null, currency = "PLN") => value === null ? "—" : new Intl.NumberFormat("pl-PL", { style: "currency", currency, maximumFractionDigits: 2 }).format(Number(value));
export const pct = (value: number | null) => value === null ? "—" : new Intl.NumberFormat("pl-PL", { style: "percent", maximumFractionDigits: 1 }).format(value);
export const number = (value: string | number, digits = 2) => new Intl.NumberFormat("pl-PL", { maximumFractionDigits: digits }).format(Number(value));

export async function investorRequest<T>(route: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/v1/investor/${route}`, { method: body === undefined ? "GET" : "POST", headers: body === undefined ? undefined : { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  const result = await response.json() as T & { detail?: string; errors?: { message: string }[] };
  if (!response.ok) throw new Error(result.errors?.map((e) => e.message).join("; ") || result.detail || "Nie udało się obliczyć portfela.");
  return result;
}

export function downloadInvestor(name: string, content: string, mime = "application/json") {
  const url = URL.createObjectURL(new Blob([content], { type: mime }));
  const a = document.createElement("a"); a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function transactionsCsv(transactions: Transaction[]): string {
  const keys = ["id", "date", "action", "symbol", "quantity", "price", "amount_pln", "fee_pln", "source"] as const;
  return [keys.join(","), ...transactions.map((t) => keys.map((key) => `"${String(t[key]).replaceAll('"', '""')}"`).join(","))].join("\n");
}
