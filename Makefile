# Minimal Makefile — `make test` runs the whole suite.
# Uses stdlib unittest so no pip install needed.

.PHONY: test test-verbose business-html business-pdf business-clean

test:
	python3 -m unittest discover tests

test-verbose:
	python3 -m unittest discover tests -v

# ---------------------------------------------------------------------------
# business/ — market analysis reports, built via Sphinx + MyST.
# Prerequisites (install once on a Mac):
#   brew install basictex
#   python3 -m pip install sphinx myst-parser
# ---------------------------------------------------------------------------

business-html:
	python3 -m sphinx -b html business business/_build/html

business-pdf:
	python3 -m sphinx -b latex business business/_build/latex
	cd business/_build/latex && pdflatex -interaction=nonstopmode analysis.tex
	@echo "PDF ready at business/_build/latex/analysis.pdf"

business-clean:
	rm -rf business/_build
