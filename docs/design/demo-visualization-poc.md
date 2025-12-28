# Demo Visualization PoC

This document describes the standalone visualization proof-of-concept.
It is **decoupled** from FSM/HITL and does not touch workflow, state, or API logic.

## Prerequisites

```bash
pip install biopython plotly
```

## Run

```bash
python scripts/demo_visualization_poc.py
```

## View

```bash
cd output/demo
python -m http.server 8000
```

Open `http://127.0.0.1:8000/report.html` in your browser (avoid `file://`).

Note: Mol* was replaced with NGL Viewer due to CORB/CORS issues in local PoC runs.
NGL is loaded from a CDN, so the browser needs network access.
