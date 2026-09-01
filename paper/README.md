# Local Paper Workflow

`paper/` is the version-controlled source of truth for the manuscript.
Overleaf is a collaboration mirror, not the authoritative copy. Commit source
files, bibliography entries, figure sources, and plotting scripts. Do not
commit TeX build products, videos, checkpoints, raw data, or downloaded
conference templates without checking their redistribution terms.

## Source Layout

`main.tex` owns only the preamble, title metadata, bibliography, and chapter
order. Write prose in `sections/` so simultaneous edits remain reviewable:

```text
sections/abstract.tex
sections/01_introduction.tex
sections/02_related_work.tex
sections/03_method.tex
sections/04_experiments.tex
sections/05_limitations.tex
sections/06_conclusion.tex
```

Add figures under `figures/` and tables under `tables/`; keep their generation
scripts beside the editable source rather than pasting values into TeX.

## Local Build

The repository intentionally does not vendor a TeX distribution. Install a
local TeX environment with `latexmk`, `pdflatex`, and `bibtex`, then run:

```bash
sudo apt-get update
sudo apt-get install -y latexmk texlive-latex-extra texlive-fonts-recommended

cd paper
make pdf
make watch
```

`make watch` recompiles when `main.tex`, `references.bib`, or included source
files change. The PDF is written to `paper/build/main.pdf`; that directory is
ignored by Git.

Verify the installation with `latexmk -v` and one successful `make pdf` before
editing in parallel with Overleaf.

The current document uses a portable development preamble. Once the target
venue is fixed, replace only the document class and venue-required style files.
Keep the source tree and Make targets unchanged.

## Figures And Results

Keep editable mechanism diagrams in `paper/figures/` and generated plots in
`paper/figures/generated/`. Every result plot must have a source script and a
RunEvidence aggregate input. A plotting script may read a versioned aggregate
table, but must not scrape arbitrary logs or manually copied values.

```text
RunEvidence run.json files
  -> aggregate metrics table
  -> paper plotting script
  -> PDF/SVG figure included by main.tex
```

## Overleaf Sync

Sync only reviewed source after a local build succeeds. Keep the Overleaf
project free of `build/`, model weights, datasets, rosbag files, and experiment
outputs. Pull remote edits before a new sync and resolve conflicts locally;
never treat two writable copies as independent sources of truth.

## Current Status

The manuscript is a development draft. It contains no experimental results and
does not authorize a claim beyond the currently implemented system boundary.
