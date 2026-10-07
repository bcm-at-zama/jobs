# Default target: show what's available.
.DEFAULT_GOAL := help

.PHONY: help install onboarding test test-verbose run kill commit pdf html clean-pdf

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
	@echo "  make kill        Kill whatever process is listening on port 8765."
	@echo "                   Rarely needed — make run auto-reclaims stale jobs.py"
	@echo "                   subprocesses on its own."
	@echo ""
	@echo "  PORT=N           Shared opt-in: works on run, kill, and onboarding."
	@echo "                   Lets a second board (e.g. sandbox) coexist with"
	@echo "                   your main one. Examples:"
	@echo "                     make run PORT=8767"
	@echo "                     make kill PORT=8767"
	@echo "                     make onboarding PORT=8767"
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

# PORT=N — shared opt-in override honoured by `make run`, `make kill`,
# and `make onboarding`. When unset, each target keeps its historical
# behaviour (run → jobs.py default 8765, kill → 8765, onboarding → auto-
# pick). We detect "explicitly set" via $(origin) so an untouched PORT
# doesn't force a --port flag onto subcommands that currently auto-pick.
PORT ?= 8765
PORT_SET := $(filter command environment,$(origin PORT))
PORT_ARG := $(if $(PORT_SET),--port $(PORT))

# `make onboarding` — interactive wizard that writes data/user_config.py.
# Prompts group-by-group through the catalog of ~150 companies, backs up
# any existing config before overwriting. Honours $JOBS_DATA_DIR so you
# can test with  JOBS_DATA_DIR=/tmp/sandbox make onboarding.
# Pass PORT=N to pin the wizard's HTTP port (default: auto-pick 8766).
onboarding:
	PYTHONPATH=src $(PYTHON) src/jobs.py --onboard $(PORT_ARG)

# `make test` runs two suites:
#   - tests/        framework behaviour (ships in OSS; passes on empty config).
#   - data/tests/   user-specific regression guards (private; skipped when
#                   absent, so a stock OSS clone just runs the first suite).
test:
	@PYTHONPATH=src $(PYTHON) -m unittest discover tests
	@if [ -d data/tests ]; then \
	  echo "--- user-decision tests (data/tests/) ---"; \
	  PYTHONPATH=src $(PYTHON) -m unittest discover data/tests; \
	fi

test-verbose:
	@PYTHONPATH=src $(PYTHON) -m unittest discover tests -v
	@if [ -d data/tests ]; then \
	  echo "--- user-decision tests (data/tests/) ---"; \
	  PYTHONPATH=src $(PYTHON) -m unittest discover data/tests -v; \
	fi

# `make run` → full pipeline: fetch every source, score, render HTML,
# open the browser, keep serving. The rendered page auto-triggers a
# `/refresh` on first load so stale per-source caches get wiped with
# the in-page progress indicator visible, instead of making the user
# wait on a blank terminal. Extra flags can be passed through:
#   make run ARGS="--skip-llm --only Anthropic,OpenAI"
# Pass PORT=N to bind the HTTP server on a non-default port (default 8765).
run:
	PYTHONPATH=src $(PYTHON) src/jobs.py $(PORT_ARG) $(ARGS)

# `make kill` → nuke anything bound to the serve port (default 8765).
# Pass PORT=N to target a different port — handy for sandbox boards
# started with `jobs.py --port N`. Useful when the pre-flight check in
# `make run` finds a non-jobs.py process squatting on the port and
# refuses to kill it on its own.
kill:
	@pids=$$(lsof -ti:$(PORT) 2>/dev/null); \
	 if [ -z "$$pids" ]; then \
	   echo "  Nothing listening on :$(PORT)."; \
	 else \
	   echo "  Killing PIDs on :$(PORT): $$pids"; \
	   kill $$pids 2>/dev/null || true; \
	   sleep 0.3; \
	   remaining=$$(lsof -ti:$(PORT) 2>/dev/null); \
	   if [ -n "$$remaining" ]; then \
	     echo "  Still up — sending SIGKILL to: $$remaining"; \
	     kill -9 $$remaining 2>/dev/null || true; \
	   fi; \
	 fi

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
