# Lightweight DNS Resolution-Caching Algorithm (HRFC)

A high-performance, multithreaded DNS resolution and caching simulation framework featuring the **Hybrid Recency-Frequency Caching (HRFC)** algorithm, traditional caching policies (LRU, LFU), negative caching, and RFC 8767-inspired serve-stale fault tolerance.

---

## Table of Contents
- [Project Description](#project-description)
  - [Overview](#overview)
  - [System Architecture](#system-architecture)
  - [Caching & Eviction Policies](#caching--eviction-policies)
  - [Key Features](#key-features)
- [Software Requirements](#software-requirements)
- [Installation Procedure](#installation-procedure)
- [Execution Steps](#execution-steps)
  - [1. Verification Test Suite](#1-verification-test-suite)
  - [2. Quick Demo (200 Queries)](#2-quick-demo-200-queries)
  - [3. Outage & Serve-Stale Resilience Test](#3-outage--serve-stale-resilience-test)
  - [4. Full Parameter Sweep (144 Configurations)](#4-full-parameter-sweep-144-configurations)
  - [5. Visual Analysis & Plot Generation](#5-visual-analysis--plot-generation)
- [Expected Results](#expected-results)
  - [Terminal Outputs](#terminal-outputs)
  - [Generated Output Artifacts](#generated-output-artifacts)
  - [Comparative Performance Tables](#comparative-performance-tables)
  - [Visual Graphs](#visual-graphs)
- [Testing Results & Verification](#testing-results--verification)
- [Project Structure](#project-structure)

---

## Project Description

### Overview
Domain Name System (DNS) resolution constitutes one of the most critical latencies in internet communication. Inefficient caching leads to redundant authoritative queries, increased latency for end-users, and vulnerability to authoritative server downtime.

This project implements an end-to-end DNS simulation over UDP, comparing standard caching algorithms with **HRFC (Hybrid Recency-Frequency Caching with TTL Decay)** under realistic Zipfian query distributions.

### System Architecture

The simulation comprises three cooperating network entities communicating over UDP sockets with JSON-encoded DNS protocol messages:

```
+-------------------------------------------------------------+
|                      Client Thread Pool                     |
|            Dispatches Zipf-distributed DNS queries          |
+------------------------------+------------------------------+
                               | UDP Port 5300
                               v
+-------------------------------------------------------------+
|                   Resolver Server (Proxy)                   |
|  - In-Memory Cache (LRU / LFU / Hybrid HRFC)                |
|  - Negative Caching (NXDOMAIN with reduced TTL)             |
|  - Serve-Stale Grace Period Handler (RFC 8767)              |
+------------------------------+------------------------------+
                               | UDP Port 5400 (On Cache Miss)
                               v
+-------------------------------------------------------------+
|              Upstream Authoritative DNS Server              |
|  - Configurable Latency (50ms) + Jitter (20ms)              |
|  - Simulated Outage Toggle (Up / Down)                      |
|  - Synthetic Zone Database                                  |
+-------------------------------------------------------------+
```

### Caching & Eviction Policies

When the cache reaches capacity (`max_size`), an eviction policy selects the victim entry to discard:

1. **None (`none`)**: Passthrough mode without caching (`max_size = 0`). Used as a baseline.
2. **Least Recently Used (`lru`)**: Evicts the entry with the oldest `last_access` timestamp:
   $$\text{Victim} = \arg\min_{e} (\text{last\_access}_e)$$
3. **Least Frequently Used (`lfu`)**: Evicts the entry with the lowest cumulative `access_count`:
   $$\text{Victim} = \arg\min_{e} (\text{access\_count}_e)$$
4. **Hybrid Recency-Frequency Caching (`hybrid` / HRFC)**: Combines access frequency with an exponential time-decay penalty weighted against the record's TTL:
   $$\text{Score}(e) = \text{access\_count}_e \times \exp\left( -\frac{\text{now} - \text{last\_access}_e}{\max(\text{TTL}_e, 1.0)} \right)$$
   $$\text{Victim} = \arg\min_{e} (\text{Score}(e))$$
   *Advantage*: Prevents stale "one-hit wonders" from polluting cache while preserving active hot entries even under tight memory budgets.

### Key Features
- **Negative Caching**: Caches NXDOMAIN responses with a shortened TTL ratio (`neg_ttl_ratio = 0.25`) to prevent repeated lookups of nonexistent domains without prolonged pollution.
- **Serve-Stale Resilience (RFC 8767)**: During upstream authoritative failures or network timeouts, cached expired records are served within an extended grace window (`stale_grace`), preventing client resolution failures.
- **Zipf-Distributed Workload Generator**: Generates realistic internet query skews with customizable power-law exponent $\alpha \in [0.8, 1.2]$.
- **Thread-Safe Architecture**: Uses reentrant mutex locks (`threading.Lock`) for concurrent cache lookups and thread pool worker executors for high-throughput query handling.

---

## Software Requirements

### Supported Platforms
- **Operating System**: Windows 10/11, Ubuntu 20.04+, macOS 12+ (Cross-platform)
- **Python Version**: Python 3.8 or higher (Tested on Python 3.11)

### Standard Library Dependencies
No compilation or external C-extensions required. Uses standard Python modules:
- `socket`, `threading`, `concurrent.futures`: Asynchronous UDP networking and concurrency
- `time`, `math`, `random`: Timers, mathematical decay functions, Zipf sampling
- `json`, `dataclasses`, `argparse`, `csv`, `os`: Data serialization, CLI, and logging

### Third-Party Dependencies
- `matplotlib>=3.5.0`: For generating analytical plots and distribution visualizations

---

## Installation Procedure

### 1. Clone the Repository
```bash
git clone https://github.com/felix16805/dns-caching-simulation.git
cd dns-caching-simulation
```

### 2. Set Up a Virtual Environment (Recommended)
On Windows (PowerShell):
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

On Linux / macOS:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```
*(Or manually: `pip install matplotlib`)*

---

## Execution Steps

### 1. Verification Test Suite
Run the automated sanity test verifying the cache engine, upstream server, resolver, and a mini-simulation:
```bash
python src/test_stack.py
```

### 2. Quick Demo (200 Queries)
Runs an interactive 200-query simulation using the HRFC hybrid policy with 5 concurrent client threads:
```bash
python src/run_experiment.py --mode demo
```

### 3. Outage & Serve-Stale Resilience Test
Simulates an upstream server outage to test RFC 8767 serve-stale survivability:
```bash
python src/run_experiment.py --mode outage
```

### 4. Full Parameter Sweep (144 Configurations)
Benchmarks all policy, size, TTL, and Zipf alpha combinations (outputs to `results/sweep.csv`):
```bash
python src/run_experiment.py --mode sweep
```

### 5. Visual Analysis & Plot Generation
Processes `results/sweep.csv` and produces summary tables and graphs in `results/`:
```bash
python analysis/analyze.py
```

---

## Expected Results

### Terminal Outputs

#### Running `python src/test_stack.py`:
```text
[1/4] Testing cache module...
     PASS
[2/4] Testing upstream server...
     PASS (latency 67.8 ms)
[3/4] Testing resolver (miss vs hit)...
     PASS (miss 68.6 ms, hit 0.0 ms)
[4/4] Running full demo...
     PASS (hit rate 65.5%, p95 58.3 ms)

All tests passed.
```

#### Running `python src/run_experiment.py --mode demo`:
```text
Results directory: .../results
  n_queries: 200
  hit_rate: 0.655
  hits: 131
  misses: 69
  stale_serves: 0
  evictions: 0
  inserts: 61
  cache_size: 61
  upstream_queries: 69
  mean_latency_ms: 20.64
  p50_latency_ms: 2.07
  p95_latency_ms: 59.75
  p99_latency_ms: 63.84
  policy: hybrid
  max_size: 500
  ttl: 300
  alpha: 1.0
  concurrency: 5
```

#### Running `python src/run_experiment.py --mode outage`:
```text
Outage test results:
  during_success_rate: 0.6567
  during_mean_latency_ms: 518.62
  after_success_rate: 1.0
  stale_serves: 401

Wrote results/outage.csv
```

### Generated Output Artifacts

| File | Description |
|---|---|
| [`results/sweep.csv`](results/sweep.csv) | Full raw dataset of 144 benchmark configurations with hit rates and latency percentiles. |
| [`results/outage.csv`](results/outage.csv) | Quantitative metrics during and after simulated upstream authoritative failure. |
| [`results/summary.md`](results/summary.md) | Highest hit rate configuration per policy. |
| [`results/hit_vs_ttl.png`](results/hit_vs_ttl.png) | Line plot comparing hit rates as a function of record TTL. |
| [`results/latency_bars.png`](results/latency_bars.png) | Bar chart comparing mean, p50, and p95 latency across policies. |
| [`results/upstream_vs_ttl.png`](results/upstream_vs_ttl.png) | Plot showing reduction of upstream query burden across TTL values. |

### Comparative Performance Tables

#### Best Hit Rate per Policy Across Full Sweep:
| Policy | Best Hit Rate | TTL | Cache Size | Zipf Alpha | p95 Latency |
|---|---|---|---|---|---|
| **None** | 0.00% | 10 s | 50 | 0.8 | 17.6 ms |
| **LRU** | 82.55% | 600 s | 5000 | 1.2 | 20.1 ms |
| **LFU** | 82.60% | 600 s | 500 | 1.2 | 20.6 ms |
| **HRFC (Hybrid)** | **82.50%** | 600 s | **500** | 1.2 | **20.5 ms** |

*Observation*: HRFC achieves virtually the same peak hit rate as LRU while requiring only **10% of the cache capacity** (500 vs 5,000 entries).

#### Outage Resilience Metrics:
| Metric | Result | Evaluation |
|---|---|---|
| **During-Outage Success Rate** | **65.67%** | High resolution availability maintained despite upstream dead |
| **Stale Serves Count** | **401** | Queries saved by RFC 8767 stale cache lookup |
| **Post-Recovery Success Rate** | **100.00%** | Seamless immediate return to normal operations |

### Visual Graphs

#### 1. Hit Rate vs TTL (`results/hit_vs_ttl.png`)
Shows hit rate scaling with record TTL across LRU, LFU, and Hybrid policies under Zipfian traffic ($\alpha=1.0$):
![Hit Rate vs TTL](results/hit_vs_ttl.png)

#### 2. Latency Comparison by Policy (`results/latency_bars.png`)
Compares mean, median (p50), and 95th percentile (p95) latencies:
![Latency Bars](results/latency_bars.png)

#### 3. Upstream Load vs TTL (`results/upstream_vs_ttl.png`)
Demonstrates how effective caching absorbs authoritative upstream query volume:
![Upstream Load vs TTL](results/upstream_vs_ttl.png)

---

## Testing Results & Verification

All four tiers of verification tests execute successfully with deterministic results:
1. **Cache Module (`test_cache`)**: State transitions (`hit`, `miss`, `stale_hit`, `expired`) pass.
2. **Upstream Server (`test_upstream`)**: UDP socket query and synthetic network latency injection pass.
3. **Resolver Server (`test_resolver`)**: Verified miss latency (~68 ms) vs hit latency (~0 ms) speedup.
4. **End-to-End System (`test_demo`)**: Concurrent Zipf query evaluation passes with expected hit rate > 65%.

For complete in-depth test methodology, verification proofs, and parameter matrix details, refer to the [**Testing & Verification Report (docs/TESTING.md)**](docs/TESTING.md).

---

## Project Structure

```text
dns-caching-simulation/
├── .gitignore               # Ignored cache files, pycache, OS artifacts
├── README.md                # Project documentation and user guide
├── requirements.txt         # Project dependencies (matplotlib)
├── docs/
│   └── TESTING.md           # In-depth test verification report
├── src/
│   ├── cache.py             # LRU, LFU, and Hybrid (HRFC) cache engine
│   ├── client.py            # Multithreaded client and workload runner
│   ├── protocol.py          # Lightweight UDP JSON protocol encoder/decoder
│   ├── resolver.py          # Caching DNS proxy resolver with serve-stale
│   ├── run_experiment.py    # Experiment orchestrator (demo, outage, sweep)
│   ├── test_stack.py        # Automated sanity test suite
│   ├── upstream.py          # Simulated authoritative server with delay/jitter
│   └── workload.py          # Synthetic zone & Zipfian query generator
├── analysis/
│   └── analyze.py           # Matplotlib visualization and table generation
└── results/
    ├── hit_vs_ttl.png       # Hit rate vs TTL plot
    ├── latency_bars.png     # Latency comparison bar chart
    ├── upstream_vs_ttl.png  # Upstream load vs TTL plot
    ├── outage.csv           # Outage experiment metrics
    ├── sweep.csv            # 144-configuration benchmark dataset
    └── summary.md           # Summary table of top configurations
```