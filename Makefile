.PHONY: all run check lint test format icons arrows site gif build clean docs

all: check

run:
	uv run python -m calculon

docs:
	uv run python -m http.server -b 127.0.0.1 -d docs

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

# the dropdown and number field arrows, one per theme colour
arrows:
	uv run python -m scripts.make_arrows

# the website's example sheets and colours, from the engine and the Glacier theme
site:
	QT_QPA_PLATFORM=offscreen uv run python -m scripts.build_site

# docs/demo.gif, the README demo of typing a sheet and switching themes, and
# docs/screenshot.png, the website's link preview (needs ffmpeg)
gif:
	QT_QPA_PLATFORM=offscreen uv run python -m scripts.make_gif

# make build            -> test build, version 0.0.0.dev0+<git describe>
# make build TAG=v1.2.3 -> release version 1.2.3
build:
	uv run python scripts/write_version.py $(TAG)
	uv run pyinstaller calculon.spec --clean --noconfirm

clean:
	rm -rf build dist calculon/_version.py
	find . -type d -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} +
