import { useState, type FormEvent } from "react";
import { createCredentials, normalizeLogin, verifyCredentials } from "../lib/localLogin";
import type { StockUser } from "../lib/stockUsers";

export function LocalLogin({ users, onRegister, onLogin }: {
  users: StockUser[]; onRegister: (name: string, credentials: NonNullable<StockUser["credentials"]>, legacyId: string) => void;
  onLogin: (id: string) => void;
}) {
  const [mode, setMode] = useState<"login" | "register">(users.some(user => user.credentials) ? "login" : "register");
  const [name, setName] = useState("");
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [legacy, setLegacy] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setBusy(true);
    try {
      if (mode === "register") {
        if (!name.trim()) throw new Error("Podaj nazwę wyświetlaną.");
        if (users.some(user => user.credentials?.login === normalizeLogin(login))) throw new Error("Ten login jest już zajęty w tej przeglądarce.");
        if (password !== repeat) throw new Error("Hasła muszą być takie same.");
        onRegister(name.trim(), await createCredentials(login, password), legacy);
      } else {
        const user = users.find(item => item.credentials?.login === normalizeLogin(login));
        if (!user || !await verifyCredentials(user, password)) throw new Error("Nieprawidłowy login lub hasło.");
        onLogin(user.id);
      }
      setPassword(""); setRepeat("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Nie można otworzyć konta."); }
    finally { setBusy(false); }
  }
  return <div className="qo-auth-layout">
    <section className="qo-auth-story"><a className="qo-wordmark" href="/">Q<span>QuantOps</span></a><div><span className="qo-kicker">TWÓJ PORTFEL. PEŁNIEJSZY OBRAZ.</span><h1>Wszystkie konta.<br />Jedno miejsce.</h1><p>Wczytaj raporty, uporządkuj pozycje i sprawdź, na jakich danych opiera się wycena.</p><ol><li><b>01</b><span>Utwórz swoje konto<small>Login i hasło do lokalnego profilu</small></span></li><li><b>02</b><span>Wybierz brokerów<small>Osobne rachunki i waluty</small></span></li><li><b>03</b><span>Wczytaj raport<small>CSV, XLSX lub ZIP z XTB</small></span></li></ol></div><p className="qo-story-foot">Badanie ryzyka portfela · bez składania zleceń</p></section>
    <section className="qo-auth-form" aria-label="Dostęp do konta"><div className="qo-auth-card"><p className="qo-kicker">ZACZNIJ OD SWOJEGO KONTA</p><h2>{mode === "register" ? "Utwórz konto" : "Witaj ponownie"}</h2><p>{mode === "register" ? "Ankietę możesz pominąć. Do importu przejdziesz w kilku krokach." : "Zaloguj się, aby wrócić do kont i raportów."}</p><div className="qo-segment" role="group" aria-label="Logowanie lub rejestracja"><button aria-pressed={mode === "login"} disabled={busy} onClick={() => { setMode("login"); setError(""); }}>Zaloguj się</button><button aria-pressed={mode === "register"} disabled={busy} onClick={() => { setMode("register"); setError(""); }}>Załóż konto</button></div>
      {error ? <p className="iv-alert iv-error" role="alert">{error}</p> : null}
      {users.some(user => user.demo_origin) ? <aside className="qo-demo-access" aria-label="Lokalne konta testowe"><b>Konta testowe</b>{users.some(user => user.demo_origin === "empty" && user.credentials?.login === "admin") ? <p><code>admin / admin</code><span>Pusty portfel</span></p> : null}{users.some(user => user.demo_origin === "uploaded_workbook" && user.credentials?.login === "admin1") ? <p><code>admin1 / admin1</code><span>Wczytany arkusz · SYNTHETIC</span></p> : null}</aside> : null}
      <form onSubmit={event => void submit(event)}><fieldset disabled={busy}>
        {mode === "register" ? <label>Nazwa wyświetlana<input required maxLength={64} autoComplete="nickname" value={name} onChange={event => setName(event.target.value)} placeholder="Jak mamy się do Ciebie zwracać?" /></label> : null}
        <label>Login<input required minLength={3} maxLength={40} pattern="[a-zA-Z0-9._-]{3,40}" autoComplete="username" autoCapitalize="none" spellCheck={false} value={login} onChange={event => setLogin(event.target.value)} placeholder="np. moj.portfel" /></label>
        <label>Hasło<input required type="password" minLength={mode === "register" ? 10 : 1} maxLength={128} autoComplete={mode === "register" ? "new-password" : "current-password"} value={password} onChange={event => setPassword(event.target.value)} aria-describedby="local-password-note" /></label>
        {mode === "register" ? <><label>Powtórz hasło<input required type="password" minLength={10} maxLength={128} autoComplete="new-password" value={repeat} onChange={event => setRepeat(event.target.value)} /></label>{users.some(user => !user.credentials) ? <label>Wcześniejszy profil<select value={legacy} onChange={event => setLegacy(event.target.value)}><option value="">Utwórz nowy, pusty profil</option>{users.filter(user => !user.credentials).map(user => <option key={user.id} value={user.id}>{user.name} — zachowaj dane</option>)}</select><small>Możesz przypisać login do wcześniejszego profilu bez hasła.</small></label> : null}</> : null}
        <p id="local-password-note" className="qo-muted">{mode === "register" ? "Minimum 10 znaków. " : ""}Konto lokalne — bez poczty i synchronizacji między urządzeniami.</p><button className="iv-button iv-primary qo-full" disabled={busy}>{busy ? "Sprawdzam…" : mode === "register" ? "Utwórz konto i kontynuuj" : "Otwórz mój portfel"}</button>
      </fieldset></form><p className="qo-auth-note">Dane pozostają w tej przeglądarce. Lokalne logowanie nie szyfruje raportów i nie zastępuje zabezpieczeń urządzenia.</p>
    </div></section>
  </div>;
}
