"""Leakage-safe point-in-time risk-regime feature engineering."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from quantops_ml.data import REQUIRED_SYMBOLS, MarketDataset
from quantops_ml.types import FEATURE_SCHEMA, KNOWN_SYNTHETIC_REGIME_MAP, FeatureRow

RISK_SYMBOLS = ("QTECH", "QGOLD", "QWTI")


@dataclass(frozen=True, slots=True)
class FeatureConfig:
    volatility_window: int = 20
    correlation_window: int = 20
    drawdown_window: int = 60
    drawdown_velocity_lag: int = 5
    volume_window: int = 20
    annualization_days: int = 252
    portfolio_weights: tuple[float, ...] = (0.30, 0.25, 0.35, 0.10)

    def __post_init__(self) -> None:
        windows = (
            self.volatility_window,
            self.correlation_window,
            self.drawdown_window,
            self.drawdown_velocity_lag,
            self.volume_window,
            self.annualization_days,
        )
        if any(value <= 1 for value in windows):
            raise ValueError("feature windows and annualization_days must be greater than one")
        if len(self.portfolio_weights) != len(REQUIRED_SYMBOLS):
            raise ValueError("portfolio_weights must align with REQUIRED_SYMBOLS")
        if not math.isclose(sum(self.portfolio_weights), 1.0, abs_tol=1e-12):
            raise ValueError("portfolio_weights must sum to one")

    @property
    def minimum_history(self) -> int:
        return max(
            self.drawdown_window,
            self.volatility_window,
            self.correlation_window,
            self.volume_window,
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "volatility_window": self.volatility_window,
            "correlation_window": self.correlation_window,
            "drawdown_window": self.drawdown_window,
            "drawdown_velocity_lag": self.drawdown_velocity_lag,
            "volume_window": self.volume_window,
            "annualization_days": self.annualization_days,
            "portfolio_weights": dict(zip(REQUIRED_SYMBOLS, self.portfolio_weights, strict=True)),
        }


DEFAULT_FEATURE_CONFIG = FeatureConfig()


def build_point_in_time_features(
    dataset: MarketDataset,
    config: FeatureConfig = DEFAULT_FEATURE_CONFIG,
) -> tuple[FeatureRow, ...]:
    """Build end-of-day features using slices ending at, never after, each row's date."""

    frames = dataset.frames
    returns: dict[str, list[float | None]] = {symbol: [None] for symbol in REQUIRED_SYMBOLS}
    log_volumes: dict[str, list[float]] = {symbol: [] for symbol in REQUIRED_SYMBOLS}
    portfolio_returns: list[float | None] = [None]
    portfolio_levels: list[float] = [1.0]

    for index, frame in enumerate(frames):
        for symbol in REQUIRED_SYMBOLS:
            log_volumes[symbol].append(math.log1p(frame.bars[symbol].volume))
        if index == 0:
            continue
        daily_returns: list[float] = []
        for symbol in REQUIRED_SYMBOLS:
            previous = frames[index - 1].bars[symbol].close
            current = frame.bars[symbol].close
            value = math.log(current / previous)
            returns[symbol].append(value)
            daily_returns.append(value)
        portfolio_return = sum(
            weight * value
            for weight, value in zip(config.portfolio_weights, daily_returns, strict=True)
        )
        portfolio_returns.append(portfolio_return)
        portfolio_levels.append(portfolio_levels[-1] * math.exp(portfolio_return))

    rows: list[FeatureRow] = []
    start_index = config.minimum_history
    for index in range(start_index, len(frames)):
        volatility_start = index - config.volatility_window + 1
        correlation_start = index - config.correlation_window + 1
        drawdown_start = index - config.drawdown_window + 1
        volume_start = index - config.volume_window + 1
        symbol_volatility = {
            symbol: _annualized_volatility(
                _finite_slice(returns[symbol], volatility_start, index + 1),
                config.annualization_days,
            )
            for symbol in RISK_SYMBOLS
        }
        portfolio_window = _finite_slice(
            portfolio_returns,
            volatility_start,
            index + 1,
        )
        portfolio_volatility = _annualized_volatility(
            portfolio_window,
            config.annualization_days,
        )
        correlations = [
            _correlation(
                _finite_slice(returns[left], correlation_start, index + 1),
                _finite_slice(returns[right], correlation_start, index + 1),
            )
            for left, right in (("QTECH", "QGOLD"), ("QTECH", "QWTI"), ("QGOLD", "QWTI"))
        ]
        mean_correlation = statistics.fmean(correlations)
        rolling_peak = max(portfolio_levels[drawdown_start : index + 1])
        drawdown = max(0.0, 1.0 - (portfolio_levels[index] / rolling_peak))
        velocity_index = max(drawdown_start, index - config.drawdown_velocity_lag)
        earlier_peak = max(portfolio_levels[drawdown_start : velocity_index + 1])
        earlier_drawdown = max(
            0.0,
            1.0 - (portfolio_levels[velocity_index] / earlier_peak),
        )
        drawdown_velocity = drawdown - earlier_drawdown
        today_returns = [
            _required_return(returns[symbol][index], symbol, index) for symbol in RISK_SYMBOLS
        ]
        dispersion = statistics.pstdev(today_returns)
        volume_zscores = [
            _last_zscore(log_volumes[symbol][volume_start : index + 1]) for symbol in RISK_SYMBOLS
        ]
        mean_volume_zscore = statistics.fmean(volume_zscores)
        expected_observations = config.volume_window * len(REQUIRED_SYMBOLS)
        observed = sum(
            1
            for frame in frames[volume_start : index + 1]
            for symbol in REQUIRED_SYMBOLS
            if symbol in frame.bars
        )
        missing_ratio = 1.0 - (observed / expected_observations)
        source_regimes = {bar.regime for bar in frames[index].bars.values()}
        if len(source_regimes) != 1:
            raise ValueError(f"{frames[index].observed_on}: inconsistent regime labels")
        source_regime = next(iter(source_regimes))
        if source_regime not in KNOWN_SYNTHETIC_REGIME_MAP:
            raise ValueError(f"unsupported known synthetic regime: {source_regime}")
        values = (
            symbol_volatility["QTECH"],
            symbol_volatility["QGOLD"],
            symbol_volatility["QWTI"],
            portfolio_volatility,
            mean_correlation,
            drawdown,
            drawdown_velocity,
            dispersion,
            mean_volume_zscore,
            missing_ratio,
        )
        if len(values) != len(FEATURE_SCHEMA.names) or not all(math.isfinite(v) for v in values):
            raise ValueError(f"{frames[index].observed_on}: invalid feature vector")
        rows.append(
            FeatureRow(
                as_of=frames[index].observed_on,
                max_input_date=frames[index].observed_on,
                values=values,
                known_regime=KNOWN_SYNTHETIC_REGIME_MAP[source_regime],
                source_regime=source_regime,
                is_synthetic=True,
            )
        )
    return tuple(rows)


def assert_point_in_time(rows: tuple[FeatureRow, ...]) -> None:
    """Fail closed if ordering or provenance reveals future-data leakage."""

    if not rows:
        raise ValueError("feature rows must not be empty")
    previous = None
    for row in rows:
        if row.max_input_date > row.as_of:
            raise ValueError(f"future input detected for {row.as_of}")
        if previous is not None and row.as_of <= previous:
            raise ValueError("feature rows must be strictly chronological")
        previous = row.as_of


def _finite_slice(values: list[float | None], start: int, end: int) -> list[float]:
    result = [value for value in values[start:end] if value is not None]
    if len(result) != end - start:
        raise ValueError("canonical feature window contains missing returns")
    return result


def _required_return(value: float | None, symbol: str, index: int) -> float:
    if value is None:
        raise ValueError(f"missing return for {symbol} at index {index}")
    return value


def _annualized_volatility(values: list[float], annualization_days: int) -> float:
    return statistics.pstdev(values) * math.sqrt(annualization_days)


def _correlation(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        raise ValueError("correlation inputs must have equal length >= 2")
    left_mean = statistics.fmean(left)
    right_mean = statistics.fmean(right)
    numerator = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left, right, strict=True)
    )
    left_sum = sum((value - left_mean) ** 2 for value in left)
    right_sum = sum((value - right_mean) ** 2 for value in right)
    denominator = math.sqrt(left_sum * right_sum)
    return 0.0 if denominator == 0 else numerator / denominator


def _last_zscore(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    deviation = statistics.pstdev(values)
    if deviation == 0:
        return 0.0
    return (values[-1] - statistics.fmean(values)) / deviation
