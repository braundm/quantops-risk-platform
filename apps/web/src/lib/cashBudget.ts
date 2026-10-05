/** Local zero-based cash budget (YNAB-style envelopes). Not investment advice. */

export const CASH_BUDGET_KEY = "quantops.cash-budget.v1";

export type BudgetGroup = "needs" | "wants" | "true_expenses" | "goals";

export interface BudgetCategory {
  readonly id: string;
  readonly name: string;
  readonly group: BudgetGroup;
  /** Amount assigned this month (string decimal). */
  readonly assigned: string;
  /** Spent / activity this month (string decimal, non-negative). */
  readonly activity: string;
}

export interface CashBudget {
  readonly version: 1;
  readonly month: string;
  readonly currency: string;
  /** Income / money available to assign this month. */
  readonly income: string;
  readonly categories: readonly BudgetCategory[];
}

export const GROUP_LABELS: Record<BudgetGroup, string> = {
  needs: "Potrzeby",
  wants: "Chęci",
  true_expenses: "Prawdziwe wydatki",
  goals: "Cele i bufor",
};

const DEFAULT_CATEGORIES: ReadonlyArray<Omit<BudgetCategory, "id" | "assigned" | "activity">> = [
  { name: "Mieszkanie / czynsz", group: "needs" },
  { name: "Żywność", group: "needs" },
  { name: "Transport", group: "needs" },
  { name: "Rozrywka", group: "wants" },
  { name: "Subskrypcje", group: "wants" },
  { name: "Samochód / serwis", group: "true_expenses" },
  { name: "Prezenty / święta", group: "true_expenses" },
  { name: "Poduszka bezpieczeństwa", group: "goals" },
  { name: "Inwestycje / oszczędności", group: "goals" },
];

function moneyNumber(value: string): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : NaN;
}

export function currentBudgetMonth(now = new Date()): string {
  const year = now.getUTCFullYear();
  const month = String(now.getUTCMonth() + 1).padStart(2, "0");
  return `${year}-${month}`;
}

export function createDefaultBudget(currency: string, month = currentBudgetMonth()): CashBudget {
  return {
    version: 1,
    month,
    currency: currency.trim().toUpperCase() || "PLN",
    income: "0",
    categories: DEFAULT_CATEGORIES.map((category) => ({
      ...category,
      id: crypto.randomUUID(),
      assigned: "0",
      activity: "0",
    })),
  };
}

export function parseAmount(value: string): number {
  const n = moneyNumber(value);
  if (!Number.isFinite(n) || n < 0) throw new Error("Kwota musi być liczbą nieujemną.");
  return n;
}

export function sumAssigned(budget: CashBudget): number {
  return budget.categories.reduce((sum, category) => sum + parseAmount(category.assigned), 0);
}

export function sumActivity(budget: CashBudget): number {
  return budget.categories.reduce((sum, category) => sum + parseAmount(category.activity), 0);
}

/** Ready to Assign: income minus all assigned amounts. */
export function readyToAssign(budget: CashBudget): number {
  return parseAmount(budget.income) - sumAssigned(budget);
}

/** Available in envelope: assigned minus activity. */
export function categoryAvailable(category: BudgetCategory): number {
  return parseAmount(category.assigned) - parseAmount(category.activity);
}

export function setIncome(budget: CashBudget, income: string): CashBudget {
  parseAmount(income);
  return { ...budget, income };
}

export function updateCategory(
  budget: CashBudget,
  id: string,
  patch: Partial<Pick<BudgetCategory, "name" | "assigned" | "activity">>,
): CashBudget {
  if (patch.assigned !== undefined) parseAmount(patch.assigned);
  if (patch.activity !== undefined) parseAmount(patch.activity);
  const name = patch.name?.trim();
  if (patch.name !== undefined && !name) throw new Error("Nazwa kategorii nie może być pusta.");
  return {
    ...budget,
    categories: budget.categories.map((category) =>
      category.id === id
        ? {
            ...category,
            ...(patch.assigned !== undefined ? { assigned: patch.assigned } : {}),
            ...(patch.activity !== undefined ? { activity: patch.activity } : {}),
            ...(name !== undefined ? { name } : {}),
          }
        : category,
    ),
  };
}

export function addCategory(
  budget: CashBudget,
  name: string,
  group: BudgetGroup,
): CashBudget {
  const trimmed = name.trim();
  if (!trimmed) throw new Error("Podaj nazwę kategorii.");
  if (budget.categories.length >= 40) throw new Error("Limit 40 kategorii.");
  return {
    ...budget,
    categories: [
      ...budget.categories,
      { id: crypto.randomUUID(), name: trimmed.slice(0, 80), group, assigned: "0", activity: "0" },
    ],
  };
}

export function removeCategory(budget: CashBudget, id: string): CashBudget {
  return { ...budget, categories: budget.categories.filter((category) => category.id !== id) };
}

/** Assign all remaining Ready-to-Assign into one category (or leave unchanged if zero). */
export function assignAllToCategory(budget: CashBudget, id: string): CashBudget {
  const leftover = readyToAssign(budget);
  if (leftover <= 0) return budget;
  const target = budget.categories.find((category) => category.id === id);
  if (!target) throw new Error("Nie znaleziono kategorii.");
  const nextAssigned = parseAmount(target.assigned) + leftover;
  return updateCategory(budget, id, { assigned: String(nextAssigned) });
}

export function changeMonth(budget: CashBudget, month: string): CashBudget {
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(month)) throw new Error("Miesiąc musi mieć format RRRR-MM.");
  return {
    ...budget,
    month,
    // New month: keep category structure, reset activity; keep assigned as starting plan.
    categories: budget.categories.map((category) => ({ ...category, activity: "0" })),
  };
}

export function changeCurrency(budget: CashBudget, currency: string): CashBudget {
  const next = currency.trim().toUpperCase();
  if (!/^[A-Z]{3}$/.test(next)) throw new Error("Waluta musi być kodem ISO (3 litery).");
  // Clear money amounts when currency changes — do not silently convert.
  return {
    ...budget,
    currency: next,
    income: "0",
    categories: budget.categories.map((category) => ({ ...category, assigned: "0", activity: "0" })),
  };
}

function isBudgetCategory(value: unknown): value is BudgetCategory {
  if (typeof value !== "object" || value === null) return false;
  const row = value as Record<string, unknown>;
  return (
    typeof row.id === "string"
    && typeof row.name === "string"
    && typeof row.group === "string"
    && typeof row.assigned === "string"
    && typeof row.activity === "string"
  );
}

export function readCashBudget(userId: string): CashBudget | null {
  try {
    const raw = localStorage.getItem(`${CASH_BUDGET_KEY}.${userId}`);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return null;
    const row = parsed as Record<string, unknown>;
    if (row.version !== 1 || typeof row.month !== "string" || typeof row.currency !== "string" || typeof row.income !== "string") {
      return null;
    }
    if (!Array.isArray(row.categories) || !row.categories.every(isBudgetCategory)) return null;
    parseAmount(row.income);
    for (const category of row.categories) {
      parseAmount(category.assigned);
      parseAmount(category.activity);
    }
    return {
      version: 1,
      month: row.month,
      currency: row.currency,
      income: row.income,
      categories: row.categories,
    };
  } catch {
    return null;
  }
}

export function writeCashBudget(userId: string, budget: CashBudget): void {
  localStorage.setItem(`${CASH_BUDGET_KEY}.${userId}`, JSON.stringify(budget));
}

export function clearCashBudget(userId: string): void {
  localStorage.removeItem(`${CASH_BUDGET_KEY}.${userId}`);
}
