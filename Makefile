# Default target: show what's available.
.DEFAULT_GOAL := help

.PHONY: help install test test-verbose run commit pdf html clean-pdf

# Virtualenv lives at ./venv-macos. If it exists, use its python3; else
# fall back to system python3. Lets `make test` / `make run` work both
# pre- and post-install without extra flags.
VENV   := venv-macos
PYTHON := $(shell test -x $(VENV)/bin/python3 && echo $(VENV)/bin/python3 || echo python3)
PIP    := $(VENV)/bin/pip

help:
	@echo "jobs — Makefile targets:"
	@echo ""
	@echo "  make install    Create ./$(VENV) and pip-install requirements.txt."
	@echo "                  Also installs Playwright's Chromium (needed for"
	@echo "                  kind: \"pw\" sources). Run once after cloning."
	@echo ""
	@echo "  make run        Full pipeline: fetch every source, score, render"
	@echo "                  the HTML, open the browser, keep serving."
	@echo "                  Pass extra flags via ARGS, e.g.:"
	@echo "                    make run ARGS=\"--skip-llm --only Anthropic\""
	@echo ""
	@echo "  make test       Run the full unittest suite (~75 tests, ~50 ms)."
	@echo "  make test-verbose   Same, verbose."
	@echo ""
	@echo "  make commit     git add + commit + push (via script/push.sh)."
	@echo ""
	@echo "  make pdf        Build business/analysis.pdf via Sphinx + latexmk."
	@echo "  make html       Build business/_build/html via Sphinx."
	@echo "  make clean-pdf  Remove the Sphinx build output."
	@echo ""
	@echo "  make help       This message."

# `make install` — create venv-macos, install runtime deps + Playwright
# Chromium. Idempotent: safe to re-run to pick up requirements.txt
# changes. Uses --upgrade so pin bumps apply.
install:
	@test -d $(VENV) || python3 -m venv $(VENV)
	@$(VENV)/bin/pip install --upgrade pip
	@$(VENV)/bin/pip install --upgrade -r requirements.txt
	@$(VENV)/bin/playwright install chromium
	@echo ""
	@echo "  Installed into ./$(VENV)/"
	@echo "  Activate with:  source $(VENV)/bin/activate"
	@echo "  Or just use:    make run / make test  (both auto-detect the venv)"

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover tests

test-verbose:
	PYTHONPATH=src $(PYTHON) -m unittest discover tests -v

# `make run` → full pipeline: fetch every source, score, render HTML,
# open the browser, keep serving. Extra flags can be passed through:
#   make run ARGS="--skip-llm --only Anthropic,OpenAI"
run:
	PYTHONPATH=src $(PYTHON) src/jobs.py $(ARGS)

# `make commit` → forwards to script/push.sh (git add + commit + push).
commit:
	@bash script/push.sh

# ---------------------------------------------------------------------------
# business/analysis.md → PDF via Sphinx + latexmk.
#
# Prerequisites (install once; run from the activated venv-macos):
#   python3 -m pip install sphinx myst-parser sphinx-rtd-theme
#   brew install basictex                 # provides latexmk + pdflatex
#
# Run `make pdf` from the repo root OR from inside business/ — a thin
# forwarding Makefile in business/ makes the latter work.
# Uses `sphinx-build` directly (NOT `python3 -m sphinx`) so the venv's
# installation is picked up even if `python3` resolves elsewhere.
# ---------------------------------------------------------------------------

SPHINXBUILD   ?= sphinx-build
SPHINX_SRC    = business
SPHINX_BUILD  = business/_build
SPHINX_PDF    = $(SPHINX_BUILD)/latex/jobsmarketanalysis.pdf

pdf:
	@$(SPHINXBUILD) -M latexpdf $(SPHINX_SRC) $(SPHINX_BUILD)
	@cp "$(SPHINX_PDF)" "business/analysis.pdf" 2>/dev/null \
	    || cp $(SPHINX_BUILD)/latex/*.pdf business/analysis.pdf
	@echo "  PDF: business/analysis.pdf"
	@-if [ "$$(uname)" = "Darwin" ]; then open business/analysis.pdf; fi

html:
	@$(SPHINXBUILD) -M html $(SPHINX_SRC) $(SPHINX_BUILD)
	@echo "  HTML: $(SPHINX_BUILD)/html/index.html"

clean-pdf:
	rm -rf $(SPHINX_BUILD) business/analysis.pdf
