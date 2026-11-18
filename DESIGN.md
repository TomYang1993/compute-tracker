# Compute Tracker: design

Cheapest GPU clouds and AI-agent sandboxes, for humans and agents.

**Moat:** measured runs ($ per real task, from billed balances). List prices are commodity:
gpuhunt, skypilot-catalog, GetDeploying, computeprices and several GPU-price MCP servers
(FastGPU, GPU Finder, Silicon Data, GPU Economy) already serve them; SpotGPU's API shut down.

## v0 (built)

```
gpuhunt (13 providers, no keys) ─┐
catalog.toml (hand-checked)  ────┼─ fetch.py ── docs/gpu.json, docs/sandboxes.json ── docs/index.html, llms.txt
ComputeSDK latest.json ──────────┘     daily GitHub Action commits docs/*.json; Pages serves docs/
```

- `best_pick` per GPU = cheapest on-demand, not a marketplace host (Vast, Lium), ≥16 vCPU and ≥128 GB RAM per GPU.
- Sandbox `$/hr` is computed for 2 vCPU / 4 GiB when per-vCPU and per-GiB rates are published.
- `untracked_in_computesdk` = sandbox names ComputeSDK benchmarks that the catalog lacks: the new-entrant queue.
- gpuhunt providers that need keys (Crusoe, DigitalOcean, Hot Aisle, JarvisLabs, Seeweb) are skipped.

## v1: measured runs (next)

One repo, one runner, one result schema, one budget guard. Two drivers:

| Driver | Covers | Tool |
|---|---|---|
| pod/VM | Runpod, Vast, Lambda, Nebius, (Shadeform for the long tail) | SkyPilot task YAML; Modal via its SDK |
| sandbox | E2B, Daytona, Modal, Vercel, Cloudflare, Blaxel, Agent37, Orble, InstaBox | ComputeSDK (extend their open harness) |

GPU sandboxes (Modal, Daytona) run both suites: pod vs sandbox for the same job.

| Suite | Workload | Output |
|---|---|---|
| G0 | provision→ready, 10 GB image pull, 16 GB HF download, fio, nvidia-smi, lscpu | overhead + real CPU per GPU |
| G1 | vLLM, fixed 8B model, 500 fixed prompts | tok/s, TTFT p50/p95, $/M tokens |
| G2 | LoRA 300 steps, fixed seed | $ per run |
| G3 | 100 images | $ per image |
| S0 | create → first command | startup |
| S1 | git clone + install + run tests | $ and time per agent task |
| S2 | fixed compile | CPU speed |
| S3 | idle 10 min → resume | resume time, idle cost |
| S4 | snapshot/fork, 1 GB download | features, network |

Shapes: sandboxes 2 vCPU / 4 GiB; GPUs L4 (cheap) and H100 (main), single GPU first.

**Billed cost:** prepaid balance before / after / +1h. The diff includes storage, egress and rounding.
Postpaid: billing API, else `rate × time` marked `estimated`.

**Result row:** run_id, harness_version, image_digest, provider, region, sku, workload, t_request,
t_provisioned, t_ready, t_start, t_end, t_teardown, metrics, list_price_hr, computed_cost, billed_cost,
billing_granularity, available_first_try, failure_reason, logs_url.

**Cadence:** GPU monthly per provider at a random hour; sandboxes weekly. Budget ~$25-35/mo.

**Spend guards (required before the first paid run):**
1. Prepaid accounts with $10-25 balances (hard cap); postpaid gets provider budget limits.
2. `--down` + idle autostop + job timeout + teardown in `finally`.
3. Hourly reaper: list `bench-*` everywhere, kill anything older than 2h, alert on Telegram.

**Secrets:** GitHub Actions secrets only; keys never on a laptop. The owner creates accounts, pays, and runs
`gh secret set NAME`. `providers.yaml` (no secrets) records billing type, cap, key name, rotation date.

## Later

- Private status page: balances, caps, leftover instances, key age.
- Discovery feed: Grok X scan + HN Algolia + Orble directory (signal only, never republish) → `untracked`.
- Money: sponsors (Stripe Payment Link) and disclosed affiliate links at ~5k visitors/mo; Pro API (Stripe Billing) and x402 when someone asks.
