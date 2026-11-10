.PHONY: all run check lint test format icons build clean

all: check

run:
	uv run python -m calculon

check: lint test

lint:
	uv run ruff check .
	uv run ruff format --check .

test:
	uv run pytest

format:
	uv run ruff format .

icons:
	QT_QPA_PLATFORM=offscreen uv run python scripts/make_icons.py

# make build            -> test build, version 0.0.0.dev0+<git describe>
# make build TAG=v1.2.3 -> release version 1.2.3
build:
	uv run python scripts/write_version.py $(TAG)
	uv run pyinstaller calculon.spec --clean --noconfirm

clean:
	rm -rf build dist calculon/_version.py
	find . -type d -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} +
