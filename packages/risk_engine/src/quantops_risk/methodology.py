"""Version metadata embedded in all externally meaningful estimates."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

METHODOLOGY_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class MethodologyMetadata:
    """Stable, serializable methodology identity and global sign conventions."""

    version: str = METHODOLOGY_VERSION
    return_price_basis: str = "close_to_close"
    var_loss_convention: str = "nonnegative_amount_is_loss"
    volatility_estimator: str = "sample_standard_deviation_ddof_1"
    covariance_estimator: str = "sample_covariance_ddof_1"
    annualization_rule: str = "daily_volatility_times_sqrt_periods_per_year"

    def to_json(self) -> str:
        """Serialize with stable key order for manifests and snapshots."""

        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


def methodology_metadata() -> MethodologyMetadata:
    """Return the immutable metadata carried by version 1 calculations."""

    return MethodologyMetadata()
