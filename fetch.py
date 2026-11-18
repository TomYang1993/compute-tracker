"""Fetch GPU offers (gpuhunt) and the sandbox catalog (catalog.toml + ComputeSDK) into docs/*.json.

    python fetch.py        # write docs/gpu.json and docs/sandboxes.json
    python fetch.py test   # offline self-check
"""
import json
import logging
import sys
import tomllib
import urllib.request
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
CSDK_URL = "https://raw.githubusercontent.com/computesdk/benchmarks/refs/heads/master/results/burst_tti/latest.json"
KIND = {"aws": "hyperscaler", "gcp": "hyperscaler", "azure": "hyperscaler", "oci": "hyperscaler",
        "vastai": "marketplace", "lium": "marketplace", "daytona": "sandbox", "modal": "sandbox"}
STRONG_VCPU, STRONG_RAM = 16, 128  # per GPU: enough CPU to keep the GPU fed
FIELDS = ("provider", "instance_name", "location", "price", "cpu", "memory",
          "gpu_count", "gpu_name", "gpu_memory", "spot")


def gpu_rows(offers, manual):
    """Cheapest offer per (gpu, vram, provider, spot, gpu_count), priced per GPU-hour."""
    best = {}
    for o in offers:
        n = o["gpu_count"]
        row = {"gpu": o["gpu_name"], "vram": round(o["gpu_memory"] or 0), "provider": o["provider"],
               "kind": KIND.get(o["provider"], "neocloud"), "spot": bool(o["spot"]), "gpu_count": n,
               "price_gpu_hr": round(o["price"] / n, 4),
               "vcpu_per_gpu": round(o["cpu"] / n, 1) if o["cpu"] else None,
               "ram_per_gpu": round(o["memory"] / n) if o["memory"] else None,
               "location": o["location"], "instance": o["instance_name"]}
        key = (row["gpu"], row["vram"], row["provider"], row["spot"], n)
        if key not in best or row["price_gpu_hr"] < best[key]["price_gpu_hr"]:
            best[key] = row
    for m in manual:
        best[(m["gpu"], m["vram"], m["provider"], False, 1)] = {
            "gpu": m["gpu"], "vram": m["vram"], "provider": m["provider"],
            "kind": KIND.get(m["provider"], "neocloud"), "spot": False, "gpu_count": 1,
            "price_gpu_hr": m["price_gpu_hr"], "vcpu_per_gpu": None, "ram_per_gpu": None,
            "location": None, "instance": None, "source": m["source"]}
    rows = sorted(best.values(), key=lambda r: (r["gpu"], r["vram"], r["price_gpu_hr"]))
    for r in rows:
        r["strong_cpu"] = bool(r["vcpu_per_gpu"] and r["ram_per_gpu"]
                               and r["vcpu_per_gpu"] >= STRONG_VCPU and r["ram_per_gpu"] >= STRONG_RAM)
    return rows


def gpu_summary(rows):
    """Per GPU: cheapest on-demand, cheapest spot, and best_pick = cheapest on-demand
    that is not a marketplace host and has a strong CPU. ponytail: list price only until benchmarks land."""
    out = {}
    for r in rows:  # rows are sorted by price within each GPU, so the first hit wins
        s = out.setdefault(f'{r["gpu"]} {r["vram"]}GB', {})
        s.setdefault("cheapest_spot" if r["spot"] else "cheapest_on_demand", r)
        if not r["spot"] and r["strong_cpu"] and r["kind"] != "marketplace":
            s.setdefault("best_pick", r)
    return out


def sandbox_rows(catalog, csdk):
    """Catalog rows + comparable $/hr + ComputeSDK startup times; also ComputeSDK names we don't track."""
    bench = {r["provider"]: r for r in csdk.get("results", [])}
    rows = []
    for key, s in catalog.items():
        if "vcpu_hr" in s:
            cost, shape = round(s["vcpu_hr"] * 2 + s["gib_hr"] * 4, 4), "2c4g"
        else:
            cost, shape = s.get("flat_hr"), s.get("shape")
        b = bench.get(s.get("computesdk"))
        tti = b["summary"]["ttiMs"] if b and b["successRate"] else {}  # failed run reports 0 ms, not a time
        rows.append({"id": key, **s, "cost_hr": cost, "cost_shape": shape,
                     "tti_median_ms": tti.get("median"), "tti_p95_ms": tti.get("p95"),
                     "success_rate": b["successRate"] if b else None})
    rows.sort(key=lambda r: (r["cost_shape"] != "2c4g", r["cost_hr"] is None, r["cost_hr"] or 0))
    tracked = {s.get("computesdk") for s in catalog.values()}
    return rows, sorted(p for p in bench if p not in tracked)


def main():
    logging.disable(logging.WARNING)  # gpuhunt logs every unknown GPU model
    import gpuhunt

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cat = tomllib.loads((ROOT / "catalog.toml").read_text())

    offers = [{f: getattr(o, f) for f in FIELDS} for o in gpuhunt.query(min_gpu_count=1)
              if getattr(o.gpu_vendor, "value", o.gpu_vendor) in ("nvidia", "amd")]
    rows = gpu_rows(offers, cat.get("gpu_manual", []))
    assert len(rows) > 200, f"only {len(rows)} GPU rows; refusing to overwrite data"  # partial outage guard
    write("gpu.json", {"updated": now, "source": f"gpuhunt {version('gpuhunt')} + catalog.toml",
                       "summary": gpu_summary(rows), "offers": rows})

    with urllib.request.urlopen(CSDK_URL, timeout=30) as r:
        csdk = json.load(r)
    sb, untracked = sandbox_rows(cat["sandbox"], csdk)
    write("sandboxes.json", {"updated": now, "computesdk_run": csdk.get("timestamp"),
                             "sandboxes": sb, "untracked_in_computesdk": untracked})
    print(f"{len(rows)} GPU rows, {len(sb)} sandboxes, {len(untracked)} untracked: {', '.join(untracked)}")


def write(name, data):
    DOCS.mkdir(exist_ok=True)
    (DOCS / name).write_text(json.dumps(data, indent=1, default=str) + "\n")


def test():
    o = dict(provider="x", instance_name="i", location="l", cpu=64, memory=512, gpu_name="H100",
             gpu_memory=80, spot=False)
    rows = gpu_rows([{**o, "price": 8.0, "gpu_count": 2}, {**o, "price": 6.0, "gpu_count": 2},
                     {**o, "price": 9.0, "gpu_count": 1, "spot": True, "cpu": 8, "memory": 32}],
                    [{"provider": "modal", "gpu": "H100", "vram": 80, "price_gpu_hr": 3.95, "source": "s"}])
    assert [r["price_gpu_hr"] for r in rows] == [3.0, 3.95, 9.0], rows  # cheaper 2x kept, per-GPU price
    assert rows[0]["strong_cpu"] and not rows[2]["strong_cpu"]  # 32 vCPU/256 GB vs 8 vCPU/32 GB
    s = gpu_summary(rows)["H100 80GB"]
    assert s["cheapest_on_demand"]["price_gpu_hr"] == 3.0 and s["cheapest_spot"]["price_gpu_hr"] == 9.0
    assert s["best_pick"]["price_gpu_hr"] == 3.0
    mk = gpu_rows([{**o, "provider": "vastai", "price": 1.0, "gpu_count": 1}], [])
    assert "best_pick" not in gpu_summary(mk)["H100 80GB"]  # marketplace hosts never win best_pick

    cat = {"a": {"vcpu_hr": 0.05, "gib_hr": 0.01, "computesdk": "a"},
           "b": {"flat_hr": 0.006, "shape": "unknown"}, "c": {}}
    csdk = {"results": [{"provider": "a", "successRate": 1, "summary": {"ttiMs": {"median": 500, "p95": 900}}},
                        {"provider": "newco", "successRate": 1, "summary": {"ttiMs": {}}},
                        {"provider": "b", "successRate": 0, "summary": {"ttiMs": {"median": 0}}}]}
    cat["b"]["computesdk"] = "b"
    sb, untracked = sandbox_rows(cat, csdk)
    assert sb[0]["id"] == "a" and sb[0]["cost_hr"] == 0.14 and sb[0]["tti_median_ms"] == 500
    assert [r["id"] for r in sb] == ["a", "b", "c"] and untracked == ["newco"]
    assert sb[1]["tti_median_ms"] is None and sb[1]["success_rate"] == 0  # failed run is not "0 ms"
    print("ok")


if __name__ == "__main__":
    test() if sys.argv[1:] == ["test"] else main()
