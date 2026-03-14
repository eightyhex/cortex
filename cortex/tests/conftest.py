"""
Shared pytest fixtures for Cortex tests.

Key fixtures (implemented in Session 2+):
- test_vault: temporary 50-note vault across all note types with known relationships
- test_index: pre-built DuckDB + LanceDB indexes over test_vault
- test_graph: pre-built NetworkX graph over test_vault

See docs/02-ARCHITECTURE.md § 8 (Testing Strategy) for fixture design.
"""
import pytest

# TODO: Implement fixtures as sessions progress
