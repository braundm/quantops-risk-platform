import { describe, expect, it } from "vitest";

import {
  addCategory,
  assignAllToCategory,
  categoryAvailable,
  changeCurrency,
  changeMonth,
  createDefaultBudget,
  readyToAssign,
  removeCategory,
  setIncome,
  sumAssigned,
  updateCategory,
} from "../src/lib/cashBudget";

function firstCategory(budget: ReturnType<typeof createDefaultBudget>) {
  const category = budget.categories[0];
  if (!category) throw new Error("expected default categories");
  return category;
}

describe("cashBudget", () => {
  it("starts with ready-to-assign equal to income", () => {
    const budget = setIncome(createDefaultBudget("PLN", "2026-10"), "5000");
    expect(readyToAssign(budget)).toBe(5000);
    expect(sumAssigned(budget)).toBe(0);
  });

  it("reduces ready-to-assign when categories are funded", () => {
    let budget = setIncome(createDefaultBudget("PLN", "2026-10"), "1000");
    const first = firstCategory(budget);
    budget = updateCategory(budget, first.id, { assigned: "400", activity: "50" });
    expect(readyToAssign(budget)).toBe(600);
    expect(categoryAvailable(firstCategory(budget))).toBe(350);
  });

  it("assigns leftover to a chosen envelope", () => {
    let budget = setIncome(createDefaultBudget("PLN", "2026-10"), "300");
    const target = budget.categories[1];
    if (!target) throw new Error("expected second category");
    budget = updateCategory(budget, target.id, { assigned: "100" });
    budget = assignAllToCategory(budget, target.id);
    expect(readyToAssign(budget)).toBe(0);
    expect(Number(budget.categories.find((c) => c.id === target.id)?.assigned)).toBe(300);
  });

  it("rejects negative amounts and empty category names", () => {
    const budget = createDefaultBudget("EUR");
    expect(() => setIncome(budget, "-1")).toThrow(/nieujemn/);
    expect(() => addCategory(budget, "  ", "needs")).toThrow(/nazw/);
  });

  it("resets activity on month change and money on currency change", () => {
    let budget = setIncome(createDefaultBudget("PLN", "2026-10"), "200");
    const id = firstCategory(budget).id;
    budget = updateCategory(budget, id, { assigned: "80", activity: "20" });
    budget = changeMonth(budget, "2026-11");
    expect(budget.month).toBe("2026-11");
    expect(firstCategory(budget).activity).toBe("0");
    expect(firstCategory(budget).assigned).toBe("80");
    budget = changeCurrency(budget, "USD");
    expect(budget.currency).toBe("USD");
    expect(budget.income).toBe("0");
    expect(firstCategory(budget).assigned).toBe("0");
  });

  it("adds and removes custom envelopes", () => {
    let budget = createDefaultBudget("PLN");
    const before = budget.categories.length;
    budget = addCategory(budget, "Wakacje", "goals");
    expect(budget.categories).toHaveLength(before + 1);
    const extra = budget.categories.find((c) => c.name === "Wakacje");
    expect(extra?.group).toBe("goals");
    if (!extra) throw new Error("expected custom category");
    budget = removeCategory(budget, extra.id);
    expect(budget.categories).toHaveLength(before);
  });
});
