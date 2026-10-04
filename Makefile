# Minimal Makefile — `make test` runs the whole suite.
# Uses stdlib unittest so no pip install needed.

.PHONY: test test-verbose pdf html clean-pdf

test:
	python3 -m unittest discover tests

test-verbose:
	python3 -m unittest discover tests -v

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
