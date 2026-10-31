import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { seedLocalDemoAccounts } from "../src/lib/localDemo";
import { readStockUsers, writeStockUsers } from "../src/lib/stockUsers";
import { readXtbAccounts, xtbKey } from "../src/lib/xtbAccounts";

describe("loopback synthetic demo initialization", () => {
  beforeEach(() => { localStorage.clear(); vi.stubEnv("DEV", true); });
  afterEach(() => { localStorage.clear(); vi.unstubAllEnvs(); });
  it("keeps accounts isolated and preserves user edits across repeated initialization", () => {
    seedLocalDemoAccounts();
    const registry = readStockUsers();
    expect(registry.users).toHaveLength(2);
    const empty = registry.users.find(user => user.credentials?.login === "admin")!;
    const loaded = registry.users.find(user => user.credentials?.login === "admin1")!;
    expect(readXtbAccounts(localStorage.getItem(xtbKey(empty.id))).accounts).toHaveLength(0);
    const accounts = readXtbAccounts(localStorage.getItem(xtbKey(loaded.id)));
    expect(accounts.accounts[0]!.book.records).toHaveLength(122);
    accounts.accounts[0]!.label = "Synthetic owner edit";
    localStorage.setItem(xtbKey(loaded.id), JSON.stringify(accounts));
    seedLocalDemoAccounts();
    expect(readStockUsers().users).toHaveLength(2);
    expect(readXtbAccounts(localStorage.getItem(xtbKey(loaded.id))).accounts[0]!.label).toBe("Synthetic owner edit");
  });
  it("preserves an existing owner who already uses a default login", () => {
    seedLocalDemoAccounts();
    const registry = readStockUsers();
    const existing = registry.users[0]!;
    existing.id = "11111111-1111-4111-8111-111111111111";
    existing.name = "Existing owner";
    delete existing.demo_origin;
    writeStockUsers({ ...registry, users: [existing] });
    seedLocalDemoAccounts();
    expect(readStockUsers().users).toHaveLength(2);
    expect(readStockUsers().users[0]!.name).toBe("Existing owner");
  });
  it("does not initialize public demo credentials in production", () => {
    vi.stubEnv("DEV", false);
    seedLocalDemoAccounts();
    expect(readStockUsers().users).toHaveLength(0);
  });
});
