# business/

Reports and analyses about the project (market research, hosting
options, go-to-market thinking). Not shipped with the engine — these
are for Benoit.

## Building the PDF

The source is Markdown (`analysis.md`), compiled through Sphinx + MyST
to PDF via LaTeX.

**One-time setup on a Mac (inside the activated venv-macos):**

```sh
python3 -m pip install sphinx myst-parser sphinx-rtd-theme
brew install basictex           # pdflatex + latexmk (~100 MB)
```

**Build:**

```sh
make pdf                        # from the repo root OR from inside business/
```

The output lands at `business/analysis.pdf` (also opens in Preview on
macOS automatically).

**HTML preview (no LaTeX needed, same source):**

```sh
make html
open business/_build/html/index.html
```
