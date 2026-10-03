"""Sphinx config for the business/ docs.

Builds analysis.md → PDF via LaTeX. On a Mac, install the toolchain once:

    brew install basictex  # provides pdflatex
    python3 -m pip install sphinx myst-parser

Then from the repo root:

    make business-pdf
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
exclude_patterns = ["_build"]

# PDF output options.
latex_engine = "pdflatex"
latex_documents = [
    (master_doc, "analysis.tex", project, author, "manual"),
]
latex_elements = {
    "papersize":   "a4paper",
    "pointsize":   "11pt",
    "preamble":    r"\usepackage{microtype}",
    "fncychap":    r"\usepackage[Bjornstrup]{fncychap}",
}

# HTML output (free bonus — same source).
html_theme = "alabaster"
