"""Sphinx config for the business/ docs.

Builds analysis.md → PDF via Sphinx → LaTeX → pdflatex.

Prerequisites (one-time, in the activated venv-macos):

    python3 -m pip install sphinx myst-parser sphinx-rtd-theme
    brew install basictex          # provides pdflatex + latexmk

Then from the repo root OR from inside business/:

    make pdf
"""
project = "Jobs — Market Analysis"
author = "Benoit Chevallier-Mames"
copyright = "2026, Benoit Chevallier-Mames"
release = "1.0"

extensions = [
    "myst_parser",   # markdown support
]

# Treat `.md` as source files, no need to write RST wrappers.
source_suffix = {
    ".md": "markdown",
    ".rst": "restructuredtext",
}

master_doc = "index"
# Exclude the venv (`.venv`, `.venv-macos`, etc.) so Sphinx doesn't pick up
# every .rst/.md inside site-packages (docutils, sphinx, idna, …). Also
# exclude README.md so it doesn't fight the toctree. Sphinx's exclude_patterns
# use fnmatch; list the specific dirs AND recursive globs for defense in depth.
exclude_patterns = [
    "_build",
    ".venv",
    ".venv/**",
    ".venv-macos",
    ".venv-macos/**",
    "**/site-packages/**",
    "**/lib/python*/**",
    "README.md",
]

# PDF output options.
# xelatex (not pdflatex) because the analysis contains Unicode box-drawing
# characters (▲ ▼ ◀ ▶ │ ─ ┼) in the ASCII market-map diagram, and pdflatex
# chokes on those out of the box. xelatex handles Unicode natively.
latex_engine = "xelatex"
# Produce a single PDF named jobsmarketanalysis.pdf (lowercase, no spaces —
# that's the filename the Makefile copies to business/analysis.pdf).
latex_documents = [
    (master_doc, "jobsmarketanalysis.tex", project, author, "manual"),
]
latex_elements = {
    "papersize":   "a4paper",
    "pointsize":   "11pt",
    "preamble":    r"\usepackage{microtype}",
    # fontspec is loaded automatically by xelatex via Sphinx; nothing to add.
}

# HTML output (free bonus — same source).
html_theme = "sphinx_rtd_theme"
