# Copy the Iteration 2 chapter, its generated tables and the result figures into this report.
# Run after regenerating them (sumo/make_plots.py, sumo/latex_tables.py):
#     powershell -ExecutionPolicy Bypass -File update_iteration2.ps1
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Resolve-Path (Join-Path $here "..\..")
New-Item -ItemType Directory -Force (Join-Path $here "figures") | Out-Null
Copy-Item (Join-Path $repo "docs\latex\chapter7_iteration2.tex") (Join-Path $here "chapters\") -Force
Copy-Item (Join-Path $repo "docs\latex\results_tables.tex") (Join-Path $here "chapters\") -Force
Copy-Item (Join-Path $repo "docs\figures\*.pdf") (Join-Path $here "figures\") -Force
Write-Output "Copied chapter7_iteration2.tex, results_tables.tex and figures\*.pdf into $here"
