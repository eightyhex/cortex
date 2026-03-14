# Cortex development tasks
# Run with: just <task>
# List all tasks: just --list

set dotenv-load

# Default task
default:
    @just --list

# Python environment setup
setup:
    uv sync
    pre-commit install

# Development server
dev:
    uv run cortex

# Run tests
test:
    uv run pytest tests/ -v

# Run tests with coverage
test-cov:
    uv run pytest tests/ --cov=src/cortex --cov-report=html

# Run linting
lint:
    uv run ruff check src/ tests/
    uv run black --check src/ tests/

# Run type checking
type-check:
    uv run mypy src/cortex

# Format code
fmt:
    uv run black src/ tests/
    uv run ruff check --fix src/ tests/

# Run eval suite
eval:
    uv run python -m pytest evals/ -v

# Rebuild indexes from vault
rebuild-index:
    uv run cortex-rebuild

# Rebuild indexes + run evals
build-and-eval: rebuild-index eval

# Docker tasks
docker-build:
    docker compose build

docker-up:
    docker compose up

docker-down:
    docker compose down

docker-rebuild-index:
    docker compose exec -T cortex uv run cortex-rebuild

docker-eval:
    docker compose exec -T cortex uv run python -m pytest evals/ -v

# Clean build artifacts
clean:
    rm -rf build/ dist/ *.egg-info/
    find . -type d -name __pycache__ -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete
    rm -rf .pytest_cache/ .coverage htmlcov/ .mypy_cache/

# Clean everything including data
clean-all: clean
    rm -rf data/ vault/00-inbox/* vault/01-daily/* vault/02-tasks/* vault/10-sources/* vault/20-concepts/* vault/30-permanent/* vault/40-projects/* vault/50-reviews/*
    docker compose down -v

# Pre-commit hooks
pre-commit:
    uv run pre-commit run --all-files

# Help
help:
    @just --list
