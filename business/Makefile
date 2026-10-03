# Forwarder — lets `make pdf` work from inside business/ by delegating
# to the top-level Makefile at the repo root. All targets are forwarded.

.PHONY: pdf html test test-verbose clean-pdf

pdf html test test-verbose clean-pdf:
	$(MAKE) -C .. $@
