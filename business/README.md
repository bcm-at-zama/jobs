# business/

Reports and analyses about the project (market research, hosting
options, go-to-market thinking). Not shipped with the engine — these
are for Benoit.

## Building the PDF

The source is Markdown (`analysis.md`), compiled through Sphinx + MyST
to PDF via LaTeX.

**One-time setup on a Mac:**

```sh
brew install basictex           # pdflatex (~100 MB)
python3 -m pip install sphinx myst-parser
```

**Build:**

```sh
make business-pdf               # from the repo root
```

The output lands at `business/_build/latex/analysis.pdf`.

**Alternative: HTML preview (no LaTeX needed)**

```sh
make business-html
open business/_build/html/index.html
```
