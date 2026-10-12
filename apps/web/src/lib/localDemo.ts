import seed from "../data/localDemo.json";
import { readStockUsers, writeStockUsers, type StockUser } from "./stockUsers";
import { readXtbAccounts, xtbKey } from "./xtbAccounts";

/** Public synthetic credentials for the owner's loopback development workspace only. */
export function seedLocalDemoAccounts(): void {
  if (!import.meta.env.DEV || !["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname)) return;
  if (seed.synthetic !== true) throw new Error("Demo musi zawierać wyłącznie oznaczone dane syntetyczne.");
  const registry = readStockUsers();
  const users = [...registry.users];
  for (const profile of seed.profiles) {
    // Existing logins and IDs belong to their current owner: never reset them on reload.
    if (users.some(user => user.id === profile.id || user.credentials?.login === profile.credentials.login)) continue;
    if (users.length >= 12) continue;
    const user: StockUser = {
      ...profile, demo_origin: profile.demo_origin === "empty" ? "empty" : "uploaded_workbook",
      created_at: new Date().toISOString(), answers: null, profile: null, positions: [],
      survey_status: "skipped", brokers: ["xtb"],
    };
    const key = xtbKey(user.id);
    if (user.demo_origin === "uploaded_workbook" && localStorage.getItem(key) === null) {
      const raw = JSON.stringify(seed.accounts);
      readXtbAccounts(raw);
      localStorage.setItem(key, raw);
    }
    users.push(user);
  }
  if (users.length !== registry.users.length) writeStockUsers({ ...registry, users });
}
