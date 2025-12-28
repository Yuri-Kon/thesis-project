# Demo Report (Local Viewing)

Generate the demo artifacts and serve them locally to avoid file:// CORS issues.

```bash
python scripts/demo_visualization_poc.py
cd output/demo
python -m http.server 8000
```

Open `http://localhost:8000/report.html` in your browser.
