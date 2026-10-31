import { useEffect, useRef, useState } from "react";
import { BrokerSelection } from "../components/BrokerSelection";
import { LocalLogin } from "../components/LocalLogin";
import { StockProfileSurvey } from "../components/StockProfileSurvey";
import { XtbWorkspace, type WorkspaceView } from "../components/XtbWorkspace";
import { stocksRequest, type ProfileAnswers } from "../data/stocksApi";
import { endLocalSession, localSession, startLocalSession } from "../lib/localLogin";
import { seedLocalDemoAccounts } from "../lib/localDemo";
import { readStockUsers, STOCK_USERS_KEY, writeStockUsers, type StockUser, type StockUsers } from "../lib/stockUsers";
import "../styles/investor.css";
import "../styles/stocks.css";
import "../styles/workspace.css";

const pages: { view: WorkspaceView; icon: string; name: string; detail: string }[] = [
  { view: "overview", icon: "◫", name: "Przegląd", detail: "Twoje rachunki, raporty i kolejne kroki w jednym miejscu." },
  { view: "holdings", icon: "▤", name: "Portfel", detail: "Otwarte pozycje, daty cen i pokrycie wyceny wybranego rachunku." },
  { view: "risk", icon: "◈", name: "Analiza ryzyka", detail: "Koncentracja, historia, scenariusze i porównanie niezależnego wariantu portfela." },
  { view: "accounts", icon: "▦", name: "Brokerzy i konta", detail: "Każdy rachunek osobno — również kilka rachunków w tej samej walucie." },
  { view: "import", icon: "↥", name: "Import raportów", detail: "Wczytaj plik, sprawdź podgląd i zatwierdź zapis na wybrane konto." },
  { view: "history", icon: "◷", name: "Historia importów", detail: "Sprawdź pochodzenie danych i pobierz kopię swoich raportów." },
  { view: "settings", icon: "⚙", name: "Ustawienia", detail: "Twój profil, opcjonalna ankieta i lokalny zapis danych." },
];

export function StocksPage() {
  const [initial] = useState(() => {
    try { seedLocalDemoAccounts(); } catch { /* Preserve the existing storage for recovery below. */ }
    try { return { data: readStockUsers(), raw: localStorage.getItem(STOCK_USERS_KEY), session: localSession(), error: "" }; }
    catch { return { data: { version: 1 as const, active_id: null, users: [] }, raw: null, session: null, error: "Nie można odczytać lokalnych danych. Pobierz kopię przed ich odzyskaniem." }; }
  });
  const [registry, setRegistry] = useState<StockUsers>(initial.data);
  const lastRaw = useRef(initial.raw);
  const [userId, setUserId] = useState(initial.session);
  const [error, setError] = useState(initial.error);
  const [blocked, setBlocked] = useState(Boolean(initial.error));
  const [busy, setBusy] = useState(false);
  const [surveyBusy, setSurveyBusy] = useState(false);
  const [editSurvey, setEditSurvey] = useState(false);
  const [editBrokers, setEditBrokers] = useState(false);
  const [view, setView] = useState<WorkspaceView>("overview");
  const user = registry.users.find(item => item.id === userId && item.credentials) ?? null;
  const surveyPending = user && !user.answers && (!user.survey_status || user.survey_status === "pending");
  const onboarding = Boolean(user && (surveyPending || !user.brokers?.length));
  const page = pages.find(item => item.view === view) ?? pages[0]!;
  useEffect(() => { document.documentElement.lang = "pl"; document.title = "QuantOps — Centrum portfela"; }, []);
  useEffect(() => {
    const changed = (event: StorageEvent) => { if (event.key === STOCK_USERS_KEY) { setBlocked(true); setError("Profil zmienił się w innej karcie. Odśwież stronę, aby wczytać aktualne dane."); } };
    window.addEventListener("storage", changed); return () => window.removeEventListener("storage", changed);
  }, []);
  function save(next: StockUsers) {
    if (blocked || localStorage.getItem(STOCK_USERS_KEY) !== lastRaw.current) throw new Error("Zapis profilu zmienił się. Odśwież stronę przed dalszym zapisem.");
    writeStockUsers(next); lastRaw.current = localStorage.getItem(STOCK_USERS_KEY); setRegistry(next);
  }
  function updateUser(patch: Partial<StockUser>) {
    if (!user) return;
    save({ ...registry, users: registry.users.map(item => item.id === user.id ? { ...user, ...patch } : item) });
  }
  function fail(reason: unknown) { setError(reason instanceof Error ? reason.message : "Nie można zapisać danych."); }
  function navigate(next: WorkspaceView) { setView(next); setError(""); setEditSurvey(false); setEditBrokers(false); window.scrollTo(0, 0); }
  function login(id: string) { startLocalSession(id); setUserId(id); setView("overview"); setError(""); }
  function register(name: string, credentials: NonNullable<StockUser["credentials"]>, legacyId: string) {
    const legacy = registry.users.find(item => item.id === legacyId && !item.credentials);
    if (legacyId && !legacy) throw new Error("Nie znaleziono wcześniejszego profilu.");
    if (!legacy && registry.users.filter(item => !item.demo_origin).length >= 10) throw new Error("Limit to 10 własnych lokalnych kont.");
    const next: StockUser = legacy ? { ...legacy, name, credentials } : {
      id: crypto.randomUUID(), name, created_at: new Date().toISOString(), credentials,
      answers: null, profile: null, positions: [], survey_status: "pending",
    };
    save({ ...registry, active_id: next.id, users: legacy ? registry.users.map(item => item.id === legacy.id ? next : item) : [...registry.users, next] });
    login(next.id);
  }
  function logout() { endLocalSession(); setUserId(null); setEditSurvey(false); setEditBrokers(false); setView("overview"); }
  async function submitSurvey(answers: ProfileAnswers) {
    setSurveyBusy(true); setError("");
    try {
      const profile = await stocksRequest<StockUser["profile"]>("profile", answers);
      updateUser({ answers, profile, survey_status: "completed" }); setEditSurvey(false);
    } catch (reason) { fail(reason); } finally { setSurveyBusy(false); }
  }
  function skipSurvey() {
    try { if (!user?.answers) updateUser({ survey_status: "skipped" }); setEditSurvey(false); } catch (reason) { fail(reason); }
  }
  function chooseBrokers(brokers: ("xtb" | "bossa")[]) {
    try { updateUser({ brokers }); setEditBrokers(false); setView("accounts"); } catch (reason) { fail(reason); }
  }
  function downloadProfile() {
    const payload = user ? { ...user, credentials: undefined } : { raw: localStorage.getItem(STOCK_USERS_KEY) };
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = "QuantOps-profil.json"; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  if (!user) return <div className="iv-app sq-app qo-auth"><a className="iv-skip" href="#login-main">Przejdź do treści</a><main id="login-main">{blocked ? <section className="iv-panel"><h1>Sprawdź lokalny zapis</h1><p role="alert">{error}</p><button className="iv-button" onClick={downloadProfile}>Pobierz zapis</button><button className="iv-button" onClick={() => window.location.reload()}>Wczytaj ponownie</button></section> : <LocalLogin users={registry.users} onRegister={register} onLogin={login} />}</main></div>;
  return <div className="iv-app sq-app qo-workspace"><a className="iv-skip" href="#stocks-main">Przejdź do treści</a>
    <aside className="iv-sidebar"><a className="iv-brand" href="/"><b>Q</b><span>QuantOps<small>CENTRUM TWOJEGO PORTFELA</small></span></a><p className="iv-nav-label">TWOJA PRZESTRZEŃ</p><nav aria-label="Centrum portfela">{pages.map(item => <button key={item.view} disabled={busy || surveyBusy || onboarding || blocked} aria-current={!onboarding && view === item.view ? "page" : undefined} onClick={() => navigate(item.view)}><span aria-hidden="true">{item.icon}</span>{item.name}</button>)}</nav><div className="iv-sidebar-foot"><a href="/instruments">Katalog instrumentów ↗</a><a href="/treasury">Treasury i płynność ↗</a><p>Raporty XTB · ceny referencyjne<br />Bez połączenia z rachunkiem brokera</p></div><div className="qo-sidebar-user"><span className="qo-avatar">{user.name.slice(0, 1).toUpperCase()}</span><span>{user.name}<small>@{user.credentials?.login}</small></span><button aria-label="Ustawienia konta" title="Ustawienia konta" disabled={busy || surveyBusy || onboarding} onClick={() => navigate("settings")}>⚙</button></div></aside>
    <div className="iv-content"><header className="iv-topbar"><span>Moja przestrzeń <b>/</b> {onboarding ? "Pierwsze kroki" : page.name}</span><div className="qo-top-actions"><span className="qo-local-badge">● Zapis lokalny</span><button className="iv-button" disabled={busy || surveyBusy} onClick={logout}>Wyloguj się</button></div></header><main id="stocks-main" tabIndex={-1}>
      {error ? <p className="iv-alert iv-error" role="alert">{error}{blocked ? <button className="iv-button" onClick={() => window.location.reload()}>Odśwież stronę</button> : null}</p> : null}
      {user.demo_origin ? <p className="qo-demo-notice" role="note"><b>Konto testowe · SYNTHETIC</b>{user.demo_origin === "empty" ? "Pusty portfel do własnych prób importu." : "Dane z quantum_ops_portfolio_test.xlsx. To syntetyczny zestaw testowy, a nie rzeczywisty wyciąg XTB; ceny wymagają osobnego odświeżenia."}</p> : null}
      {onboarding ? <><ol className="qo-steps" aria-label="Konfiguracja konta"><li className="done"><b>✓</b>Konto</li><li className={surveyPending ? "current" : "done"}><b>{surveyPending ? "2" : "✓"}</b>Ankieta <small>opcjonalnie</small></li><li className={!surveyPending ? "current" : ""}><b>3</b>Brokerzy</li><li><b>4</b>Raport</li></ol>{surveyPending ? <div className="qo-survey-intro"><p className="iv-eyebrow">OPCJONALNIE · OKOŁO 2 MINUT</p><h1>Najpierw portfel czy krótka ankieta?</h1><p>Ankieta dopasowuje objaśnienia. Nie zmienia wyceny ani obliczeń ryzyka i nie jest wymagana do importu.</p><button className="iv-button iv-primary" disabled={surveyBusy || blocked} onClick={skipSurvey}>Pomiń ankietę i wybierz brokerów →</button></div> : null}{surveyPending ? <details className="qo-survey-choice"><summary>Chcę wypełnić ankietę teraz</summary><StockProfileSurvey name={user.name} saved={user.answers} busy={surveyBusy || blocked} onSubmit={submitSurvey} /></details> : <BrokerSelection key={user.id} saved={user.brokers ?? []} onSave={chooseBrokers} />}</> : <>
        <div className="qo-page-heading"><div><p className="iv-eyebrow">{view === "overview" ? `DZIEŃ DOBRY, ${user.name}` : "CENTRUM PORTFELA"}</p><h1>{page.name}</h1><p>{page.detail}</p></div>{view !== "import" && view !== "settings" ? <button className="iv-button iv-primary" disabled={busy || blocked} onClick={() => navigate("import")}>↥ Wczytaj raport</button> : null}</div>
        {view === "settings" ? <><section className="iv-panel"><h2>Twój profil</h2><dl className="qo-details"><div><dt>Nazwa</dt><dd>{user.name}</dd></div><div><dt>Login lokalny</dt><dd>{user.credentials?.login}</dd></div><div><dt>Ankieta</dt><dd>{user.answers ? "Uzupełniona" : "Pominięta — możesz wrócić w dowolnym momencie"}</dd></div></dl><button className="iv-button" disabled={surveyBusy} onClick={() => setEditSurvey(current => !current)}>{user.answers ? "Edytuj ankietę" : "Uzupełnij ankietę"}</button><button className="iv-button" onClick={downloadProfile}>Pobierz profil{user.positions.length ? " i wcześniejsze pozycje" : ""}</button></section>{editSurvey ? <><button className="iv-button" disabled={surveyBusy} onClick={() => setEditSurvey(false)}>Wróć bez zmian</button><StockProfileSurvey key={user.id} name={user.name} saved={user.answers} busy={surveyBusy} onSubmit={submitSurvey} /></> : null}<section className="iv-panel"><h2>O tym koncie</h2><p>Logowanie działa lokalnie w tej przeglądarce. Hasło jest zapisywane jako skrót z osobną solą; nie wysyłamy go do brokera. Raporty nie są szyfrowane. Nie ma synchronizacji ani odzyskiwania hasła przez e-mail.</p><p className="iv-note">Kopie rachunków pobierzesz w Historii importów. Ankieta dopasowuje objaśnienia; nie jest modelem ryzyka ani rekomendacją inwestycyjną.</p></section></> : null}
        {view === "accounts" ? <section className="qo-provider-summary"><span>Wybrani brokerzy: <b>{user.brokers?.map(broker => broker === "xtb" ? "XTB" : "Bossa").join(" · ")}</b></span><button className="iv-text" disabled={busy} onClick={() => setEditBrokers(current => !current)}>Zmień wybór brokerów</button></section> : null}
        {view === "accounts" && editBrokers ? <BrokerSelection saved={user.brokers ?? []} onSave={chooseBrokers} /> : null}
        <XtbWorkspace key={user.id} userId={user.id} onBusy={setBusy} view={view} onNavigate={navigate} brokers={user.brokers ?? []} />
      </>}
    </main><footer className="iv-footer">QuantOps · Badanie ryzyka portfela.<span>Stan z raportów · datowane ceny · jawne braki danych</span></footer></div>
  </div>;
}
