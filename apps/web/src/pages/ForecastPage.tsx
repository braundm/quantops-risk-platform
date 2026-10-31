import { ForecastQuiz } from "../components/ForecastQuiz";
import "../styles/retail.css";
import "../styles/retail-next.css";

/** Research-shell host for the synthetic forecast calibration quiz. */
export function ForecastPage() {
  return (
    <div className="qo-research-forecast">
      <header className="page-header">
        <div>
          <p className="eyebrow">Synthetic calibration exercise</p>
          <h1>Forecast direction quiz</h1>
          <p>
            Anonymous synthetic charts cut at NOW. Predict up or down, state your confidence, then
            reveal the held-back path. This is a calibration drill — not live market data and not
            investment advice.
          </p>
        </div>
        <a className="button button-secondary" href="/">Open personal workspace</a>
      </header>
      <ForecastQuiz />
    </div>
  );
}
