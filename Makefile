# All commands run inside a local .venv so they work on PEP 668
# "externally-managed" systems without touching system Python.
# Uses `uv` if available (fast); otherwise falls back to stdlib venv + pip.
PY := .venv/bin/python

.PHONY: install seed run clean

.venv:
	uv venv .venv 2>/dev/null || python3 -m venv .venv

install: .venv
	uv pip install -p .venv -r requirements.txt 2>/dev/null || .venv/bin/pip install -r requirements.txt

seed:
	$(PY) -m scripts.seed

run:
	$(PY) -m uvicorn app.main:app --reload --port 8000

clean:
	rm -rf .venv
