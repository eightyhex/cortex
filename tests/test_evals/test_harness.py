"""Tests for the eval harness and report."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from evals.harness import CaseResult, EvalCase, EvalHarness, EvalReport
from cortex.query.pipeline import QueryResult, RankedResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_dataset(tmp_path: Path, cases: list[dict]) -> Path:
    """Write a golden dataset JSON and return its path."""
    ds_path = tmp_path / "dataset.json"
    ds_path.write_text(json.dumps({"version": "0.1", "cases": cases}))
    return ds_path


def _make_pipeline(results_map: dict[str, list[str]]) -> MagicMock:
    """Create a mock pipeline that returns specified note IDs per query."""
    pipeline = MagicMock()

    async def mock_execute(query: str, limit: int = 10) -> QueryResult:
        ids = results_map.get(query, [])
        ranked = [
            RankedResult(note_id=nid, title=nid, score=1.0 / (i + 1), matched_by=["lexical"])
            for i, nid in enumerate(ids)
        ]
        return QueryResult(query=query, results=ranked, context="", explanation="")

    pipeline.execute = mock_execute
    return pipeline


CASES_BASIC = [
    {
        "id": "q001",
        "query": "caching strategies",
        "category": "semantic",
        "expected_notes": ["note-a", "note-b"],
        "tags": ["retrieval"],
    },
    {
        "id": "q002",
        "query": "database indexing",
        "category": "keyword",
        "expected_notes": ["note-c"],
        "tags": ["keyword"],
    },
]


# ---------------------------------------------------------------------------
# EvalHarness tests
# ---------------------------------------------------------------------------

class TestEvalHarness:
    def test_load_dataset(self, tmp_path: Path) -> None:
        ds = _make_dataset(tmp_path, CASES_BASIC)
        pipeline = _make_pipeline({})
        harness = EvalHarness(pipeline, ds)
        assert len(harness._cases) == 2
        assert harness._cases[0].id == "q001"

    def test_run_all_all_pass(self, tmp_path: Path) -> None:
        ds = _make_dataset(tmp_path, CASES_BASIC)
        pipeline = _make_pipeline({
            "caching strategies": ["note-a", "note-b"],
            "database indexing": ["note-c", "note-d"],
        })
        harness = EvalHarness(pipeline, ds)
        report = harness.run_all()
        assert report.total_cases == 2
        assert report.passed == 2
        assert report.failed == 0
        assert len(report.failed_cases) == 0

    def test_run_all_some_fail(self, tmp_path: Path) -> None:
        ds = _make_dataset(tmp_path, CASES_BASIC)
        pipeline = _make_pipeline({
            "caching strategies": ["note-a"],
            "database indexing": ["note-x"],  # note-c not returned
        })
        harness = EvalHarness(pipeline, ds)
        report = harness.run_all()
        assert report.passed == 1
        assert report.failed == 1
        assert len(report.failed_cases) == 1
        assert report.failed_cases[0].case_id == "q002"

    def test_run_tagged(self, tmp_path: Path) -> None:
        ds = _make_dataset(tmp_path, CASES_BASIC)
        pipeline = _make_pipeline({
            "caching strategies": ["note-a"],
        })
        harness = EvalHarness(pipeline, ds)
        report = harness.run_tagged(["keyword"])
        assert report.total_cases == 1
        assert report.failed_cases[0].case_id == "q002"

    def test_metrics_computed(self, tmp_path: Path) -> None:
        ds = _make_dataset(tmp_path, CASES_BASIC)
        pipeline = _make_pipeline({
            "caching strategies": ["note-a", "note-b"],
            "database indexing": ["note-c"],
        })
        harness = EvalHarness(pipeline, ds)
        report = harness.run_all()
        assert "mrr@10" in report.metrics
        assert "precision@5" in report.metrics
        assert "ndcg@10" in report.metrics
        # All expected notes found at top, MRR should be 1.0
        assert report.metrics["mrr@10"] == 1.0

    def test_empty_dataset(self, tmp_path: Path) -> None:
        ds = _make_dataset(tmp_path, [])
        pipeline = _make_pipeline({})
        harness = EvalHarness(pipeline, ds)
        report = harness.run_all()
        assert report.total_cases == 0
        assert report.passed == 0
        assert report.metrics["mrr@10"] == 0.0

    def test_case_result_has_returned_ids(self, tmp_path: Path) -> None:
        ds = _make_dataset(tmp_path, CASES_BASIC[:1])
        pipeline = _make_pipeline({
            "caching strategies": ["note-a", "note-x"],
        })
        harness = EvalHarness(pipeline, ds)
        report = harness.run_all()
        # The single case passes (note-a is expected and returned)
        assert report.passed == 1


# ---------------------------------------------------------------------------
# EvalReport tests
# ---------------------------------------------------------------------------

class TestEvalReport:
    def test_save_snapshot(self, tmp_path: Path) -> None:
        report = EvalReport(
            timestamp="2026-03-15T00:00:00Z",
            total_cases=5,
            passed=4,
            failed=1,
            metrics={"mrr@10": 0.8, "precision@5": 0.6, "ndcg@10": 0.7},
            failed_cases=[
                CaseResult(case_id="q005", query="test", passed=False),
            ],
        )
        snap_dir = tmp_path / "snapshots"
        filepath = report.save_snapshot(snap_dir)
        assert filepath.exists()
        assert filepath.name == "snapshot_v000.json"
        data = json.loads(filepath.read_text())
        assert data["total_cases"] == 5
        assert data["metrics"]["mrr@10"] == 0.8

    def test_save_snapshot_increments_version(self, tmp_path: Path) -> None:
        snap_dir = tmp_path / "snapshots"
        report = EvalReport(
            timestamp="2026-03-15T00:00:00Z",
            total_cases=1,
            passed=1,
            failed=0,
            metrics={"mrr@10": 0.9},
        )
        p1 = report.save_snapshot(snap_dir)
        p2 = report.save_snapshot(snap_dir)
        assert p1.name == "snapshot_v000.json"
        assert p2.name == "snapshot_v001.json"

    def test_compare_to_no_regression(self) -> None:
        prev = EvalReport(
            timestamp="t0", total_cases=1, passed=1, failed=0,
            metrics={"mrr@10": 0.8, "precision@5": 0.6},
        )
        curr = EvalReport(
            timestamp="t1", total_cases=1, passed=1, failed=0,
            metrics={"mrr@10": 0.82, "precision@5": 0.62},
        )
        comparison = curr.compare_to(prev)
        assert comparison["has_regression"] is False
        assert len(comparison["regressions"]) == 0

    def test_compare_to_with_regression(self) -> None:
        prev = EvalReport(
            timestamp="t0", total_cases=1, passed=1, failed=0,
            metrics={"mrr@10": 0.9, "precision@5": 0.7},
        )
        curr = EvalReport(
            timestamp="t1", total_cases=1, passed=1, failed=0,
            metrics={"mrr@10": 0.8, "precision@5": 0.7},  # MRR dropped 0.1
        )
        comparison = curr.compare_to(prev)
        assert comparison["has_regression"] is True
        assert len(comparison["regressions"]) == 1
        assert comparison["regressions"][0]["metric"] == "mrr@10"

    def test_compare_to_with_improvement(self) -> None:
        prev = EvalReport(
            timestamp="t0", total_cases=1, passed=1, failed=0,
            metrics={"mrr@10": 0.5},
        )
        curr = EvalReport(
            timestamp="t1", total_cases=1, passed=1, failed=0,
            metrics={"mrr@10": 0.9},
        )
        comparison = curr.compare_to(prev)
        assert comparison["has_regression"] is False
        assert len(comparison["improved"]) == 1

    def test_from_snapshot(self, tmp_path: Path) -> None:
        report = EvalReport(
            timestamp="2026-03-15T00:00:00Z",
            total_cases=3,
            passed=2,
            failed=1,
            metrics={"mrr@10": 0.75},
            failed_cases=[
                CaseResult(case_id="q003", query="test q", passed=False, mrr=0.0),
            ],
        )
        snap_dir = tmp_path / "snapshots"
        filepath = report.save_snapshot(snap_dir)
        loaded = EvalReport.from_snapshot(filepath)
        assert loaded.total_cases == 3
        assert loaded.passed == 2
        assert loaded.metrics["mrr@10"] == 0.75
        assert len(loaded.failed_cases) == 1
        assert loaded.failed_cases[0].case_id == "q003"


# ---------------------------------------------------------------------------
# Golden dataset validation
# ---------------------------------------------------------------------------

class TestGoldenDataset:
    def test_golden_dataset_loads(self) -> None:
        ds_path = Path(__file__).parent.parent.parent / "evals" / "golden_dataset.json"
        data = json.loads(ds_path.read_text())
        assert "cases" in data
        assert len(data["cases"]) >= 20

    def test_eval_snapshot_v0_v1_no_regression(self, tmp_path: Path) -> None:
        """Simulate v0 (baseline) and v1 (with reranker) eval runs; verify no regression."""
        # v0 baseline
        pipeline_v0 = _make_pipeline({
            "caching strategies": ["note-a", "note-b"],
            "database indexing": ["note-c"],
        })
        ds = _make_dataset(tmp_path, CASES_BASIC)
        harness_v0 = EvalHarness(pipeline_v0, ds)
        report_v0 = harness_v0.run_all()
        snap_dir = tmp_path / "snapshots"
        p0 = report_v0.save_snapshot(snap_dir)
        assert p0.name == "snapshot_v000.json"

        # v1 with reranker (same or better results)
        pipeline_v1 = _make_pipeline({
            "caching strategies": ["note-a", "note-b"],
            "database indexing": ["note-c"],
        })
        harness_v1 = EvalHarness(pipeline_v1, ds)
        report_v1 = harness_v1.run_all()
        p1 = report_v1.save_snapshot(snap_dir)
        assert p1.name == "snapshot_v001.json"

        # Compare: no regression
        comparison = report_v1.compare_to(report_v0)
        assert comparison["has_regression"] is False

    def test_golden_dataset_cases_have_required_fields(self) -> None:
        ds_path = Path(__file__).parent.parent.parent / "evals" / "golden_dataset.json"
        data = json.loads(ds_path.read_text())
        categories = set()
        for case in data["cases"]:
            assert "id" in case
            assert "query" in case
            assert "category" in case
            assert "expected_notes" in case
            assert len(case["expected_notes"]) > 0
            categories.add(case["category"])
        # Must cover all four categories
        assert "keyword" in categories
        assert "semantic" in categories
        assert "relational" in categories
        assert "temporal" in categories
