import { useState, type FormEvent } from "react";

interface RetailLoginProps {
  readonly onLogin: (displayName: string) => void;
}

export function RetailLogin({ onLogin }: RetailLoginProps) {
  const [name, setName] = useState("");
  const [error, setError] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    try {
      onLogin(name);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Nie udało się zalogować.");
    }
  }

  return (
    <div className="qo-gate">
      <a className="skip-link" href="#login-form">Przejdź do logowania</a>
      <div className="qo-gate-card">
        <p className="qo-eyebrow">QUANTOPS · PRZESTRZEŃ OSOBISTA</p>
        <h1>Zaloguj się lokalnie</h1>
        <p>
          Sesja pozostaje w tej przeglądarce. Nie ma konta serwerowego ani połączenia z brokerem.
          Po zalogowaniu najpierw wypełnisz ankietę ryzyka albo wybierzesz ustawienia domyślne z pełnym dostępem.
        </p>
        {error ? <p className="qo-alert qo-error" role="alert">{error}</p> : null}
        <form id="login-form" className="qo-gate-form" onSubmit={submit}>
          <label className="qo-field">
            Nazwa użytkownika
            <input
              autoComplete="username"
              autoFocus
              maxLength={64}
              required
              value={name}
              onChange={(event) => { setName(event.target.value); setError(""); }}
              placeholder="np. Anna"
            />
          </label>
          <button className="qo-button qo-primary" type="submit">Zaloguj i przejdź do ankiety →</button>
        </form>
        <p className="qo-note">
          To lokalna etykieta sesji, nie weryfikacja tożsamości. Na współdzielonym komputerze używaj
          „Wyloguj” i „Usuń moje dane” po zakończeniu pracy.
        </p>
        <a className="qo-gate-link" href="/research">Środowisko badawcze (bez logowania) →</a>
      </div>
    </div>
  );
}
