# Compute Tracker

Cheapest GPU clouds and AI-agent sandboxes, refreshed daily. Static site in `docs/`, data in `docs/*.json`.

```bash
uv venv && uv pip install -r requirements.txt
.venv/bin/python fetch.py test   # offline self-check
.venv/bin/python fetch.py        # refresh docs/gpu.json and docs/sandboxes.json
python3 -m http.server 8742 -d docs
```

- GPU prices: [gpuhunt](https://github.com/dstackai/gpuhunt) + `[[gpu_manual]]` in `catalog.toml`.
- Sandboxes: `[sandbox.*]` in `catalog.toml` (every row has `source` and `checked`) + [ComputeSDK](https://www.computesdk.com/benchmarks/sandboxes) startup times.
- `.github/workflows/fetch.yml` refreshes daily and commits only when data changed.

See `DESIGN.md` for the measured-runs plan.
