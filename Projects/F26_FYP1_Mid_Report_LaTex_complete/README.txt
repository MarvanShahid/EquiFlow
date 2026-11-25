FYP-1 Mid Report - Chapter-wise LaTeX Template

Structure:
main.tex
chapters/
references/references.bib
figures/
tables/

Compile:
1. pdflatex main.tex
2. bibtex main
3. pdflatex main.tex
4. pdflatex main.tex

The template is designed around the proposed FYP-1 mid-report structure aligned with Form 2 and Form 3 evaluation criteria.

Iteration 2 chapter:
chapters/chapter7_iteration2.tex, chapters/results_tables.tex and figures/*.pdf are copies of
docs/latex/ and docs/figures/. After regenerating them (sumo/make_plots.py, sumo/latex_tables.py) run
  powershell -ExecutionPolicy Bypass -File update_iteration2.ps1
to refresh the copies here.
