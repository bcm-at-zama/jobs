# Minimal Makefile — `make test` runs the whole suite.
# Uses stdlib unittest so no pip install needed.

.PHONY: test test-verbose pdf html clean-pdf

test:
	python3 -m unittest discover tests

test-verbose:
	python3 -m unittest discover tests -v

# ---------------------------------------------------------------------------
# business/analysis.md → PDF via Sphinx → LaTeX → pdflatex.
# Prerequisites (install once on a Mac):
#   brew install basictex           # pdflatex
#   python3 -m pip install sphinx myst-parser
#
# Run `make pdf` from the repo root OR from inside business/ — a thin
# forwarding Makefile in business/ makes the latter work.
# ---------------------------------------------------------------------------

pdf:
	python3 -m sphinx -b latex business business/_build/latex
	cd business/_build/latex && pdflatex -interaction=nonstopmode analysis.tex
	@echo "PDF ready at business/_build/latex/analysis.pdf"

html:
	python3 -m sphinx -b html business business/_build/html
	@echo "HTML ready at business/_build/html/index.html"

clean-pdf:
	rm -rf business/_build
