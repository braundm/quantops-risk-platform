export const DEMO_PORTFOLIO_ID = "11111111-1111-4111-8111-111111111111";

export type DemoMode =
  | "normal"
  | "loading"
  | "empty"
  | "error"
  | "stale"
  | "partial"
  | "insufficient"
  | "offline";

export type CalculationStatus = "valid" | "insufficient_data";

export interface RiskMetric {
  readonly label: string;
  readonly value: number | null;
  readonly kind: "currency" | "percent";
  readonly status: CalculationStatus;
  readonly description: string;
}

export interface Position {
  readonly symbol: string;
  readonly name: string;
  readonly assetClass: string;
  readonly quantity: number;
  readonly lastPrice: number;
  readonly marketValue: number;
  readonly weight: number;
  readonly contribution: number;
  readonly dataStatus: "complete" | "late";
}

export interface RiskHistoryPoint {
  readonly date: string;
  readonly portfolioValue: number;
  readonly historicalVar: number;
}

export interface CorrelationCell {
  readonly row: string;
  readonly column: string;
  readonly value: number;
  readonly observations: number;
}

export interface ScenarioDefinition {
  readonly id: string;
  readonly version: string;
  readonly name: string;
  readonly description: string;
  readonly impact: number;
  readonly componentImpacts: ReadonlyArray<{
    readonly symbol: string;
    readonly impact: number;
  }>;
  readonly assumptions: readonly string[];
}

export interface PipelineRun {
  readonly id: string;
  readonly pipeline: string;
  readonly status: "succeeded" | "failed" | "running";
  readonly startedAt: string;
  readonly completedAt: string | null;
  readonly watermark: string;
  readonly accepted: number;
  readonly quarantined: number;
}

export interface QualityIssue {
  readonly id: string;
  readonly code: string;
  readonly severity: "warning" | "error";
  readonly instrument: string;
  readonly observedAt: string;
  readonly description: string;
  readonly remediation: string;
  readonly downstreamImpact: string;
}

export interface EvidenceRecord {
  readonly id: string;
  readonly type: "risk_snapshot" | "price_bar" | "methodology" | "pipeline_run";
  readonly title: string;
  readonly recordedAt: string;
  readonly source: string;
  readonly detail: string;
  readonly checksum: string;
}

export interface DemoPortfolio {
  readonly id: string;
  readonly name: string;
  readonly baseCurrency: "USD";
  readonly value: number;
  readonly asOf: string;
  readonly snapshotId: string;
  readonly methodology: {
    readonly name: string;
    readonly version: string;
    readonly confidence: number;
    readonly window: number;
    readonly horizon: number;
  };
  readonly metrics: readonly RiskMetric[];
  readonly positions: readonly Position[];
  readonly history: readonly RiskHistoryPoint[];
  readonly correlations: readonly CorrelationCell[];
}

export interface DemoBundle {
  readonly portfolio: DemoPortfolio;
  readonly scenarios: readonly ScenarioDefinition[];
  readonly pipelineRuns: readonly PipelineRun[];
  readonly qualityIssues: readonly QualityIssue[];
  readonly evidence: readonly EvidenceRecord[];
  readonly fixture: {
    readonly label: string;
    readonly seed: number;
    readonly datasetVersion: string;
    readonly generatedRange: string;
  };
}

export interface DemoResult {
  readonly data: DemoBundle | null;
  readonly mode: DemoMode;
  readonly warnings: readonly string[];
}

const positions: readonly Position[] = [
  {
    symbol: "QTECH",
    name: "QuantOps Synthetic Technology Index",
    assetClass: "Equity index",
    quantity: 6_100,
    lastPrice: 95.457199,
    marketValue: 582_288.9139,
    weight: 0.3874,
    contribution: 7_978.51898494884,
    dataStatus: "complete",
  },
  {
    symbol: "QGOLD",
    name: "QuantOps Synthetic Gold Exposure",
    assetClass: "Commodity",
    quantity: 2_300,
    lastPrice: 164.829931,
    marketValue: 379_108.8413,
    weight: 0.2522,
    contribution: 1_448.04635298005,
    dataStatus: "complete",
  },
  {
    symbol: "QWTI",
    name: "QuantOps Synthetic Crude-Oil Exposure",
    assetClass: "Commodity",
    quantity: 5_200,
    lastPrice: 42.983067,
    marketValue: 223_511.9484,
    weight: 0.1487,
    contribution: 5_301.3055680771,
    dataStatus: "complete",
  },
  {
    symbol: "QCASH",
    name: "QuantOps Synthetic Cash Reference",
    assetClass: "Cash",
    quantity: 3_100,
    lastPrice: 102.677015,
    marketValue: 318_298.7465,
    weight: 0.2117,
    contribution: -161.331251283103,
    dataStatus: "complete",
  },
];

const symbols = positions.map((position) => position.symbol);
const correlationValues = [
  [1, 0.62, 0.54, 0.04],
  [0.62, 1, 0.41, 0.02],
  [0.54, 0.41, 1, 0.03],
  [0.04, 0.02, 0.03, 1],
] as const;

const correlations: readonly CorrelationCell[] = symbols.flatMap((row, rowIndex) =>
  symbols.map((column, columnIndex) => ({
    row,
    column,
    value: correlationValues[rowIndex]?.[columnIndex] ?? 0,
    observations: row === column ? 521 : 520,
  })),
);

const portfolio: DemoPortfolio = {
  id: DEMO_PORTFOLIO_ID,
  name: "Synthetic Multi-Asset Research",
  baseCurrency: "USD",
  value: 1_503_208.4501,
  asOf: "2024-12-31T21:02:00Z",
  snapshotId: "9070191f-15f2-53b4-bdaa-87fb0e818c8e",
  methodology: {
    name: "Historical and variance-covariance risk",
    version: "1.0.0",
    confidence: 0.95,
    window: 40,
    horizon: 1,
  },
  metrics: [
    {
      label: "Historical VaR",
      value: 7_964.476582948232,
      kind: "currency",
      status: "valid",
      description: "95% one-day empirical loss quantile",
    },
    {
      label: "Parametric VaR",
      value: 14_566.539654722888,
      kind: "currency",
      status: "valid",
      description: "95% one-day normal variance-covariance estimate",
    },
    {
      label: "Expected Shortfall",
      value: 27_263.462032870295,
      kind: "currency",
      status: "valid",
      description: "Mean observed loss at or beyond Historical VaR",
    },
    {
      label: "Annualized volatility",
      value: 0.09419958397407178,
      kind: "percent",
      status: "valid",
      description: "Daily sample volatility scaled by √252",
    },
    {
      label: "Maximum drawdown",
      value: 0.03597625080761113,
      kind: "percent",
      status: "valid",
      description: "Largest peak-to-trough decline in the supplied window",
    },
  ],
  positions,
  history: [
    { date: "2024-07-31", portfolioValue: 1_468_400, historicalVar: 22_940 },
    { date: "2024-08-30", portfolioValue: 1_505_700, historicalVar: 21_650 },
    { date: "2024-09-30", portfolioValue: 1_526_900, historicalVar: 20_880 },
    { date: "2024-10-31", portfolioValue: 1_489_200, historicalVar: 23_410 },
    { date: "2024-11-29", portfolioValue: 1_451_800, historicalVar: 27_260 },
    { date: "2024-12-31", portfolioValue: 1_503_208.4501, historicalVar: 7_964.476582948232 },
  ],
  correlations,
};

const scenarios: readonly ScenarioDefinition[] = [
  {
    id: "combined_liquidity_stress",
    version: "1.0.0",
    name: "Combined liquidity stress",
    description: "Applies versioned equity, oil, gold, volatility, and correlation shocks.",
    impact: -168_940.017105,
    componentImpacts: [
      { symbol: "QTECH", impact: -116_457.78278 },
      { symbol: "QGOLD", impact: -18_955.442065 },
      { symbol: "QWTI", impact: -33_526.79226 },
      { symbol: "QCASH", impact: 0 },
    ],
    assumptions: [
      "Instantaneous deterministic price shocks",
      "Volatility scales 1.80x for analytical comparison",
      "Positions and quantities remain unchanged",
    ],
  },
  {
    id: "cross_asset_correlation_breakdown",
    version: "1.0.0",
    name: "Cross-asset correlation breakdown",
    description: "Raises selected correlations to 0.80 and volatility 1.25x without a revaluation P&L.",
    impact: 0,
    componentImpacts: [
      { symbol: "QTECH", impact: 0 },
      { symbol: "QGOLD", impact: 0 },
      { symbol: "QWTI", impact: 0 },
      { symbol: "QCASH", impact: 0 },
    ],
    assumptions: [
      "Selected cross-asset correlations become +0.80",
      "Volatility scales 1.25x for analytical comparison",
      "Correlation is not a deterministic revaluation P&L",
    ],
  },
  {
    id: "equity_selloff_15pct",
    version: "1.0.0",
    name: "Equity selloff 15%",
    description: "Applies a hypothetical −15% shock to the QTECH equity-index exposure.",
    impact: -87_343.337085,
    componentImpacts: [
      { symbol: "QTECH", impact: -87_343.337085 },
      { symbol: "QGOLD", impact: 0 },
      { symbol: "QWTI", impact: 0 },
      { symbol: "QCASH", impact: 0 },
    ],
    assumptions: [
      "All equity prices fall 15% instantaneously",
      "No position rebalancing",
    ],
  },
  {
    id: "gold_down_10pct",
    version: "1.0.0",
    name: "Gold down 10%",
    description: "Applies a hypothetical −10% shock to QGOLD.",
    impact: -37_910.88413,
    componentImpacts: [
      { symbol: "QTECH", impact: 0 },
      { symbol: "QGOLD", impact: -37_910.88413 },
      { symbol: "QWTI", impact: 0 },
      { symbol: "QCASH", impact: 0 },
    ],
    assumptions: [
      "QGOLD falls 10% instantaneously",
      "Hypothetical engineering scenario",
    ],
  },
  {
    id: "oil_spike_25pct",
    version: "1.0.0",
    name: "Oil spike 25%",
    description: "Applies a hypothetical +25% shock to QWTI.",
    impact: 55_877.9871,
    componentImpacts: [
      { symbol: "QTECH", impact: 0 },
      { symbol: "QGOLD", impact: 0 },
      { symbol: "QWTI", impact: 55_877.9871 },
      { symbol: "QCASH", impact: 0 },
    ],
    assumptions: [
      "QWTI rises 25% instantaneously",
      "Hypothetical engineering scenario",
    ],
  },
];

const pipelineRuns: readonly PipelineRun[] = [
  {
    id: "run-synthetic-20250317",
    pipeline: "deterministic_synthetic_generator",
    status: "succeeded",
    startedAt: "2025-03-17T08:00:00Z",
    completedAt: "2025-03-17T08:00:01Z",
    watermark: "2024-12-31T21:00:00Z",
    accepted: 2_088,
    quarantined: 0,
  },
  {
    id: "run-quality-cases-20250317",
    pipeline: "isolated_quality_case_validator",
    status: "succeeded",
    startedAt: "2025-03-17T08:01:00Z",
    completedAt: "2025-03-17T08:01:01Z",
    watermark: "2024-12-31T21:00:00Z",
    accepted: 17,
    quarantined: 4,
  },
];

const qualityIssues: readonly QualityIssue[] = [
  {
    id: "dq-missing-qgold",
    code: "BAR_MISSING",
    severity: "warning",
    instrument: "QGOLD",
    observedAt: "2024-01-10T21:00:00Z",
    description: "An isolated fixture omits one expected daily QGOLD bar.",
    remediation: "Confirm source completeness before allowing the case into risk inputs.",
    downstreamImpact: "Quarantined; canonical snapshot unaffected.",
  },
  {
    id: "dq-late-qwti",
    code: "EVENT_LATE",
    severity: "warning",
    instrument: "QWTI",
    observedAt: "2024-01-09T21:00:00Z",
    description: "An isolated QWTI fixture arrives after its declared watermark.",
    remediation: "Reprocess within the allowed lateness window or quarantine.",
    downstreamImpact: "Quarantined; canonical snapshot unaffected.",
  },
  {
    id: "dq-duplicate-qtech",
    code: "EVENT_DUPLICATE",
    severity: "warning",
    instrument: "QTECH",
    observedAt: "2024-01-08T21:00:00Z",
    description: "A duplicate source-event ID is included to exercise idempotency.",
    remediation: "Retain the first accepted event and record the duplicate.",
    downstreamImpact: "Deduplicated; canonical snapshot unaffected.",
  },
  {
    id: "dq-malformed-qtech",
    code: "OHLC_INVALID",
    severity: "error",
    instrument: "QTECH",
    observedAt: "2024-01-11T21:00:00Z",
    description: "A deliberately malformed bar violates OHLC invariants.",
    remediation: "Reject the record and investigate the source mapping.",
    downstreamImpact: "Quarantined; never used as authoritative risk input.",
  },
];

const evidence: readonly EvidenceRecord[] = [
  {
    id: "evidence-risk-001",
    type: "risk_snapshot",
    title: "Risk snapshot 8c6a5ec2",
    recordedAt: "2024-12-31T21:02:00Z",
    source: "quantops-risk 1.0.0",
    detail:
      "Historical VaR is USD 7,964.48 and Expected Shortfall is USD 27,263.46 for the deterministic 40-observation API fixture.",
    checksum: "sha256:5ee461f…a1c9",
  },
  {
    id: "evidence-price-001",
    type: "price_bar",
    title: "QTECH closing price bar",
    recordedAt: "2024-12-31T21:00:00Z",
    source: "quantops_deterministic_synthetic_generator",
    detail: "Synthetic QTECH close: USD 95.457199. Source event is stable and idempotent.",
    checksum: "sha256:ab63533…5995",
  },
  {
    id: "evidence-method-001",
    type: "methodology",
    title: "Risk methodology 1.0.0",
    recordedAt: "2025-03-17T08:00:00Z",
    source: "docs/risk-methodology.md",
    detail: "Losses are nonnegative amounts. VaR uses an explicit linear empirical quantile.",
    checksum: "sha256:methodology…100",
  },
  {
    id: "evidence-pipeline-001",
    type: "pipeline_run",
    title: "Synthetic generation run",
    recordedAt: "2025-03-17T08:00:01Z",
    source: "run-synthetic-20250317",
    detail: "2,088 canonical bars accepted; deterministic seed 20250317.",
    checksum: "sha256:2796bd5…1150",
  },
];

export const demoBundle: DemoBundle = {
  portfolio,
  scenarios,
  pipelineRuns,
  qualityIssues,
  evidence,
  fixture: {
    label: "Deterministic synthetic demo",
    seed: 20_250_317,
    datasetVersion: "1.0.0",
    generatedRange: "2 January 2023 – 31 December 2024",
  },
};

const knownModes = new Set<DemoMode>([
  "normal",
  "loading",
  "empty",
  "error",
  "stale",
  "partial",
  "insufficient",
  "offline",
]);

export function parseDemoMode(search: string): DemoMode {
  const requested = new URLSearchParams(search).get("state");
  return requested !== null && knownModes.has(requested as DemoMode)
    ? (requested as DemoMode)
    : "normal";
}

function warningForMode(mode: DemoMode): readonly string[] {
  switch (mode) {
    case "stale":
      return ["The simulated watermark is behind the selected replay point. Values remain visible but are marked stale."];
    case "partial":
      return ["QWTI has partial source coverage. Portfolio metrics exclude the incomplete interval."];
    case "insufficient":
      return ["Only 18 observations are available; VaR, Expected Shortfall, and drawdown are not reported as trustworthy."];
    case "offline":
      return ["The optional replay broker is offline. This batch fixture remains available and no live updates are implied."];
    default:
      return [];
  }
}

function resultForMode(mode: DemoMode): DemoResult {
  if (mode === "empty") {
    return { data: null, mode, warnings: [] };
  }

  if (mode === "insufficient") {
    const insufficientMetrics = portfolio.metrics.map((metric) => ({
      ...metric,
      value: null,
      status: "insufficient_data" as const,
    }));
    return {
      data: {
        ...demoBundle,
        portfolio: { ...portfolio, metrics: insufficientMetrics },
      },
      mode,
      warnings: warningForMode(mode),
    };
  }

  if (mode === "partial") {
    const partialPositions = portfolio.positions.map((position) =>
      position.symbol === "QWTI" ? { ...position, dataStatus: "late" as const } : position,
    );
    return {
      data: {
        ...demoBundle,
        portfolio: { ...portfolio, positions: partialPositions },
      },
      mode,
      warnings: warningForMode(mode),
    };
  }

  return { data: demoBundle, mode, warnings: warningForMode(mode) };
}

export interface DemoDataAdapter {
  load(mode: DemoMode): Promise<DemoResult>;
}

export const localDemoAdapter: DemoDataAdapter = {
  load(mode) {
    if (mode === "loading") {
      return new Promise<DemoResult>(() => undefined);
    }
    if (mode === "error") {
      return Promise.reject(new Error("The deterministic demo fixture could not be loaded."));
    }
    return Promise.resolve(resultForMode(mode));
  },
};
