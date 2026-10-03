# Minimal Makefile — `make test` runs the whole suite.
# Uses stdlib unittest so no pip install needed.

.PHONY: test test-verbose

test:
	python3 -m unittest discover tests

test-verbose:
	python3 -m unittest discover tests -v
