# Demo Report (Local Viewing)

Generate the demo artifacts and serve them locally to avoid file:// CORS issues.

```bash
export PYTHONPATH=/home/yurikon/文档/thesis/thesis-project
python scripts/demo_visualization_poc.py
cd output/demo
python -m http.server 8000
```

Open `http://127.0.0.1:8000/report.html` in your browser (avoid `file://`).

Note: Mol* was replaced with NGL Viewer due to CORB/CORS issues in local PoC runs.
NGL is loaded from a CDN, so the browser needs network access.
