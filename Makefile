# Subtitled Cinema — dev tasks
.PHONY: help install fetch build serve test test-parse test-ui all

help:
	@echo "make install    - install python deps + playwright chromium"
	@echo "make fetch      - download fresh source pages into .cache/pages"
	@echo "make build      - parse pages -> public/data.json"
	@echo "make serve      - serve public/ at http://localhost:8000"
	@echo "make test       - run all tests (parser + UI)"
	@echo "make all        - fetch + build"

install:
	python3 -m pip install --user beautifulsoup4 playwright
	python3 -m playwright install chromium

fetch:
	python3 -m build.fetch_pages

build:
	python3 -m build.build_site

serve:
	cd public && python3 -m http.server 8000

test-parse:
	python3 -m unittest tests.test_parse -v

test-ui:
	python3 -m unittest tests.test_ui -v

test: test-parse test-ui

all: fetch build
