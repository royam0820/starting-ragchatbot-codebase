#!/bin/bash
# Format code with isort and black

set -e

echo "Sorting imports with isort..."
uv run isort backend/

echo "Formatting code with black..."
uv run black backend/

echo "Done! Code has been formatted."
