import type { CashBudget } from "./cashBudget";

/** Validate the non-financial presentation budget before displaying imported browser state. */
export function validInvestorBudget(value: unknown): value is CashBudget {
  if (typeof value !== "object" || value === null) return false;
  const row = value as Record<string, unknown>;
  const amount = (n: unknown) => typeof n === "string" && n.trim() !== "" && Number.isFinite(Number(n)) && Number(n) >= 0;
  if (row.version !== 1 || row.currency !== "PLN" || typeof row.month !== "string" || !/^\d{4}-(0[1-9]|1[0-2])$/.test(row.month) || !amount(row.income) || !Array.isArray(row.categories) || row.categories.length > 200) return false;
  const ids = new Set<string>();
  return row.categories.every((value: unknown) => {
    if (typeof value !== "object" || value === null) return false;
    const item = value as Record<string, unknown>;
    if (typeof item.id !== "string" || ids.has(item.id) || typeof item.name !== "string" || item.name.length > 200 || !["needs", "wants", "true_expenses", "goals"].includes(String(item.group)) || !amount(item.assigned) || !amount(item.activity)) return false;
    ids.add(item.id); return true;
  });
}
