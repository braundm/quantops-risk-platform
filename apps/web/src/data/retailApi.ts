export interface Holding {
  id: string;
  account: string;
  symbol: string;
  asset_class: "equity" | "etf" | "cash";
  currency: string;
  quantity: string;
  price: string;
  multiplier: string;
  as_of: string;
  source: "synthetic" | "user";
}

export interface Portfolio {
  base_currency: string;
  positions: Holding[];
  fx: Record<string, string>;
  fx_as_of: string;
  fx_source: "synthetic" | "user";
}

export interface AnalysisInput {
  portfolio: Portfolio;
  currency: string;
  fx_shock: string;
  asset_shock: string;
  hedge_ratio: string;
  days: number;
  base_rate: string;
  foreign_rate: string;
  entry_bps: string;
  annual_holding_bps: string;
}

export interface Analysis {
  model_version: string;
  calculated_at: string;
  run_id: string | null;
  base_currency: string;
  source: "synthetic" | "user" | "mixed";
  net_value: string;
  cash_value: string;
  gross_exposure: string;
  net_exposure: string;
  gross_to_equity: string | null;
  concentration: string | null;
  unhedged_impact: string;
  impact_fraction: string | null;
  historical_risk_status: "insufficient_data";
  positions: { id: string; symbol: string; currency: string; value: string; stressed_value: string; impact: string; gross_weight: string | null }[];
  exposures: { currency: string; foreign_amount: string; net_base: string; gross_base: string }[];
  hedges: {
    ratio: string; signed_foreign_notional: string; base_notional: string;
    remaining_foreign_exposure: string; theoretical_forward: string; terminal_spot: string;
    payoff: string; entry_cost: string; holding_cost: string; net_payoff: string;
    portfolio_impact: string; terminal_value: string; overhedged_after_shock: boolean;
  }[];
  warnings: string[];
}

export interface CsvPreview {
  positions: Holding[];
  errors: { row: number; message: string }[];
  importable: boolean;
  import_kind: "current_positions";
}

export async function retailRequest<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/v1/retail/${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    let detail: string;
    try {
      const problem = await response.json() as { detail?: string | { msg?: string }[]; errors?: { location: string[]; message: string }[]; title?: string };
      detail = problem.errors?.map((issue) => `${issue.location.join(".")}: ${issue.message}`).join("; ")
        ?? (typeof problem.detail === "string" ? problem.detail : undefined)
        ?? problem.title
        ?? "";
    } catch {
      detail = "";
    }
    if (response.status === 404) {
      throw new Error(
        "API nie zna endpointu quizu (404). Zrestartuj serwer API z aktualnym kodem: "
        + "python -m uvicorn quantops_api.main:app --host 127.0.0.1 --port 8000 --reload",
      );
    }
    throw new Error(detail || `Nie udało się wykonać obliczeń (HTTP ${response.status}).`);
  }
  return await response.json() as T;
}

export const csvExample = `account,symbol,asset_class,currency,quantity,price,multiplier,as_of,source
Demo,QGLOBAL,etf,USD,100,100,1,2026-01-02T16:00:00Z,synthetic
Demo,QEURO,equity,EUR,100,50,1,2026-01-02T16:00:00Z,synthetic
Demo,QPOL,equity,PLN,100,100,1,2026-01-02T16:00:00Z,synthetic
Demo,CASH-PLN,cash,PLN,10000,1,1,2026-01-02T16:00:00Z,synthetic
`;
