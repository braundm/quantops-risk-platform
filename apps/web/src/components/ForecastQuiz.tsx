import { useState } from "react";

import { retailRequest } from "../data/retailApi";
import { ForecastChart } from "./ForecastChart";

interface ForecastReveal {
  future_values: number[];
  future_return_pct: string;
  actual: "up" | "down" | "sideways";
  result: "hit" | "miss" | "sideways";
}

interface ForecastAnswerRow {
  question_no: number;
  case_id: number;
  prediction: "up" | "down";
  confidence: number;
  future_return_pct: string;
  actual: "up" | "down" | "sideways";
  result: "hit" | "miss" | "sideways";
}

interface ForecastSummary {
  hits: number;
  misses: number;
  sideways: number;
  effectiveness_pct: string | null;
  mean_confidence: string;
  mean_confidence_hit: string | null;
  mean_confidence_miss: string | null;
  mean_brier: string | null;
  by_confidence: { confidence: string; accuracy_pct: string; count: number }[];
  most_confident: ForecastAnswerRow | null;
}

interface ForecastRound {
  token: string;
  question_no: number;
  total: number;
  instrument: string;
  hist_values: number[];
  confidence_style: "numeric" | "words";
  reveal: ForecastReveal | null;
  finished: boolean;
  progress: ForecastAnswerRow[];
  summary: ForecastSummary | null;
}

const CONF = [50, 60, 70, 80, 90, 100] as const;
const WORDS: Record<(typeof CONF)[number], string> = {
  50: "Równe szanse",
  60: "Nieco bardziej",
  70: "Prawdopodobne",
  80: "Bardzo prawdopodobne",
  90: "Prawie pewne",
  100: "Pewne",
};

const pct = (value: string | number | null | undefined) =>
  value === null || value === undefined
    ? "—"
    : `${new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 1 }).format(Number(value))}%`;

const resultLabel = (result: ForecastReveal["result"]) =>
  result === "hit" ? "TRAFIONA" : result === "miss" ? "NIETRAFIONA" : "BRAK WYRAŹNEGO RUCHU";

export function ForecastQuiz() {
  const [round, setRound] = useState<ForecastRound | null>(null);
  const [style, setStyle] = useState<"numeric" | "words">("numeric");
  const [direction, setDirection] = useState<"up" | "down" | null>(null);
  const [confidence, setConfidence] = useState<(typeof CONF)[number] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function start(nextStyle: "numeric" | "words" = style) {
    setBusy(true);
    setError("");
    setDirection(null);
    setConfidence(null);
    try {
      setRound(await retailRequest<ForecastRound>("forecast/start", { confidence_style: nextStyle }));
      setStyle(nextStyle);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Nie udało się rozpocząć quizu.");
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!round || direction === null || confidence === null || busy) return;
    setBusy(true);
    setError("");
    try {
      const next = await retailRequest<ForecastRound>("forecast/answer", {
        token: round.token,
        prediction: direction,
        confidence,
      });
      setRound(next);
      setDirection(null);
      setConfidence(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Nie udało się zapisać prognozy.");
    } finally {
      setBusy(false);
    }
  }

  async function acknowledge() {
    if (!round || busy) return;
    setBusy(true);
    setError("");
    try {
      setRound(await retailRequest<ForecastRound>("forecast/continue", { token: round.token }));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Nie udało się kontynuować.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="qo-panel qo-forecast-panel" id="forecast">
      <div className="qo-panel-heading">
        <div>
          <p className="qo-eyebrow">KALIBRACJA PROGNOZ</p>
          <h2>Quiz kierunku rynku</h2>
        </div>
        <span className="qo-tag">12 syntetycznych wykresów</span>
      </div>
      <p className="qo-muted">
        Widzisz historię do punktu TERAZ. Oceń, czy za ok. miesiąc będzie wyżej czy niżej, i jak bardzo
        jesteś pewien. Co kilka pytań odsłaniamy prawdziwy ciąg dalszy. To ćwiczenie kalibracji —
        nie rekomendacja inwestycyjna.
      </p>
      {error ? <p className="qo-alert qo-error" role="alert">{error}</p> : null}

      {!round ? (
        <div className="qo-lab-intro">
          <div className="qo-lab-mark" aria-hidden="true">↗</div>
          <h3>Prognoza bez podpowiedzi z przyszłości</h3>
          <p>
            12 anonimowych, syntetycznych serii. Bez nazw realnych instrumentów. Co 4 odpowiedzi —
            odsłonięcie tego, co stało się później.
          </p>
          <div className="qo-forecast-style">
            <button className={`qo-button ${style === "numeric" ? "qo-primary" : ""}`} type="button" disabled={busy} onClick={() => setStyle("numeric")}>
              Pewność w %
            </button>
            <button className={`qo-button ${style === "words" ? "qo-primary" : ""}`} type="button" disabled={busy} onClick={() => setStyle("words")}>
              Pewność słownie
            </button>
          </div>
          <button className="qo-button qo-primary" type="button" disabled={busy} onClick={() => void start(style)}>
            Zaczynam quiz →
          </button>
        </div>
      ) : round.finished && round.summary ? (
        <div className="qo-forecast-results">
          <h3>Twój wynik</h3>
          <p className="qo-muted">Podsumowanie dotyczy tylko tej sesji. Nie ocenia kompetencji inwestycyjnych.</p>
          <div className="qo-risk-strip">
            <article>
              <p>Skuteczność</p>
              <strong>{pct(round.summary.effectiveness_pct)}</strong>
              <small>{round.summary.hits} trafionych · {round.summary.misses} nietrafionych · {round.summary.sideways} bok</small>
            </article>
            <article>
              <p>Średnia pewność</p>
              <strong>{pct(round.summary.mean_confidence)}</strong>
              <small>
                Trafione: {pct(round.summary.mean_confidence_hit)} · nietrafione: {pct(round.summary.mean_confidence_miss)}
              </small>
            </article>
            <article>
              <p>Kalibracja (Brier)</p>
              <strong>{round.summary.mean_brier ?? "—"}</strong>
              <small>Mniej = lepiej · porównaj z skutecznością</small>
            </article>
            <article>
              <p>Pewność ↔ skuteczność</p>
              <strong>{pct(round.summary.mean_confidence)} ↔ {pct(round.summary.effectiveness_pct)}</strong>
              <small>Duża różnica sugeruje przeszacowanie lub niedoszacowanie</small>
            </article>
          </div>
          {round.summary.by_confidence.length >= 2 ? (
            <div className="qo-forecast-buckets">
              <h4>Czy większa pewność oznaczała większą trafność?</h4>
              <ul>
                {round.summary.by_confidence.map((bucket) => (
                  <li key={bucket.confidence}>
                    <strong>{bucket.confidence}</strong>
                    <span>{pct(bucket.accuracy_pct)} trafności</span>
                    <small>{bucket.count} prognoz</small>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="qo-note">Używałeś prawie jednego poziomu pewności — trudno porównać skalę kalibracji.</p>
          )}
          <p className="qo-note">
            Inwestowanie to nie tylko zgadywanie kierunku. Wielkość pozycji, ryzyko strat i konsekwencja
            często ważą więcej niż sama prognoza. Ruch od −2,5% do +2,5% liczymy jako brak wyraźnego ruchu.
          </p>
          <button className="qo-button qo-primary" type="button" disabled={busy} onClick={() => void start(style)}>
            Nowy quiz
          </button>
        </div>
      ) : round.reveal ? (
        <div className="qo-forecast-reveal">
          <div className="qo-lab-progress">
            <strong>Prognoza {round.question_no} / {round.total}</strong>
            <div aria-hidden="true">
              {Array.from({ length: round.total }, (_, index) => (
                <i key={index} className={index < round.progress.length ? "completed" : ""} />
              ))}
            </div>
          </div>
          <p className="qo-forecast-instrument">{round.instrument} · dane syntetyczne</p>
          <p className={`qo-forecast-verdict qo-${round.reveal.result}`}>
            {`${Number(round.reveal.future_return_pct) > 0 ? "+" : ""}${new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 1 }).format(Number(round.reveal.future_return_pct))}%`}
            {" — "}
            {resultLabel(round.reveal.result)}
          </p>
          <ForecastChart
            history={round.hist_values}
            future={round.reveal.future_values}
            title={`Odsłonięty przebieg ${round.instrument}`}
          />
          <p className="qo-muted">
            {round.progress.length >= round.total
              ? "To był ostatni wykres. Zobacz podsumowanie kalibracji."
              : `Zostało jeszcze ${round.total - round.progress.length} wykresów.`}
          </p>
          <button className="qo-button qo-primary" type="button" disabled={busy} onClick={() => void acknowledge()}>
            Dalej →
          </button>
        </div>
      ) : (
        <div className="qo-forecast-play">
          <div className="qo-lab-progress">
            <strong>Prognoza {round.question_no} / {round.total}</strong>
            <div aria-hidden="true">
              {Array.from({ length: round.total }, (_, index) => (
                <i key={index} className={index < round.progress.length ? "completed" : ""} />
              ))}
            </div>
          </div>
          <p className="qo-forecast-instrument">{round.instrument} · wykres znormalizowany · dane syntetyczne</p>
          <ForecastChart history={round.hist_values} title={`Historia do TERAZ: ${round.instrument}`} />
          <h3>Gdzie będzie rynek za miesiąc?</h3>
          <div className="qo-decision-buttons">
            <button
              className={`qo-button ${direction === "down" ? "qo-primary" : ""}`}
              type="button"
              disabled={busy}
              onClick={() => setDirection("down")}
            >
              Spadnie
            </button>
            <button
              className={`qo-button ${direction === "up" ? "qo-primary" : ""}`}
              type="button"
              disabled={busy}
              onClick={() => setDirection("up")}
            >
              Wzrośnie
            </button>
          </div>
          <h3>Jak bardzo jesteś pewien?</h3>
          {round.confidence_style === "numeric" ? (
            <div className="qo-forecast-confidence">
              {CONF.map((value) => (
                <button
                  key={value}
                  className={`qo-button ${confidence === value ? "qo-primary" : ""}`}
                  type="button"
                  disabled={busy}
                  onClick={() => setConfidence(value)}
                >
                  {value}%
                </button>
              ))}
            </div>
          ) : (
            <div className="qo-forecast-confidence qo-forecast-words">
              {CONF.map((value) => (
                <button
                  key={value}
                  className={`qo-button ${confidence === value ? "qo-primary" : ""}`}
                  type="button"
                  disabled={busy}
                  onClick={() => setConfidence(value)}
                >
                  {WORDS[value]}
                </button>
              ))}
            </div>
          )}
          <button
            className="qo-button qo-primary"
            type="button"
            disabled={busy || direction === null || confidence === null}
            onClick={() => void submit()}
          >
            Zapisz prognozę →
          </button>
        </div>
      )}
      <p className="qo-note">
        Ścieżki są deterministyczne i syntetyczne — nie pochodzą z realnego rynku. Serwer trzyma przyszłość;
        przeglądarka dostaje ją dopiero przy odsłonięciu. Sesja wygasa po godzinie lub restarcie API.
      </p>
    </section>
  );
}
