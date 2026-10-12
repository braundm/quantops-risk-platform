export type Knowledge = "none" | "basic" | "experienced";
export interface Stock { symbol: string; name: string; market: string; currency: string }
export interface StockQuote {
  stock: Stock; requested_date: string; purchase_reference_date: string | null;
  purchase_reference_close: string | null; latest_date: string; latest_close: string;
  fetched_at: string; source_url: string; provider: string; corporate_action_review: boolean; warnings: string[];
}
export interface ProfileAnswers {
  goal: string; horizon_months: number; willingness_pct: number; capacity_pct: number;
  needs_cash_soon: boolean; stocks: Knowledge; bonds: Knowledge; etfs: Knowledge;
  options: Knowledge; futures: Knowledge; knows_loss: boolean;
  knows_diversification: boolean; knows_leverage: boolean;
}
export interface ProfileResult {
  learning_level: "introductory" | "standard" | "detailed";
  flags: string[]; learning_topics: string[]; available_tools: string[]; deferred_instruments: string[];
}
export interface OwnedStock {
  id: string; symbol: string; quantity: string; purchased: string; purchase_price: string | null;
  price_basis: "actual" | "reference" | "unknown"; quote: StockQuote;
}
export interface ValueResult {
  positions: { id: string; mark: { value: string; cost: string | null; unrealized_change: string | null; status: string } }[];
  totals: { currency: "USD" | "PLN"; value: string; cost: string | null; unrealized_change: string | null; estimated_cost: boolean }[];
}
export async function stocksRequest<T>(route: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/v1/stocks/${route}`, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json() as T & { detail?: string; errors?: { message: string }[] };
  if (!response.ok) throw new Error(data.errors?.map((e) => e.message).join("; ") || data.detail || "Nie udało się przetworzyć danych.");
  return data;
}
