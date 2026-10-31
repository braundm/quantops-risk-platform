/** Local-only retail session. Not hosted authentication or multi-user persistence. */

export const SESSION_KEY = "quantops.local-session.v1";

export type AccessMode = "survey" | "defaults";

export interface OnboardingAnswers {
  readonly goal: string;
  readonly horizonMonths: number;
  readonly lossPercent: number;
  readonly lossAmount: string;
  readonly lossCapacity: string;
  readonly concentrationLimitPercent: number;
  readonly experienceLevel: "none" | "basic" | "experienced";
  readonly understandsLeverage: boolean;
  readonly understandsMargin: boolean;
}

export interface RetailSession {
  readonly version: 1;
  readonly userId: string;
  readonly displayName: string;
  readonly loggedInAt: string;
  readonly onboardingComplete: boolean;
  readonly accessMode: AccessMode | null;
  readonly concentrationLimit: number;
  readonly onboarding: OnboardingAnswers | null;
}

/** Exploratory defaults unlock every retail panel without claiming suitability. */
export const DEFAULT_ONBOARDING: OnboardingAnswers = {
  goal: "Eksploracja funkcji platformy (ustawienia domyślne)",
  horizonMonths: 60,
  lossPercent: 25,
  lossAmount: "0",
  lossCapacity: "0",
  concentrationLimitPercent: 100,
  experienceLevel: "basic",
  understandsLeverage: true,
  understandsMargin: true,
};

export function createSession(displayName: string): RetailSession {
  const name = displayName.trim().slice(0, 64);
  if (!name) throw new Error("Podaj nazwę użytkownika.");
  return {
    version: 1,
    userId: crypto.randomUUID(),
    displayName: name,
    loggedInAt: new Date().toISOString(),
    onboardingComplete: false,
    accessMode: null,
    concentrationLimit: 0.4,
    onboarding: null,
  };
}

export function completeOnboarding(
  session: RetailSession,
  answers: OnboardingAnswers,
  accessMode: AccessMode,
): RetailSession {
  return {
    ...session,
    onboardingComplete: true,
    accessMode,
    concentrationLimit: answers.concentrationLimitPercent / 100,
    onboarding: answers,
  };
}

export function readSession(): RetailSession | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as RetailSession;
    if (parsed.version !== 1 || typeof parsed.displayName !== "string" || !parsed.displayName.trim()) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function writeSession(session: RetailSession): void {
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  localStorage.removeItem(SESSION_KEY);
}
