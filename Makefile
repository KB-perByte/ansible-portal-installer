.PHONY: help install dev-install clean test lint format check

help:
	@echo "Ansible Portal Installer - Makefile Commands"
	@echo ""
	@echo "  make install      - Install package"
	@echo "  make dev-install  - Install with dev dependencies"
	@echo "  make clean        - Clean build artifacts"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linter"
	@echo "  make format       - Format code"
	@echo "  make check        - Run all checks (lint + format + type check)"

install:
	pip install -e .

dev-install:
	pip install -e ".[dev]"

clean:
	rm -rf build/ dist/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

test:
	pytest

lint:
	ruff check src/ tests/

format:
	black src/ tests/

format-check:
	black --check src/ tests/

type-check:
	mypy src/

check: lint format-check type-check
	@echo "All checks passed!"

.DEFAULT_GOAL := help
