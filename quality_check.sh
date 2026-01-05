#!/bin/bash
# Run all code quality checks

set -e

echo "Running code quality checks..."
echo ""

echo "1. Checking import sorting with isort..."
uv run isort --check-only backend/
echo "✓ Import sorting check passed"
echo ""

echo "2. Checking code formatting with black..."
uv run black --check backend/
echo "✓ Code formatting check passed"
echo ""

echo "3. Running flake8 linter..."
uv run flake8 backend/
echo "✓ Linting check passed"
echo ""

echo "4. Running type checks with mypy..."
uv run mypy backend/
echo "✓ Type checking passed"
echo ""

echo "All quality checks passed! ✨"
