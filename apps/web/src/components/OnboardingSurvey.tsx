import { useState, type FormEvent } from "react";

import { DEFAULT_ONBOARDING, type OnboardingAnswers } from "../lib/retailSession";

interface OnboardingSurveyProps {
  readonly displayName: string;
  readonly onComplete: (answers: OnboardingAnswers, mode: "survey" | "defaults") => void;
  readonly onLogout: () => void;
}

export function OnboardingSurvey({ displayName, onComplete, onLogout }: OnboardingSurveyProps) {
  const [goal, setGoal] = useState("");
  const [months, setMonths] = useState("60");
  const [lossPercent, setLossPercent] = useState("10");
  const [lossAmount, setLossAmount] = useState("0");
  const [capacity, setCapacity] = useState("0");
  const [limit, setLimit] = useState("40");
  const [experience, setExperience] = useState<OnboardingAnswers["experienceLevel"]>("none");
  const [leverage, setLeverage] = useState(false);
  const [margin, setMargin] = useState(false);
  const [error, setError] = useState("");

  function answersFromForm(): OnboardingAnswers {
    const horizonMonths = Number(months);
    const concentrationLimitPercent = Number(limit);
    const loss = Number(lossPercent);
    if (![horizonMonths, concentrationLimitPercent, loss].every(Number.isFinite)) {
      throw new Error("Uzupełnij poprawne wartości liczbowe.");
    }
    if (horizonMonths < 1 || horizonMonths > 1200) throw new Error("Horyzont musi być od 1 do 1200 miesięcy.");
    if (loss < 0 || loss > 100 || concentrationLimitPercent < 0 || concentrationLimitPercent > 100) {
      throw new Error("Procenty muszą być w zakresie 0–100.");
    }
    return {
      goal: goal.trim() || "Cel niepodany",
      horizonMonths,
      lossPercent: loss,
      lossAmount,
      lossCapacity: capacity,
      concentrationLimitPercent,
      experienceLevel: experience,
      understandsLeverage: leverage,
      understandsMargin: margin,
    };
  }

  function submitSurvey(event: FormEvent) {
    event.preventDefault();
    try {
      setError("");
      onComplete(answersFromForm(), "survey");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Nie udało się zapisać ankiety.");
    }
  }

  function applyDefaults() {
    setError("");
    onComplete(DEFAULT_ONBOARDING, "defaults");
  }

  return (
    <div className="qo-gate qo-onboarding">
      <a className="skip-link" href="#onboarding-form">Przejdź do ankiety</a>
      <div className="qo-gate-card qo-gate-wide">
        <div className="qo-gate-top">
          <div>
            <p className="qo-eyebrow">WITAJ, {displayName.toUpperCase()}</p>
            <h1>Ankieta ryzyka — pierwszy krok</h1>
          </div>
          <button className="qo-button" type="button" onClick={onLogout}>Wyloguj</button>
        </div>
        <p>
          Zanim otworzysz portfel, określ cele i granice albo użyj ustawień domyślnych z pełnym dostępem
          do wszystkich opcji. Ankieta nie jest badaniem MiFID i nie stanowi rekomendacji inwestycyjnej.
        </p>

        <div className="qo-defaults-banner">
          <div>
            <strong>Ustawienia domyślne · pełny dostęp</strong>
            <p>
              Odblokowuje wszystkie panele od razu: pozycje, ryzyko historyczne, scenariusze, zabezpieczenia,
              koszty, laboratorium i pełną ankietę w profilu. Limit koncentracji = 100%. To tryb eksploracji,
              nie profil inwestycyjny.
            </p>
          </div>
          <button className="qo-button qo-primary" type="button" onClick={applyDefaults}>
            Ustawienia domyślne — pełny dostęp
          </button>
        </div>

        <hr className="qo-gate-divider" />
        <h2>Albo wypełnij krótką ankietę ryzyka</h2>
        {error ? <p className="qo-alert qo-error" role="alert">{error}</p> : null}
        <form id="onboarding-form" onSubmit={submitSurvey}>
          <label className="qo-field">
            Cel inwestowania
            <input maxLength={300} required value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="np. rezerwa na przyszłe wydatki" />
          </label>
          <div className="qo-form-grid qo-profile-fields">
            <label className="qo-field">Horyzont (miesiące)<input type="number" required min={1} max={1200} step="1" value={months} onChange={(e) => setMonths(e.target.value)} /></label>
            <label className="qo-field">Tolerowana strata (%)<input type="number" required min={0} max={100} step="any" value={lossPercent} onChange={(e) => setLossPercent(e.target.value)} /></label>
            <label className="qo-field">Tolerowana strata w pieniądzu<input type="number" required min={0} step="any" value={lossAmount} onChange={(e) => setLossAmount(e.target.value)} /></label>
            <label className="qo-field">Finansowa zdolność do poniesienia straty<input type="number" required min={0} step="any" value={capacity} onChange={(e) => setCapacity(e.target.value)} /></label>
            <label className="qo-field">Mój limit koncentracji (%)<input type="number" required min={0} max={100} step="any" value={limit} onChange={(e) => setLimit(e.target.value)} /></label>
            <label className="qo-field">Doświadczenie rynkowe
              <select value={experience} onChange={(e) => setExperience(e.target.value as OnboardingAnswers["experienceLevel"])}>
                <option value="none">Brak</option>
                <option value="basic">Podstawowe</option>
                <option value="experienced">Praktyczne</option>
              </select>
            </label>
          </div>
          <div className="qo-profile-checks">
            <label className="qo-checkbox"><input type="checkbox" checked={leverage} onChange={(e) => setLeverage(e.target.checked)} /> Rozumiem wpływ dźwigni</label>
            <label className="qo-checkbox"><input type="checkbox" checked={margin} onChange={(e) => setMargin(e.target.checked)} /> Rozumiem depozyt i możliwe dopłaty</label>
          </div>
          <button className="qo-button qo-primary" type="submit">Zapisz ankietę i otwórz portfel →</button>
        </form>
        <p className="qo-note">
          Pełną ankietę (przepływy, rezerwa płynności, doświadczenie per klasa, ograniczenia) uzupełnisz później w sekcji „Moje cele i limity”.
        </p>
      </div>
    </div>
  );
}
