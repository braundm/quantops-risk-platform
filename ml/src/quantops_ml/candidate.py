"""Deterministic pure-Python K-Means risk-regime candidate."""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass

from quantops_ml.baseline import RuleBaseline
from quantops_ml.types import FEATURE_SCHEMA, FeatureRow, Prediction, RiskRegime

CANDIDATE_VERSION = "standardized-kmeans-v1"


@dataclass(frozen=True, slots=True)
class Standardizer:
    means: tuple[float, ...]
    scales: tuple[float, ...]

    @classmethod
    def fit(cls, rows: tuple[FeatureRow, ...]) -> Standardizer:
        if not rows:
            raise ValueError("cannot fit a standardizer without rows")
        columns = tuple(zip(*(row.values for row in rows), strict=True))
        means = tuple(statistics.fmean(column) for column in columns)
        scales = tuple(
            deviation if (deviation := statistics.pstdev(column)) > 1e-12 else 1.0
            for column in columns
        )
        return cls(means=means, scales=scales)

    def transform(self, values: tuple[float, ...]) -> tuple[float, ...]:
        if len(values) != len(self.means):
            raise ValueError("feature vector does not match fitted standardizer")
        return tuple(
            (value - mean) / scale
            for value, mean, scale in zip(values, self.means, self.scales, strict=True)
        )

    def inverse(self, values: tuple[float, ...]) -> tuple[float, ...]:
        return tuple(
            (value * scale) + mean
            for value, mean, scale in zip(values, self.means, self.scales, strict=True)
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "means": list(self.means),
            "scales": list(self.scales),
            "fit_scope": "training_partition_only",
        }


@dataclass(frozen=True, slots=True)
class CandidateConfig:
    clusters: int = 4
    max_iterations: int = 100
    tolerance: float = 1e-8

    def __post_init__(self) -> None:
        if self.clusters < 2:
            raise ValueError("clusters must be at least two")
        if self.max_iterations < 1 or self.tolerance <= 0:
            raise ValueError("max_iterations and tolerance must be positive")

    def to_mapping(self) -> dict[str, object]:
        return {
            "clusters": self.clusters,
            "max_iterations": self.max_iterations,
            "tolerance": self.tolerance,
        }


DEFAULT_CANDIDATE_CONFIG = CandidateConfig()


@dataclass(frozen=True, slots=True)
class KMeansCandidate:
    version: str
    seed: int
    config: CandidateConfig
    standardizer: Standardizer
    centroids: tuple[tuple[float, ...], ...]
    cluster_labels: tuple[RiskRegime, ...]
    distance_scales: tuple[float, ...]
    iterations: int
    training_start: str
    training_end: str

    def predict(self, row: FeatureRow | None) -> Prediction:
        if row is None or not all(math.isfinite(value) for value in row.values):
            return Prediction(
                RiskRegime.INSUFFICIENT_DATA,
                1.0,
                "candidate requires a complete finite feature vector",
            )
        transformed = self.standardizer.transform(row.values)
        cluster, distance = _nearest(transformed, self.centroids)
        scale = max(self.distance_scales[cluster], 1e-12)
        confidence = max(0.25, min(0.99, 1.0 - (distance / (2.0 * scale))))
        return Prediction(
            label=self.cluster_labels[cluster],
            confidence=confidence,
            reason=(
                "nearest standardized K-Means centroid; semantic mapping is the "
                "documented rule-baseline classification of that centroid"
            ),
            cluster_id=cluster,
        )

    def predict_many(self, rows: tuple[FeatureRow, ...]) -> tuple[Prediction, ...]:
        return tuple(self.predict(row) for row in rows)

    def to_mapping(self) -> dict[str, object]:
        return {
            "version": self.version,
            "seed": self.seed,
            "feature_schema_version": FEATURE_SCHEMA.version,
            "config": self.config.to_mapping(),
            "standardizer": self.standardizer.to_mapping(),
            "centroids": [list(centroid) for centroid in self.centroids],
            "cluster_labels": [label.value for label in self.cluster_labels],
            "distance_scales": list(self.distance_scales),
            "iterations": self.iterations,
            "training_window": {
                "start": self.training_start,
                "end": self.training_end,
            },
            "mapping_policy": "centroid_features_classified_by_rule-baseline-v1",
            "intended_use": "risk-regime classification only",
        }


def fit_candidate(
    rows: tuple[FeatureRow, ...],
    seed: int,
    baseline: RuleBaseline,
    config: CandidateConfig = DEFAULT_CANDIDATE_CONFIG,
) -> KMeansCandidate:
    """Fit on one chronological training partition with seed-local random state."""

    if len(rows) < config.clusters:
        raise ValueError("training rows must be at least the requested number of clusters")
    standardizer = Standardizer.fit(rows)
    points = tuple(standardizer.transform(row.values) for row in rows)
    centroids = _initialize_kmeans_plus_plus(points, config.clusters, seed)
    iterations = 0
    assignments: tuple[int, ...] = ()
    for iteration in range(1, config.max_iterations + 1):
        assignments = tuple(_nearest(point, centroids)[0] for point in points)
        next_centroids = _recompute_centroids(points, assignments, centroids)
        movement = max(
            _distance(left, right) for left, right in zip(centroids, next_centroids, strict=True)
        )
        centroids = next_centroids
        iterations = iteration
        if movement <= config.tolerance:
            break

    assignments = tuple(_nearest(point, centroids)[0] for point in points)
    labels: list[RiskRegime] = []
    scales: list[float] = []
    for cluster, centroid in enumerate(centroids):
        raw_centroid = standardizer.inverse(centroid)
        centroid_row = FeatureRow(
            as_of=rows[-1].as_of,
            max_input_date=rows[-1].as_of,
            values=raw_centroid,
            known_regime=RiskRegime.NORMAL,
            source_regime="unsupervised_centroid",
            is_synthetic=True,
        )
        label = baseline.classify(centroid_row).label
        if label is RiskRegime.INSUFFICIENT_DATA:
            label = RiskRegime.NORMAL
        labels.append(label)
        distances = sorted(
            _distance(point, centroid)
            for point, assignment in zip(points, assignments, strict=True)
            if assignment == cluster
        )
        scales.append(_quantile(distances, 0.90) if distances else 1.0)

    return KMeansCandidate(
        version=CANDIDATE_VERSION,
        seed=seed,
        config=config,
        standardizer=standardizer,
        centroids=centroids,
        cluster_labels=tuple(labels),
        distance_scales=tuple(scales),
        iterations=iterations,
        training_start=rows[0].as_of.isoformat(),
        training_end=rows[-1].as_of.isoformat(),
    )


def _initialize_kmeans_plus_plus(
    points: tuple[tuple[float, ...], ...],
    clusters: int,
    seed: int,
) -> tuple[tuple[float, ...], ...]:
    generator = random.Random(seed)  # noqa: S311 - deterministic model initialization, not security
    first_index = generator.randrange(len(points))
    selected = {first_index}
    centroids = [points[first_index]]
    while len(centroids) < clusters:
        distances = [min(_distance(point, center) ** 2 for center in centroids) for point in points]
        total = sum(distances)
        if total <= 0:
            next_index = next(index for index in range(len(points)) if index not in selected)
        else:
            threshold = generator.random() * total
            cumulative = 0.0
            next_index = len(points) - 1
            for index, weight in enumerate(distances):
                cumulative += weight
                if cumulative >= threshold:
                    next_index = index
                    break
            if next_index in selected:
                next_index = max(
                    (index for index in range(len(points)) if index not in selected),
                    key=lambda index: (distances[index], -index),
                )
        selected.add(next_index)
        centroids.append(points[next_index])
    return tuple(centroids)


def _recompute_centroids(
    points: tuple[tuple[float, ...], ...],
    assignments: tuple[int, ...],
    previous: tuple[tuple[float, ...], ...],
) -> tuple[tuple[float, ...], ...]:
    result: list[tuple[float, ...]] = []
    for cluster, previous_centroid in enumerate(previous):
        members = [
            point
            for point, assignment in zip(points, assignments, strict=True)
            if assignment == cluster
        ]
        if not members:
            result.append(previous_centroid)
            continue
        columns = tuple(zip(*members, strict=True))
        result.append(tuple(statistics.fmean(column) for column in columns))
    return tuple(result)


def _nearest(
    point: tuple[float, ...],
    centroids: tuple[tuple[float, ...], ...],
) -> tuple[int, float]:
    candidates = tuple((index, _distance(point, center)) for index, center in enumerate(centroids))
    return min(candidates, key=lambda item: (item[1], item[0]))


def _distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return math.sqrt(
        sum(
            (left_value - right_value) ** 2
            for left_value, right_value in zip(left, right, strict=True)
        )
    )


def _quantile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("quantile values must not be empty")
    if len(values) == 1:
        return max(values[0], 1e-12)
    position = (len(values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return max(values[lower], 1e-12)
    weight = position - lower
    return max((values[lower] * (1.0 - weight)) + (values[upper] * weight), 1e-12)
