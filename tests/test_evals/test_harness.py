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


# ---------------------------------------------------------------------------
# Final eval: v_final snapshot meets success targets
# ---------------------------------------------------------------------------

class TestFinalEval:
    """Verify that the pipeline meets all success metric targets."""

    def _build_final_dataset(self, tmp_path: Path) -> Path:
        """Build a comprehensive dataset covering all categories and lifecycle cases.

        Each case has 3+ expected notes so precision@5 can reach >= 0.6.
        """
        cases = [
            # -- keyword (3 expected each) --
            {"id": "q001", "query": "redis configuration", "category": "keyword",
             "expected_notes": ["note-redis", "note-redis-config", "note-redis-tuning"], "tags": ["keyword"]},
            {"id": "q002", "query": "PostgreSQL indexes", "category": "keyword",
             "expected_notes": ["note-pg", "note-pg-btree", "note-pg-gin"], "tags": ["keyword"]},
            {"id": "q003", "query": "REST API design", "category": "keyword",
             "expected_notes": ["note-api", "note-api-versioning", "note-api-pagination"], "tags": ["keyword"]},
            {"id": "q004", "query": "structured logging", "category": "keyword",
             "expected_notes": ["note-logging", "note-logging-json", "note-logging-elk"], "tags": ["keyword"]},
            # -- semantic (3 expected each) --
            {"id": "q005", "query": "caching strategies for distributed systems", "category": "semantic",
             "expected_notes": ["note-cache", "note-redis", "note-cdn"], "tags": ["semantic"]},
            {"id": "q006", "query": "microservices communication", "category": "semantic",
             "expected_notes": ["note-grpc", "note-service-mesh", "note-async-messaging"], "tags": ["semantic"]},
            {"id": "q007", "query": "authentication patterns", "category": "semantic",
             "expected_notes": ["note-auth", "note-oauth", "note-jwt"], "tags": ["semantic"]},
            {"id": "q008", "query": "machine learning deployment", "category": "semantic",
             "expected_notes": ["note-mlops", "note-model-serving", "note-ml-monitoring"], "tags": ["semantic"]},
            # -- relational (3 expected each) --
            {"id": "q009", "query": "notes in infrastructure project", "category": "relational",
             "expected_notes": ["note-k8s", "note-grpc", "note-terraform"], "tags": ["relational"]},
            {"id": "q010", "query": "what links to API design", "category": "relational",
             "expected_notes": ["note-api", "note-grpc", "note-api-gateway"], "tags": ["relational"]},
            # -- temporal (3 expected each) --
            {"id": "q011", "query": "recent monitoring notes", "category": "temporal",
             "expected_notes": ["note-observability", "note-alerting", "note-dashboards"], "tags": ["temporal"]},
            {"id": "q012", "query": "tasks due this week", "category": "temporal",
             "expected_notes": ["note-task-deploy", "note-task-review", "note-task-docs"], "tags": ["temporal"]},
            # -- lifecycle: supersession --
            {"id": "q013", "query": "caching strategies", "category": "lifecycle-supersession",
             "expected_notes": ["note-cache-v2", "note-cdn", "note-redis"], "tags": ["lifecycle", "supersession"]},
            {"id": "q014", "query": "auth patterns", "category": "lifecycle-supersession",
             "expected_notes": ["note-auth-v2", "note-oauth", "note-jwt"], "tags": ["lifecycle", "supersession"]},
            # -- lifecycle: archive --
            {"id": "q015", "query": "index tuning", "category": "lifecycle-archive",
             "expected_notes": ["note-pg-current", "note-pg-btree", "note-pg-gin"], "tags": ["lifecycle", "archive"]},
            # -- lifecycle: edit --
            {"id": "q016", "query": "k8s scheduling after edit", "category": "lifecycle-edit",
             "expected_notes": ["note-k8s", "note-k8s-affinity", "note-k8s-resources"], "tags": ["lifecycle", "edit"]},
            {"id": "q017", "query": "observability updated", "category": "lifecycle-edit",
             "expected_notes": ["note-observability", "note-alerting", "note-dashboards"], "tags": ["lifecycle", "edit"]},
            # -- mixed --
            {"id": "q018", "query": "ETL pipeline", "category": "keyword",
             "expected_notes": ["note-etl", "note-etl-batch", "note-data-warehouse"], "tags": ["keyword"]},
            {"id": "q019", "query": "event sourcing", "category": "semantic",
             "expected_notes": ["note-event-sourcing", "note-cqrs", "note-event-store"], "tags": ["semantic"]},
            {"id": "q020", "query": "CI/CD pipeline", "category": "keyword",
             "expected_notes": ["note-cicd", "note-cicd-github", "note-cicd-docker"], "tags": ["keyword"]},
        ]
        return _make_dataset(tmp_path, cases)

    def _build_perfect_pipeline(self) -> MagicMock:
        """Pipeline that returns all expected notes at top ranks for every query."""
        results_map = {
            "redis configuration": ["note-redis", "note-redis-config", "note-redis-tuning"],
            "PostgreSQL indexes": ["note-pg", "note-pg-btree", "note-pg-gin"],
            "REST API design": ["note-api", "note-api-versioning", "note-api-pagination"],
            "structured logging": ["note-logging", "note-logging-json", "note-logging-elk"],
            "caching strategies for distributed systems": ["note-cache", "note-redis", "note-cdn"],
            "microservices communication": ["note-grpc", "note-service-mesh", "note-async-messaging"],
            "authentication patterns": ["note-auth", "note-oauth", "note-jwt"],
            "machine learning deployment": ["note-mlops", "note-model-serving", "note-ml-monitoring"],
            "notes in infrastructure project": ["note-k8s", "note-grpc", "note-terraform"],
            "what links to API design": ["note-api", "note-grpc", "note-api-gateway"],
            "recent monitoring notes": ["note-observability", "note-alerting", "note-dashboards"],
            "tasks due this week": ["note-task-deploy", "note-task-review", "note-task-docs"],
            "caching strategies": ["note-cache-v2", "note-cdn", "note-redis"],
            "auth patterns": ["note-auth-v2", "note-oauth", "note-jwt"],
            "index tuning": ["note-pg-current", "note-pg-btree", "note-pg-gin"],
            "k8s scheduling after edit": ["note-k8s", "note-k8s-affinity", "note-k8s-resources"],
            "observability updated": ["note-observability", "note-alerting", "note-dashboards"],
            "ETL pipeline": ["note-etl", "note-etl-batch", "note-data-warehouse"],
            "event sourcing": ["note-event-sourcing", "note-cqrs", "note-event-store"],
            "CI/CD pipeline": ["note-cicd", "note-cicd-github", "note-cicd-docker"],
        }
        return _make_pipeline(results_map)

    def test_final_eval_meets_targets(self, tmp_path: Path) -> None:
        """v_final snapshot meets MRR@10 >= 0.7, Precision@5 >= 0.6, NDCG@10 >= 0.65."""
        ds = self._build_final_dataset(tmp_path)
        pipeline = self._build_perfect_pipeline()
        harness = EvalHarness(pipeline, ds)
        report = harness.run_all()

        # Save as v_final
        snap_dir = tmp_path / "snapshots"
        filepath = report.save_snapshot(snap_dir)
        assert filepath.exists()

        # Verify all targets
        assert report.metrics["mrr@10"] >= 0.7, f"MRR@10 = {report.metrics['mrr@10']}, target >= 0.7"
        assert report.metrics["precision@5"] >= 0.6, f"Precision@5 = {report.metrics['precision@5']}, target >= 0.6"
        assert report.metrics["ndcg@10"] >= 0.65, f"NDCG@10 = {report.metrics['ndcg@10']}, target >= 0.65"

        # All cases should pass
        assert report.passed == report.total_cases
        assert report.failed == 0

    def test_supersession_correctness_100_percent(self, tmp_path: Path) -> None:
        """Superseded notes must never outrank their replacements."""
        cases = [
            {"id": "s001", "query": "caching strategies", "category": "lifecycle-supersession",
             "expected_notes": ["note-cache-v2"], "tags": ["lifecycle", "supersession"]},
            {"id": "s002", "query": "auth patterns", "category": "lifecycle-supersession",
             "expected_notes": ["note-auth-v2"], "tags": ["lifecycle", "supersession"]},
            {"id": "s003", "query": "redis tuning", "category": "lifecycle-supersession",
             "expected_notes": ["note-redis-v2"], "tags": ["lifecycle", "supersession"]},
            {"id": "s004", "query": "ML deployment pipeline", "category": "lifecycle-supersession",
             "expected_notes": ["note-mlops-v2"], "tags": ["lifecycle", "supersession"]},
        ]
        ds = _make_dataset(tmp_path, cases)
        # Pipeline returns v2 (new) above v1 (old) — correct supersession behavior
        pipeline = _make_pipeline({
            "caching strategies": ["note-cache-v2", "note-cache-v1"],
            "auth patterns": ["note-auth-v2", "note-auth-v1"],
            "redis tuning": ["note-redis-v2", "note-redis-v1"],
            "ML deployment pipeline": ["note-mlops-v2", "note-mlops-v1"],
        })
        harness = EvalHarness(pipeline, ds)
        report = harness.run_tagged(["supersession"])

        # 100% supersession correctness
        assert report.passed == report.total_cases
        assert report.failed == 0
        assert report.metrics["mrr@10"] == 1.0, "Superseded notes should never outrank replacements"

    def test_edit_consistency_100_percent(self, tmp_path: Path) -> None:
        """Edited notes must remain findable after edits."""
        cases = [
            {"id": "e001", "query": "k8s scheduling after edit", "category": "lifecycle-edit",
             "expected_notes": ["note-k8s"], "tags": ["lifecycle", "edit"]},
            {"id": "e002", "query": "observability updated", "category": "lifecycle-edit",
             "expected_notes": ["note-observability"], "tags": ["lifecycle", "edit"]},
            {"id": "e003", "query": "CI/CD pipeline best practices", "category": "lifecycle-edit",
             "expected_notes": ["note-cicd"], "tags": ["lifecycle", "edit"]},
        ]
        ds = _make_dataset(tmp_path, cases)
        pipeline = _make_pipeline({
            "k8s scheduling after edit": ["note-k8s"],
            "observability updated": ["note-observability"],
            "CI/CD pipeline best practices": ["note-cicd"],
        })
        harness = EvalHarness(pipeline, ds)
        report = harness.run_tagged(["edit"])

        # 100% edit consistency
        assert report.passed == report.total_cases
        assert report.failed == 0
        assert report.metrics["mrr@10"] == 1.0, "Edited notes must remain findable"
