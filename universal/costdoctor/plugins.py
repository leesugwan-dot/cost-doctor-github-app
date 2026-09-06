from __future__ import annotations

from typing import Any, Protocol


class ProviderAdapterPlugin(Protocol):
    def normalize_usage(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def health_check(self) -> dict[str, Any]: ...


class PricingSourcePlugin(Protocol):
    def select(self, provider: str, model: str, occurred_at: str) -> dict[str, Any] | None: ...


class UsageImporterPlugin(Protocol):
    def normalize_records(self, records: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]: ...


class DetectorPlugin(Protocol):
    def __call__(self, events: list[dict[str, Any]], registry: Any) -> list[dict[str, Any]]: ...


class QualityEvaluatorPlugin(Protocol):
    def __call__(self, before: list[float], after: list[float], threshold: float) -> dict[str, Any]: ...


class BenchmarkWorkloadPlugin(Protocol):
    def __call__(self, specification: dict[str, Any], strategy: dict[str, Any]) -> list[dict[str, Any]]: ...


class ReportRendererPlugin(Protocol):
    def __call__(self, packet: dict[str, Any], validation: dict[str, Any], language: str) -> str: ...


class ValidatorPlugin(Protocol):
    def __call__(self, packet: dict[str, Any]) -> dict[str, Any]: ...


PLUGIN_BOUNDARIES = (
    "provider_adapter",
    "pricing_source",
    "usage_importer",
    "detector",
    "quality_evaluator",
    "benchmark_workload",
    "report_renderer",
    "validator",
)
