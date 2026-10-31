import type { StockQuote } from "./stocksApi";

export interface XtbRecord {
  id: string; kind: "open" | "closed" | "fill" | "cash"; symbol: string;
  asset_type: string; account_number: string; source_id: string; observed_at: string;
  event_at?: string;
}
export interface XtbBook {
  account_number: string; currency: string; records: XtbRecord[];
  open_snapshot_at: string | null; ledger_complete: boolean;
}
export interface XtbPreview {
  book: XtbBook; report_hash: string; sheets: string[]; has_open_section: boolean;
  snapshot_at: string | null; warnings: string[]; closed_count: number; open_count: number;
  fill_count: number; cash_count: number;
}
export interface XtbHolding {
  symbol: string; name: string; asset_type: string; side: string; quantity: string;
  cost: string | null; opened_at: string; status: string;
}
export interface XtbAnalysis {
  holdings: XtbHolding[]; closed_count: number; cash_count: number;
  reported_realized_pnl: string | null; cash_movement: string; currency: string;
  holdings_status: string; warnings: string[];
}
export interface ImportedQuote { symbol: string; quote: StockQuote }
export interface XtbValuation {
  coverage: string;
  positions: { symbol: string; asset_type: string; side: string; quantity: string; currency: string | null; value: string | null;
    cost: string | null; unrealized: string | null; price_date: string | null; status: string }[];
  totals: { currency: string; value: string; cost: string | null; unrealized: string | null }[];
}
export interface XtbMerge { book: XtbBook; duplicates: number; analysis: XtbAnalysis }

export async function xtbRequest<T>(route: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/v1/xtb/${route}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal,
  });
  const data = await response.json() as T & { detail?: string; errors?: { message: string }[] };
  if (!response.ok) throw new Error(data.errors?.map(item => item.message).join("; ") || data.detail || "Nie udało się przetworzyć raportu XTB.");
  return data;
}

export function fileBase64(file: File): Promise<string> {
  if (file.size > 8 * 1024 * 1024) return Promise.reject(new Error("Maksymalny rozmiar raportu to 8 MiB."));
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Nie udało się odczytać pliku."));
    reader.onload = () => typeof reader.result === "string" ? resolve(reader.result.split(",")[1] ?? "") : reject(new Error("Niepoprawny plik."));
    reader.readAsDataURL(file);
  });
}
