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

Open `http://localhost:8000/report.html` in your browser.
