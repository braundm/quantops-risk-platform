import type { StockUser } from "./stockUsers";

const SESSION_KEY = "quantops.local-session.v1";
const ITERATIONS = 600000;
const hex = (bytes: Uint8Array) => Array.from(bytes, value => value.toString(16).padStart(2, "0")).join("");
export const normalizeLogin = (login: string) => login.trim().toLowerCase();

async function derive(password: string, salt: string): Promise<string> {
  const saltBytes = Uint8Array.from(salt.match(/.{2}/g) ?? [], value => parseInt(value, 16));
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(password), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits({ name: "PBKDF2", salt: saltBytes, iterations: ITERATIONS, hash: "SHA-256" }, key, 256);
  return hex(new Uint8Array(bits));
}

/** A local UI lock, not server authentication or encryption of portfolio storage. */
export async function createCredentials(login: string, password: string): Promise<NonNullable<StockUser["credentials"]>> {
  const normalized = normalizeLogin(login);
  if (!/^[a-z0-9._-]{3,40}$/.test(normalized)) throw new Error("Login: 3–40 znaków, litery bez polskich znaków, cyfry, kropka, myślnik lub podkreślenie.");
  if (password.length < 10 || password.length > 128) throw new Error("Hasło musi mieć od 10 do 128 znaków.");
  const salt = hex(crypto.getRandomValues(new Uint8Array(16)));
  return { login: normalized, salt, digest: await derive(password, salt), iterations: ITERATIONS };
}

export async function verifyCredentials(user: StockUser, password: string): Promise<boolean> {
  if (!user.credentials || password.length > 128) return false;
  const candidate = await derive(password, user.credentials.salt);
  let mismatch = 0;
  for (let index = 0; index < candidate.length; index++) mismatch |= candidate.charCodeAt(index) ^ user.credentials.digest.charCodeAt(index);
  return mismatch === 0;
}
export function localSession(): string | null { return sessionStorage.getItem(SESSION_KEY); }
export function startLocalSession(id: string): void { sessionStorage.setItem(SESSION_KEY, id); }
export function endLocalSession(): void { sessionStorage.removeItem(SESSION_KEY); }
