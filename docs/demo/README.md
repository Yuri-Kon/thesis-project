# Demo Report (Local Viewing)

Generate the demo artifacts and serve them locally to avoid file:// CORS issues.

```bash
python scripts/demo_visualization_poc.py
cd output/demo
python -m http.server 8000
```

Open `http://127.0.0.1:8000/report.html` in your browser (avoid `file://`).

Note: Mol* is loaded from a CDN in this PoC, so the browser needs network access.
