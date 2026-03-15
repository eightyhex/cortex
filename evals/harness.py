"""
Cortex Retrieval Eval Harness

Runs annotated query -> expected-results pairs against the query pipeline
and computes MRR@10, Precision@5, NDCG@10.

See docs/02-ARCHITECTURE.md § 8a for full design.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.metrics import mrr_at_k, ndcg_at_k, precision_at_k

from cortex.query.pipeline import QueryPipeline, QueryResult


@dataclass
class EvalCase:
    """A single eval case from the golden dataset."""

    id: str
    query: str
    category: str
    expected_notes: list[str]
    tags: list[str] = field(default_factory=list)


@dataclass
class CaseResult:
    """Result of running a single eval case."""

    case_id: str
    query: str
    passed: bool
    returned_ids: list[str] = field(default_factory=list)
    expected_ids: list[str] = field(default_factory=list)
    mrr: float = 0.0
    precision: float = 0.0
    ndcg: float = 0.0
    error: str = ""


@dataclass
class EvalReport:
    """Aggregated results from running the eval suite."""

    timestamp: str
    total_cases: int
    passed: int
    failed: int
    metrics: dict[str, float] = field(default_factory=dict)
    failed_cases: list[CaseResult] = field(default_factory=list)

    def save_snapshot(self, path: Path) -> Path:
        """Save report as versioned JSON snapshot.

        Returns the path to the saved snapshot file.
        """
        path.mkdir(parents=True, exist_ok=True)
        # Find next version number
        existing = sorted(path.glob("snapshot_v*.json"))
        if existing:
            last = existing[-1].stem  # e.g. "snapshot_v003"
            last_num = int(last.split("_v")[1])
            version = last_num + 1
        else:
            version = 0
        filename = f"snapshot_v{version:03d}.json"
        filepath = path / filename
        filepath.write_text(json.dumps(self._to_dict(), indent=2))
        return filepath

    def compare_to(self, previous: EvalReport) -> dict[str, Any]:
        """Compare this report to a previous one. Flag regressions > 0.05.

        Returns a dict with:
          - regressions: list of {metric, previous, current, delta}
          - improved: list of {metric, previous, current, delta}
          - has_regression: bool
        """
        regressions: list[dict[str, Any]] = []
        improved: list[dict[str, Any]] = []

        for metric_name in self.metrics:
            current_val = self.metrics.get(metric_name, 0.0)
            previous_val = previous.metrics.get(metric_name, 0.0)
            delta = current_val - previous_val

            entry = {
                "metric": metric_name,
                "previous": round(previous_val, 4),
                "current": round(current_val, 4),
                "delta": round(delta, 4),
            }

            if delta < -0.05:
                regressions.append(entry)
            elif delta > 0.05:
                improved.append(entry)

        return {
            "regressions": regressions,
            "improved": improved,
            "has_regression": len(regressions) > 0,
        }

    def _to_dict(self) -> dict[str, Any]:
        """Convert report to a JSON-serializable dict."""
        return {
            "timestamp": self.timestamp,
            "total_cases": self.total_cases,
            "passed": self.passed,
            "failed": self.failed,
            "metrics": self.metrics,
            "failed_cases": [
                {
                    "case_id": c.case_id,
                    "query": c.query,
                    "passed": c.passed,
                    "returned_ids": c.returned_ids,
                    "expected_ids": c.expected_ids,
                    "mrr": c.mrr,
                    "precision": c.precision,
                    "ndcg": c.ndcg,
                    "error": c.error,
                }
                for c in self.failed_cases
            ],
        }

    @classmethod
    def from_snapshot(cls, filepath: Path) -> EvalReport:
        """Load an EvalReport from a snapshot JSON file."""
        data = json.loads(filepath.read_text())
        failed_cases = [
            CaseResult(
                case_id=c["case_id"],
                query=c["query"],
                passed=c["passed"],
                returned_ids=c.get("returned_ids", []),
                expected_ids=c.get("expected_ids", []),
                mrr=c.get("mrr", 0.0),
                precision=c.get("precision", 0.0),
                ndcg=c.get("ndcg", 0.0),
                error=c.get("error", ""),
            )
            for c in data.get("failed_cases", [])
        ]
        return cls(
            timestamp=data["timestamp"],
            total_cases=data["total_cases"],
            passed=data["passed"],
            failed=data["failed"],
            metrics=data.get("metrics", {}),
            failed_cases=failed_cases,
        )


class EvalHarness:
    """Run retrieval evals against a query pipeline and score the results."""

    def __init__(self, pipeline: QueryPipeline, dataset_path: Path) -> None:
        self._pipeline = pipeline
        self._cases = self._load_dataset(dataset_path)

    def _load_dataset(self, dataset_path: Path) -> list[EvalCase]:
        """Load and parse the golden dataset JSON."""
        data = json.loads(dataset_path.read_text())
        cases = []
        for raw in data.get("cases", []):
            cases.append(
                EvalCase(
                    id=raw["id"],
                    query=raw["query"],
                    category=raw.get("category", ""),
                    expected_notes=raw.get("expected_notes", []),
                    tags=raw.get("tags", []),
                )
            )
        return cases

    def run_all(self) -> EvalReport:
        """Execute all cases and compute aggregate metrics."""
        return self._run_cases(self._cases)

    def run_tagged(self, tags: list[str]) -> EvalReport:
        """Run only cases matching any of the given tags."""
        tag_set = set(tags)
        filtered = [c for c in self._cases if tag_set & set(c.tags)]
        return self._run_cases(filtered)

    def _run_cases(self, cases: list[EvalCase]) -> EvalReport:
        """Run a list of cases and build the report."""
        results: list[CaseResult] = []
        for case in cases:
            result = self._execute_case(case)
            results.append(result)

        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        failed_cases = [r for r in results if not r.passed]

        # Aggregate metrics
        if results:
            avg_mrr = sum(r.mrr for r in results) / len(results)
            avg_precision = sum(r.precision for r in results) / len(results)
            avg_ndcg = sum(r.ndcg for r in results) / len(results)
        else:
            avg_mrr = avg_precision = avg_ndcg = 0.0

        return EvalReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_cases=len(results),
            passed=passed,
            failed=failed,
            metrics={
                "mrr@10": round(avg_mrr, 4),
                "precision@5": round(avg_precision, 4),
                "ndcg@10": round(avg_ndcg, 4),
            },
            failed_cases=failed_cases,
        )

    def _execute_case(self, case: EvalCase) -> CaseResult:
        """Run a single eval case through the pipeline."""
        try:
            query_result: QueryResult = asyncio.get_event_loop().run_until_complete(
                self._pipeline.execute(case.query)
            )
        except RuntimeError:
            # If no event loop exists, create one
            loop = asyncio.new_event_loop()
            try:
                query_result = loop.run_until_complete(
                    self._pipeline.execute(case.query)
                )
            finally:
                loop.close()
        except Exception as e:
            return CaseResult(
                case_id=case.id,
                query=case.query,
                passed=False,
                expected_ids=case.expected_notes,
                error=str(e),
            )

        returned_ids = [r.note_id for r in query_result.results]
        expected_set = set(case.expected_notes)

        # Compute per-case metrics
        mrr = mrr_at_k(returned_ids, case.expected_notes, k=10)
        precision = precision_at_k(returned_ids, case.expected_notes, k=5)
        ndcg = ndcg_at_k(returned_ids, case.expected_notes, k=10)

        # A case passes if at least one expected note appears in results
        hit = bool(expected_set & set(returned_ids))

        return CaseResult(
            case_id=case.id,
            query=case.query,
            passed=hit,
            returned_ids=returned_ids,
            expected_ids=case.expected_notes,
            mrr=mrr,
            precision=precision,
            ndcg=ndcg,
        )
