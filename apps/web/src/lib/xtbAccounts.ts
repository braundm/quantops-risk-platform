import type { ImportedQuote, XtbBook } from "../data/xtbApi";

export interface XtbAccount {
  id: string; label: string; broker: "xtb"; book: XtbBook; marks: ImportedQuote[];
  imports: { hash: string; at: string; filename: string; records: number }[];
}
export interface XtbAccounts { version: 1; selected: string | null; accounts: XtbAccount[] }
export const xtbKey = (user: string) => `quantops.xtb-books.v1.${user}`;
export const emptyXtbAccounts = (): XtbAccounts => ({ version: 1, selected: null, accounts: [] });

export function readXtbAccounts(raw: string | null): XtbAccounts {
  if (!raw) return emptyXtbAccounts();
  const data = JSON.parse(raw) as XtbAccounts;
  if (data.version !== 1 || !Array.isArray(data.accounts) || data.accounts.length > 50 ||
      !data.accounts.every(account => account && typeof account.id === "string" &&
        typeof account.label === "string" && account.label.length <= 64 && account.broker === "xtb" &&
        account.book && /^\d{1,20}$/.test(account.book.account_number) && typeof account.book.currency === "string" &&
        Array.isArray(account.book.records) && account.book.records.length <= 20000 &&
        Array.isArray(account.marks) && Array.isArray(account.imports)) ||
      new Set(data.accounts.map(account => account.id)).size !== data.accounts.length ||
      new Set(data.accounts.map(account => account.book.account_number)).size !== data.accounts.length ||
      (data.selected !== null && !data.accounts.some(account => account.id === data.selected))) {
    throw new Error("Niepoprawny zapis kont XTB. Pobierz kopię przed odzyskaniem danych.");
  }
  return data;
}

export function downloadXtbBackup(userId: string): void {
  const url = URL.createObjectURL(new Blob([localStorage.getItem(xtbKey(userId)) ?? ""], { type: "application/json" }));
  const link = document.createElement("a"); link.href = url; link.download = "quantops-konta-xtb.json";
  link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
