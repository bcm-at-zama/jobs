# Default target: show what's available.
.DEFAULT_GOAL := help

.PHONY: help install onboarding test test-verbose run commit pdf html clean-pdf

# Virtualenv lives at ./venv-macos. If it exists, use its python3; else
# fall back to system python3. Lets `make test` / `make run` work both
# pre- and post-install without extra flags.
VENV   := venv-macos
PYTHON := $(shell test -x $(VENV)/bin/python3 && echo $(VENV)/bin/python3 || echo python3)
PIP    := $(VENV)/bin/pip

help:
	@echo "jobs — Makefile targets:"
	@echo ""
	@echo "  make install     One-shot setup: venv + Python deps + Playwright"
	@echo "                   Chromium. Run once after cloning."
	@echo ""
	@echo "  make onboarding  Create data/user_config.py from the template so"
	@echo "                   you can edit YOUR sources / blacklists / highlights."
	@echo "                   Safe to re-run (skips if the file already exists)."
	@echo ""
	@echo "  make run         Full pipeline: fetch every source, render the HTML,"
	@echo "                   open the browser, keep serving. Pass extra flags"
	@echo "                   via ARGS, e.g.  make run ARGS=\"--only Anthropic\"."
	@echo ""
	@echo "  make test        Run the full unittest suite (~70 tests, ~50 ms)."
	@echo "  make test-verbose    Same, verbose."
	@echo ""
	@echo "  make commit      git add + commit + push (via script/push.sh)."
	@echo ""
	@echo "  make pdf         Build business/analysis.pdf via Sphinx + latexmk."
	@echo "  make html        Build business/_build/html via Sphinx."
	@echo "  make clean-pdf   Remove the Sphinx build output."
	@echo ""
	@echo "  make help        This message."

# `make install` — one-shot setup: create venv, install deps, install
# Playwright Chromium. Idempotent: safe to re-run to pick up changes to
# requirements.txt or Playwright updates.
install:
	@test -d $(VENV) || python3 -m venv $(VENV)
	@$(VENV)/bin/pip install --upgrade --quiet pip
	@$(VENV)/bin/pip install --upgrade --quiet -r requirements.txt
	@$(VENV)/bin/playwright install chromium
	@echo ""
	@echo "  Installed into ./$(VENV)/"
	@echo "  Next: run  make onboarding  to create your data/user_config.py."

# `make onboarding` — copy src/user_config.example.py → data/user_config.py
# so the user has a template to edit. Idempotent: never overwrites an
# existing file. Also drops an empty data/profile.md if missing — the
# Claude "C" button in the UI needs it to score jobs against your profile.
onboarding:
	@mkdir -p data
	@if [ -f data/user_config.py ]; then \
	    echo "  data/user_config.py already exists — not overwriting."; \
	else \
	    cp src/user_config.example.py data/user_config.py; \
	    echo "  Created data/user_config.py — open it and edit SOURCES / BLACKLIST / HIGHLIGHTS."; \
	fi
	@if [ -f data/profile.md ]; then \
	    echo "  data/profile.md already exists — leaving it alone."; \
	else \
	    echo "# Your profile" > data/profile.md; \
	    echo "" >> data/profile.md; \
	    echo "<!-- 1-2 paragraphs describing the role you want: seniority, domain," >> data/profile.md; \
	    echo "     geography, dealbreakers, salary floor. The Claude \"C\" button in the UI" >> data/profile.md; \
	    echo "     reads this to score jobs against your profile. -->" >> data/profile.md; \
	    echo "  Created data/profile.md — write 1-2 paragraphs about the role you want."; \
	fi
	@echo ""
	@echo "  Then: run  make run  to fetch and open the browser."

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
