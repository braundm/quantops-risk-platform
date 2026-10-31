import { useState, type FormEvent } from "react";

import {
  GROUP_LABELS,
  addCategory,
  assignAllToCategory,
  categoryAvailable,
  changeMonth,
  readyToAssign,
  removeCategory,
  setIncome,
  sumActivity,
  sumAssigned,
  updateCategory,
  type BudgetGroup,
  type CashBudget,
} from "../lib/cashBudget";

const money = (value: number | string, currency: string) =>
  new Intl.NumberFormat("pl-PL", { style: "currency", currency, maximumFractionDigits: 2 }).format(Number(value));

const GROUPS: BudgetGroup[] = ["needs", "wants", "true_expenses", "goals"];

interface CashBudgetPanelProps {
  readonly currency: string;
  readonly portfolioCash: string | null;
  readonly budget: CashBudget;
  readonly onChange: (next: CashBudget) => void;
}

export function CashBudgetPanel({ currency, portfolioCash, budget, onChange }: CashBudgetPanelProps) {
  const [name, setName] = useState("");
  const [group, setGroup] = useState<BudgetGroup>("needs");
  const [error, setError] = useState("");

  function apply(mutator: () => CashBudget) {
    try {
      setError("");
      onChange(mutator());
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Nie udało się zaktualizować budżetu.");
    }
  }

  function addEnvelope(event: FormEvent) {
    event.preventDefault();
    apply(() => {
      const next = addCategory(budget, name, group);
      setName("");
      return next;
    });
  }

  function importCash() {
    if (portfolioCash === null) return;
    apply(() => setIncome(budget, portfolioCash));
  }

  const leftover = readyToAssign(budget);
  const leftoverClass = leftover > 0.005 ? "positive" : leftover < -0.005 ? "negative" : "zero";

  return (
    <section className="qo-panel qo-cash-budget" id="budget">
      <div className="qo-panel-heading">
        <div>
          <p className="qo-eyebrow">KAŻDA ZŁOTÓWKA MA ZADANIE</p>
          <h2>Budżet gotówki · koperty</h2>
        </div>
        <span className="qo-tag">Styl YNAB · lokalnie</span>
      </div>
      <p className="qo-muted">
        Zero-based budgeting: najpierw ustal dochód miesiąca, potem przypisz kwoty do kopert.
        „Do dyspozycji” powinno dążyć do zera. To plan płynności osobistej — nie rekomendacja
        inwestycyjna i nie powiązanie z brokerem.
      </p>

      {error ? <p className="qo-alert qo-error" role="alert">{error}</p> : null}

      <div className="qo-budget-ready" data-state={leftoverClass} aria-live="polite">
        <div>
          <span>Do dyspozycji</span>
          <strong>{money(leftover, currency)}</strong>
          <small>
            {leftover > 0.005
              ? "Przypisz pozostałą kwotę do kopert."
              : leftover < -0.005
                ? "Przypisano więcej niż dochód — skoryguj koperty."
                : "Każda złotówka ma zadanie."}
          </small>
        </div>
        <dl>
          <div><dt>Dochód miesiąca</dt><dd>{money(budget.income, currency)}</dd></div>
          <div><dt>Przypisano</dt><dd>{money(sumAssigned(budget), currency)}</dd></div>
          <div><dt>Wydatki (aktywność)</dt><dd>{money(sumActivity(budget), currency)}</dd></div>
        </dl>
      </div>

      <div className="qo-budget-controls">
        <label className="qo-field">
          Miesiąc budżetu
          <input
            type="month"
            value={budget.month}
            onChange={(event) => apply(() => changeMonth(budget, event.target.value))}
          />
        </label>
        <label className="qo-field">
          Dochód / środki do przypisania ({currency})
          <input
            type="number"
            min={0}
            step="0.01"
            value={budget.income}
            onChange={(event) => apply(() => setIncome(budget, event.target.value || "0"))}
          />
        </label>
        <button
          className="qo-button"
          type="button"
          disabled={portfolioCash === null || Number(portfolioCash) < 0}
          onClick={importCash}
          title="Wstaw gotówkę netto z wyceny portfela jako dochód miesiąca"
        >
          Użyj gotówki z portfela
        </button>
      </div>

      <div className="qo-budget-table-wrap">
        <table className="qo-budget-table">
          <thead>
            <tr>
              <th scope="col">Kategoria</th>
              <th scope="col">Przypisano</th>
              <th scope="col">Wydano</th>
              <th scope="col">Dostępne</th>
              <th scope="col"><span className="visually-hidden">Akcje</span></th>
            </tr>
          </thead>
          {GROUPS.map((groupKey) => {
            const rows = budget.categories.filter((category) => category.group === groupKey);
            if (!rows.length) return null;
            return (
              <tbody key={groupKey}>
                <tr className="qo-budget-group">
                  <th scope="rowgroup" colSpan={5}>{GROUP_LABELS[groupKey]}</th>
                </tr>
                {rows.map((category) => {
                  const available = categoryAvailable(category);
                  return (
                    <tr key={category.id}>
                      <td>{category.name}</td>
                      <td>
                        <input
                          aria-label={`Przypisano: ${category.name}`}
                          type="number"
                          min={0}
                          step="0.01"
                          value={category.assigned}
                          onChange={(event) =>
                            apply(() => updateCategory(budget, category.id, { assigned: event.target.value || "0" }))
                          }
                        />
                      </td>
                      <td>
                        <input
                          aria-label={`Wydano: ${category.name}`}
                          type="number"
                          min={0}
                          step="0.01"
                          value={category.activity}
                          onChange={(event) =>
                            apply(() => updateCategory(budget, category.id, { activity: event.target.value || "0" }))
                          }
                        />
                      </td>
                      <td>
                        <strong className={available < -0.005 ? "qo-budget-over" : undefined}>
                          {money(available, currency)}
                        </strong>
                      </td>
                      <td className="qo-budget-row-actions">
                        <button
                          className="qo-text-button"
                          type="button"
                          disabled={leftover <= 0}
                          onClick={() => apply(() => assignAllToCategory(budget, category.id))}
                        >
                          Przypisz resztę
                        </button>
                        <button
                          className="qo-text-button"
                          type="button"
                          aria-label={`Usuń kategorię ${category.name}`}
                          onClick={() => apply(() => removeCategory(budget, category.id))}
                        >
                          Usuń
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            );
          })}
        </table>
      </div>

      <form className="qo-budget-add" onSubmit={addEnvelope}>
        <label className="qo-field">
          Nowa koperta
          <input maxLength={80} required value={name} onChange={(event) => setName(event.target.value)} placeholder="np. Wakacje" />
        </label>
        <label className="qo-field">
          Grupa
          <select value={group} onChange={(event) => setGroup(event.target.value as BudgetGroup)}>
            {GROUPS.map((key) => <option key={key} value={key}>{GROUP_LABELS[key]}</option>)}
          </select>
        </label>
        <button className="qo-button qo-primary" type="submit">Dodaj kategorię</button>
      </form>

      <p className="qo-note">
        Zasady w stylu YNAB: (1) każda złotówka ma zadanie, (2) planuj prawdziwe wydatki z wyprzedzeniem,
        (3) gdy przekroczysz kopertę — przenieś z innej, (4) im dłużej pieniądze „dojrzewają”, tym spokojniejszy budżet.
        Zmiana waluty bazowej portfela resetuje kwoty budżetu. Dane zapisują się lokalnie w tej przeglądarce.
      </p>
    </section>
  );
}
