import type { OwnedStock, ProfileAnswers, ProfileResult } from "../data/stocksApi";

export const STOCK_USERS_KEY = "quantops.stock-users.v1";
export interface StockUser {
  id: string; name: string; created_at: string;
  answers: ProfileAnswers | null; profile: ProfileResult | null; positions: OwnedStock[];
  credentials?: { login: string; salt: string; digest: string; iterations: number };
  survey_status?: "pending" | "skipped" | "completed";
  brokers?: ("xtb" | "bossa")[];
  demo_origin?: "empty" | "uploaded_workbook";
}
export interface StockUsers { version: 1; active_id: string | null; users: StockUser[] }
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Storage is presentation state, not authentication. Position values are revalidated by the API. */
export function readStockUsers(): StockUsers {
  const raw = localStorage.getItem(STOCK_USERS_KEY);
  if (!raw) return { version: 1, active_id: null, users: [] };
  const data = JSON.parse(raw) as StockUsers;
  if (data.version !== 1 || !Array.isArray(data.users) || data.users.length > 12 ||
      !data.users.every((u) => u && typeof u.id === "string" && uuid.test(u.id) &&
        typeof u.name === "string" && u.name.trim().length > 0 && u.name.length <= 64 &&
        Array.isArray(u.positions) && u.positions.length <= 100 &&
        (!u.credentials || (typeof u.credentials.login === "string" &&
          /^[a-z0-9._-]{3,40}$/.test(u.credentials.login) &&
          /^[a-f0-9]{32}$/.test(u.credentials.salt) && /^[a-f0-9]{64}$/.test(u.credentials.digest) &&
          u.credentials.iterations === 600000)) &&
        (!u.brokers || (Array.isArray(u.brokers) && u.brokers.length <= 2 &&
          new Set(u.brokers).size === u.brokers.length && u.brokers.every(b => b === "xtb" || b === "bossa"))) &&
        (!u.survey_status || ["pending", "skipped", "completed"].includes(u.survey_status)) &&
        (!u.demo_origin || ["empty", "uploaded_workbook"].includes(u.demo_origin))) ||
      new Set(data.users.map((u) => u.id)).size !== data.users.length ||
      new Set(data.users.filter(u => u.credentials).map(u => u.credentials?.login)).size !== data.users.filter(u => u.credentials).length ||
      (data.active_id !== null && !data.users.some((u) => u.id === data.active_id))) {
    throw new Error("Zapis profili jest niepoprawny. Pobierz kopię danych przed wyczyszczeniem zapisu.");
  }
  return data;
}

export function writeStockUsers(data: StockUsers): void {
  localStorage.setItem(STOCK_USERS_KEY, JSON.stringify(data));
}
