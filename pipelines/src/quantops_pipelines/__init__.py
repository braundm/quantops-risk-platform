"""Deterministic, offline data pipelines for the QuantOps demo."""

from quantops_pipelines.generator import (
    GenerationResult,
    GeneratorConfig,
    generate_dataset,
    load_config,
    verify_dataset,
)

__all__ = [
    "GenerationResult",
    "GeneratorConfig",
    "generate_dataset",
    "load_config",
    "verify_dataset",
]

__version__ = "0.1.0"
