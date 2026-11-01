export interface MonteCarloBand { day: number; low: string; median: string; high: string }
export interface MonteCarloResult {
  methodology: string; engine: string; synthetic_input: boolean; base_currency: string;
  valuation_date: string; calibration_start: string; calibration_end: string; observations: number;
  days: number; simulations: number; seed: number; annual_drift: number; confidence: number;
  initial_value: string; probability_of_loss: number; var_amount: string; es_amount: string;
  mean_terminal: string; bands: MonteCarloBand[]; sample_paths: string[][];
  histogram: { low: string; high: string; count: number }[]; warnings: string[];
}
